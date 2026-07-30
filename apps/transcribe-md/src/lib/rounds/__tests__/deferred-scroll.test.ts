// ============================================================================
// Close the drawer, THEN scroll — the ordering, watched.
// ----------------------------------------------------------------------------
// The failure this guards is not "the scroll is wrong". It is "the handler ran
// and nothing happened": a scroll issued while the chat drawer is still
// mounted moves the sheet behind an overlay, so the chat's "took you to the
// E/M gate" is true about the code and false about the doctor's screen.
//
// A test that only asserts the callback fired passes on exactly that bug,
// which is why the scheduler is injected and the assertions are about ORDER.
// ============================================================================

import { describe, expect, it, vi } from 'vitest';

import { createDeferredScroll } from '../deferred-scroll';

/** A scheduler that runs nothing until the test says so. */
function manualScheduler() {
  const queue: (() => void)[] = [];
  return {
    schedule: (fn: () => void) => queue.push(fn),
    runAll: () => {
      const pending = queue.splice(0);
      pending.forEach((fn) => fn());
    },
    depth: () => queue.length,
  };
}

describe('createDeferredScroll', () => {
  it('does NOT scroll while the target is merely recorded', () => {
    // The whole point. Recording must not move the page — the drawer is still
    // open at that instant.
    const scrollTo = vi.fn();
    const sched = manualScheduler();
    const d = createDeferredScroll(scrollTo, sched.schedule);

    d.record('em_gate');

    expect(scrollTo).not.toHaveBeenCalled();
    expect(d.pending()).toBe('em_gate');
  });

  it('does not scroll on flush EITHER — only when the scheduler runs', () => {
    // If flush scrolled synchronously, it would fire from `onBeforeClose`,
    // which the drawer calls BEFORE `setOpen(false)`. The overlay would still
    // be mounted. This is the assertion that distinguishes a real fix from a
    // handler that is merely wired.
    const scrollTo = vi.fn();
    const sched = manualScheduler();
    const d = createDeferredScroll(scrollTo, sched.schedule);

    d.record('rx_gate');
    d.flush();

    expect(scrollTo).not.toHaveBeenCalled();
    expect(sched.depth()).toBe(1);

    sched.runAll();
    expect(scrollTo).toHaveBeenCalledExactlyOnceWith('rx_gate');
  });

  it('flushing with nothing pending schedules nothing at all', () => {
    const scrollTo = vi.fn();
    const sched = manualScheduler();
    const d = createDeferredScroll(scrollTo, sched.schedule);

    d.flush();
    sched.runAll();

    expect(sched.depth()).toBe(0);
    expect(scrollTo).not.toHaveBeenCalled();
  });

  it('a second flush does not re-scroll — the page must not jump twice', () => {
    const scrollTo = vi.fn();
    const sched = manualScheduler();
    const d = createDeferredScroll(scrollTo, sched.schedule);

    d.record('em_gate');
    d.flush();
    d.flush();
    sched.runAll();

    expect(scrollTo).toHaveBeenCalledTimes(1);
  });

  it('clears BEFORE scheduling, so a flush during the wait cannot double up', () => {
    // The target is taken out of the ref before the frame is queued. If it
    // were cleared inside the callback instead, two flushes before the first
    // frame ran would queue the same scroll twice and the doctor would watch
    // the page settle and then jump again.
    const scrollTo = vi.fn();
    const sched = manualScheduler();
    const d = createDeferredScroll(scrollTo, sched.schedule);

    d.record('em_gate');
    d.flush();
    expect(d.pending()).toBeNull();

    d.flush();
    sched.runAll();

    expect(scrollTo).toHaveBeenCalledTimes(1);
  });

  it('the last recorded target wins', () => {
    const scrollTo = vi.fn();
    const sched = manualScheduler();
    const d = createDeferredScroll(scrollTo, sched.schedule);

    d.record('rx_gate');
    d.record('em_gate');
    d.flush();
    sched.runAll();

    expect(scrollTo).toHaveBeenCalledExactlyOnceWith('em_gate');
  });

  it('is reusable — open, ask, close, then do it again', () => {
    const scrollTo = vi.fn();
    const sched = manualScheduler();
    const d = createDeferredScroll(scrollTo, sched.schedule);

    d.record('rx_gate');
    d.flush();
    sched.runAll();

    d.record('em_gate');
    d.flush();
    sched.runAll();

    expect(scrollTo).toHaveBeenNthCalledWith(1, 'rx_gate');
    expect(scrollTo).toHaveBeenNthCalledWith(2, 'em_gate');
  });
});
