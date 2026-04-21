import { describe, it, expect } from 'vitest';

import { shouldMarkVisitFailed } from './retry-decision';

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
