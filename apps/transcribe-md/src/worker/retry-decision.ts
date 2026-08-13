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

/**
 * B8 step 3 — should THIS attempt emit the `failure cost` observation?
 *
 * ⚠️ EXTRACTED BECAUSE THE INLINE VERSION WAS WRONG TWICE, AND NOTHING IN CI
 * COULD SEE EITHER. The observation shipped unguarded, and the first guard
 * written for it was also wrong; both were caught only by re-running the QA
 * behavioural proof by hand (`scripts/qa/b8-failure-cost-on-qa.ts` +
 * `scripts/qa/b8-failure-cost-log-assert.py`, 2026-08-13).
 *
 *   unguarded                          → 3 lines for one visit (one per attempt)
 *   `isFinalAttempt || attemptsMade===0` → 2 lines (the first AND the last)
 *   this predicate                     → 1
 *
 * No unit test runs `processVisit`, which is ruling #96(a)'s standing gap and
 * the reason `shouldMarkVisitFailed` above was extracted in the first place.
 * Putting the decision in a pure function is what moves it from "proven on QA
 * by whoever remembered to look" to "proven on every CI run".
 *
 * ⚠️ THE CALLER IS ALREADY INSIDE `shouldFailNow = isFinalAttempt || permanent`.
 * That is what makes this a question about the permanent case only:
 *
 *   permanent  — the branch is entered on EVERY attempt, because the re-throw
 *                still hands the error to BullMQ and nothing discards the job.
 *                Only the first entry should observe.
 *   otherwise  — the branch is reachable only on the final attempt, so the one
 *                entry is the one to observe.
 *
 * The observation charges nothing either way, so a duplicate is a MEASUREMENT
 * defect rather than a money one — but the number it inflates is exactly the
 * one that will price the decision to enable `BILLING_ENFORCED`, and it
 * inflates it in the direction that makes failures look more expensive than
 * they are.
 *
 * ⚠️ THE OBVIOUS ALTERNATIVE IS `isFinalAttempt` ALONE, IT IS MORE ACCURATE
 * TODAY, AND IT IS STILL NOT THE ONE CHOSEN. It is also exactly-once — the
 * branch IS entered on the final attempt for a permanent failure — and it would
 * observe AFTER every retry, so it would see all the spend. This predicate
 * observes a permanent failure on its FIRST attempt and therefore MISSES
 * whatever attempts 2..n re-spend.
 *
 * That understatement is real and is accepted, for one reason: `isFinalAttempt`
 * BREAKS SILENTLY THE DAY B8 step 3c IS FIXED. 3c's fix is to stop retrying
 * permanent failures at all (the log already claims "fail-fast (skipping BullMQ
 * retries)" and is lying). Under that fix `attemptsMade` is 0 and
 * `isFinalAttempt` is false, so the observation would simply never run again —
 * a measurement silently switched off by an unrelated correctness fix, with
 * nothing anywhere going red. That is the class AGENTS.md names as "a check
 * that fails when the thing it guards starts working", and it is worse than a
 * known, bounded understatement.
 *
 * So this predicate measures the INTENDED semantics — a permanent failure runs
 * once — and the gap between that and today's behaviour is 3c's, not this
 * function's. Fixing 3c closes the gap rather than opening one.
 *
 * @param category      the worker's own `ErrorCategory` for this failure
 * @param attemptsMade  BullMQ's 0-indexed attempt counter
 */
export function shouldObserveFailureCost(
  category: string,
  attemptsMade: number
): boolean {
  return category !== 'permanent' || attemptsMade === 0;
}
