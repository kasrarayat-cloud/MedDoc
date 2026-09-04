// ============================================================================
// Gastroenterology ICD-10 cohort — the data-side guard for the GI pilot.
// ----------------------------------------------------------------------------
// `07a-icd-coding.ts` drops any code failing isValidIcd10 and emits a
// fire-and-forget CODING_COACH_REJECTED_INVALID_ICD row. A MISSING code and a
// WRONG code are therefore indistinguishable to the doctor: the correctly
// documented diagnosis simply does not appear, with nothing on screen.
//
// ⚠️ THIS COHORT IS THE HALF THAT ACTUALLY FIRED IN PRODUCTION. The first real
// GI visit (2026-08-14, 04:37:17Z, ~20 minutes after the specialty went live)
// carries CODING_COACH_REJECTED_INVALID_ICD and ZERO CPT rejections. The
// procedure-code gap was the one everybody predicted; the DIAGNOSIS gap is the
// one that drew blood.
//
// ⚠️ AND THE PRIOR COVERAGE WAS PARTIAL, WHICH IS WORSE THAN ABSENT. Three
// families had exactly one sibling present, and the screening ENCOUNTER was
// covered while the FINDING screening exists to detect was not. Those pairs
// are pinned below as pairs, deliberately — a future curation pass that drops
// one side of one of them reproduces the original defect exactly.
// ============================================================================

import { describe, expect, it } from 'vitest';

import { ICD10_ALLOWLIST, isValidIcd10 } from '../data/icd10-allowlist';

/** Measured ABSENT on 2026-08-14 before this cohort landed, positive-controlled
 *  against E11.9 and I10 (both present). Grouped by the clinical job each does. */
const GI_COHORT: Record<string, readonly string[]> = {
  'colonoscopy findings + surveillance drivers': [
    'K63.5',
    'D12.0', 'D12.1', 'D12.2', 'D12.3', 'D12.4', 'D12.5', 'D12.6', 'D12.7', 'D12.8',
    // ⚠️ WAS 'Z86.010'. It is a category HEADER, not billable — so this cohort,
    // in the same file that asserts headers must be refused, was admitting one.
    // The surveillance interval is driven by these four billable children.
    'Z86.0100', 'Z86.0101', 'Z86.0102', 'Z86.0109', 'Z80.0',
  ],
  'inflammatory bowel disease (was uncovered entirely)': ['K50.90', 'K51.90'],
  'GI bleeding + anorectal': ['K92.1', 'K92.2', 'K62.5', 'K64.0', 'K64.1', 'K64.8', 'K64.9'],
  'upper GI / EGD': [
    'K21.00', 'K21.01',
    'K22.70', 'K22.710', 'K22.711', 'K22.719',
    'K20.0', 'B96.81', 'K29.70', 'K31.89',
  ],
  // ⚠️ 'K58.3' WAS HERE AND IS NOT AN ICD-10-CM CODE. The allowlist entry it
  // mirrored was commented "Other irritable bowel syndrome" — which is **K58.8**.
  // So the phantom was admitted AND the real code was never carried: a gap that
  // read as coverage in the one file written to stop exactly that.
  'functional + half-covered families': ['K58.1', 'K58.2', 'K58.8', 'K58.9', 'K57.32', 'R19.7'],
  hepatology: ['K74.60'],
};

describe('GI ICD-10 cohort — every code is allowed', () => {
  for (const [group, codes] of Object.entries(GI_COHORT)) {
    it(`${group}: none would be dropped by 07a`, () => {
      const missing = codes.filter((c) => !ICD10_ALLOWLIST.has(c));
      expect(
        missing,
        `07a would drop these for a GI doctor: ${missing.join(', ')}`,
      ).toEqual([]);
    });
  }

  it('the cohort is non-vacuous and every code passes the REAL validator', () => {
    // Assert what we COUNTED, not only what we found: a cohort that shrank to
    // nothing would satisfy every filter above while checking nothing.
    const all = Object.values(GI_COHORT).flat();
    // 38 -> 41: Z86.010 (one header) was replaced by its FOUR billable
    // children; K58.3 -> K58.8 is one-for-one. The count is re-derived, not
    // relaxed — a floor here would let the cohort shrink silently.
    expect(all.length, 'GI cohort collapsed — the loops above check nothing').toBe(41);
    for (const c of all) {
      expect(isValidIcd10(c), `${c} rejected by isValidIcd10`).toBe(true);
      expect(isValidIcd10(c.toLowerCase()), `${c} lowercase must normalise`).toBe(true);
      expect(isValidIcd10(` ${c} `), `${c} padded must normalise`).toBe(true);
    }
  });

  it('still fails closed — an unlisted GI-shaped code is refused', () => {
    // The allowlist is a safety floor. If everything passed, the floor is gone.
    expect(isValidIcd10('K63.99'), 'a non-existent code must be refused').toBe(false);
    expect(isValidIcd10('D12.99'), 'a non-existent D12 sibling must be refused').toBe(false);
    expect(isValidIcd10(''), 'empty must be refused').toBe(false);
    expect(isValidIcd10(null), 'null must be refused').toBe(false);
  });
});

