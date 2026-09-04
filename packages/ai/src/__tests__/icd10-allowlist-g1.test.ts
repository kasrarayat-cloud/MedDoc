// ============================================================================
// G1 deep-audit closure — ICD-10 allowlist additions regression guards.
// ----------------------------------------------------------------------------
// The post-PR-#219/#220 deep audit (docs/qa-reports/specialty-deep-audit-
// 20260512T182300Z.md) identified 10 ICD-10 codes that the L7a layer
// emitted (or *should* have emitted) but which would have been silently
// dropped at the allowlist filter because they weren't in the table.
// This test pins the additions so a future cleanup pass can't accidentally
// drop them without breaking the test suite.
//
// The codes fall into 5 thematic groups, each tied to a specific audit
// finding:
//   - HFpEF / HFrEF / acute-on-chronic HF subtypes (B3)
//   - AKI N17.x family (B4)
//   - Dehydration E86.x (B4)
//   - Site-specific abdominal pain R10.1x / .3x (B4)
//   - Personal-history Z86.7x + acquired-absence Z90.x (B6 / V2 / B7)
//   - Severe protein-calorie malnutrition E43-E46 (B9)
// ============================================================================

import { describe, expect, it } from 'vitest';

import { ICD10_ALLOWLIST, isValidIcd10 } from '../data/icd10-allowlist';

describe('G1 — Heart failure subtype codes', () => {
  it.each([
    ['I50.20', 'HFrEF unspecified'],
    ['I50.21', 'HFrEF acute'],
    ['I50.22', 'HFrEF chronic'],
    ['I50.23', 'HFrEF acute on chronic'],
    ['I50.30', 'HFpEF unspecified'],
    ['I50.31', 'HFpEF acute'],
    ['I50.32', 'HFpEF chronic'],
    ['I50.33', 'HFpEF acute on chronic'],
    ['I50.40', 'combined HF unspecified'],
    ['I50.43', 'combined HF acute on chronic'],
  ])('%s (%s) is in the allowlist', (code) => {
    expect(isValidIcd10(code)).toBe(true);
  });
});

describe('G1 — Acute kidney injury (N17 family)', () => {
  it.each(['N17.0', 'N17.1', 'N17.2', 'N17.8', 'N17.9'])(
    '%s is in the allowlist',
    (code) => {
      expect(isValidIcd10(code)).toBe(true);
    },
  );
});

describe('G1 — Dehydration / volume depletion (E86)', () => {
  it.each([
    ['E86.0', 'dehydration'],
    ['E86.1', 'hypovolemia'],
    ['E86.9', 'volume depletion, unspecified'],
  ])('%s (%s) is in the allowlist', (code) => {
    expect(isValidIcd10(code)).toBe(true);
  });
});

describe('G1 — Site-specific abdominal pain (R10.1x / .3x)', () => {
  it.each([
    ['R10.10', 'upper unspecified'],
    ['R10.11', 'RUQ'],
    ['R10.12', 'LUQ'],
    ['R10.13', 'epigastric'],
    ['R10.30', 'lower unspecified'],
    ['R10.31', 'RLQ'],
    ['R10.32', 'LLQ'],
    ['R10.84', 'generalized'],
    ['R10.819', 'abdominal tenderness, unspecified site'],
  ])('%s (%s) is in the allowlist', (code) => {
    expect(isValidIcd10(code)).toBe(true);
  });

  it('legacy R10.9 still resolves (pre-G1 entry not clobbered)', () => {
    expect(isValidIcd10('R10.9')).toBe(true);
  });
});

describe('G1 — Personal-history Z-codes (Z86.7x)', () => {
  it.each([
    // ⚠️ 'Z86.71' REMOVED by T8 — it is a category HEADER (flag=0 in
    // icd10cm_order_2026.txt), not valid for submission. Its two billable
    // children were already on the very next lines, so nothing is lost: the
    // row asserted a code that could never be billed.
    ['Z86.711', 'history of PE specifically'],
    ['Z86.718', 'history of other venous thrombosis'],
    ['Z86.73', 'history of TIA / cerebral infarction w/o residual'],
    ['Z86.74', 'history of sudden cardiac arrest'],
    ['Z86.79', 'history of other circulatory disease'],
  ])('%s (%s) is in the allowlist', (code) => {
    expect(isValidIcd10(code)).toBe(true);
  });
});

describe('G1 — Acquired-absence Z-codes (Z90.x)', () => {
  it.each([
    ['Z90.3', 'acquired absence of stomach (post-bariatric anatomy)'],
    ['Z90.49', 'acquired absence of other digestive-tract parts'],
  ])('%s (%s) is in the allowlist', (code) => {
    expect(isValidIcd10(code)).toBe(true);
  });

  it('legacy Z98.84 (bariatric status) still resolves', () => {
    // Z98.84 was added in the bariatric-surgery PR; G1 adds Z90.3 as
    // the anatomical-status counterpart. Both should coexist.
    expect(isValidIcd10('Z98.84')).toBe(true);
  });
});

describe('G1 — Severe protein-calorie malnutrition (E43-E46)', () => {
  it.each([
    ['E40', 'kwashiorkor'],
    ['E41', 'nutritional marasmus'],
    ['E42', 'marasmic kwashiorkor'],
    ['E43', 'unspecified severe PCM'],
    ['E44.0', 'moderate PCM'],
    ['E44.1', 'mild PCM'],
    ['E45', 'retarded development following PCM'],
    ['E46', 'unspecified PCM'],
    ['E63.0', 'essential fatty acid deficiency'],
    ['E63.1', 'imbalance of food intake'],
    ['E63.9', 'nutritional deficiency, unspecified'],
  ])('%s (%s) is in the allowlist', (code) => {
    expect(isValidIcd10(code)).toBe(true);
  });

  it('legacy symptom-codes R63.4 + R53.83 still resolve (used as fallbacks when no diagnosis)', () => {
    expect(isValidIcd10('R63.4')).toBe(true);
    expect(isValidIcd10('R53.83')).toBe(true);
  });
});

describe('G1 — Allowlist sanity (no regressions)', () => {
  it('original K21.9 GERD entry still in allowlist (referenced in prompt)', () => {
    // The L7a prompt now cites K21.9 by name as an example of "chronic
    // GERD on PPI" hoisting. The code was already in the allowlist
    // pre-G1 — guard so a future cleanup that touches the chronic-
    // disease cluster doesn't sweep it out.
    expect(isValidIcd10('K21.9')).toBe(true);
  });

  it('Z79.02 long-term antiplatelet still resolves (vascular cohort, not clobbered)', () => {
    expect(isValidIcd10('Z79.02')).toBe(true);
  });

  it('rejects a bogus code shape (validator floor still active)', () => {
    expect(isValidIcd10('XX99.99')).toBe(false);
    expect(isValidIcd10('Z99.99')).toBe(false);
  });

  it('total allowlist size grew by at least the G1 batch (sanity)', () => {
    // 50 codes added in this PR. ICD10_ALLOWLIST is a Set so the size
    // is the deduped count. Guard against a future copy-paste error
    // that introduces a duplicate (which would silently lower the
    // count and might hide a real drop elsewhere).
    // ⚠️ Same caveat as the 540 floor in icd10-allowlist-procedure-dominant:
    // against 74,719 codes this cannot detect the duplicate-collapse it names.
    // The exact-count + digest assertions in icd10-fy2026-ingestion.test.ts
    // are what actually guard that now.
    expect(ICD10_ALLOWLIST.size).toBeGreaterThan(450);
  });
});
