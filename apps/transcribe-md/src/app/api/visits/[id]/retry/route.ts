// ============================================================================
// POST /api/visits/[id]/retry (T-M16.4)
// ----------------------------------------------------------------------------
// Last-ditch "something got stuck" button surfaced by the processing UI
// after 30 min elapsed with no pipeline progress. Re-enqueues the visit
// for the worker with a per-minute idempotent jobId so double-clicks
// collapse into a single retry.
//
// Eligibility:
//   - Session required (owner only — 404 anti-enumeration on mismatch).
//   - visit.status === SIGNED → 409 (nothing to retry, it's terminal).
//   - visit.updatedAt > now - 10 min AND status is an "in-flight"
//     state → 409 + { code: "STILL_PROCESSING" }. A live worker
//     writes to the visit row (status transitions, processingStartedAt,
//     etc.) as each layer runs; a stale updatedAt indicates the worker
//     is probably dead/wedged, safe to re-enqueue. Fresh updatedAt
//     means the worker is likely making progress we don't want to
//     duplicate.
//
// On success: reset visit status to QUEUED, clear reviewReason + the
// processing-finished timestamp, enqueue the retry job. Worker's
// T-M13 resume logic skips whatever layers already completed.
// ============================================================================

import { NextResponse } from 'next/server';

import prisma from '@meddoc/db';
import { TranscribeVisitStatus } from '@prisma/client';

import { apiError, withApiHandler } from '@/lib/api-error';
import { auth } from '@/lib/nextauth';
import { enqueueProcessVisit } from '@/lib/queue';
import { RATE_LIMITS, rateLimitOr429 } from '@/lib/rate-limit';
import { redactPhi } from '@meddoc/ai';
import { log } from '@/lib/log';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

/** How "fresh" updatedAt has to be for the retry to be rejected as
 *  STILL_PROCESSING. A working worker writes the row at every layer
 *  transition (~10s between writes); 10 min covers the longest
 *  single-layer span (a big Deepgram batch + a slow Anthropic polish).
 *  See docs/T-M15-AUDIT-REPORT.md finding H13. */
const STILL_PROCESSING_WINDOW_MS = 10 * 60 * 1000;

/** Statuses that mean "the worker might be running this right now".
 *  Any other status (FAILED, QUEUED) doesn't need the staleness check
 *  — FAILED is an explicit failure, QUEUED means nothing is running. */
const IN_FLIGHT_STATUSES: TranscribeVisitStatus[] = [
  TranscribeVisitStatus.TRANSCRIBING,
  TranscribeVisitStatus.EXTRACTING,
  TranscribeVisitStatus.DRAFTING,
  TranscribeVisitStatus.CRITIQUING,
  TranscribeVisitStatus.POLISHING,
  TranscribeVisitStatus.AUTOMATING,
];

export const POST = withApiHandler<{ id: string }>(
  'api:visits:retry',
  async (_req, { params }) => {
    const { id: visitId } = await params;

    const session = await auth();
    const userId = session?.user?.id;
    if (!userId) return apiError('unauthorized', 401);

    const blocked = rateLimitOr429(RATE_LIMITS.UPLOAD, userId);
    if (blocked) return blocked;

    const visit = await prisma.transcribeVisit.findUnique({
      where: { id: visitId },
      select: {
        id: true,
        userId: true,
        status: true,
        updatedAt: true,
      },
    });
    if (!visit || visit.userId !== userId) return apiError('not found', 404);

    if (visit.status === TranscribeVisitStatus.SIGNED) {
      return NextResponse.json(
        {
          error: 'Signed visits cannot be retried.',
          code: 'ALREADY_SIGNED',
        },
        { status: 409 }
      );
    }

    const isInFlight = IN_FLIGHT_STATUSES.includes(visit.status);
    const freshlyUpdated =
      Date.now() - visit.updatedAt.getTime() < STILL_PROCESSING_WINDOW_MS;
    if (isInFlight && freshlyUpdated) {
      return NextResponse.json(
        {
          error: 'Visit is still processing, please wait.',
          code: 'STILL_PROCESSING',
        },
        { status: 409 }
      );
    }

    // Reset + re-enqueue. Resume logic (T-M13) inside processVisit
    // checks column presence; layers that already wrote their output
    // stay skipped, so this isn't a full re-run.
    try {
      await prisma.transcribeVisit.update({
        where: { id: visit.id },
        data: {
          status: TranscribeVisitStatus.QUEUED,
          needsReview: false,
          reviewReason: null,
          processingFinishedAt: null,
        },
      });
      await enqueueProcessVisit(visitId, userId, { retry: true });
      log.info('api:visits:retry', 're-enqueued', {
        userId,
        visitId,
        prevStatus: visit.status,
      });
    } catch (err) {
      console.error(
        '[api:visits:retry] enqueue failed:',
        redactPhi(err instanceof Error ? err.message : err)
      );
      return apiError('Could not re-enqueue the visit. Try again.', 502);
    }

    return NextResponse.json({ ok: true }, { status: 200 });
  }
);
