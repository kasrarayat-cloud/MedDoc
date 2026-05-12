// ============================================================================
// Bariatric Surgery Rx safety table — the L7c-rx-drafting / Rx-warning
// rail leans on DOSE_RANGES for adult-max + contraindication matching.
// The bariatric cohort introduces a unique class of Rx safety: the
// regimen is mostly vitamin / mineral supplementation (no FDA-published
// mg/day cap) and one HARD SAFETY BULLET — calcium carbonate is
// non-absorbed in post-RYGB / post-BPD-DS patients because the acidic
// gastric environment that dissolves it is absent. Citrate must be
// substituted; the validator treats this as a contraindication match.
// ============================================================================

import { describe, expect, it } from 'vitest';

import { getDoseRange } from '../data/dose-ranges';

describe('Bariatric Surgery dose-range entries', () => {
  it.each([
    'cholecalciferol',
    'cyanocobalamin',
    'calcium citrate',
    'calcium carbonate',
    'ferrous sulfate',
    'thiamine',
    'ursodiol',
    'pantoprazole',
    'bariatric multivitamin',
  ])('%s is in the catalog', (drug) => {
    expect(getDoseRange(drug)).toBeTruthy();
  });

  it('vitamin supplements are flagged complexDosing (no static mg/day cap)', () => {
    for (const d of [
      'cholecalciferol',
      'cyanocobalamin',
      'calcium citrate',
      'thiamine',
      'bariatric multivitamin',
    ]) {
      const entry = getDoseRange(d);
      expect(entry?.complexDosing, d).toBe(true);
      expect(entry?.adultMaxMgPerDay, d).toBeUndefined();
    }
  });

  it('calcium carbonate carries the post-bypass HARD SAFETY contraindication', () => {
    const entry = getDoseRange('calcium carbonate');
    expect(entry?.drug).toBe('calcium carbonate');
    const c = entry?.contraindications ?? [];
    expect(c.some((x) => /post-roux-en-y gastric bypass/i.test(x))).toBe(true);
    expect(c.some((x) => /post-duodenal switch|post-bpd-ds/i.test(x))).toBe(true);
    expect(entry?.notes).toMatch(/HARD SAFETY|non[-\s]?absorbed|citrate/i);
  });

  it('cholecalciferol brand aliases resolve', () => {
    expect(getDoseRange('vitamin d3')?.drug).toBe('cholecalciferol');
    expect(getDoseRange('vitamin d')?.drug).toBe('cholecalciferol');
    expect(getDoseRange('d3')?.drug).toBe('cholecalciferol');
  });

  it('cyanocobalamin aliases resolve (B12 sublingual / IM variants)', () => {
    expect(getDoseRange('vitamin b12')?.drug).toBe('cyanocobalamin');
    expect(getDoseRange('b12')?.drug).toBe('cyanocobalamin');
    expect(getDoseRange('methylcobalamin')?.drug).toBe('cyanocobalamin');
    expect(getDoseRange('hydroxocobalamin')?.drug).toBe('cyanocobalamin');
  });

  it('calcium citrate aliases resolve (Citracal)', () => {
    expect(getDoseRange('citracal')?.drug).toBe('calcium citrate');
  });

  it('ferrous sulfate has the 325 mg/day adult max + iron-overload contraindication', () => {
    const entry = getDoseRange('ferrous sulfate');
    expect(entry?.adultMaxMgPerDay).toBe(325);
    expect(
      entry?.contraindications?.some((x) => /iron overload|hemochromatosis/i.test(x)),
    ).toBe(true);
  });

  it('ursodiol caps at 600 mg/day for post-bariatric gallstone prophylaxis', () => {
    const entry = getDoseRange('ursodiol');
    expect(entry?.adultMaxMgPerDay).toBe(600);
    expect(getDoseRange('actigall')?.drug).toBe('ursodiol');
    expect(entry?.notes).toMatch(/300 mg PO BID|gallstone PROPHYLAXIS/i);
  });

  it('pantoprazole caps at 80 mg/day with PPI-allergy contraindication', () => {
    const entry = getDoseRange('pantoprazole');
    expect(entry?.adultMaxMgPerDay).toBe(80);
    expect(getDoseRange('protonix')?.drug).toBe('pantoprazole');
    expect(
      entry?.contraindications?.some((x) => /ppi allergy/i.test(x)),
    ).toBe(true);
  });

  it('bariatric multivitamin aliases resolve to one entry', () => {
    expect(getDoseRange('bariatric advantage')?.drug).toBe('bariatric multivitamin');
    expect(getDoseRange('celebrate vitamins')?.drug).toBe('bariatric multivitamin');
    expect(getDoseRange('bariatric fusion')?.drug).toBe('bariatric multivitamin');
    expect(getDoseRange('optisource')?.drug).toBe('bariatric multivitamin');
  });

  it('every bariatric entry carries operator notes (visibility on Rx rail)', () => {
    for (const d of [
      'cholecalciferol',
      'cyanocobalamin',
      'calcium citrate',
      'calcium carbonate',
      'ferrous sulfate',
      'thiamine',
      'ursodiol',
      'pantoprazole',
      'bariatric multivitamin',
    ]) {
      expect(getDoseRange(d)?.notes, `${d} notes`).toBeTruthy();
    }
  });

  it('pre-existing entries still resolve (smoke check after batch insert)', () => {
    // Sanity that the bariatric batch didn't drop earlier entries.
    expect(getDoseRange('lisinopril')).toBeTruthy();
    expect(getDoseRange('semaglutide')).toBeTruthy();
    expect(getDoseRange('phentermine')).toBeTruthy();
  });
});
