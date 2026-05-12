// ============================================================================
// L7a system-prompt regression guards (G1 deep-audit closure).
// ----------------------------------------------------------------------------
// The L7a prompt encodes the clinical hoisting rules that determine
// whether the ICD layer captures documented PMH conditions as billable
// codes. PR #217 added the K76.0 NAFLD / G47.33 OSA hoisting pattern;
// this PR extends it to cover the 5 thematic groups surfaced by the
// post-PR-#219/#220 deep audit (docs/qa-reports/specialty-deep-audit-
// 20260512T182300Z.md §G1):
//
//   1. HFpEF + acute-on-chronic HF subtype examples (B3)
//   2. Personal-history Z86.7x family (B6, V2)
//   3. Acquired-absence Z90.x family (B7)
//   4. Acute documented findings during a workup — AKI (N17), dehydration
//      (E86), site-specific abdominal pain (R10.1x/.3x) (B4)
//   5. "Prefer documented diagnosis over symptom codes" — E43/E44 over
//      R63.4 + R53.83; D51.9 over E53.8 + D50.9 (B8, B9)
//   6. K21.9 GERD-on-PPI hoisting (B2)
//
// These tests anchor on substrings in L7A_SYSTEM_PROMPT so a future
// cleanup-pass on the prompt can't silently drop a hoisting rule
// without flagging.
// ============================================================================

import { describe, expect, it, vi } from 'vitest';

// L7a's `logAudit` import pulls in next-auth via the @/lib/audit chain,
// which doesn't resolve under vitest's node environment. We're testing
// the static prompt string only — no audit calls happen at import time —
// so stubbing the module surface is the cheapest way to load the source.
// Same pattern as worker/layers/__tests__/07c-rx-drafting.validator.test.ts.
vi.mock('@/lib/audit', () => ({ logAudit: vi.fn() }));
vi.mock('@meddoc/db', () => ({ default: {} }));

import { L7A_SYSTEM_PROMPT } from '@/worker/layers/07a-icd-coding';

describe('L7a prompt — HFpEF / HFrEF hoisting (G1 group 1, finding B3)', () => {
  it('mentions HFpEF + the I50.32 chronic code', () => {
    expect(L7A_SYSTEM_PROMPT).toMatch(/HFpEF/);
    expect(L7A_SYSTEM_PROMPT).toMatch(/I50\.32/);
  });

  it('mentions HFrEF + the I50.22 chronic code', () => {
    expect(L7A_SYSTEM_PROMPT).toMatch(/HFrEF/);
    expect(L7A_SYSTEM_PROMPT).toMatch(/I50\.22/);
  });

  it('clarifies the systolic-vs-diastolic decision is based on EF', () => {
    expect(L7A_SYSTEM_PROMPT).toMatch(/EF|ejection fraction/i);
  });
});

describe('L7a prompt — K21.9 GERD-on-PPI hoisting (G1 group 6, finding B2)', () => {
  it('cites K21.9 + makes chronic PPI use the marker (not active reflux)', () => {
    expect(L7A_SYSTEM_PROMPT).toMatch(/K21\.9/);
    expect(L7A_SYSTEM_PROMPT).toMatch(/chronic\s+GERD\s+on\s+PPI/i);
    expect(L7A_SYSTEM_PROMPT).toMatch(/chronic\s+PPI\s+use/i);
  });
});

describe('L7a prompt — personal-history Z-codes (G1 group 2, finding B6 + V2)', () => {
  it('explicitly calls out Z86.7x family', () => {
    expect(L7A_SYSTEM_PROMPT).toMatch(/Z86\.7/);
  });

  it('names Z86.718 VTE history as the index example', () => {
    expect(L7A_SYSTEM_PROMPT).toMatch(/Z86\.718/);
    expect(L7A_SYSTEM_PROMPT).toMatch(/VTE/);
  });

  it('names Z86.73 TIA / cerebral infarction history', () => {
    expect(L7A_SYSTEM_PROMPT).toMatch(/Z86\.73/);
    expect(L7A_SYSTEM_PROMPT).toMatch(/TIA/);
  });

  it('preserves Z87.891 nicotine-history example', () => {
    expect(L7A_SYSTEM_PROMPT).toMatch(/Z87\.891/);
  });
});

