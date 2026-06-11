// Coverage for the shared SPECIALTIES catalog (P2-002 fix).
// Pinning the id list as a snapshot makes adding/removing/renaming a
// specialty a deliberate test-update rather than a silent vocab drift.
// The Zod + guidance checks catch the two ways drift could break the
// pipeline: API edge rejecting valid ids, or a doctor's selection
// landing on a generic SOAP prompt because no guidance entry was
// added alongside the catalog row.

import { describe, expect, it } from 'vitest';
import { z } from 'zod';

import {
  SPECIALTIES,
  SPECIALTY_IDS,
  SPECIALTIES_FOR_VISIT_CREATE,
  findSpecialty,
} from '@meddoc/shared/specialties';
import { SPECIALTY_GUIDANCE } from '@/worker/prompts/specialty-guidance';

describe('SPECIALTIES catalog', () => {
  it('exposes a stable id list (snapshot)', () => {
    // Adding/removing a specialty here is intentional — update this
    // snapshot AND the marketing H2 copy ("Eight specialty templates")
    // in apps/marketing/src/components/home/Specialties.tsx if the
    // count outside 'unspecified' changes.
    expect(SPECIALTY_IDS).toEqual([
      'unspecified',
      'primary-care',
      'cardiology',
      'psychiatry',
      'pediatrics',
      'ob-gyn',
      'dermatology',
      'orthopedics',
      'urgent-care',
      'pain-management',
      'weight-management',
      'bariatric-surgery',
      'vascular-surgery',
    ]);
  });

  it('has unique ids and labels', () => {
    const ids = SPECIALTIES.map((s) => s.id);
    const labels = SPECIALTIES.map((s) => s.label);
    expect(new Set(ids).size).toBe(ids.length);
    expect(new Set(labels).size).toBe(labels.length);
  });

  it('SPECIALTIES_FOR_VISIT_CREATE excludes Unspecified', () => {
    const ids = SPECIALTIES_FOR_VISIT_CREATE.map((s) => s.id);
    expect(ids).not.toContain('unspecified');
    expect(ids).toHaveLength(SPECIALTIES.length - 1);
  });
});

describe('SPECIALTY_GUIDANCE coverage', () => {
  // Every catalog templateId should map to a guidance entry OR the
  // explicit 'generic' fallback. Without guidance the SOAP prompt
  // falls back to generic — fine for 'unspecified', a soft
  // regression for clinical specialties.
  for (const spec of SPECIALTIES) {
    const expectsGuidance = spec.templateId !== 'generic';
    if (!expectsGuidance) continue;
    it(`has SOAP guidance text for ${spec.id} (templateId=${spec.templateId})`, () => {
      expect(Object.keys(SPECIALTY_GUIDANCE)).toContain(spec.templateId);
      expect(SPECIALTY_GUIDANCE[spec.templateId]).toMatch(/\S/);
    });
  }
});

describe('z.enum(SPECIALTY_IDS)', () => {
  const Schema = z.enum(SPECIALTY_IDS);

  it('accepts every catalog id', () => {
    for (const id of SPECIALTY_IDS) {
      expect(() => Schema.parse(id)).not.toThrow();
    }
  });

  it('rejects unknown ids', () => {
    expect(() => Schema.parse('cardio')).toThrow();
    expect(() => Schema.parse('Cardiology')).toThrow();
    expect(() => Schema.parse('')).toThrow();
    expect(() => Schema.parse('internal-medicine')).toThrow();
  });
});

describe('findSpecialty (legacy fallback)', () => {
  it('returns the canonical entry for a current id', () => {
    expect(findSpecialty('cardiology').label).toBe('Cardiology');
    expect(findSpecialty('pain-management').label).toBe('Pain Management');
  });

  it('maps legacy display-name DB rows to the new catalog', () => {
    expect(findSpecialty('Cardiology').id).toBe('cardiology');
    expect(findSpecialty('Orthopedics').id).toBe('orthopedics');
    expect(findSpecialty('Primary Care / Family Medicine').id).toBe('primary-care');
    expect(findSpecialty('Internal Medicine').id).toBe('primary-care');
  });

  it('maps legacy short-id user.specialty rows to the new catalog', () => {
    expect(findSpecialty('pain').id).toBe('pain-management');
    expect(findSpecialty('ortho').id).toBe('orthopedics');
    expect(findSpecialty('primary').id).toBe('primary-care');
  });

  it('returns Unspecified for null / empty / unknown', () => {
    expect(findSpecialty(null).id).toBe('unspecified');
    expect(findSpecialty(undefined).id).toBe('unspecified');
    expect(findSpecialty('').id).toBe('unspecified');
    expect(findSpecialty('telepathy').id).toBe('unspecified');
  });
});
