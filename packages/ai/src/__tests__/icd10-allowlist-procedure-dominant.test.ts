// ============================================================================
// Cross-input-mode audit Finding 3 — procedure-dominant ICD allowlist
// additions regression guards.
// ----------------------------------------------------------------------------
// PR #232's first-run audit surfaced three scenarios where the L7a layer
// emitted empty `codes: []` across all 3 input modes:
//   - OB2 (postpartum visit) → missing Z39.2 (most-concerning miss;
//     stock postpartum encounter code)
//   - DERM1 (suspicious-mole biopsy) → missing D22.x family + D48.5
//   - ORT2 (acute lateral ankle sprain) → missing S93.4xxA family
//
// Root cause for the missed codes: the codes themselves were not in the
// allowlist, so the model couldn't pick them even when contextually
// correct. This file pins the gap-closure additions so a future cleanup
// can't sweep them out without breaking tests.
//
// The L7a prompt extension (in 07a-icd-coding.ts MINIMUM CODING
// REQUIREMENT section) handles the prompt-side fix; this file is the
// data-side guard.
// ============================================================================

import { describe, expect, it } from 'vitest';

import { ICD10_ALLOWLIST, isValidIcd10 } from '../data/icd10-allowlist';

describe('OB-GYN postpartum + delivery codes', () => {
  it('Z39.2 (routine postpartum follow-up — the OB2 miss) is in the allowlist', () => {
    expect(isValidIcd10('Z39.2')).toBe(true);
  });

  it.each([
    ['Z39.0', 'care immediately after delivery'],
    ['Z39.1', 'lactating mother'],
    ['Z39.2', 'routine postpartum follow-up'],
  ])('%s (%s)', (code) => {
    expect(isValidIcd10(code)).toBe(true);
  });

  it.each([
    'Z34.01', 'Z34.02', 'Z34.03',  // first pregnancy by trimester
    'Z34.81', 'Z34.82', 'Z34.83',  // other pregnancy by trimester
    'Z34.90', 'Z34.91', 'Z34.92', 'Z34.93',
  ])('Z34.x trimester-specific supervision %s', (code) => {
    expect(isValidIcd10(code)).toBe(true);
  });

  it('legacy Z34.00 + Z34.80 still resolve (starter set codes not clobbered)', () => {
    expect(isValidIcd10('Z34.00')).toBe(true);
    expect(isValidIcd10('Z34.80')).toBe(true);
  });

  it.each([
    'O24.410', 'O24.414', 'O24.415', 'O24.419',  // GDM by control modality
    'O82',                                         // cesarean delivery encounter
    'O36.0991',                                    // materno-fetal supervision T3
    'O09.211', 'O09.213',                          // pre-term labor hx supervision
  ])('OB procedure-context code %s', (code) => {
    expect(isValidIcd10(code)).toBe(true);
  });

  it.each([
    'Z30.430', 'Z30.431', 'Z30.432', 'Z30.433', 'Z30.09',
  ])('contraception encounter code %s (postpartum visits often pair)', (code) => {
    expect(isValidIcd10(code)).toBe(true);
  });
});

