// ============================================================================
// specialty-keys.ts — normalization round-trip (PR-1: Issues #202 + #206)
// ============================================================================

import { describe, expect, it } from 'vitest';
import {
  normalizeSpecialty,
  SPECIALTY_KEYS,
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
    const allKeys = new Set<string>(SPECIALTY_KEYS);
    const examples = [
      'orthopedics', 'Orthopedics', 'bariatric-surgery', 'primary-care',
      'cardiology', 'ob-gyn', 'urgent-care', 'pain-management',
      'pediatrics', 'vascular-surgery', 'dermatology', 'weight-management',
      'endocrinology', 'functional-medicine', 'psychiatry', 'unknown-foo',
    ];
    for (const ex of examples) {
      expect(allKeys.has(normalizeSpecialty(ex))).toBe(true);
    }
  });
});
