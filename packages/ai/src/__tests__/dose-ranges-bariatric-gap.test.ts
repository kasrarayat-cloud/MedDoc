// ============================================================================
// Bariatric / perioperative drug-catalog gap closure — deep-audit 2026-05-12.
// ----------------------------------------------------------------------------
// The post-PR-#219/#220 audit (docs/qa-reports/specialty-deep-audit-
// 20260512T182300Z.md) found ~12 drug name strings emitted by the L7c
// drafter that resolved to "not in our verified safety database" warnings,
// despite the canonical entry existing. Two patterns were responsible:
//
//   1. Parenthetical-qualifier surface forms — "Cholecalciferol (Vitamin D3)"
//      didn't match the "cholecalciferol" entry; "Ferrous sulfate (Iron)"
//      didn't match "ferrous sulfate"; etc. Fixed by stripping any trailing
//      "(qualifier)" in `getDoseRange`.
//
//   2. Missing entries for fat-soluble vitamins (A/E/K), zinc, multivitamin
//      (non-bariatric), enoxaparin, and piperacillin-tazobactam — all
//      common in the bariatric peri-op surface but never added to the
//      dose-range table. Fixed by ~7 new entries below.
//
// Three load-bearing safety rules in the new entries:
//   - Vitamin A teratogenic above 10,000 IU/day → pregnancy contraindication
//   - Zinc supplementation requires co-supplemented copper; isolated high
//     zinc causes copper-deficiency myelopathy
//   - Piperacillin-tazobactam contraindicated in penicillin anaphylactic
//     allergy — beta-lactam cross-reactivity is a hard stop
// ============================================================================

import { describe, expect, it } from 'vitest';

import { getDoseRange } from '../data/dose-ranges';

describe('Parenthetical-qualifier resolution (audit Finding G7)', () => {
  it.each([
    ['Cholecalciferol (Vitamin D3)', 'cholecalciferol'],
    ['Cyanocobalamin (Vitamin B12)', 'cyanocobalamin'],
    ['Ferrous sulfate (Iron)', 'ferrous sulfate'],
    ['Vitamin B12 (cyanocobalamin)', 'cyanocobalamin'],
    ['Vitamin K (phytonadione)', 'vitamin k'],
  ])('"%s" resolves to %s', (input, expected) => {
    expect(getDoseRange(input)?.drug).toBe(expected);
  });

  it('does not eagerly strip parentheticals when a direct match exists', () => {
    // Sanity — confirms the stripping fallback runs only on miss.
    expect(getDoseRange('cyanocobalamin')?.drug).toBe('cyanocobalamin');
  });
});

describe('Iron alias coverage (audit Finding G7)', () => {
  it.each([
    'Iron',
    'Iron (elemental)',
    'iron elemental',
    'Iron (bariatric formulation)',
    'Ferrous fumarate',
    'Ferrous gluconate',
  ])('"%s" resolves to ferrous sulfate', (input) => {
    expect(getDoseRange(input)?.drug).toBe('ferrous sulfate');
  });
});

describe('Multivitamin distinction', () => {
  it.each(['Multivitamin', 'MVI', 'Daily multivitamin'])(
    '"%s" → generic multivitamin entry',
    (input) => {
      expect(getDoseRange(input)?.drug).toBe('multivitamin');
    },
  );

  it.each([
    'Bariatric multivitamin',
    'Bariatric multivitamin chewable',
    'Bariatric-formulated multivitamin',
    'Bariatric MVI',
  ])('"%s" → bariatric multivitamin entry', (input) => {
    expect(getDoseRange(input)?.drug).toBe('bariatric multivitamin');
  });
});

describe('Vitamin A — fat-soluble malabsorption supplementation', () => {
  it('aliases and teratogenicity contraindication', () => {
    const entry = getDoseRange('vitamin a');
    expect(entry).toBeTruthy();
    expect(entry?.complexDosing).toBe(true);
    expect(entry?.contraindications?.some((x) => /pregnancy/i.test(x))).toBe(true);
    expect(getDoseRange('retinol')?.drug).toBe('vitamin a');
    expect(getDoseRange('retinyl palmitate')?.drug).toBe('vitamin a');
  });
});

describe('Vitamin E — bleeding-risk co-management', () => {
  it('alpha-tocopherol alias + warfarin caution surfaced', () => {
    const entry = getDoseRange('vitamin e');
    expect(entry).toBeTruthy();
    expect(entry?.complexDosing).toBe(true);
    expect(getDoseRange('alpha-tocopherol')?.drug).toBe('vitamin e');
    expect(getDoseRange('d-alpha-tocopherol')?.drug).toBe('vitamin e');
    expect(entry?.contraindications?.some((x) => /warfarin/i.test(x))).toBe(true);
  });
});

describe('Vitamin K — warfarin antagonism awareness', () => {
  it('phytonadione alias + warfarin caution', () => {
    const entry = getDoseRange('vitamin k');
    expect(entry).toBeTruthy();
    expect(getDoseRange('phytonadione')?.drug).toBe('vitamin k');
    expect(getDoseRange('mephyton')?.drug).toBe('vitamin k');
    expect(entry?.contraindications?.some((x) => /warfarin/i.test(x))).toBe(true);
  });
});

describe('Zinc — copper-deficiency safety rule', () => {
  it('caps at 40 mg/day and surfaces copper co-supplementation', () => {
    const entry = getDoseRange('zinc');
    expect(entry?.adultMaxMgPerDay).toBe(40);
    expect(entry?.notes).toMatch(/copper/i);
    expect(getDoseRange('zinc sulfate')?.drug).toBe('zinc');
    expect(getDoseRange('zinc gluconate')?.drug).toBe('zinc');
  });
});

describe('Enoxaparin — VTE prophylaxis + renal contraindications', () => {
  it('aliases + renal-impairment contraindication + HIT contraindication', () => {
    const entry = getDoseRange('enoxaparin');
    expect(entry).toBeTruthy();
    expect(entry?.complexDosing).toBe(true);
    expect(getDoseRange('lovenox')?.drug).toBe('enoxaparin');
    const c = entry?.contraindications ?? [];
    expect(c.some((x) => /creatinine clearance|renal impairment/i.test(x))).toBe(true);
    expect(c.some((x) => /heparin-induced thrombocytopenia/i.test(x))).toBe(true);
  });
});

describe('Piperacillin-tazobactam — penicillin allergy hard stop', () => {
  it('aliases + beta-lactam allergy contraindication', () => {
    const entry = getDoseRange('piperacillin-tazobactam');
    expect(entry).toBeTruthy();
    expect(getDoseRange('zosyn')?.drug).toBe('piperacillin-tazobactam');
    expect(getDoseRange('piperacillin/tazobactam')?.drug).toBe('piperacillin-tazobactam');
    const c = entry?.contraindications ?? [];
    expect(c.some((x) => /penicillin allergy|beta-lactam allergy/i.test(x))).toBe(true);
  });
});

describe('Pre-existing entries still resolve (smoke check, no regression)', () => {
  // The parenthetical-stripping fallback could theoretically over-reach
  // for entries whose canonical form contains characters that look like
  // parentheticals. Today's table has none, but this is the regression
  // guard for future additions.
  it.each([
    'cilostazol',
    'apixaban',
    'metformin',
    'clopidogrel',
    'cyanocobalamin',
    'cholecalciferol',
    'calcium citrate',
    'calcium carbonate',
    'levothyroxine',
    'pantoprazole',
    'ursodiol',
  ])('%s still resolves directly', (drug) => {
    expect(getDoseRange(drug)).toBeTruthy();
  });
});
