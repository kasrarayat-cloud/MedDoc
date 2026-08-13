// ============================================================================
// B8 step 3c — MAKE "fail-fast (skipping BullMQ retries)" TRUE
// ----------------------------------------------------------------------------
// The worker has logged, verbatim, `permanent failure, fail-fast (skipping
// BullMQ retries)` since T-M23.A — and then BullMQ retried. Measured on QA
// 2026-08-13: three attempts, five seconds apart, on a permanent failure.
//
// The sentence describes an INTENT and reads as a description of behaviour.
// AGENTS.md: *"a stated invariant is a WISH until something asserts it"* —
// arriving here in a log message rather than in a runbook.
//
// This module is the assertion. It converts a caught error into the shape
// BullMQ recognises as "do not retry this", so the log line becomes a
// description of what happens.
//
// ============================================================================
// ⚠️ BULLMQ CHECKS **TWO** THINGS, AND THE OBVIOUS IMPLEMENTATION SATISFIES
//    ONLY ONE OF THEM
// ----------------------------------------------------------------------------
// `Job.shouldRetryJob` (bullmq 5.76.6, `dist/cjs/classes/job.js:486`) reads:
//
//     !(err instanceof UnrecoverableError || err.name == 'UnrecoverableError')
//
// A DISJUNCTION, and both halves are load-bearing here for different reasons:
//
//   `instanceof` — fails across two copies of the package. There ARE two in
//                  this tree: `node_modules/bullmq` and
//                  `apps/transcribe-md/.next/standalone/node_modules/bullmq`.
//                  A cross-copy `instanceof` is false with no error anywhere.
//   `err.name`   — a plain string comparison, immune to that.
//
// ⚠️ AND SUBCLASSING — THE NATURAL WAY TO WRITE THIS — SILENTLY BREAKS THE
// SECOND HALF. `UnrecoverableError`'s constructor is
// `this.name = this.constructor.name`, so `class PermanentFailure extends
// UnrecoverableError` gets `name === 'PermanentFailure'` and the string arm
// stops matching. The class would then be relying on `instanceof` alone —
// exactly the arm that the dual-copy layout can defeat. Two silent failures
// composing into one retry that still happens, and the log line still lying.
//
// So this constructs the base class DIRECTLY and asserts the name it got.
// Verified at runtime before this was written:
//   `new UnrecoverableError('x').name === 'UnrecoverableError'` → true.
//
// ============================================================================
// ⚠️ WHAT IS PRESERVED, AND WHY IT IS SAFE TO REPLACE THE THROWN OBJECT
// ----------------------------------------------------------------------------
// By the time the worker reaches this call, every consumer of the ORIGINAL
// error object has already run against the original:
//
//   `captureWorkerException(err, …)`   — Sentry has the real error and stack
//   `categorizeError(err)`             — the category is already computed
//   `buildUserFacingFailureReason(…)`  — the doctor-facing banner is written
//   `persistFailedState({originalErr})` — the row already carries it
//   `observeFailedVisitUsage({errorName: err.name})` — already read
//
// The only remaining consumer is BullMQ's own bookkeeping, which stores
// `err.message` as `failedReason` and `err.stack` into the job's `stacktrace`.
// Both are carried across, so the DLQ entry an operator opens is unchanged
// apart from the name — and the name change is the informative part.
//
// `cause` keeps the original reachable for anything added later.
// ============================================================================

import { UnrecoverableError } from 'bullmq';

/**
 * Wrap a caught error in the marker BullMQ reads as "do not retry".
 *
 * @param err the original caught error, whose message and stack are carried
 *            onto the marker so the DLQ entry stays diagnostic.
 */
export function asUnrecoverable(err: unknown): UnrecoverableError {
  const marker = new UnrecoverableError(
    err instanceof Error ? err.message : String(err ?? '')
  );
  // Belt AND braces — see the header. `instanceof` alone is defeated by the
  // second copy of bullmq in the standalone bundle; the name alone is defeated
  // by a future subclass. Setting it explicitly costs nothing and makes the
  // marker satisfy BOTH arms of bullmq's disjunction regardless of which copy
  // of the class this module ended up importing.
  marker.name = 'UnrecoverableError';
  if (err instanceof Error) {
    // The original stack is the diagnosis. A stack pointing at this file would
    // name the messenger.
    marker.stack = err.stack;
    (marker as Error & { cause?: unknown }).cause = err;
  }
  return marker;
}
