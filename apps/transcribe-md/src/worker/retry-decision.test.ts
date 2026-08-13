import { describe, it, expect } from 'vitest';

import { shouldMarkVisitFailed, shouldObserveFailureCost } from './retry-decision';

describe('shouldMarkVisitFailed', () => {
  // Our production queue config is attempts=3, so these three cases
  // are the ones that matter day-to-day.
  it('returns false on the first attempt of a 3-attempt job', () => {
    expect(shouldMarkVisitFailed(0, 3)).toBe(false);
  });

  it('returns false on the middle attempt of a 3-attempt job', () => {
    expect(shouldMarkVisitFailed(1, 3)).toBe(false);
  });

  it('returns true on the final attempt of a 3-attempt job', () => {
    expect(shouldMarkVisitFailed(2, 3)).toBe(true);
  });

  // A job with no retries configured (attempts=1) should mark FAILED
  // immediately on the first throw — there's nobody else to catch it.
  it('returns true on a single-attempt job', () => {
    expect(shouldMarkVisitFailed(0, 1)).toBe(true);
  });

  it('returns true across an attempts=2 job', () => {
    expect(shouldMarkVisitFailed(0, 2)).toBe(false);
    expect(shouldMarkVisitFailed(1, 2)).toBe(true);
  });

  // Defensive: a mis-configured attempts=0 / negative shouldn't leave
  // the visit in a zombie in-flight state. Treat it as attempts=1.
  it('treats non-positive attempts as attempts=1', () => {
    expect(shouldMarkVisitFailed(0, 0)).toBe(true);
    expect(shouldMarkVisitFailed(0, -1)).toBe(true);
  });
});

// ============================================================================
// B8 step 3 — the `failure cost` observation is ONCE PER VISIT, not per attempt
// ----------------------------------------------------------------------------
// ⚠️ THIS SUITE EXISTS BECAUSE THE PRODUCTION PREDICATE WAS WRONG TWICE AND CI
// COULD NOT SEE EITHER TIME. Measured on QA 2026-08-13, one admission-refused
// visit:
//
//   unguarded                             → 3 `failure cost` lines
//   `isFinalAttempt || attemptsMade === 0` → 2  (the first AND the last)
//   `shouldObserveFailureCost`             → 1
//
// The middle row is the one worth remembering: it reads like "the first one or
// the last one" and is exactly-TWICE for a permanent failure, because that
// branch is entered on every attempt so BOTH disjuncts fire — on different
// attempts. It halved the defect and looked like a fix.
//
// ⚠️ THE CALLER'S PRECONDITION IS PART OF THE CONTRACT. `worker.ts` only
// reaches this predicate inside `shouldFailNow = isFinalAttempt || permanent`.
// So a NON-permanent category reaching here is necessarily the final attempt,
// which is why the non-permanent arm below is unconditionally true — it is not
// ignoring the attempt counter, it is relying on a guarantee the caller makes.
// ============================================================================
describe('shouldObserveFailureCost', () => {
  // The defect, stated as the thing that must not come back. Our production
  // queue is attempts=3, so a permanent failure enters the branch at 0, 1, 2.
  it('observes a permanent failure exactly once, on the first attempt', () => {
    expect(shouldObserveFailureCost('permanent', 0)).toBe(true);
    expect(shouldObserveFailureCost('permanent', 1)).toBe(false);
    expect(shouldObserveFailureCost('permanent', 2)).toBe(false);
  });

  // ⚠️ THE POSITIVE HALF, AND IT IS THE ONE A NARROWING FIX WOULD BREAK. A
  // guard that silenced duplicates by observing nothing would satisfy the case
  // above perfectly. AGENTS.md: a guard proven only in the red direction is
  // half-proven, and it is the cheaper half.
  it('observes a transient failure, which reaches this branch only when final', () => {
    expect(shouldObserveFailureCost('transient', 2)).toBe(true);
  });

  it('observes a provider_down failure on the same terms as transient', () => {
    expect(shouldObserveFailureCost('provider_down', 2)).toBe(true);
  });

  // A single-attempt job: attemptsMade is 0 AND it is the final attempt. Both
  // categories must still emit exactly one observation.
  it('observes once on a single-attempt job, whatever the category', () => {
    expect(shouldObserveFailureCost('permanent', 0)).toBe(true);
    expect(shouldObserveFailureCost('transient', 0)).toBe(true);
  });

  // ⚠️ THE CATEGORY IS COMPARED WITH `===` ON THE WHOLE TOKEN, NEVER SEARCHED
  // FOR. AGENTS.md records four sightings of the substring trap. A category
  // that merely CONTAINS "permanent" is not `permanent`, and must not inherit
  // its suppression — otherwise a future category name would silently stop
  // being measured.
  it('does not treat a category that merely contains "permanent" as permanent', () => {
    expect(shouldObserveFailureCost('semi-permanent', 1)).toBe(true);
    expect(shouldObserveFailureCost('permanently_gone', 1)).toBe(true);
  });
});
