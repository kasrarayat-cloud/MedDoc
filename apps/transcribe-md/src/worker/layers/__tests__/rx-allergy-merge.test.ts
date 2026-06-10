// ============================================================================
// Q1 #02.8 — allergy conflict resolution: caution-first Rx safety merge.
// ----------------------------------------------------------------------------
// The deterministic Rx contraindication check must run against the UNION of
// the patient-chart allergies AND every allergy stated in THIS visit
// (from the L3 entities), INCLUDING entries flagged `superseded`. A
// conflicting / retracted in-visit allergy still warns until the doctor
// resolves it — the extraction layer never drops an allergy from a safety
// check. These tests pin that invariant end-to-end through the REAL
// validateRxDose.
// ============================================================================

import { describe, it, expect, vi } from 'vitest';

// Importing 07c pulls @/lib/audit (→ next-auth) + @meddoc/db transitively;
// stub them so the module loads in the test env. @meddoc/ai stays REAL — we
// exercise the actual validateRxDose contraindication check.
vi.mock('@/lib/audit', () => ({ logAudit: vi.fn() }));
vi.mock('@meddoc/db', () => ({ default: {} }));

import { validateRxDose } from '@meddoc/ai';
import { mergeAllergiesForSafety } from '../07c-rx-drafting';

const entities = (allergies: unknown[]) => JSON.stringify({ allergies });

describe('mergeAllergiesForSafety (Q1 #02.8)', () => {
  it('returns the chart allergies when there are no in-visit allergies', () => {
    expect(mergeAllergiesForSafety(['penicillin'], entities([]))).toEqual([
      'penicillin',
    ]);
  });

  it('merges in-visit allergy substances with the chart (case-insensitive dedupe)', () => {
    const res = mergeAllergiesForSafety(
      ['Penicillin'],
      entities([{ substance: 'penicillin' }, { substance: 'Sulfa' }])
    );
    expect(res).toHaveLength(2); // penicillin deduped, sulfa added
    expect(res.map((s) => s.toLowerCase())).toEqual(
      expect.arrayContaining(['penicillin', 'sulfa'])
    );
  });

  it('SAFETY: a superseded / retracted in-visit allergy is STILL included (never filtered)', () => {
    const res = mergeAllergiesForSafety(
      [],
      entities([
        {
          substance: 'penicillin allergy',
          superseded: true,
          conflict_note: 'patient first denied allergies, then reported penicillin',
        },
      ])
    );
    expect(res.map((s) => s.toLowerCase())).toContain('penicillin allergy');
  });

  it('degrades to the chart allergies on malformed entitiesJson (never throws)', () => {
    expect(mergeAllergiesForSafety(['aspirin'], 'not json {{')).toEqual([
      'aspirin',
    ]);
  });

  it('handles null/empty chart with only in-visit allergies', () => {
    expect(
      mergeAllergiesForSafety(null, entities([{ substance: 'latex' }]))
    ).toEqual(['latex']);
  });
});

describe('Rx-layer handling: superseded allergy still fires a contraindication (Q1 #02.8)', () => {
  it('a SUPERSEDED in-visit penicillin allergy still triggers RX_CONTRAINDICATION_MATCH on amoxicillin', () => {
    // The retracted allergy flows through the caution-first merge into the
    // real validateRxDose contraindication check — exactly the "fail toward
    // caution" semantics: the warning fires until the DOCTOR resolves it.
    const allergies = mergeAllergiesForSafety(
      [],
      entities([{ substance: 'penicillin allergy', superseded: true }])
    );
    const result = validateRxDose({
      drug: 'amoxicillin',
      doseMgPerDay: 1500,
      patient: {
        dateOfBirth: '1980-01-01',
        weightKg: 80,
        allergies,
      },
    });
    expect(
      result.warnings.some((w) => w.code === 'RX_CONTRAINDICATION_MATCH')
    ).toBe(true);
  });

  it('control: with NO allergy, the same Rx produces no contraindication match', () => {
    const result = validateRxDose({
      drug: 'amoxicillin',
      doseMgPerDay: 1500,
      patient: { dateOfBirth: '1980-01-01', weightKg: 80, allergies: [] },
    });
    expect(
      result.warnings.some((w) => w.code === 'RX_CONTRAINDICATION_MATCH')
    ).toBe(false);
  });

  it('documents the validateRxDose match boundary (N-2): a BARE "penicillin" substance does NOT match the "penicillin allergy" needle', () => {
    // validateRxDose matches `patientAllergy.includes(contraindication)`
    // (dose-ranges-validator.ts) and amoxicillin's needle is the literal
    // "penicillin allergy". A bare-substance allergy ("penicillin") therefore
    // does NOT fire — a PRE-EXISTING property of the matcher, unchanged by the
    // merge. mergeAllergiesForSafety faithfully passes the substring through;
    // it correctly INCLUDES the superseded substance regardless of whether the
    // downstream matcher fires. (Normalizing bare substances → "<x> allergy"
    // is a separate follow-up, out of this batch's scope.)
    const allergies = mergeAllergiesForSafety(
      [],
      entities([{ substance: 'penicillin', superseded: true }])
    );
    expect(allergies).toContain('penicillin'); // merge included it (the invariant)
    const result = validateRxDose({
      drug: 'amoxicillin',
      doseMgPerDay: 1500,
      patient: { dateOfBirth: '1980-01-01', weightKg: 80, allergies },
    });
    // No match — documents the matcher boundary, not a merge defect.
    expect(
      result.warnings.some((w) => w.code === 'RX_CONTRAINDICATION_MATCH')
    ).toBe(false);
  });
});
