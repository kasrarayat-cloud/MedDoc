import { describe, it, expect } from 'vitest';
import { UnrecoverableError } from 'bullmq';

import { asUnrecoverable, isUnrecoverableMarker } from './unrecoverable';

// ============================================================================
// B8 step 3c — the marker that makes "fail-fast" true
// ----------------------------------------------------------------------------
// ⚠️ THE ASSERTION IS AGAINST BULLMQ'S OWN PREDICATE, COPIED VERBATIM, NOT
// AGAINST WHAT I BELIEVE IT DOES. From `bullmq@5.76.6`,
// `dist/cjs/classes/job.js:486`, inside `shouldRetryJob`:
//
//     !(err instanceof UnrecoverableError || err.name == 'UnrecoverableError')
//
// A test that asserted `marker instanceof UnrecoverableError` and stopped would
// be checking the half that the two-copies-of-bullmq layout can defeat, and
// would pass while the retry still happened in the container. Ruling #98(b) —
// "a stub is a statement of what its author believes" — applies to a predicate
// restated from memory just as much as to a mock.
// ============================================================================

/** bullmq's real retry predicate, transcribed from the installed package. */
function bullmqWouldStopRetrying(err: unknown): boolean {
  return (
    err instanceof UnrecoverableError ||
    (err as Error)?.name === 'UnrecoverableError'
  );
}

describe('asUnrecoverable', () => {
  it('produces an error bullmq will NOT retry', () => {
    expect(bullmqWouldStopRetrying(asUnrecoverable(new Error('boom')))).toBe(
      true
    );
  });

  // ⚠️ BOTH ARMS ASSERTED SEPARATELY, BECAUSE THE DISJUNCTION HIDES A HALF
  // FAILURE. If only `instanceof` held, this would still pass the test above
  // and still fail in the standalone bundle, where a second copy of the class
  // makes `instanceof` false with no error anywhere.
  it('satisfies the `instanceof` arm', () => {
    expect(asUnrecoverable(new Error('boom'))).toBeInstanceOf(
      UnrecoverableError
    );
  });

  it('satisfies the `name` arm independently of `instanceof`', () => {
    expect(asUnrecoverable(new Error('boom')).name).toBe('UnrecoverableError');
  });

  // ⚠️ THE NEGATIVE CONTROL. Without it, a `bullmqWouldStopRetrying` that
  // returned `true` for everything would pass every assertion above — the
  // emptiness-test failure from AGENTS.md, pointed at a predicate.
  it('a plain Error is NOT recognised — the predicate discriminates', () => {
    expect(bullmqWouldStopRetrying(new Error('boom'))).toBe(false);
    expect(bullmqWouldStopRetrying(new TypeError('boom'))).toBe(false);
  });

  // ⚠️ THE TRAP THIS MODULE EXISTS TO AVOID, ASSERTED SO IT CANNOT BE
  // REINTRODUCED BY SOMEBODY TIDYING. `UnrecoverableError`'s constructor is
  // `this.name = this.constructor.name`, so the natural "make it a subclass"
  // refactor silently drops the string arm and leaves only the arm the dual
  // package copy defeats.
  it('a naive subclass would lose the `name` arm — which is why we do not subclass', () => {
    class PermanentFailureError extends UnrecoverableError {}
    const naive = new PermanentFailureError('boom');
    expect(naive.name).toBe('PermanentFailureError');
    expect(naive.name === 'UnrecoverableError').toBe(false);
  });

  it('carries the original message so the DLQ entry stays diagnostic', () => {
    expect(asUnrecoverable(new Error('L4 returned non-JSON')).message).toBe(
      'L4 returned non-JSON'
    );
  });

  it('carries the original stack, not this module’s', () => {
    const original = new Error('boom');
    expect(asUnrecoverable(original).stack).toBe(original.stack);
  });

  it('keeps the original reachable as `cause`', () => {
    const original = new Error('boom');
    expect(
      (asUnrecoverable(original) as Error & { cause?: unknown }).cause
    ).toBe(original);
  });

  // Non-Error throws are legal in JS and the worker's catch is untyped.
  it('survives a non-Error throw without losing the value', () => {
    const marker = asUnrecoverable('a bare string');
    expect(marker.message).toBe('a bare string');
    expect(bullmqWouldStopRetrying(marker)).toBe(true);
  });

  it('survives null / undefined', () => {
    expect(asUnrecoverable(null).message).toBe('');
    expect(asUnrecoverable(undefined).message).toBe('');
    expect(bullmqWouldStopRetrying(asUnrecoverable(null))).toBe(true);
  });
});

// ============================================================================
// `isUnrecoverableMarker` — the recognition the DLQ path needs
// ----------------------------------------------------------------------------
// ⚠️ IT IS VALIDATED AGAINST THE TRANSCRIBED ORACLE, NOT ASSERTED ALONE. If this
// suite only checked `isUnrecoverableMarker` against cases I chose, it would be
// a matcher agreeing with its author. Every case below is asserted to AGREE with
// `bullmqWouldStopRetrying`, which was copied from bullmq's source — so the
// helper is pinned to what bullmq actually does, and a future edit that drifts
// from bullmq's disjunction reddens here rather than silently changing which
// jobs an operator can see.
// ============================================================================
describe('isUnrecoverableMarker', () => {
  const cases: Array<[string, unknown]> = [
    ['the marker this module builds', asUnrecoverable(new Error('boom'))],
    ['a bare UnrecoverableError', new UnrecoverableError('boom')],
    ['a plain Error', new Error('boom')],
    ['a TypeError', new TypeError('boom')],
    ['null', null],
    ['undefined', undefined],
    ['a string', 'not an error at all'],
    ['an object wearing the name', { name: 'UnrecoverableError' }],
  ];

  it.each(cases)('agrees with bullmq’s own predicate on %s', (_label, value) => {
    expect(isUnrecoverableMarker(value)).toBe(bullmqWouldStopRetrying(value));
  });

  // The two that matter for the DLQ, stated plainly so the intent survives a
  // refactor of the table above.
  it('recognises a discarded job', () => {
    expect(isUnrecoverableMarker(asUnrecoverable(new Error('boom')))).toBe(true);
  });

  it('does NOT recognise an ordinary failure — the DLQ must not change for those', () => {
    expect(isUnrecoverableMarker(new Error('boom'))).toBe(false);
  });

  it('does not throw on null, undefined or a non-object', () => {
    expect(isUnrecoverableMarker(null)).toBe(false);
    expect(isUnrecoverableMarker(undefined)).toBe(false);
    expect(isUnrecoverableMarker('boom')).toBe(false);
  });
});
