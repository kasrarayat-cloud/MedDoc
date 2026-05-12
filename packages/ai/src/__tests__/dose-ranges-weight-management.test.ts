// ============================================================================
// Weight-management Rx safety table — the L7c-rx-drafting / Rx-warning
// rail leans on DOSE_RANGES for adult-max + contraindication matching.
// The weight-management cohort introduces drug classes (GLP-1 / GIP
// agonists, combination obesity tablets, MC4R agonists) whose dosing
// is intrinsically titrated, so we lean on `complexDosing: true` for
// the GLP-1s and a concrete adult max for the structured combos.
//
// These tests guard the load-bearing properties of each entry — the
// boxed warnings + class-match contraindications drive what shows up
// in the Rx safety rail when a doctor opens a weight-management visit.
// ============================================================================

import { describe, expect, it } from 'vitest';

import { DOSE_RANGES, getDoseRange } from '../data/dose-ranges';

describe('Weight-management dose-range entries', () => {
  it.each([
    'liraglutide',
    'semaglutide',
    'tirzepatide',
    'phentermine',
    'phentermine-topiramate',
    'naltrexone-bupropion',
    'orlistat',
    'setmelanotide',
  ])('%s is in the catalog', (drug) => {
    expect(getDoseRange(drug)).toBeTruthy();
  });

  it('GLP-1 / GIP agonists are flagged complexDosing', () => {
    for (const d of ['liraglutide', 'semaglutide', 'tirzepatide']) {
      const entry = getDoseRange(d);
      expect(entry?.complexDosing, d).toBe(true);
      // Validator should NOT emit a static mg/day cap for titrated agents.
      expect(entry?.adultMaxMgPerDay, d).toBeUndefined();
    }
  });

  it('GLP-1 agonists carry medullary thyroid / MEN-2 contraindications', () => {
    for (const d of ['liraglutide', 'semaglutide', 'tirzepatide']) {
      const c = getDoseRange(d)?.contraindications ?? [];
      expect(
        c.some((x) => /medullary thyroid carcinoma/i.test(x)),
        `${d} medullary`,
      ).toBe(true);
      expect(c.some((x) => /men-2/i.test(x)), `${d} men-2`).toBe(true);
      expect(c.some((x) => /pregnancy/i.test(x)), `${d} pregnancy`).toBe(true);
    }
  });

  it('phentermine carries cardiovascular + sympathomimetic contraindications', () => {
    const c = getDoseRange('phentermine')?.contraindications ?? [];
    expect(c.some((x) => /cardiovascular disease/i.test(x))).toBe(true);
    expect(c.some((x) => /hypertension/i.test(x))).toBe(true);
    expect(c.some((x) => /hyperthyroidism/i.test(x))).toBe(true);
    expect(c.some((x) => /mao inhibitor/i.test(x))).toBe(true);
  });

  it('phentermine has the 37.5 mg/day adult max', () => {
    expect(getDoseRange('phentermine')?.adultMaxMgPerDay).toBe(37.5);
  });

  it('orlistat aliases resolve to a single entry', () => {
    expect(getDoseRange('xenical')?.drug).toBe('orlistat');
    expect(getDoseRange('alli')?.drug).toBe('orlistat');
  });

  it('brand aliases resolve for the GLP-1 family', () => {
    expect(getDoseRange('wegovy')?.drug).toBe('semaglutide');
    expect(getDoseRange('ozempic')?.drug).toBe('semaglutide');
    expect(getDoseRange('mounjaro')?.drug).toBe('tirzepatide');
    expect(getDoseRange('zepbound')?.drug).toBe('tirzepatide');
    expect(getDoseRange('saxenda')?.drug).toBe('liraglutide');
    expect(getDoseRange('victoza')?.drug).toBe('liraglutide');
  });

  it('naltrexone-bupropion (Contrave) caps at the combined 32 mg naltrexone ceiling', () => {
    const entry = getDoseRange('contrave');
    expect(entry?.drug).toBe('naltrexone-bupropion');
    expect(entry?.adultMaxMgPerDay).toBe(32);
    expect(
      entry?.contraindications?.some((x) => /seizure disorder/i.test(x)),
    ).toBe(true);
  });

  it('every weight-management entry has a notes field (operator visibility)', () => {
    for (const d of [
      'liraglutide',
      'semaglutide',
      'tirzepatide',
      'phentermine',
      'phentermine-topiramate',
      'naltrexone-bupropion',
      'orlistat',
      'setmelanotide',
    ]) {
      expect(getDoseRange(d)?.notes, `${d} notes`).toBeTruthy();
    }
  });

  it('DOSE_RANGES did not lose any pre-existing entries (smoke check)', () => {
    // Sanity guard for the alphabetical-insertion patch we landed
    // alongside the weight-management additions.
    expect(getDoseRange('amoxicillin')).toBeTruthy();
    expect(getDoseRange('lisinopril')).toBeTruthy();
    expect(getDoseRange('warfarin')).toBeTruthy();
    expect(DOSE_RANGES.length).toBeGreaterThanOrEqual(30);
  });
});
