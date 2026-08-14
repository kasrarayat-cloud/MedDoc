// ============================================================================
// Catalog invariants — the shared specialties module drives Zod input
// validation, marketing pill list, dropdown labels, and the SOAP-prompt
// guidance map. The pairs here are load-bearing: a regression that
// drops a row, duplicates an id, or breaks the legacy-id fallback would
// flip every visit using that specialty to "Unspecified".
// ============================================================================

import { describe, expect, it } from 'vitest';

import {
  SPECIALTIES,
  SPECIALTY_IDS,
  SPECIALTIES_FOR_VISIT_CREATE,
  findSpecialty,
} from './specialties';

describe('SPECIALTIES catalog', () => {
  it('contains the canonical pilot specialties', () => {
    const ids = SPECIALTIES.map((s) => s.id);
    expect(ids).toEqual(
      expect.arrayContaining([
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
      ]),
    );
  });

  it('ids are unique', () => {
    const ids = SPECIALTIES.map((s) => s.id);
    expect(new Set(ids).size).toBe(ids.length);
  });

  it('every clinical specialty has templateId === id (unspecified routes to generic)', () => {
    // Drift check — the SOAP guidance prompt looks up templateId; if it
    // diverges from id the lookup misses + the generic prompt runs.
    // The `unspecified` sentinel intentionally routes to `generic` so
    // its templateId differs; every clinical row must match.
    for (const s of SPECIALTIES) {
      if (s.id === 'unspecified') {
        expect(s.templateId).toBe('generic');
        continue;
      }
      expect(s.templateId, `${s.id} templateId`).toBe(s.id);
    }
  });

  it('SPECIALTY_IDS mirrors the catalog id list (for z.enum)', () => {
    expect(SPECIALTY_IDS).toEqual(SPECIALTIES.map((s) => s.id));
  });

  it('weight-management is exposed to the visit-create dropdown', () => {
    expect(
      SPECIALTIES_FOR_VISIT_CREATE.find((s) => s.id === 'weight-management'),
    ).toBeTruthy();
  });

  it('weight-management has the expected display label', () => {
    expect(findSpecialty('weight-management').label).toBe('Weight Management');
  });

  it('bariatric-surgery is in the catalog (distinct from weight-management)', () => {
    expect(
      SPECIALTIES.find((s) => s.id === 'bariatric-surgery'),
    ).toBeTruthy();
  });

  it('bariatric-surgery is exposed to the visit-create dropdown', () => {
    expect(
      SPECIALTIES_FOR_VISIT_CREATE.find((s) => s.id === 'bariatric-surgery'),
    ).toBeTruthy();
  });

  it('bariatric-surgery has the expected display label', () => {
    expect(findSpecialty('bariatric-surgery').label).toBe('Bariatric Surgery');
  });

  it('vascular-surgery is in the catalog (distinct from bariatric-surgery)', () => {
    expect(
      SPECIALTIES.find((s) => s.id === 'vascular-surgery'),
    ).toBeTruthy();
  });

  it('vascular-surgery is exposed to the visit-create dropdown', () => {
    expect(
      SPECIALTIES_FOR_VISIT_CREATE.find((s) => s.id === 'vascular-surgery'),
    ).toBeTruthy();
  });

  it('vascular-surgery has the expected display label', () => {
    expect(findSpecialty('vascular-surgery').label).toBe('Vascular Surgery');
  });

  it('catalog row count is 15 (1 unspecified + 14 clinical incl. flag-gated ultrasound)', () => {
    // Guard so catalog growth is a deliberate test-update. NOTE: marketing now
    // derives its count from visibleSpecialties({forVisitCreate:true}) (flag-
    // aware), so Ultrasound is in the raw catalog (14/13) but is NOT shown
    // publicly until NEXT_PUBLIC_ULTRASOUND_SPECIALTY is on.
    expect(SPECIALTIES).toHaveLength(15);
    expect(SPECIALTIES_FOR_VISIT_CREATE).toHaveLength(14);
  });
});

describe('findSpecialty', () => {
  it('returns the row for a canonical id', () => {
    expect(findSpecialty('cardiology').label).toBe('Cardiology');
  });

  it('falls back to Unspecified for unknown ids', () => {
    expect(findSpecialty('martian-medicine').id).toBe('unspecified');
  });

  it('resolves a legacy display name to its canonical id', () => {
    expect(findSpecialty('Primary Care / Family Medicine').id).toBe(
      'primary-care',
    );
  });
});
