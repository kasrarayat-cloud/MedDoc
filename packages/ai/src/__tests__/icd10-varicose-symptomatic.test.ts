// BUG 3 supporting fix — the symptomatic/complicated varicose-vein I83.8x
// family must pass the allowlist so a corrected code isn't silently dropped.
import { describe, expect, it } from 'vitest';
import { isValidIcd10 } from '../data/icd10-allowlist';

describe('varicose-vein symptomatic ICD codes (I83.8x)', () => {
  it('accepts the "with other complications" family (swelling/heaviness/edema)', () => {
    for (const c of ['I83.891', 'I83.892', 'I83.893', 'I83.899']) {
      expect(isValidIcd10(c), c).toBe(true);
    }
  });
  it('accepts the "with pain" family incl. unspecified LE', () => {
    // ⚠️ WAS ['I83.810', …]. `I83.810` IS NOT AN ICD-10-CM CODE — measured
    // absent from the FY2026 release in every form. The "with pain" family is
    // 811/812/813 plus **819** for the unspecified limb, which is the code this
    // test's own name ("incl. unspecified LE") was reaching for. The block
    // below already asserted the rule — "only its 6-char children bill" — so
    // the principle was understood and a sibling was assumed into existence
    // anyway. Corrected by T8 against the official file.
    for (const c of ['I83.811', 'I83.812', 'I83.813', 'I83.819']) {
      expect(isValidIcd10(c), c).toBe(true);
    }
  });
  it('still accepts the asymptomatic family (no regression)', () => {
    for (const c of ['I83.90', 'I83.91', 'I83.92', 'I83.93']) {
      expect(isValidIcd10(c), c).toBe(true);
    }
  });
  it('rejects the non-billable bare I83.81 subcategory (only its 6-char children bill)', () => {
    expect(isValidIcd10('I83.81')).toBe(false);
    // sanity: the billable children remain valid
    expect(isValidIcd10('I83.811')).toBe(true);
  });
});
