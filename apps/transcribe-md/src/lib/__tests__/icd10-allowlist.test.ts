// ============================================================================
// Round 3 PR-D — ICD-10 allowlist validator tests (audit A06-P0-002)
// ============================================================================

import { describe, expect, it } from 'vitest';

import { isValidIcd10, ICD10_ALLOWLIST_SIZE } from '@meddoc/ai';

describe('isValidIcd10', () => {
  it('accepts a real common ICD-10 code from the starter set', () => {
    expect(isValidIcd10('I10')).toBe(true); // Essential hypertension
    expect(isValidIcd10('E11.9')).toBe(true); // T2DM without complications
    expect(isValidIcd10('Z00.00')).toBe(true); // Adult exam, no abnormal findings
  });

  it('rejects fabricated codes that match the regex shape', () => {
    // The audit's smoking-gun adversarial input — Z99.999 is regex-valid
    // (ICD-10-CM allows up to 7 chars after the period) but does not exist.
    expect(isValidIcd10('Z99.999')).toBe(false);
    // Numeric "99999" — looks like a 5-digit code but ICD-10 starts with letter.
    expect(isValidIcd10('99999')).toBe(false);
    // Plausible-shape but not a real code.
    expect(isValidIcd10('Q9X.XX')).toBe(false);
  });

  it('normalizes case + whitespace', () => {
    expect(isValidIcd10('i10')).toBe(true);
    expect(isValidIcd10(' I10 ')).toBe(true);
    expect(isValidIcd10('I10\n')).toBe(true);
  });

  it('rejects empty / null / undefined', () => {
    expect(isValidIcd10('')).toBe(false);
    expect(isValidIcd10(null)).toBe(false);
    expect(isValidIcd10(undefined)).toBe(false);
    expect(isValidIcd10('   ')).toBe(false);
  });

  it('starter set has at least 80 codes (regression guard against accidental shrink)', () => {
    expect(ICD10_ALLOWLIST_SIZE).toBeGreaterThanOrEqual(80);
  });
});
