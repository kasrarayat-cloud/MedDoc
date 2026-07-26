// ============================================================================
// POST /api/visits/[id]/em-score/apply-additions  (Phase 5.2 stub completion)
// ----------------------------------------------------------------------------
// Body: { additions: Array<{ criterionId: string; text: string }> }
// Response: { ok: true, newScore: UiEmScore, applied: number, skipped: number }
//
// Persists doctor-edited bump-modal additions into the visit's
// soapDraft, re-runs the L7b CPT scorer against the new SOAP, writes
// an EM_BUMP_APPLIED audit row, and returns the new UI-shaped EmScore
// so the rail can re-render with the bumped code (e.g. 99213 → 99214)
// without a full page reload.
//
// Refuses signed/locked visits (status=SIGNED or signedAt set). Refuses
// archived/deleted visits. Returns 404 on ownership mismatch consistent
// with the rest of the visits API.
// ============================================================================

import { NextResponse } from 'next/server';
import { invalidateVisitFills } from '@/lib/docx-preview/fill-cache';
import { z } from 'zod';

import prisma from '@meddoc/db';
import { TranscribeVisitStatus } from '@prisma/client';
import { auth } from '@/lib/nextauth';
import { apiError, withApiHandler } from '@/lib/api-error';
import { computeEmScore } from '@/lib/em-coding/score';
import { engineToUiScore } from '@/lib/em-coding/to-ui-score';
import { extractIcdRows, extractRxRows } from '@/lib/em-coding/displayed-level';
import { mergeAdditions } from '@/lib/em-coding/merge-additions';
import { logAudit } from '@/lib/audit';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';
export const maxDuration = 30;

// Conservative caps so a malicious or fat-fingered payload can't bloat
// the soapDraft or burn through the request.
const MAX_ADDITIONS = 20;
const MAX_TEXT_LENGTH = 4000;

const AdditionSchema = z.object({
  criterionId: z.string().min(1).max(120),
  text: z.string().max(MAX_TEXT_LENGTH),
});

const BodySchema = z.object({
  additions: z.array(AdditionSchema).min(1).max(MAX_ADDITIONS),
});

export const POST = withApiHandler<{ id: string }>(
  'api:visits:em-score:apply-additions',
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
      return apiError('invalid additions payload', 400, {
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
        'Visit is signed and locked — additions can no longer be applied.',
        409,
        { code: 'VISIT_LOCKED' },
      );
    }
    // Only allow on visits that have actually completed the pipeline.
    // Earlier statuses mean the SOAP isn't stable yet.
    if (visit.status !== TranscribeVisitStatus.READY) {
      return apiError(
        `Visit is in status ${visit.status}; bump additions require a READY visit.`,
        409,
        { code: 'VISIT_NOT_READY' },
      );
    }

    const currentSoap = visit.soapFinal ?? visit.soapDraft ?? '';
    if (!currentSoap.trim()) {
      return apiError(
        'Visit has no SOAP draft to apply additions to.',
        400,
        { code: 'NO_SOAP_DRAFT' },
      );
    }

    // Merge the additions into the SOAP. Pure function — testable
    // without the DB.
    const merge = mergeAdditions(currentSoap, parsed.data.additions);

    // Re-score against the new SOAP using the LLM MDM judge path.
    //
    // Pre-2026-05-11 the route passed `mdmCachedJudgement: null` to
    // force the deterministic fallback "for synchronous + deterministic
    // behaviour." That broke the bump UX: the deterministic counter
    // reads structured ICD codes + Rx warnings from the SOAP, not the
    // free-text additions the BumpModal writes into Assessment. So the
    // MDM tier never moved on a successful bump and the rail kept
    // showing the pre-bump code (e.g. 99212 stays 99212 even when the
    // doctor's addition was the exact gap-filler the rubric prompted
    // for). Every EM_BUMP_APPLIED audit row from the 22-day production
    // window had `toCode === fromCode`.
    //
    // The LLM judge path (`judgeMdm` — purpose=`judge`) reads the SOAP
    // prose and re-evaluates MDM tier. p95 latency 11s in production —
    // well inside the route's maxDuration=30 — so the synchronous
    // concern was over-cautious. `priorSoap: currentSoap` lets the
    // cache's drift bypass fire when the additions move the SOAP
    // enough (>20% drift) so we don't return a stale cached judgement
    // built on the pre-bump body.
    const icdCodes = extractIcdRows(visit.icdCodes);
    const rxDrafts = extractRxRows(visit.rxDrafts);
    const engineScore = await computeEmScore(merge.newSoap, {
      practiceId,
      visitId,
      userId,
      icdCodes,
      rxDrafts,
      priorSoap: currentSoap,
    });

    const durationSec =
      visit.inputMode === 'voice_dictation'
        ? (visit.dictationDurationSec ?? 0)
        : (visit.audioDurationSec ?? 0);
    const newUiScore = engineToUiScore(engineScore, durationSec);

    // Persist. Both columns updated so:
    //   soapDraft  → the rail's source of truth for re-score POSTs
    //   soapFinal  → what the renderer + sign action read
    // The pre-merge soapFinal is preserved as soapL6Original (set by
    // L6 polish; not touched here so the original-AI-output snapshot
    // remains immutable for the doctor-edit-pattern capture path).
    await prisma.transcribeVisit.update({
      where: { id: visitId },
      data: {
        soapDraft: merge.newSoap,
        soapFinal: merge.newSoap,
        // This route rewrites the note, so it must move the version with it.
        // The document preview is cached on (visitId, soapVersion); leaving
        // this untouched served the pre-addition render for the whole TTL and
        // falsified the cache's central claim — that every path which can
        // change what the document says bumps this.
        soapVersion: { increment: 1 },
        // The additions changed the note; the level must be revalidated.
        emStale: true,
      },
    });
    void invalidateVisitFills(visitId);

    // Audit row. Metadata carries the from→to code pair + per-criterion
    // counts; never the addition text itself (PHI).
    void logAudit({
      action: 'EM_BUMP_APPLIED',
      targetType: 'transcribe_visit',
      targetId: visitId,
      metadata: {
        fromCode: engineScore.code,
        // toCode comes from the engine's bumpableTo — may be null if
        // the additions resolved the gap and the new score IS the
        // target tier. In that case the rail's `score.suggestedCode`
        // moved (e.g. 99213 → 99214); we record it explicitly so
        // forensics can see the transition.
        toCode: newUiScore.suggestedCode,
        appliedCount: merge.applied.length,
        skippedCount: merge.skipped.length,
        criterionIds: merge.applied.map((a) => a.criterionId),
      },
    });

    return NextResponse.json(
      {
        ok: true,
        newScore: newUiScore,
        applied: merge.applied.length,
        skipped: merge.skipped.length,
      },
      { status: 200 },
    );
  },
);

// ──────────────────────────────────────────────────────────────────────
// JSON column normalisers — copied from /api/visits/[id]/em-score/route.ts
// to keep the two routes' wire-shape handling consistent. If a third
// route ever needs them, lift to a shared util.
// ──────────────────────────────────────────────────────────────────────

// E/M signal extractors now come from @/lib/em-coding/displayed-level
// (the single source shared with the rail + sign gate — 2026-06-13).
