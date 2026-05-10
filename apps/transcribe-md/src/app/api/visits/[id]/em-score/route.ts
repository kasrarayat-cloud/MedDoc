// ============================================================================
// POST /api/visits/[id]/em-score (Phase 5.2)
// ----------------------------------------------------------------------------
// Body: { soapText: string }
// Response: { ok: true, score: UiEmScore }
//
// Loads the visit, validates ownership, runs the hybrid scoring engine
// (deterministic counts + LLM-judged MDM with Redis cache + fallback).
// Read-only on SOAP data — never writes back to soapNote/soapFinal.
// Coding feedback is COACHING ONLY: the engine returns scores; the
// rail decides display. The Sign action proceeds regardless.
//
// Wire shape: { ok: true, score: <UI-shape> }. The CodingRail consumes
// the UI shape from `lib/em-coding-ui/types` (suggestedCode, groups,
// bump.{...}, timeBand, override, …) — not the raw engine shape from
// `lib/em-coding/types` (code, satisfied, bumpableTo, …). Pre-fix the
// route returned the engine shape directly; the rail's `RescoreResult`
// reader checks `result.ok && result.score`, both of which were
// undefined on the wire, so every doctor edit silently fell through to
// the "Coding feedback temporarily unavailable" branch — including the
// rescore that runs immediately after a successful Bump apply, which
// made the bump look like it had not persisted.
// ============================================================================

import { NextResponse } from 'next/server';
import { z } from 'zod';

import prisma from '@meddoc/db';
import { auth } from '@/lib/nextauth';
import { apiError, withApiHandler } from '@/lib/api-error';
import { computeEmScore } from '@/lib/em-coding/score';
import { engineToUiScore } from '@/lib/em-coding/to-ui-score';
import type { IcdCodeRow, RxDraftRow } from '@/lib/em-coding/fallback-mdm';
import type { EmCode, EmOverride } from '@/lib/em-coding-ui/types';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';
export const maxDuration = 30;

const BodySchema = z.object({
  soapText: z.string().min(1).max(50_000),
});

export const POST = withApiHandler<{ id: string }>(
  'api:visits:em-score',
  async (req, { params }) => {
    const { id: visitId } = await params;

    const session = await auth();
    const userId = session?.user?.id;
    const practiceId = session?.user?.practiceId;
    if (!userId || !practiceId) return apiError('unauthorized', 401);

    let body: unknown;
    try {
      body = await req.json();
    } catch {
      return apiError('invalid JSON body', 400);
    }
    const parsed = BodySchema.safeParse(body);
    if (!parsed.success) return apiError('invalid soapText payload', 400);

    // Ownership check — 404 on any mismatch (consistent with the rest
    // of the visits API; never expose existence of a foreign visit).
    const visit = await prisma.transcribeVisit.findUnique({
      where: { id: visitId },
      select: {
        id: true,
        userId: true,
        deletedAt: true,
        archivedAt: true,
        // Pull these for the deterministic fallback's structured signals.
        icdCodes: true,
        rxDrafts: true,
        // Time-band derivation in the UI score.
        inputMode: true,
        audioDurationSec: true,
        dictationDurationSec: true,
        // Existing doctor override hydration so the rail keeps showing
        // the doctor-set code after a re-score (matching page.tsx's
        // initial render path).
        cptCodes: true,
      },
    });
    if (!visit || visit.userId !== userId) return apiError('not found', 404);
    if (visit.deletedAt !== null || visit.archivedAt !== null) {
      return apiError('Visit is no longer active.', 400, {
        code: 'VISIT_NOT_ACTIVE',
      });
    }

    // Extract structured signals from the visit row. The Prisma JSON
    // typing is loose; we narrow at the boundary so the engine sees a
    // well-shaped array regardless of older drafts.
    const icdCodes = extractIcdCodes(visit.icdCodes);
    const rxDrafts = extractRxDrafts(visit.rxDrafts);

    const engineScore = await computeEmScore(parsed.data.soapText, {
      practiceId,
      visitId,
      userId,
      icdCodes,
      rxDrafts,
    });

    // Project engine → UI shape (matches page.tsx initial render +
    // override route + apply-additions route). Same three inputs as
    // page.tsx so the rescore wire shape is consistent.
    const durationSec =
      visit.inputMode === 'voice_dictation'
        ? (visit.dictationDurationSec ?? 0)
        : (visit.audioDurationSec ?? 0);
    const existingOverride = extractEmOverride(visit.cptCodes);
    const uiScore = engineToUiScore(engineScore, durationSec, existingOverride);

    return NextResponse.json(
      { ok: true, score: uiScore },
      { status: 200 },
    );
  },
);

/** Hydrate the doctor's previously-set override (if any) from
 *  cptCodes.em.override. Mirror of the helper in
 *  apps/transcribe-md/src/app/visits/[id]/page.tsx so the rescore route
 *  preserves the override across re-scores. Kept inline to avoid a
 *  refactor for a single-call site; lift to a shared util if a third
 *  consumer ever needs it. */
function extractEmOverride(raw: unknown): EmOverride | undefined {
  if (typeof raw !== 'object' || raw === null) return undefined;
  const blob = raw as { em?: { override?: unknown } };
  const override = blob.em?.override;
  if (typeof override !== 'object' || override === null) return undefined;
  const o = override as Record<string, unknown>;
  if (typeof o.code !== 'string') return undefined;
  return {
    code: o.code as EmCode,
    reason: typeof o.reason === 'string' ? o.reason : undefined,
    overriddenAt: typeof o.overriddenAt === 'string' ? o.overriddenAt : '',
  };
}

/** The icdCodes column shape varies across migrations — Layer 7a writes
 *  `{ codes: [{ code, description, ... }] }` but legacy writes were a
 *  bare array. Normalize to IcdCodeRow[]. */
function extractIcdCodes(raw: unknown): IcdCodeRow[] {
  if (!raw) return [];
  if (Array.isArray(raw)) {
    return raw
      .filter((r): r is Record<string, unknown> => !!r && typeof r === 'object')
      .map((r) => ({
        code: typeof r.code === 'string' ? r.code : '',
        description: typeof r.description === 'string' ? r.description : undefined,
      }))
      .filter((r) => r.code.length > 0);
  }
  if (typeof raw === 'object' && raw !== null) {
    const blob = raw as { codes?: unknown };
    if (Array.isArray(blob.codes)) return extractIcdCodes(blob.codes);
  }
  return [];
}

/** rxDrafts shape: `{ drafts: [{ drug, action, ... }], warnings?: [...] }`. */
function extractRxDrafts(raw: unknown): RxDraftRow[] {
  if (!raw) return [];
  if (typeof raw === 'object' && raw !== null) {
    const blob = raw as { drafts?: unknown };
    if (Array.isArray(blob.drafts)) {
      return blob.drafts
        .filter((d): d is Record<string, unknown> => !!d && typeof d === 'object')
        .map((d) => ({
          drug: typeof d.drug === 'string' ? d.drug : (typeof d.drug_name === 'string' ? d.drug_name : undefined),
          drug_name: typeof d.drug_name === 'string' ? d.drug_name : undefined,
          action: typeof d.action === 'string' ? d.action : undefined,
        }));
    }
  }
  return [];
}
