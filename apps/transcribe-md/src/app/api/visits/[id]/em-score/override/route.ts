// ============================================================================
// POST /api/visits/[id]/em-score/override  (Phase 5.2 orphan-completion)
// ----------------------------------------------------------------------------
// Body:    { overrideToCode: EmCode, reason?: string }
// Response: { ok: true, newScore: UiEmScore }
//
// Persists the doctor's E&M override into transcribe_visits.cptCodes
// (under the `em.override` sub-blob), writes an EM_OVERRIDE_APPLIED
// audit row, and returns a freshly-projected UI score so the rail
// re-renders with the doctor-set code on the same network round-trip.
//
// Pre-2026-05-05 the override dropdown dispatched a `qm:em-override`
// CustomEvent that no listener consumed (Bug F-01 in the QA agent's
// 20260505T230801Z report — silent clinical data loss with a lying
// "recorded in audit trail" toast). This route is its server-side
// landing zone; the rail now calls onApplyOverride(code, reason?)
// instead of dispatching.
//
// Refuses signed/locked visits. Refuses archived/deleted visits.
// Returns 404 on ownership mismatch (consistent with rest of /api/visits).
// ============================================================================

import { NextResponse } from 'next/server';
import { z } from 'zod';

import prisma from '@meddoc/db';
import { Prisma, TranscribeVisitStatus } from '@prisma/client';

import {
  emAppliesToSpecialty,
  isImagingReportSpecialty,
  ultrasoundSpecialtyEnabled,
} from '@meddoc/shared/specialties';

import { unacknowledgedEmChange } from '@/lib/em-pending-change';
import { getSession } from '@/lib/auth';
import { apiError, withApiHandler } from '@/lib/api-error';
import { visitByIdScope } from '@/lib/practice-scope';
import { invalidateVisitFills } from '@/lib/docx-preview/fill-cache';
import { computeEmScore } from '@/lib/em-coding/score';
import { engineToUiScore } from '@/lib/em-coding/to-ui-score';
import { extractIcdRows, extractRxRows } from '@/lib/em-coding/displayed-level';
import { logAudit } from '@/lib/audit';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';
export const maxDuration = 30;

// AMA 2021 Office E&M code surface (mirrors the rail's union literal).
const EM_CODES = [
  '99202',
  '99203',
  '99204',
  '99205',
  '99211',
  '99212',
  '99213',
  '99214',
  '99215',
] as const;

// REASON IS REQUIRED, and that is a change from this route's first version.
//
// It was optional because the only caller was a dropdown in a coding rail,
// where the level was one of several things on screen and the audit row was a
// by-product. It is now reached from the gate stack — the surface a doctor
// crosses on the way to a signature — and a level set there is a clinical
// judgement recorded against a note they are about to attest to. "Who changed
// it to what" without "and why" is the half of the audit row that cannot be
// reconstructed later.
//
// Length-capped so a fat-fingered payload cannot bloat audit metadata.
const MIN_REASON_LENGTH = 3;
const MAX_REASON_LENGTH = 240;

const BodySchema = z.object({
  overrideToCode: z.enum(EM_CODES),
  reason: z.string().trim().min(MIN_REASON_LENGTH).max(MAX_REASON_LENGTH),
});

