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
import { TranscribeVisitStatus } from '@prisma/client';
import { auth } from '@/lib/nextauth';
import { apiError, withApiHandler } from '@/lib/api-error';
import { computeEmScore } from '@/lib/em-coding/score';
import { engineToUiScore } from '@/lib/em-coding/to-ui-score';
import type { IcdCodeRow, RxDraftRow } from '@/lib/em-coding/fallback-mdm';
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

// Reason is optional + length-capped so a fat-fingered payload can't
// bloat audit metadata.
const MAX_REASON_LENGTH = 240;

const BodySchema = z.object({
  overrideToCode: z.enum(EM_CODES),
  reason: z.string().max(MAX_REASON_LENGTH).optional(),
});

export const POST = withApiHandler<{ id: string }>(
  'api:visits:em-score:override',
  async (req, { params }) => {
    const { id: visitId } = await params;

    const session = await auth();
    const userId = session?.user?.id;
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
    const visit = await prisma.transcribeVisit.findUnique({
      where: { id: visitId },
      select: {
        id: true,
        userId: true,
        status: true,
        deletedAt: true,
        archivedAt: true,
        signedAt: true,
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
    if (!visit || visit.userId !== userId) return apiError('not found', 404);
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
    const icdCodes = extractIcdCodes(visit.icdCodes);
    const rxDrafts = extractRxDrafts(visit.rxDrafts);
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

    await prisma.transcribeVisit.update({
      where: { id: visitId },
      data: { cptCodes: nextCpt },
    });

    void logAudit({
      action: 'EM_OVERRIDE_APPLIED',
      targetType: 'transcribe_visit',
      targetId: visitId,
      metadata: {
        fromCode: engineScore.code,
        toCode: parsed.data.overrideToCode,
        reason: parsed.data.reason ?? null,
      },
    });

    return NextResponse.json(
      { ok: true, newScore: newUiScore },
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

function extractIcdCodes(raw: unknown): IcdCodeRow[] {
  if (!raw) return [];
  if (Array.isArray(raw)) {
    return raw
      .filter((r): r is Record<string, unknown> => !!r && typeof r === 'object')
      .map((r) => ({
        code: typeof r.code === 'string' ? r.code : '',
        description:
          typeof r.description === 'string' ? r.description : undefined,
      }))
      .filter((r) => r.code.length > 0);
  }
  if (typeof raw === 'object' && raw !== null) {
    const blob = raw as { codes?: unknown };
    if (Array.isArray(blob.codes)) return extractIcdCodes(blob.codes);
  }
  return [];
}

function extractRxDrafts(raw: unknown): RxDraftRow[] {
  if (!raw) return [];
  if (typeof raw === 'object' && raw !== null) {
    const blob = raw as { drafts?: unknown };
    if (Array.isArray(blob.drafts)) {
      return blob.drafts
        .filter((d): d is Record<string, unknown> => !!d && typeof d === 'object')
        .map((d) => ({
          drug:
            typeof d.drug === 'string'
              ? d.drug
              : typeof d.drug_name === 'string'
                ? d.drug_name
                : undefined,
          drug_name: typeof d.drug_name === 'string' ? d.drug_name : undefined,
          action: typeof d.action === 'string' ? d.action : undefined,
        }));
    }
  }
  return [];
}
