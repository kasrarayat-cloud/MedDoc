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
 * That understatement was real and was accepted, for one reason: `isFinalAttempt`
 * BREAKS SILENTLY THE DAY B8 step 3c IS FIXED. 3c's fix is to stop retrying
 * permanent failures at all (the log already claimed "fail-fast (skipping BullMQ
 * retries)" and was lying). Under that fix `attemptsMade` is 0 and
 * `isFinalAttempt` is false, so the observation would simply never run again —
 * a measurement silently switched off by an unrelated correctness fix, with
 * nothing anywhere going red. That is the class AGENTS.md names as "a check
 * that fails when the thing it guards starts working", and it is worse than a
 * known, bounded understatement.
 *
 * ⚠️ **3c HAS SINCE LANDED — see `shouldDiscardPermanentJob` below — AND THE
 * PREDICTION HELD.** A permanent failure now enters the branch exactly once, at
 * `attemptsMade === 0`, so this predicate describes the behaviour instead of
 * compensating for it, and the understatement above is closed: there are no
 * attempts 2..n left to miss. `isFinalAttempt` would today be UNREACHABLE for a
 * permanent failure and the measurement would be gone. This is the reference
 * case for that rule, recorded because both halves were written before the
 * outcome was known.
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

/**
 * B8 step 3c — should this failure be handed back to BullMQ for RETRY, or
 * discarded so the job stops here?
 *
 * ⚠️ THIS CLOSES A THREE-MONTH GAP BETWEEN A LOG LINE AND THE BEHAVIOUR IT
 * DESCRIBES. `worker.ts` logs `permanent failure, fail-fast (skipping BullMQ
 * retries)` and then re-throws, which hands the error straight back to BullMQ;
 * nothing anywhere discarded the job. Measured on QA 2026-08-13: THREE attempts,
 * five seconds apart, every one of them logging the line that says it is
 * skipping them.
 *
 * The claim was never idle. `categorizeError` defines `permanent` as *"retrying
 * is futile — the same input fails the same way"*, and with per-layer resume
 * (`resume-state.ts`) a retry re-runs every layer whose checkpoint column is
 * still null. So a permanent failure that happens BELOW a meter and ABOVE that
 * layer's checkpoint write re-spends vendor money on attempts the system has
 * already classified as useless.
 *
 * ⚠️ `persistOk` IS IN THE PREDICATE, NOT LEFT TO THE CALLER'S ORDERING, AND
 * THAT IS DELIBERATE. A retry is still wanted when the FAILED-state write
 * itself failed: that write is a database blip, not the permanent error, and
 * dropping the job there leaves the visit stuck in a non-terminal status until
 * the 15-minute stuck-visit watchdog force-fails it. `worker.ts` also throws
 * `persistErr` before reaching here, so today the parameter is redundant at the
 * only call site — it is stated anyway because AGENTS.md has already recorded
 * the cost of a predicate whose correctness depends on a precondition the
 * caller happens to maintain (`shouldObserveFailureCost`'s own header). A
 * self-sufficient predicate cannot be broken by moving its call.
 *
 * ⚠️ WHAT IS LOST, NAMED RATHER THAN DISCOVERED. Today a MIS-classified
 * permanent failure can self-heal: the visit is marked FAILED on attempt 1
 * (`shouldFailNow` fires immediately), then attempt 2 or 3 can still complete
 * and flip it to READY. After this change it cannot. The exposure is bounded to
 * the one permanent class whose recurrence is genuinely stochastic —
 * `ModelOutputMalformedError`, where the model returned non-JSON — and
 * `error-categorize.ts:167-173` already argues on the record that a BullMQ
 * retry does not help there, because the only retry-context that ever helped
 * lives INSIDE the model-client loop and has already burned its budget. Every
 * other permanent door (empty transcript, unsupported format, a 4xx on the
 * wire, an empty wallet) is deterministic on the same input by construction.
 *
 * @param category  the worker's own `ErrorCategory` for this failure
 * @param persistOk whether the FAILED-state write succeeded
 */
export function shouldDiscardPermanentJob(
  category: string,
  persistOk: boolean
): boolean {
  return category === 'permanent' && persistOk;
}

/**
 * B8 step 3c — has this job reached the end of the line, so it belongs in the
 * DLQ an operator reads?
 *
 * ⚠️ THIS PREDICATE EXISTS BECAUSE THE DISCARD BROKE THE OLD ONE, AND THE BREAK
 * WAS SILENT. `worker.ts`'s `failed` handler dead-lettered on
 * `attemptsMade >= opts.attempts` — a perfectly correct test of *"the retry
 * budget is exhausted"* right up until a job could stop for a different reason.
 * A discarded permanent failure ends at `attemptsMade = 1` of 3, so the old test
 * says `1 >= 3` → false, and the job quietly never reaches `/admin/queues`.
 *
 * MEASURED, not reasoned about — QA, 2026-08-13, `bull:dlq-permanent-failures`:
 *
 *     413  pre-fix   permanent  3 attempts  → IN the DLQ
 *     415  with fix  transient  3 attempts  → IN the DLQ
 *     416  with fix  transient  3 attempts  → IN the DLQ
 *     414  with fix  permanent  1 attempt   → **ABSENT**
 *
 * B8's own gate text says *"this makes `/admin/queues` load-bearing for money"*.
 * Losing every insufficient-balance refusal from it is the opposite of that.
 *
 * ⚠️ THE NAME OF THE OLD CONDITION WAS THE PROBLEM, WHICH IS THE LESSON.
 * *"The retry budget is exhausted"* and *"this job will not run again"* were the
 * same sentence for as long as exhaustion was the only way to stop. They are not
 * the same sentence any more, and the code was written against the narrower one
 * — AGENTS.md's *"a check whose TITLE is narrower than what it MEASURES"*,
 * arriving in the inverse direction: a check whose title was narrower than what
 * it needed to measure.
 *
 * @param attemptsMade   BullMQ's 0-indexed counter as recorded on the failure
 * @param attempts       the allowance from `job.opts.attempts`
 * @param wasDiscarded   whether the job carried the unrecoverable marker; get
 *                       this from `isUnrecoverableMarker`, never by re-deriving
 *                       bullmq's disjunction at the call site
 */
export function shouldDeadLetter(
  attemptsMade: number,
  attempts: number,
  wasDiscarded: boolean
): boolean {
  return wasDiscarded || attemptsMade >= attempts;
}