describe('L7a prompt — acquired-absence Z-codes (G1 group 3, finding B7)', () => {
  it('cites Z90.3 acquired absence of stomach + pairs with Z98.84', () => {
    expect(L7A_SYSTEM_PROMPT).toMatch(/Z90\.3/);
    expect(L7A_SYSTEM_PROMPT).toMatch(/Z98\.84/);
  });

  it('explains the lifelong pairing rationale', () => {
    expect(L7A_SYSTEM_PROMPT).toMatch(/persists\s+for\s+life|every\s+follow-up/i);
  });
});

describe('L7a prompt — acute findings during workup (G1 group 4, finding B4)', () => {
  it('covers AKI (N17.x) from baseline shift', () => {
    expect(L7A_SYSTEM_PROMPT).toMatch(/AKI/);
    expect(L7A_SYSTEM_PROMPT).toMatch(/N17/);
    expect(L7A_SYSTEM_PROMPT).toMatch(/baseline/i);
  });

  it('covers dehydration (E86.0) from clinical exam', () => {
    expect(L7A_SYSTEM_PROMPT).toMatch(/E86\.0/);
    expect(L7A_SYSTEM_PROMPT).toMatch(/dehydration/i);
  });

  it('covers site-specific abdominal pain prefer over R10.9', () => {
    expect(L7A_SYSTEM_PROMPT).toMatch(/R10\.\d/);
    expect(L7A_SYSTEM_PROMPT).toMatch(/LUQ|RUQ|epigastric|site-specific/i);
  });
});

describe('L7a prompt — documented diagnosis preferred over symptom codes (G1 group 5)', () => {
  it('cites E43 / E44.0 over R63.4 for documented PCM (finding B9)', () => {
    expect(L7A_SYSTEM_PROMPT).toMatch(/E43/);
    expect(L7A_SYSTEM_PROMPT).toMatch(/R63\.4/);
    expect(L7A_SYSTEM_PROMPT).toMatch(/PROTEIN-CALORIE MALNUTRITION/);
  });

  it('cites D51.9 over the E53.8 + D50.9 split (finding B8)', () => {
    expect(L7A_SYSTEM_PROMPT).toMatch(/D51\.9/);
    expect(L7A_SYSTEM_PROMPT).toMatch(/E53\.8/);
    expect(L7A_SYSTEM_PROMPT).toMatch(/D50\.9/);
  });

  it('explicitly says "PREFER" the diagnosis', () => {
    expect(L7A_SYSTEM_PROMPT).toMatch(/PREFER/);
  });
});

describe('L7a prompt — pre-G1 PR-#217 rules still present (no regression)', () => {
  it('preserves NAFLD (K76.0) + OSA (G47.33) hoisting examples', () => {
    // PR #217 added these; G1 extension must not clobber.
    expect(L7A_SYSTEM_PROMPT).toMatch(/K76\.0/);
    expect(L7A_SYSTEM_PROMPT).toMatch(/G47\.33/);
  });

  it('preserves chronic medication Z-codes guidance', () => {
    expect(L7A_SYSTEM_PROMPT).toMatch(/Z79\.\d/);
    expect(L7A_SYSTEM_PROMPT).toMatch(/long-term/i);
  });

  it('preserves "do NOT code rule-out / suspected" guidance', () => {
    expect(L7A_SYSTEM_PROMPT).toMatch(/rule out|suspected|differential/i);
    expect(L7A_SYSTEM_PROMPT).toMatch(/uncertainty/i);
  });

  it('preserves the final JSON-only output contract', () => {
    expect(L7A_SYSTEM_PROMPT).toMatch(/VALID JSON ONLY/);
    expect(L7A_SYSTEM_PROMPT).toMatch(/no markdown fences/);
  });
});
