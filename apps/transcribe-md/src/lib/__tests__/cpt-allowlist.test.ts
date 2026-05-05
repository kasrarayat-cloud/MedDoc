// ============================================================================
// Round 3 PR-D — CPT allowlist validator tests (audit A06-P0-002)
// ============================================================================

import { describe, expect, it } from 'vitest';

import { isValidCpt, CPT_ALLOWLIST_SIZE } from '@meddoc/ai';

describe('isValidCpt', () => {
  it('accepts common E&M codes', () => {
    expect(isValidCpt('99213')).toBe(true); // Established pt, low-mod, 15min
    expect(isValidCpt('99214')).toBe(true); // Est pt, mod, 25min
    expect(isValidCpt('99204')).toBe(true); // New pt, mod, 45min
    expect(isValidCpt('99291')).toBe(true); // Critical care first 30-74 min
  });

  it('rejects fabricated codes', () => {
    expect(isValidCpt('99999')).toBe(false); // Plausible shape, not a real code
    expect(isValidCpt('00000')).toBe(false);
    expect(isValidCpt('12345')).toBe(false);
  });

  it('accepts codes with valid AMA modifiers', () => {
    expect(isValidCpt('99213-25')).toBe(true); // -25 = significant separately ID E&M
    expect(isValidCpt('99214-95')).toBe(true); // -95 = telemedicine
    expect(isValidCpt('20610-50')).toBe(true); // -50 = bilateral
  });

  it('rejects codes with invalid modifiers', () => {
    expect(isValidCpt('99213-99')).toBe(false); // -99 not a real modifier
    expect(isValidCpt('99213-XZ')).toBe(false);
    expect(isValidCpt('99213-')).toBe(false); // trailing dash
  });

  it('rejects codes whose base is invalid even with valid modifier', () => {
    expect(isValidCpt('99999-25')).toBe(false);
    expect(isValidCpt('00000-95')).toBe(false);
  });

  it('rejects empty / null / undefined', () => {
    expect(isValidCpt('')).toBe(false);
    expect(isValidCpt(null)).toBe(false);
    expect(isValidCpt(undefined)).toBe(false);
  });

  it('starter set has at least 50 codes', () => {
    expect(CPT_ALLOWLIST_SIZE).toBeGreaterThanOrEqual(50);
  });
});
