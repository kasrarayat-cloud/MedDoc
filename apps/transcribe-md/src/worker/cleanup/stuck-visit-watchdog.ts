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

import prisma from "@meddoc/db";
import { Prisma, TranscribeVisitStatus } from "@prisma/client";

import { log } from "@/lib/log";
import { runSerializableTransactionWithRetry } from "@/lib/db/transaction-retry";
import { canonicalSha256 } from "@/lib/template-twin/canonical";
import { TEMPLATE_TWIN_DURABLE_VISIT_EXCLUSION_WHERE } from "@/lib/template-twin/durable-visit-exclusion";
import { hasDurableTemplateTwinVisitProvenance } from "@/lib/template-twin/durable-visit-provenance";
import { enqueueIdempotentTemplateTwinAudit } from "@/lib/template-twin/audit-outbox";

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
      // Every durable Twin marker is excluded. The canonical provider and
      // staging ledgers own their own ambiguity-aware terminal transitions.
      ...TEMPLATE_TWIN_DURABLE_VISIT_EXCLUSION_WHERE,
    },
    select: {
      id: true,
      status: true,
      userId: true,
      user: { select: { practiceId: true } },
      processingStartedAt: true,
      patient: { select: { externalId: true } },
      noteTemplate: {
        select: {
          templateKind: true,
          templateTwinCompiledVersion: { select: { id: true } },
        },
      },
      templateTwinFill: { select: { id: true } },
      templateTwinSyntheticQaRun: { select: { id: true } },
      templateTwinSyntheticQaAdmission: { select: { id: true } },
      templateTwinProviderExecutions: {
        select: { id: true },
        take: 1,
      },
    },
  });

  let rescued = 0;
  let errors = 0;

  for (const v of stuck) {
    const elapsedMs =
      now.getTime() - (v.processingStartedAt?.getTime() ?? now.getTime());
    const elapsedMin = Math.round(elapsedMs / 60_000);
    const prevStatus = v.status;

    if (hasDurableTemplateTwinVisitProvenance(v)) {
      errors += 1;
      log.error("ops:stuck-visit-watchdog", "durable Twin candidate rejected", {
        visitId: v.id,
        prevStatus,
      });
      continue;
    }

    // The canonical visit lock serializes this ordinary-only re-census with
    // provider ownership. The status transition and required outbox audit
    // commit together; an outbox failure rolls the transition back.
    try {
      const outcome = await runSerializableTransactionWithRetry({
        prisma,
        operation: "stuck_visit_watchdog",
        context: { visitId: v.id, practiceId: v.user.practiceId },
        transaction: async (tx) => {
          const practices = await tx.$queryRaw<Array<{ id: string }>>(
            Prisma.sql`
              SELECT "id" FROM "practices"
              WHERE "id" = ${v.user.practiceId}
              FOR UPDATE
            `,
          );
          const actors = await tx.$queryRaw<Array<{ id: string }>>(Prisma.sql`
            SELECT "id" FROM "users"
            WHERE "id" = ${v.userId}
              AND "practiceId" = ${v.user.practiceId}
            FOR UPDATE
          `);
          const visits = await tx.$queryRaw<Array<{ id: string }>>(Prisma.sql`
            SELECT "id" FROM "transcribe_visits"
            WHERE "id" = ${v.id}
              AND "userId" = ${v.userId}
            FOR UPDATE
          `);
          if (
            practices.length !== 1 ||
            actors.length !== 1 ||
            visits.length !== 1
          ) {
            return "RACE_LOST" as const;
          }
          const current = await tx.transcribeVisit.findUnique({
            where: { id: v.id },
            select: {
              id: true,
              status: true,
              processingStartedAt: true,
              patient: { select: { externalId: true } },
              noteTemplate: {
                select: {
                  templateKind: true,
                  templateTwinCompiledVersion: { select: { id: true } },
                },
              },
              templateTwinFill: { select: { id: true } },
              templateTwinSyntheticQaRun: { select: { id: true } },
              templateTwinSyntheticQaAdmission: { select: { id: true } },
              templateTwinProviderExecutions: {
                select: { id: true },
                take: 1,
              },
            },
          });
          if (!current || hasDurableTemplateTwinVisitProvenance(current)) {
            return "TWIN_REJECTED" as const;
          }
          if (
            !IN_FLIGHT_STATUSES.includes(current.status) ||
            !current.processingStartedAt ||
            current.processingStartedAt >= cutoff
          ) {
            return "RACE_LOST" as const;
          }

          const upd = await tx.transcribeVisit.updateMany({
            where: {
              id: v.id,
              status: { in: IN_FLIGHT_STATUSES },
              processingStartedAt: { lt: cutoff },
              ...TEMPLATE_TWIN_DURABLE_VISIT_EXCLUSION_WHERE,
            },
            data: {
              status: TranscribeVisitStatus.FAILED,
              failureCategory: "transient",
              needsReview: true,
              reviewReason:
                `Visit processing exceeded ${Math.round(thresholdMs / 60_000)}-min global timeout ` +
                `(was ${prevStatus} for ${elapsedMin} min) — likely pipeline stall, retry to reprocess.`,
              processingFinishedAt: now,
            },
          });
          if (upd.count !== 1) return "RACE_LOST" as const;

          const processingStartedAt = current.processingStartedAt.toISOString();
          await enqueueIdempotentTemplateTwinAudit(tx, {
            eventKey: `visit-processing-timeout:${canonicalSha256({
              visitId: v.id,
              prevStatus,
              processingStartedAt,
            })}`,
            practiceId: v.user.practiceId,
            actorId: v.userId,
            action: "VISIT_PROCESSING_TIMEOUT",
            targetId: v.id,
            targetType: "TranscribeVisit",
            metadata: {
              prevStatus,
              elapsedMin,
              thresholdMin: Math.round(thresholdMs / 60_000),
              processingStartedAt,
            },
          });
          return "RESCUED" as const;
        },
      });

      if (outcome === "TWIN_REJECTED") {
        errors += 1;
        log.error(
          "ops:stuck-visit-watchdog",
          "durable Twin appeared under lock",
          { visitId: v.id, prevStatus },
        );
      } else if (outcome === "RESCUED") {
        rescued += 1;
        log.info("ops:stuck-visit-watchdog", "rescued", {
          visitId: v.id,
          prevStatus,
          elapsedMin,
        });
      }
    } catch (err) {
      errors += 1;
      log.error("ops:stuck-visit-watchdog", "rescue failed", {
        visitId: v.id,
        prevStatus,
        elapsedMin,
        err: err instanceof Error ? err.message : String(err),
      });
    }
  }

  return { scanned: stuck.length, rescued, errors };
}