describe('Dermatology benign-lesion + biopsy + skin-cancer hx codes', () => {
  it.each([
    ['D22.0', 'lip'],
    // ⚠️ D22.1 / D22.2 / D22.3 WERE LISTED HERE AND ARE CATEGORY HEADERS —
    // not valid for submission. Eyelid and ear nevi split by LATERALITY;
    // face nevi (D22.3) split by SITE instead — D22.30 unspecified part vs
    // D22.39 other parts — so "always laterality" would be wrong. What is
    // true of all three is that the billable answer is always a CHILD. A
    // dermatologist billing "D22.1" would have had a non-submittable code
    // accepted by the floor. Replaced with the real children by T8.
    ['D22.10', 'eyelid, unspecified'],
    ['D22.111', 'right upper eyelid'],
    ['D22.112', 'right lower eyelid'],
    ['D22.121', 'left upper eyelid'],
    ['D22.122', 'left lower eyelid'],
    ['D22.20', 'ear + canal, unspecified'],
    ['D22.21', 'right ear + canal'],
    ['D22.22', 'left ear + canal'],
    ['D22.30', 'face, unspecified'],
    ['D22.39', 'other parts of face'],
    ['D22.4', 'scalp + neck'],
    ['D22.5', 'trunk'],
    ['D22.60', 'upper limb'],
    ['D22.70', 'lower limb'],
    ['D22.9', 'unspecified'],
  ])('D22.x melanocytic nevus by site (%s — %s)', (code) => {
    expect(isValidIcd10(code)).toBe(true);
  });

  it('D48.5 (neoplasm uncertain behavior of skin — the pre-pathology placeholder for biopsy day)', () => {
    expect(isValidIcd10('D48.5')).toBe(true);
  });

  it.each([
    ['L82.0', 'inflamed seborrheic keratosis'],
    ['L82.1', 'other seborrheic keratosis'],
    ['L57.0', 'actinic keratosis'],
    ['L57.8', 'other UV-damage skin changes'],
  ])('benign-skin-lesion %s (%s)', (code) => {
    expect(isValidIcd10(code)).toBe(true);
  });

  it.each([
    ['Z85.828', 'personal hx of other malignant skin'],
    ['Z85.820', 'personal hx of malignant melanoma'],
    ['Z80.8', 'family hx of malignant neoplasm of other organs'],
    ['Z12.83', 'screening for malignant neoplasm of skin'],
  ])('skin-cancer surveillance Z-code %s (%s)', (code) => {
    expect(isValidIcd10(code)).toBe(true);
  });

  it('acne family (L70.0/.1/.8/.9) for isotretinoin / acne-treatment scenarios', () => {
    for (const c of ['L70.0', 'L70.1', 'L70.8', 'L70.9']) {
      expect(isValidIcd10(c), c).toBe(true);
    }
  });
});

describe('Orthopedics joint-pain + aftercare + acute-injury codes', () => {
  it.each([
    'M25.511', 'M25.512', 'M25.519',  // shoulder L/R/unspecified
    'M25.521', 'M25.522',              // elbow L/R
    'M25.531', 'M25.532',              // wrist L/R
    'M25.551', 'M25.552',              // hip L/R
    'M25.561', 'M25.562',              // knee L/R
    'M25.571', 'M25.572',              // ankle L/R
  ])('M25.x joint-pain by site (%s)', (code) => {
    expect(isValidIcd10(code)).toBe(true);
  });

  it('legacy M25.50 still resolves (starter-set code not clobbered)', () => {
    expect(isValidIcd10('M25.50')).toBe(true);
  });

  it.each([
    ['S93.401A', 'unspecified ligament right ankle'],
    ['S93.402A', 'unspecified ligament left ankle'],
    ['S93.409A', 'unspecified ligament unspecified ankle'],
    ['S93.411A', 'calcaneofibular right'],
    ['S93.412A', 'calcaneofibular left'],
    ['S93.421A', 'deltoid right'],
    ['S93.422A', 'deltoid left'],
    ['S93.491A', 'other right'],
    ['S93.492A', 'other left'],
  ])('S93.4xxA ankle sprain by ligament (%s — %s)', (code) => {
    expect(isValidIcd10(code)).toBe(true);
  });

  it.each([
    'S83.401A', 'S83.402A',          // knee CL sprains
    'S39.012A',                       // lumbar muscle strain (UC2)
  ])('other acute musculoskeletal injury %s', (code) => {
    expect(isValidIcd10(code)).toBe(true);
  });

  it.each([
    'Z47.1', 'Z47.2', 'Z47.81', 'Z47.82', 'Z47.89',
  ])('Z47.x ortho aftercare (%s)', (code) => {
    expect(isValidIcd10(code)).toBe(true);
  });

  it.each([
    'M79.601', 'M79.602', 'M79.604', 'M79.605', 'M79.606',
  ])('M79.6xx limb pain (%s)', (code) => {
    expect(isValidIcd10(code)).toBe(true);
  });
});

