// ============================================================================
// Worker resume-state loader (T-M13 / FIND-P1-011 hardening).
// ----------------------------------------------------------------------------
// Reads the per-visit pipeline checkpoint columns at the start of each retry
// attempt. The returned shape feeds `isLayerComplete()` so the worker can
// skip layers that already succeeded in a prior attempt.
//
// FIND-P1-011 (comprehensive-audit 2026-05-14): the prior implementation
// returned an all-nulls fallback when the visit row was missing. On a BullMQ
// retry where the visit had been deleted between attempts, that fallback
// caused the next `prisma.update` (L1 / L2 checkpoint write) to throw
// Prisma `P2025 (record not found)` — surfaces as
// `"Processing failed during init"` rather than a clean "visit gone" exit.
//
// Fix: throw a typed `VisitNotFoundError` on retry with a missing row so
// the worker's outer catch can short-circuit (skip FAILED-state persist,
// skip admin notify) without burning further BullMQ attempts on a
// non-existent row. On first attempt, the top-level `findUnique` has
// already verified existence; a missing row here means a race between two
// `findUnique` calls — surface as a plain Error so Sentry catches it.
// ============================================================================

import prisma from '@meddoc/db';
import { currentClinicalVisitActorWhere } from '@/lib/clinical-visit-authority';
import type { LayerSkipState } from './layer-skip';

/** Thrown by `loadResumeState` when a BullMQ retry attempt finds the
 *  visit row already deleted. The worker's outer catch handler should
 *  treat this as a clean exit (no FAILED-state write — the row's gone)
 *  rather than a pipeline failure. */
export class VisitNotFoundError extends Error {
  readonly visitId: string;
  constructor(visitId: string) {
    super(`Visit ${visitId} no longer exists (deleted during retry)`);
    this.name = 'VisitNotFoundError';
    this.visitId = visitId;
  }
}

/** Load every layer's checkpoint column in one query. Returns a
 *  `LayerSkipState` shape the skip checks consume. An all-nulls shape on
 *  the first attempt → every `isLayerComplete()` returns false → the
 *  pipeline runs end-to-end. A partially-populated shape on retry →
 *  skips fire for completed layers.
 *
 *  @param visitId      — the visit being processed
 *  @param actorUserId  — current queued owner; lifecycle and patient tenant
 *                        are bound in this same PHI-bearing query
 *  @param attemptsMade — `job.attemptsMade` from BullMQ. 0 on first
 *                        attempt; >0 on retry. Disambiguates the
 *                        missing-row error class.
 *  @throws VisitNotFoundError on retry (`attemptsMade > 0`) when the
 *                             row is gone.
 *  @throws Error on first attempt (`attemptsMade === 0`) when the row
 *                is gone — indicates a race between the top-level
 *                `findUnique` and this load; surfaces to Sentry.
 */
export async function loadResumeState(
  visitId: string,
  actorUserId: string,
  attemptsMade: number
): Promise<LayerSkipState> {
  const row = await prisma.transcribeVisit.findUnique({
    where: {
      id: visitId,
      ...currentClinicalVisitActorWhere(actorUserId),
    },
    select: {
      transcriptRaw: true,
      transcriptText: true,
      speakerMap: true,
      entities: true,
      soapDraft: true,
      critique: true,
      soapFinal: true,
      icdCodes: true,
      cptCodes: true,
      rxDrafts: true,
      referrals: true,
      patientSummary: true,
    },
  });
  if (!row) {
    if (attemptsMade > 0) {
      throw new VisitNotFoundError(visitId);
    }
    throw new Error(
      `Visit ${visitId} disappeared between top-level find and resume-state load (first attempt — likely a race)`
    );
  }
  return row as LayerSkipState;
}
