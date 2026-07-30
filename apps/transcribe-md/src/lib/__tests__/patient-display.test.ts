// ============================================================================
// The two display derivations Rounds Screen 2 shares with the existing surfaces.
// ----------------------------------------------------------------------------
// They were module-private copies in DemographicsCard and visit-ready-view and
// had no tests at all. Moving them out is only an improvement if the behaviour
// they already had is pinned first — including the edge cases the originals
// handled deliberately, which is why `null` (not 0) for a bad DOB is asserted.
// ============================================================================

import { afterEach, describe, expect, it, vi } from 'vitest';

import { ageYearsOf, formatDurationLabel } from '../patient-display';

afterEach(() => {
  vi.useRealTimers();
});

/** Freeze the clock so an age assertion is not a slow-burning flake. */
function at(iso: string) {
  vi.useFakeTimers();
  vi.setSystemTime(new Date(iso));
}

describe('ageYearsOf', () => {
  it('floors to whole years', () => {
    at('2026-07-30T12:00:00Z');
    expect(ageYearsOf('1990-07-29')).toBe(36);
  });

  it('has not had this year’s birthday yet', () => {
    at('2026-07-30T12:00:00Z');
    expect(ageYearsOf('1990-12-31')).toBe(35);
  });

  it('accepts a Date as well as a string', () => {
    at('2026-07-30T12:00:00Z');
    expect(ageYearsOf(new Date('1990-07-29'))).toBe(36);
  });

  it('returns null — not 0 — for an absent DOB', () => {
    // 0 reads as a newborn on a clinical header. Nothing is the honest render.
    expect(ageYearsOf(null)).toBeNull();
    expect(ageYearsOf(undefined)).toBeNull();
    expect(ageYearsOf('')).toBeNull();
  });

  it('returns null for an unparseable or future DOB', () => {
    at('2026-07-30T12:00:00Z');
    expect(ageYearsOf('not-a-date')).toBeNull();
    expect(ageYearsOf('2030-01-01')).toBeNull();
  });
});

describe('formatDurationLabel', () => {
  it('zero-pads the seconds', () => {
    expect(formatDurationLabel(363)).toBe('6m 03s');
  });

  it('renders whole minutes and sub-minute durations', () => {
    expect(formatDurationLabel(0)).toBe('0m 00s');
    expect(formatDurationLabel(59)).toBe('0m 59s');
    expect(formatDurationLabel(600)).toBe('10m 00s');
  });

  it('clamps negatives and truncates fractions rather than rendering junk', () => {
    expect(formatDurationLabel(-5)).toBe('0m 00s');
    expect(formatDurationLabel(90.9)).toBe('1m 30s');
  });
});
