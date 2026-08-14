// ============================================================================
// specialty-keys.ts — normalization round-trip (PR-1: Issues #202 + #206)
// ============================================================================

import { describe, expect, it } from 'vitest';
import {
  normalizeSpecialty,
  SPECIALTY_KEYS,
  SPECIALTY_VARIANTS,
} from '@/lib/specialty-keys';

describe('normalizeSpecialty — canonical mapping', () => {
  it('returns unspecified for null / undefined / empty', () => {
    expect(normalizeSpecialty(null)).toBe('unspecified');
    expect(normalizeSpecialty(undefined)).toBe('unspecified');
    expect(normalizeSpecialty('')).toBe('unspecified');
    expect(normalizeSpecialty('   ')).toBe('unspecified');
  });

  it('returns unspecified for unknown values', () => {
    expect(normalizeSpecialty('not-a-real-specialty')).toBe('unspecified');
    expect(normalizeSpecialty('foo')).toBe('unspecified');
  });

  it('collapses case + separator variants of orthopedics', () => {
    expect(normalizeSpecialty('orthopedics')).toBe('orthopedics');
    expect(normalizeSpecialty('Orthopedics')).toBe('orthopedics');
    expect(normalizeSpecialty('ORTHOPEDICS')).toBe('orthopedics');
    expect(normalizeSpecialty('orthopaedics')).toBe('orthopedics');
    expect(normalizeSpecialty('ortho')).toBe('orthopedics');
    expect(normalizeSpecialty('sports-medicine')).toBe('orthopedics');
  });

  it('collapses primary-care / family-medicine / internal-medicine into one bundle', () => {
    expect(normalizeSpecialty('primary-care')).toBe('primary_care');
    expect(normalizeSpecialty('primary_care')).toBe('primary_care');
    expect(normalizeSpecialty('Primary Care / Family Medicine')).toBe('primary_care');
    expect(normalizeSpecialty('family-medicine')).toBe('primary_care');
    expect(normalizeSpecialty('internal medicine')).toBe('primary_care');
  });

  it('handles bariatric-surgery + bariatrics variants', () => {
    expect(normalizeSpecialty('bariatric-surgery')).toBe('bariatric_surgery');
    expect(normalizeSpecialty('bariatrics')).toBe('bariatric_surgery');
    expect(normalizeSpecialty('bariatric_surgery')).toBe('bariatric_surgery');
  });

  it('handles ob_gyn + obstetrics + gynecology variants', () => {
    expect(normalizeSpecialty('ob_gyn')).toBe('ob_gyn');
    expect(normalizeSpecialty('ob-gyn')).toBe('ob_gyn');
    expect(normalizeSpecialty('OB/GYN')).toBe('ob_gyn');
    expect(normalizeSpecialty('obstetrics')).toBe('ob_gyn');
    expect(normalizeSpecialty('gynecology')).toBe('ob_gyn');
  });

  it('handles functional / integrative medicine as one bundle', () => {
    expect(normalizeSpecialty('functional-medicine')).toBe('functional_medicine');
    expect(normalizeSpecialty('integrative medicine')).toBe('functional_medicine');
  });

  it('trims whitespace before lookup', () => {
    expect(normalizeSpecialty('  orthopedics  ')).toBe('orthopedics');
    expect(normalizeSpecialty('\tcardiology\n')).toBe('cardiology');
  });

  it('every variant maps to a value in SPECIALTY_KEYS', () => {
    // Defensive: catches a future variant added to the map but
    // pointing at a key not in the SPECIALTY_KEYS tuple.
    // ⚠ THIS USED TO WALK A HARDCODED 16-STRING `examples` ARRAY rather
    // than SPECIALTY_VARIANTS itself, so a variant added to the map and
    // not to the array was unchecked — the title claimed "every variant"
    // and the body checked sixteen. It now enumerates the map.
    // (2026-08-14, GI onboarding.)
    const allKeys = new Set<string>(SPECIALTY_KEYS);
    const variants = Object.keys(SPECIALTY_VARIANTS);
    expect(variants.length).toBeGreaterThan(16); // non-vacuity
    for (const v of variants) {
      expect(
        allKeys.has(normalizeSpecialty(v)),
        `variant '${v}' -> '${normalizeSpecialty(v)}' which is not in SPECIALTY_KEYS`,
      ).toBe(true);
    }
    // and the unknown case still falls through to the sentinel
    expect(normalizeSpecialty('unknown-foo')).toBe('unspecified');
  });

  it('every variant KEY is reachable — lowercase and trimmed', () => {
    // normalizeSpecialty lowercases and trims its INPUT before the lookup
    // (specialty-keys.ts), so a variant stored under a mixed-case or padded
    // key can never be hit. It is dead config that reads as coverage, and
    // the enumeration above cannot see it: normalizeSpecialty('Colon Clinic')
    // misses the map, returns 'unspecified', and 'unspecified' IS a valid
    // SpecialtyKey — so the row passes while the variant does nothing.
    expect(Object.keys(SPECIALTY_VARIANTS).length).toBeGreaterThan(16); // non-vacuity
    const unreachable = Object.keys(SPECIALTY_VARIANTS).filter(
      (k) => k !== k.trim().toLowerCase(),
    );
    expect(
      unreachable,
      `these variant keys can never match (normalizeSpecialty lowercases+trims first): ${unreachable.join(', ')}`,
    ).toEqual([]);
  });
});
