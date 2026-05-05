// ============================================================================
// Round 3 PR-D — dose-range validator tests (audit A06-P0-004)
// ============================================================================

import { describe, expect, it } from 'vitest';

import {
  validateRxDose,
  getDoseRange,
  isInDoseRangeTable,
  DOSE_RANGE_TABLE_SIZE,
} from '@meddoc/ai';

const ADULT = {
  dateOfBirth: '1980-01-01',
  weightKg: 80,
  allergies: [] as string[],
};

const TODDLER = {
  dateOfBirth: '2023-01-01', // ~3 yo at audit time (2026)
  weightKg: 15,
  allergies: [] as string[],
};

describe('validateRxDose — adult dose ceilings', () => {
  it('flags amoxicillin 5g/day in adult (exceeds 4g cap)', () => {
    const r = validateRxDose({
      drug: 'amoxicillin',
      doseMgPerDay: 5000,
      patient: ADULT,
    });
    expect(r.validated).toBe(true);
    expect(r.warnings.some((w) => w.code === 'RX_DOSE_EXCEEDS_VERIFIED_RANGE')).toBe(true);
  });

  it('passes amoxicillin 2g/day in adult (within cap)', () => {
    const r = validateRxDose({
      drug: 'amoxicillin',
      doseMgPerDay: 2000,
      patient: ADULT,
    });
    expect(r.validated).toBe(true);
    expect(r.warnings.filter((w) => w.code === 'RX_DOSE_EXCEEDS_VERIFIED_RANGE')).toHaveLength(0);
  });

  it('flags acetaminophen 5g/day adult', () => {
    const r = validateRxDose({
      drug: 'acetaminophen',
      doseMgPerDay: 5000,
      patient: ADULT,
    });
    expect(r.warnings.some((w) => w.code === 'RX_DOSE_EXCEEDS_VERIFIED_RANGE')).toBe(true);
  });

  it('resolves brand alias (tylenol → acetaminophen)', () => {
    expect(getDoseRange('tylenol')?.drug).toBe('acetaminophen');
    expect(getDoseRange('Tylenol')?.drug).toBe('acetaminophen');
  });
});

describe('validateRxDose — peds mg/kg', () => {
  it('flags amoxicillin 100 mg/kg/day in toddler (>90 max)', () => {
    // 15 kg toddler × 100 mg/kg/day = 1500 mg/day
    const r = validateRxDose({
      drug: 'amoxicillin',
      doseMgPerDay: 1500,
      patient: TODDLER,
    });
    expect(r.warnings.some((w) => w.code === 'RX_DOSE_EXCEEDS_VERIFIED_RANGE')).toBe(true);
  });

  it('passes amoxicillin 60 mg/kg/day in toddler (within 20-90 range)', () => {
    // 15 kg × 60 mg/kg/day = 900 mg/day
    const r = validateRxDose({
      drug: 'amoxicillin',
      doseMgPerDay: 900,
      patient: TODDLER,
    });
    expect(r.warnings.filter((w) => w.code === 'RX_DOSE_EXCEEDS_VERIFIED_RANGE')).toHaveLength(0);
  });
});

describe('validateRxDose — drug not in table', () => {
  it('emits RX_DRUG_NOT_IN_VERIFIED_DATABASE for an unknown drug (fail-closed)', () => {
    const r = validateRxDose({
      drug: 'xyzpharmadrug',
      doseMgPerDay: 100,
      patient: ADULT,
    });
    expect(r.validated).toBe(false);
    expect(r.warnings).toHaveLength(1);
    expect(r.warnings[0].code).toBe('RX_DRUG_NOT_IN_VERIFIED_DATABASE');
    expect(isInDoseRangeTable('xyzpharmadrug')).toBe(false);
  });
});

describe('validateRxDose — complex dosing', () => {
  it('emits complex-dosing warning for warfarin (no numeric cap)', () => {
    const r = validateRxDose({
      drug: 'warfarin',
      doseMgPerDay: 5,
      patient: ADULT,
    });
    expect(r.validated).toBe(false);
    expect(r.warnings.some((w) => w.code === 'RX_COMPLEX_DOSING_VERIFY_INDIVIDUALLY')).toBe(true);
  });

  it('emits complex-dosing warning for levothyroxine', () => {
    const r = validateRxDose({
      drug: 'levothyroxine',
      doseMgPerDay: 0.1,
      patient: ADULT,
    });
    expect(r.warnings.some((w) => w.code === 'RX_COMPLEX_DOSING_VERIFY_INDIVIDUALLY')).toBe(true);
  });
});

describe('validateRxDose — allergy contraindication', () => {
  it('flags amoxicillin in penicillin-allergic patient', () => {
    const r = validateRxDose({
      drug: 'amoxicillin',
      doseMgPerDay: 1500,
      patient: { ...ADULT, allergies: ['penicillin allergy — anaphylaxis'] },
    });
    expect(r.warnings.some((w) => w.code === 'RX_CONTRAINDICATION_MATCH')).toBe(true);
  });

  it('does not flag amoxicillin without allergy', () => {
    const r = validateRxDose({
      drug: 'amoxicillin',
      doseMgPerDay: 1500,
      patient: ADULT,
    });
    expect(r.warnings.some((w) => w.code === 'RX_CONTRAINDICATION_MATCH')).toBe(false);
  });

  it('flags ciprofloxacin in fluoroquinolone-allergic patient', () => {
    const r = validateRxDose({
      drug: 'ciprofloxacin',
      doseMgPerDay: 1000,
      patient: { ...ADULT, allergies: ['fluoroquinolone allergy'] },
    });
    expect(r.warnings.some((w) => w.code === 'RX_CONTRAINDICATION_MATCH')).toBe(true);
  });
});

describe('dose-range table size', () => {
  it('has at least 25 curated drugs (regression guard)', () => {
    expect(DOSE_RANGE_TABLE_SIZE).toBeGreaterThanOrEqual(25);
  });
});
