// ============================================================================
// FAILED-state persistence helper (FIND-P1-014 hardening).
// ----------------------------------------------------------------------------
// Writes `{ status: FAILED, reviewReason, failureCategory, ... }` to the
// visit row when the pipeline gives up. Wrapped in its own try/catch so the
// worker's outer catch can decide what to do when the persist itself fails.
//
// FIND-P1-014 (comprehensive-audit 2026-05-14): the prior inline
// implementation used `.update().catch(() => console.error(...))` which
// silently swallowed write failures. Combined with the worker's outer
// `throw err` (line ~1060), a DB outage at the exact wrong moment left
// visits in their non-terminal status (POLISHING / AUTOMATING / etc.)
// indefinitely — only the stuck-visit watchdog (15-min sweep) rescued them.
//
// Fix: extract the persist into a helper that returns a structured
// `{ persistOk, persistErr }` result. The caller (worker outer catch)
// re-throws `persistErr` so BullMQ marks the job failed with the
// secondary failure context. The original error has already been
// captured to Sentry by the time we get here, so context isn't lost.
// Policy (Kasra, 2026-05-14): re-throw to BullMQ. Silent stuck-in-
// non-terminal is the worse failure mode. The watchdog catches BullMQ
// retries; it doesn't catch silent swallows.
// ============================================================================

import { TranscribeVisitStatus } from "@prisma/client";
import { redactPhi } from "@meddoc/ai";
import { log } from "@/lib/log";
import { enqueueTemplateTwinAudit } from "@/lib/template-twin/audit-outbox";
import { captureWorkerException } from "../worker-sentry";
import type { ErrorCategory } from "./error-categorize";
import { runVisitAutomationTransaction } from "./automation-locks";
import { markVisitAutomationManifestFailed } from "./automation-manifest";

export interface PersistFailedArgs {
  visitId: string;
  category: ErrorCategory;
  /** Pipeline tracker ('L1', 'L2', 'automation', 'finalize', etc.).
   *  Used for Sentry tagging only; never written to the DB. */
  layer: string;
  /** The original pipeline error — already captured to Sentry by the
   *  caller. Passed in so the structured log line carries BOTH
   *  failure causes for post-mortem diagnostics. */
  originalErr: unknown;
  /** User-facing failure reason string. Derived from `layer` +
   *  `category` by the caller (`buildUserFacingFailureReason`) — kept
   *  PHI-free so it can render in the UI banner. */
  reviewReason: string;
  /** For Sentry tagging on the secondary (persist) failure. */
  userId: string;
  practiceId: string;
}

export interface PersistFailedResult {
  /** True if the FAILED-state row write succeeded. */
  persistOk: boolean;
  /** Populated only when `persistOk === false`. The caller should
   *  re-throw this so BullMQ marks the job failed with the persist
   *  failure as its proximate cause. */
  persistErr: unknown;
}

/** Persist the FAILED status to the visit row. Returns a structured
 *  result so the caller can decide whether to re-throw. Logs +
 *  captures the secondary (persist) failure to Sentry on its own —
 *  the original error must already be in Sentry by the time this is
 *  called.
 *
 *  Does NOT throw. Failures land in the returned `persistErr` field. */
export async function persistFailedState(
  args: PersistFailedArgs,
): Promise<PersistFailedResult> {
  try {
    await runVisitAutomationTransaction({
      operation: "persist_visit_automation_failed",
      visitId: args.visitId,
      userId: args.userId,
      practiceId: args.practiceId,
      transaction: async (tx) => {
        const completedAt = new Date();
        const manifest = await markVisitAutomationManifestFailed(tx, {
          visitId: args.visitId,
          failureCode: "WORKER_ATTEMPT_FAILED",
          completedAt,
        });
        await tx.transcribeVisit.update({
          where: { id: args.visitId },
          data: {
            status: TranscribeVisitStatus.FAILED,
            processingFinishedAt: completedAt,
            needsReview: true,
            // Phase-tagged user copy only; never persist raw errors.
            reviewReason: args.reviewReason,
            failureCategory: args.category,
          },
        });
        await enqueueTemplateTwinAudit(tx, {
          eventKey: manifest
            ? `visit-automation:failed:${args.visitId}:${manifest.manifestVersion}:${manifest.attemptCount}`
            : `visit-processing:failed:${args.visitId}:${args.layer}`,
          practiceId: args.practiceId,
          actorId: args.userId,
          action: "VISIT_AUTOMATION_INCOMPLETE",
          targetType: "TranscribeVisit",
          targetId: args.visitId,
          metadata: {
            reasonCode: manifest
              ? "VISIT_AUTOMATION_WORKER_FAILED"
              : "VISIT_PIPELINE_FAILED_BEFORE_AUTOMATION",
            layer: args.layer,
            category: args.category,
            ...(manifest
              ? {
                  manifestId: manifest.id,
                  manifestVersion: manifest.manifestVersion,
                }
              : {}),
          },
        });
      },
    });
    return { persistOk: true, persistErr: null };
  } catch (writeErr: unknown) {
    // FIND-P1-014: surface the double-failure so post-mortems are
    // diagnosable. Original error went to Sentry at the top of the
    // outer catch; this Sentry event is its companion.
    log.error("transcribe-md-worker", "FAILED-state persist also failed", {
      visitId: args.visitId,
      layer: args.layer,
      category: args.category,
      originalErrMessage: redactPhi(
        args.originalErr instanceof Error
          ? args.originalErr.message
          : String(args.originalErr ?? ""),
      ),
      persistErrMessage: redactPhi(
        writeErr instanceof Error ? writeErr.message : String(writeErr ?? ""),
      ),
    });
    captureWorkerException(writeErr, {
      visitId: args.visitId,
      layer: "finalize",
      userId: args.userId,
      practiceId: args.practiceId,
    });
    return { persistOk: false, persistErr: writeErr };
  }
}