describe('General encounter Z-codes (procedure-dominant fallback)', () => {
  it.each([
    // ⚠️ 'Z48.0' REMOVED — a category header. Its four billable children were
    // already listed immediately after it, so the row asserted a code that
    // could never be submitted while the real ones sat beside it.
    'Z48.00', 'Z48.01', 'Z48.02', 'Z48.03', 'Z48.298',
  ])('Z48.x post-procedural follow-up %s', (code) => {
    expect(isValidIcd10(code)).toBe(true);
  });

  it('Z09 (follow-up after completed treatment, non-malignancy)', () => {
    expect(isValidIcd10('Z09')).toBe(true);
  });

  it.each([
    // ⚠️ 'Z71.4' and 'Z71.5' WERE HERE AND ARE CATEGORY HEADERS. Alcohol and
    // drug abuse counseling split by WHO is counselled — the patient or a
    // family member — and only those children bill.
    'Z71.3', 'Z71.41', 'Z71.42', 'Z71.51', 'Z71.52', 'Z71.82', 'Z71.89',
  ])('Z71.x counseling encounter %s', (code) => {
    expect(isValidIcd10(code)).toBe(true);
  });
});

describe('Z76.89 last-resort placeholder (the prompt-instructed escape)', () => {
  it('Z76.89 is in the allowlist so the model can emit it', () => {
    // The L7a system prompt instructs the model: "If you genuinely
    // cannot identify any diagnosis or encounter Z-code … return ONE
    // confidence:0.3-0.4 Z76.89 and let the L7a post-validation layer
    // flag the visit for review." That escape only works if the code
    // can survive the post-validation allowlist filter.
    expect(isValidIcd10('Z76.89')).toBe(true);
  });
});

describe('Pre-existing entries (no regression)', () => {
  it.each([
    'I10',           // hypertension (Round-1 starter)
    'E11.65',        // T2DM hyperglycemia (G1 / Round-1)
    'I50.32',        // HFpEF chronic (G1)
    'Z98.84',        // bariatric status (bariatric cohort)
    'Z90.3',         // acquired absence of stomach (bariatric + G1)
    // ⚠️ WAS 'I71.4', a category header. FY2021 split abdominal aortic
    // aneurysm without rupture by location (pararenal / juxtarenal /
    // infrarenal / unspecified); '.40' is the unspecified billable code this
    // legacy row meant. SEVEN of the twelve I71.x entries the starter set
    // carried were headers; I71.00/.02/.03/.8/.9 were correct billable codes
    // all along (an earlier draft here said "the whole family", which is false).
    'I71.40',        // AAA without rupture, unspecified (vascular)
    'R10.11',        // RUQ pain (G1)
    'K80.20',        // gallstones (starter)
  ])('legacy code %s still resolves', (code) => {
    expect(isValidIcd10(code)).toBe(true);
  });

  it('rejects a clearly-bogus code (validator floor still active)', () => {
    expect(isValidIcd10('XX99.99')).toBe(false);
    expect(isValidIcd10('00000')).toBe(false);
  });

  it('allowlist size sanity (procedure-dominant batch added ~70 codes)', () => {
    // ⚠️ THIS FLOOR NO LONGER GUARDS WHAT ITS COMMENT CLAIMS. It was written
    // against a ~600-code set, where 540 was a meaningful floor. Against the
    // full CMS release (74,719) it cannot fire until 99.3% of the data is
    // gone — the adversarial pass deleted a real billable code and watched
    // this assertion pass at size 74,718. It is kept because it still pins
    // "this set is not empty", and REPLACED as a regression guard by the
    // exact-count and payload-digest assertions in
    // icd10-fy2026-ingestion.test.ts. Do not read it as coverage.
    expect(ICD10_ALLOWLIST.size).toBeGreaterThan(540);
  });
});
