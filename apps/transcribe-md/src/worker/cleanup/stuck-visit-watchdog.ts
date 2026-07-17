// ============================================================================
// Stuck-visit watchdog (2026-05-12)
// ----------------------------------------------------------------------------
// Per-minute sweep that force-fails visits stuck in an in-flight processing
// state past the global 15-min budget. Catches the failure mode the Kasra
// incident exposed (cmp31iojc001201psjlrvaiwn): the 4th retry within the
// same minute silently deduped against a prior failed BullMQ job, leaving
// the visit pinned at status=QUEUED for 2.5 hours with no worker running.
//
// Why a separate sweep is needed even with the worker-side JOB_TIMEOUT_MS
// + per-layer timeouts (see `withTimeout` wrapping in worker.ts):
//   - JOB_TIMEOUT_MS only fires while a worker IS processing the job.
//     If the job got dropped / deduped / never picked up, the timeout
//     never trips. Sweep catches that case.
//   - Per-layer timeouts catch a hung layer call, not a hung overall
//     job. Sweep is the belt-and-braces.
//
// Sweep semantics:
//   - Scope: status IN (TRANSCRIBING, EXTRACTING, DRAFTING, CRITIQUING,
//     POLISHING, AUTOMATING) WITH processingStartedAt < NOW() - 15 min.
//     QUEUED is NOT included — a fresh QUEUED visit may legitimately
//     be sitting in the BullMQ wait state for seconds; the
//     stale-visit-cleanup sweep (T-M17.3) handles abandoned-QUEUED.
//   - Action: transition to FAILED + failureCategory='transient' +
//     reviewReason naming the prior status + elapsed time, so the
//     visit-failed-view UX layer (PR #227) renders the right copy.
//   - Audit: one VISIT_PROCESSING_TIMEOUT row per rescued visit, with
//     metadata { prevStatus, elapsedSec, processingStartedAt }.
// ============================================================================

import prisma from '@meddoc/db';
import { TranscribeVisitStatus } from '@prisma/client';

import { log } from '@/lib/log';
import { logAudit } from '@/lib/audit';

/** Force-fail threshold. The Kasra incident's stuck visit was at 146 min
 *  elapsed when discovered; 15 min is the global JOB_TIMEOUT_MS cap and
 *  is also the worker-side hard cap on a single job attempt, so anything
 *  past 15 min in a processing state is genuinely stuck.
 *
 *  Configurable via env so ops can tighten (e.g. 10 min for a smaller
 *  visit volume) without redeploy. */
const STUCK_THRESHOLD_MS = Number.parseInt(
  process.env.STUCK_VISIT_THRESHOLD_MS ?? String(15 * 60 * 1000),
  10,
);

/** Statuses the worker writes during pipeline execution. A visit in any
 *  of these states past the threshold is stuck — the worker is supposed
 *  to transition through these in seconds-to-minutes, never 15+ min
 *  total. QUEUED is intentionally excluded (covered by the T-M17.3
 *  abandoned-QUEUED sweep). */
const IN_FLIGHT_STATUSES: TranscribeVisitStatus[] = [
  TranscribeVisitStatus.TRANSCRIBING,
  TranscribeVisitStatus.EXTRACTING,
  TranscribeVisitStatus.DRAFTING,
  TranscribeVisitStatus.CRITIQUING,
  TranscribeVisitStatus.POLISHING,
  TranscribeVisitStatus.AUTOMATING,
];

export interface StuckVisitSweepResult {
  scanned: number;
  rescued: number;
  errors: number;
}

/** Run a single sweep cycle. Idempotent — re-runs are cheap (one
 *  indexed query + at most N row updates). Returns a per-cycle tally
 *  for the heartbeat log + admin /health endpoint. */
export async function runStuckVisitWatchdog(opts?: {
  thresholdMs?: number;
  now?: Date;
}): Promise<StuckVisitSweepResult> {
  const thresholdMs = opts?.thresholdMs ?? STUCK_THRESHOLD_MS;
  const now = opts?.now ?? new Date();
  const cutoff = new Date(now.getTime() - thresholdMs);

  const stuck = await prisma.transcribeVisit.findMany({
    where: {
      status: { in: IN_FLIGHT_STATUSES },
      processingStartedAt: { lt: cutoff },
      deletedAt: null,
      // Staging attempts are DB-exclusive and deliberately have no
      // Promise.race cancellation. Only their attempt ledger may publish a
      // terminal state; the generic watchdog must never race that claim.
      templateTwinSyntheticQaRun: { is: null },
    },
    select: {
      id: true,
      status: true,
      userId: true,
      user: { select: { practiceId: true } },
      processingStartedAt: true,
    },
  });

  let rescued = 0;
  let errors = 0;

  for (const v of stuck) {
    const elapsedMs = now.getTime() - (v.processingStartedAt?.getTime() ?? now.getTime());
    const elapsedMin = Math.round(elapsedMs / 60_000);
    const prevStatus = v.status;

    // Defensive re-read inside the update: if the worker has just
    // (within the last few ms) finished and transitioned the row, the
    // updateMany's WHERE constraint prevents us from clobbering its
    // result. Belt-and-braces against a race we'd otherwise never see.
    try {
      const upd = await prisma.transcribeVisit.updateMany({
        where: {
          id: v.id,
          status: { in: IN_FLIGHT_STATUSES },
          processingStartedAt: { lt: cutoff },
        },
        data: {
          status: TranscribeVisitStatus.FAILED,
          failureCategory: 'transient',
          needsReview: true,
          reviewReason:
            `Visit processing exceeded ${Math.round(thresholdMs / 60_000)}-min global timeout ` +
            `(was ${prevStatus} for ${elapsedMin} min) — likely pipeline stall, retry to reprocess.`,
          processingFinishedAt: now,
        },
      });

      if (upd.count > 0) {
        rescued += 1;
        log.info('ops:stuck-visit-watchdog', 'rescued', {
          visitId: v.id,
          prevStatus,
          elapsedMin,
        });

        // Audit-row write is best-effort — a failure here shouldn't
        // un-rescue the visit. The visit row itself carries the
        // reviewReason; the audit row is for admin forensics.
        try {
          await logAudit({
            action: 'VISIT_PROCESSING_TIMEOUT',
            targetId: v.id,
            targetType: 'TranscribeVisit',
            userId: v.userId,
            practiceId: v.user?.practiceId ?? null,
            success: false,
            metadata: {
              prevStatus,
              elapsedMin,
              thresholdMin: Math.round(thresholdMs / 60_000),
              processingStartedAt: v.processingStartedAt?.toISOString() ?? null,
            },
          });
        } catch (auditErr) {
          // Worker context — logAudit's auth() pull may fail outside
          // a request scope. The visit transition succeeded; just
          // note the audit gap.
          errors += 1;
          log.warn('ops:stuck-visit-watchdog', 'audit write failed', {
            visitId: v.id,
            err: auditErr instanceof Error ? auditErr.message : String(auditErr),
          });
        }
      }
      // upd.count === 0 means the worker won the race — no action needed.
    } catch (err) {
      errors += 1;
      log.error('ops:stuck-visit-watchdog', 'rescue failed', {
        visitId: v.id,
        prevStatus,
        elapsedMin,
        err: err instanceof Error ? err.message : String(err),
      });
    }
  }

  return { scanned: stuck.length, rescued, errors };
}