export const POST = withApiHandler<{ id: string }>(
  'api:visits:em-score:override',
  async (req, { params }) => {
    const { id: visitId } = await params;

    const session = await getSession();
    const userId = session?.user.id;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const practiceId = (session?.user as any)?.practiceId as string | undefined;
    if (!userId || !practiceId) return apiError('unauthorized', 401);

    let body: unknown;
    try {
      body = await req.json();
    } catch {
      return apiError('invalid JSON body', 400);
    }
    const parsed = BodySchema.safeParse(body);
    if (!parsed.success) {
      return apiError('invalid override payload', 400, {
        code: 'INVALID_REQUEST',
      });
    }

    // Ownership + status gates. 404 on mismatch — never leak existence.
    const visit = await prisma.transcribeVisit.findFirst({
      where: visitByIdScope(visitId, session.user.practiceId),
      select: {
        id: true,
        userId: true,
        status: true,
        deletedAt: true,
        archivedAt: true,
        signedAt: true,
        specialty: true,
        emPendingChange: true,
        soapDraft: true,
        soapFinal: true,
        audioDurationSec: true,
        dictationDurationSec: true,
        inputMode: true,
        icdCodes: true,
        cptCodes: true,
        rxDrafts: true,
      },
    });
    // T6 §4.1c — the author conjunct is GONE; practice membership is the gate.
    // The read above is practice-scoped (T5), so reaching this line means the
    // visit is in the caller's practice. SIGNING is the only role-gated action
    // (SPEC §1.2); tech-creates/doctor-signs requires every member to be able to
    // prepare work.
    if (!visit) return apiError('not found', 404);
    if (visit.deletedAt !== null || visit.archivedAt !== null) {
      return apiError('Visit is no longer active.', 400, {
        code: 'VISIT_NOT_ACTIVE',
      });
    }
    if (visit.signedAt !== null || visit.status === TranscribeVisitStatus.SIGNED) {
      return apiError(
        'Visit is signed and locked — override can no longer be set.',
        409,
        { code: 'VISIT_LOCKED' },
      );
    }
    // AN IMAGING REPORT HAS NO OFFICE E/M LEVEL, so there is nothing here to
    // override and no code that would be correct to write.
    //
    // The UI never offers this on an imaging visit — the level row does not
    // render when E/M does not apply — but the route is the thing that owns the
    // column, and "the caller wouldn't do that" is how an office code ends up
    // on an ultrasound report. It reaches the export and the signed record from
    // there, which is why this is a 409 and not a silent no-op.
    if (!emAppliesToSpecialty(visit.specialty)) {
      return apiError(
        'This visit is an imaging report and has no office E/M level.',
        409,
        { code: 'EM_NOT_APPLICABLE' },
      );
    }

    // Only allow on visits that have actually completed the pipeline —
    // earlier statuses mean the AI's suggestedCode isn't stable yet, so
    // the override semantics are undefined.
    if (visit.status !== TranscribeVisitStatus.READY) {
      return apiError(
        `Visit is in status ${visit.status}; override requires a READY visit.`,
        409,
        { code: 'VISIT_NOT_READY' },
      );
    }

    const currentSoap = visit.soapFinal ?? visit.soapDraft ?? '';
    if (!currentSoap.trim()) {
      return apiError(
        'Visit has no SOAP draft to score.',
        400,
        { code: 'NO_SOAP_DRAFT' },
      );
    }

    // Re-score against the current SOAP so the rail receives a fresh
    // groups/bump payload with the override applied. Same fast-path
    // (mdmCachedJudgement: null) the apply-additions route uses.
    const icdCodes = extractIcdRows(visit.icdCodes);
    const rxDrafts = extractRxRows(visit.rxDrafts);
    const engineScore = await computeEmScore(currentSoap, {
      mdmCachedJudgement: null,
      icdCodes,
      rxDrafts,
    });

    const durationSec =
      visit.inputMode === 'voice_dictation'
        ? (visit.dictationDurationSec ?? 0)
        : (visit.audioDurationSec ?? 0);

    const overrideRecord = {
      code: parsed.data.overrideToCode,
      reason: parsed.data.reason,
      overriddenAt: new Date().toISOString(),
    };

    const newUiScore = engineToUiScore(
      engineScore,
      durationSec,
      overrideRecord
    );

    // cptCodes is a Json column. Merge `em.override` into whatever
    // existing top-level shape lives there (the doctor may have
    // overridden once before; this overwrites). Other top-level keys
    // are preserved.
    const existing = isPlainObject(visit.cptCodes) ? { ...visit.cptCodes } : {};
    const existingEm = isPlainObject(existing.em) ? { ...existing.em } : {};
    const nextCpt = {
      ...existing,
      em: { ...existingEm, override: overrideRecord },
    };

    // THE OVERRIDE ARMS THE CONFIRM GATE. It does not bypass it.
    //
    // Choosing a level and attesting to a level are two acts, and this route
    // performs the first. The doctor still meets the same confirm card the
    // model's own re-scores raise, and the sign route still refuses without a
    // matching acknowledgement — so "I set it myself" never becomes a shortcut
    // past the one control that records that a human looked.
    //
    // `from` is the level as displayed BEFORE this write. When an
    // unacknowledged change already exists its original `from` is carried
    // forward, exactly as the re-score does: the baseline is the level the
    // doctor last had validated, not whatever the previous unconfirmed hop
    // happened to say.
    const priorEm = isPlainObject(existing.em)
      ? (existing.em as { code?: string; override?: { code?: string } })
      : null;
    const displayedBefore =
      priorEm?.override?.code ?? priorEm?.code ?? engineScore.code ?? null;
    const alreadyPending = unacknowledgedEmChange(visit.emPendingChange);
    const from = alreadyPending?.from ?? displayedBefore;
    const moved = from !== null && from !== parsed.data.overrideToCode;

    await prisma.transcribeVisit.update({
      where: { id: visitId },
      data: {
        cptCodes: nextCpt,
        ...(moved
          ? {
              emPendingChange: {
                cause: 'doctor_override',
                at: new Date().toISOString(),
                from,
                to: parsed.data.overrideToCode,
              } as unknown as Prisma.InputJsonValue,
            }
          : alreadyPending
            ? // Overridden back to the level already reviewed — nothing left to
              // confirm, and leaving the record would block the signature over
              // a change that no longer exists.
              //
              // MOVE THE BASELINE WITH IT. `emScoredCode` is what the next
              // re-score measures movement from, and it still held the level
              // this record was raised against. Clearing the record without it
              // left the two disagreeing, so the following re-score computed a
              // move that the doctor had already resolved and raised a fresh
              // confirm card for a level nothing had changed to.
              {
                emPendingChange: Prisma.DbNull,
                emScoredCode: parsed.data.overrideToCode,
              }
            : {}),
      },
    });

    // The override CHANGES THE DOCUMENT, so the cached rendering of it is now
    // wrong. The E/M level is printed into the exported DOCX/PDF, and the
    // preview cache is keyed on (visit, soapVersion) — which this route does
    // not move, deliberately: an override is not a note edit, and bumping the
    // note's version here would arm the stale-E/M gate against the doctor's own
    // choice. So the key cannot expire this entry; the entry has to be dropped.
    //
    // Harmless until now, because the only cached variant was the twin one and
    // no production visit had a certified twin. Every visit caches a STYLED
    // rendering now, so without this a doctor overriding 99213 → 99214 would
    // re-read a document still showing 99213 for the rest of the 30-minute TTL
    // while the file they download — and the record they sign — says 99214.
    // "What they read is what they sign" is the whole claim of that surface.
    void invalidateVisitFills(visitId);

    void logAudit({
      action: 'EM_OVERRIDE_APPLIED',
      targetType: 'transcribe_visit',
      targetId: visitId,
      metadata: {
        // The level as DISPLAYED before this write, not the engine's raw
        // suggestion — a doctor overriding their own earlier override was
        // logged as moving from the model's code, which is a hop that never
        // happened. CPT codes and a free-text reason the doctor typed about
        // documentation level; no note text.
        fromCode: displayedBefore,
        engineCode: engineScore.code,
        toCode: parsed.data.overrideToCode,
        reason: parsed.data.reason,
        requiresConfirmation: moved,
      },
    });

    return NextResponse.json(
      {
        ok: true,
        newScore: newUiScore,
        // The client re-arms its confirm card from this rather than guessing.
        pendingChange: moved ? { from, to: parsed.data.overrideToCode } : null,
      },
      { status: 200 },
    );
  },
);

// ──────────────────────────────────────────────────────────────────────
// Helpers
// ──────────────────────────────────────────────────────────────────────

function isPlainObject(v: unknown): v is Record<string, unknown> {
  return typeof v === 'object' && v !== null && !Array.isArray(v);
}

// E/M signal extractors now come from @/lib/em-coding/displayed-level
// (the single source shared with the rail + sign gate — 2026-06-13).