describe('NON-BILLABLE CATEGORY HEADERS ARE REFUSED — the defect this file made once', () => {
  // ⚠️ THIS ARM EXISTS BECAUSE THE FIRST DRAFT OF THIS COHORT ADMITTED TWO OF
  // THEM. 'K21.0' and 'K22.7' are subcategory HEADERS — K21.0 was expanded by
  // FY2023 into K21.00/K21.01, K22.7 by FY2017 into K22.70/K22.71x — and a
  // header cannot be submitted on a claim.
  //
  // Admitting one is the WORST failure this allowlist can have, and it is the
  // inverse of the one everybody watches for. A missing code is a silent drop;
  // an admitted non-billable header is a code that PASSES the safety floor and
  // reaches a bill. The file's own header names "false positive on validity"
  // as the thing it exists to prevent, and the first draft walked into it while
  // fixing the opposite problem.
  //
  // The tell was inside the diff: the comment written on 'K22.7' read "Barrett
  // oesophagus without dysplasia", which is the official title of K22.70 — the
  // comment described the code that was MEANT, not the code that was WRITTEN.
  const HEADERS_THAT_MUST_NOT_BE_ALLOWED: ReadonlyArray<readonly [string, string]> = [
    ['K21.0', 'expanded FY2023 into K21.00 / K21.01'],
    ['K22.7', 'expanded FY2017 into K22.70 / K22.710 / K22.711 / K22.719'],
    // ⚠️ ADDED BY T8, AND IT WAS IN THIS FILE'S OWN COHORT UNTIL NOW. This
    // block already stated the rule; the cohort above broke it. Pinning the
    // header here makes the file agree with itself.
    ['Z86.010', 'expanded into Z86.0100 / .0101 / .0102 / .0109'],
  ];

  for (const [header, why] of HEADERS_THAT_MUST_NOT_BE_ALLOWED) {
    it(`${header} is refused (${why})`, () => {
      expect(
        isValidIcd10(header),
        `${header} is a non-billable header — admitting it puts an unsubmittable code on the accepted side of the billing floor`,
      ).toBe(false);
    });
  }

  it('and the BILLABLE CHILDREN are the ones allowed — the whole point of refusing the parent', () => {
    // Refusing the header is only correct if the codes a chart maps to survive.
    // Refusing both would be a stricter floor and a worse product.
    for (const c of ['K21.00', 'K21.01', 'K22.70', 'K22.710', 'K22.711', 'K22.719']) {
      expect(isValidIcd10(c), `${c} must be allowed — it is what the header was standing in for`).toBe(true);
    }
  });
});

describe('the SPLIT FAMILIES — pinned as pairs, because one side used to be missing', () => {
  // ⚠️ Each pair below had exactly ONE member present before this cohort. That
  // is the defect this file exists to prevent recurring: a clinician
  // documenting the other half of a pair had the code silently dropped.
  // Asserting them as PAIRS is the point — asserting only the new side would
  // let a future edit remove the old side and reproduce the gap inverted.
  const PAIRS: ReadonlyArray<readonly [string, string, string]> = [
    ['K21.9', 'K21.00', 'GERD without vs WITH esophagitis'],
    ['K58.0', 'K58.1', 'IBS-D (K58.0) vs IBS-C (K58.1)'],
    ['K57.30', 'K57.32', 'diverticulosis vs diverticulitis'],
    ['Z12.11', 'K63.5', 'the screening ENCOUNTER vs the FINDING it screens for'],
  ];

  for (const [wasPresent, wasMissing, label] of PAIRS) {
    it(`${label}: BOTH sides are allowed`, () => {
      expect(isValidIcd10(wasPresent), `${wasPresent} (the side that was already there)`).toBe(true);
      expect(isValidIcd10(wasMissing), `${wasMissing} (the side that was missing)`).toBe(true);
    });
  }
});
