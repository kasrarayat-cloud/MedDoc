// ============================================================================
// Retry-decision helper for the transcribe-md worker (T-M23.A)
// ----------------------------------------------------------------------------
// Pure predicate used by processVisit's catch block to decide whether a
// caught error should flip the visit's status to FAILED. On a non-final
// BullMQ attempt we leave the status at whatever the last-running layer
// wrote (EXTRACTING / DRAFTING / …), so the UI keeps showing the
// processing spinner during the backoff window before the next attempt.
// Only the FINAL attempt — the one that, if it throws, will exhaust the
// job's allowed retries — actually persists FAILED.
//
// Extracted to its own module so the decision is trivially unit-testable
// against mock `attemptsMade` / `attempts` values without needing the
// full worker harness + Prisma + BullMQ in scope.
// ============================================================================

/**
 * Should a caught error at this attempt-index result in writing
 * `visit.status = FAILED`? Returns `true` when this is the last attempt
 * the job has, meaning a re-throw here won't be retried by BullMQ.
 *
 * BullMQ's `job.attemptsMade` is 0-indexed: 0 during the first execution
 * of the processFn, 1 during the first retry, etc. `job.opts.attempts`
 * is the total number of tries including the initial one (our queue.ts
 * sets it to 3).
 */
export function shouldMarkVisitFailed(
  attemptsMade: number,
  attempts: number
): boolean {
  // `Math.max(1, …)` guards against a mis-configured job where
  // `opts.attempts` is 0 or negative — any such call counts as "this is
  // the only attempt, mark FAILED on throw" rather than leaving the
  // visit in a zombie in-flight state forever.
  return attemptsMade >= Math.max(1, attempts) - 1;
}
