// ============================================================================
// L7a prompt — MINIMUM CODING REQUIREMENT regression guards (2026-05-13).
// ----------------------------------------------------------------------------
// Cross-input-mode audit Finding 3 surfaced empty `codes: []` returns on
// procedure-dominant scenarios (postpartum visit / suspicious-mole biopsy
// / acute ankle sprain). The prompt-side fix is the new "MINIMUM CODING
// REQUIREMENT" section in 07a-icd-coding.ts L7A_SYSTEM_PROMPT, which
// makes "every visit emits at least one code" explicit + lists the
// concrete patterns the model should match.
//
// Tests below anchor each load-bearing substring so a future prompt
// cleanup can't silently drop the rule without flagging.
// ============================================================================

import { describe, expect, it, vi } from 'vitest';

// L7a's logAudit + @meddoc/db imports pull in next-auth via the chain
// — mock at module-boundary so the test environment loads cleanly.
vi.mock('@/lib/audit', () => ({ logAudit: vi.fn() }));
vi.mock('@meddoc/db', () => ({ default: {} }));

import { L7A_SYSTEM_PROMPT } from '@/worker/layers/07a-icd-coding';

describe('L7a prompt — MINIMUM CODING REQUIREMENT section', () => {
  it('contains the explicit MINIMUM CODING REQUIREMENT header', () => {
    expect(L7A_SYSTEM_PROMPT).toMatch(/MINIMUM CODING REQUIREMENT/);
    expect(L7A_SYSTEM_PROMPT).toMatch(/EVERY VISIT EMITS AT LEAST ONE CODE/);
  });

  it('explicitly bans empty codes array as an acceptable output', () => {
    expect(L7A_SYSTEM_PROMPT).toMatch(/Returning an empty `codes` array/);
    expect(L7A_SYSTEM_PROMPT).toMatch(/not an acceptable output/);
  });
});

describe('L7a prompt — postpartum coverage (OB2 miss fix)', () => {
  it('cites Z39.x family for postpartum / lactation visits', () => {
    expect(L7A_SYSTEM_PROMPT).toMatch(/Z39\.0|Z39\.1|Z39\.2/);
    expect(L7A_SYSTEM_PROMPT).toMatch(/postpartum/i);
  });
});

describe('L7a prompt — derm biopsy coverage (DERM1 miss fix)', () => {
  it('cites D22.x melanocytic nevi + D48.5 uncertain-behavior placeholder', () => {
    expect(L7A_SYSTEM_PROMPT).toMatch(/D22\.x/);
    expect(L7A_SYSTEM_PROMPT).toMatch(/D48\.5/);
    expect(L7A_SYSTEM_PROMPT).toMatch(/biopsy/i);
  });

  it('reasons explicitly about path-result vs day-of-biopsy coding', () => {
    // The prompt has line breaks inside the multi-line bullet, so
    // match across whitespace incl. newlines.
    expect(L7A_SYSTEM_PROMPT).toMatch(/path[\s\S]+?result is the eventual code/i);
    expect(L7A_SYSTEM_PROMPT).toMatch(/clinical[\s\S]+?impression at biopsy time/i);
  });
});

describe('L7a prompt — acute injury coverage (ORT2 miss fix)', () => {
  it('cites S93.4xxA + S83.xxxA + S39.012A acute-injury codes', () => {
    expect(L7A_SYSTEM_PROMPT).toMatch(/S93\.4xxA/);
    expect(L7A_SYSTEM_PROMPT).toMatch(/S83\.xxxA/);
    expect(L7A_SYSTEM_PROMPT).toMatch(/S39\.012A/);
  });

  it('makes S-codes mandatory for acute injuries', () => {
    expect(L7A_SYSTEM_PROMPT).toMatch(/Acute injuries ALWAYS get an S-code/);
  });
});

describe('L7a prompt — knee OA / aftercare coverage', () => {
  it('cites M17.x + M25.x + Z47.x for joint-pain / aftercare visits', () => {
    expect(L7A_SYSTEM_PROMPT).toMatch(/M17\.x/);
    expect(L7A_SYSTEM_PROMPT).toMatch(/M25\.x/);
    expect(L7A_SYSTEM_PROMPT).toMatch(/Z47\.x/);
  });
});

describe('L7a prompt — counseling / lifestyle coverage', () => {
  it('cites Z71.x family for counseling-dominant visits', () => {
    expect(L7A_SYSTEM_PROMPT).toMatch(/Z71\.x/);
  });

  it('makes T2DM / obesity codes mandatory on metabolic follow-up', () => {
    expect(L7A_SYSTEM_PROMPT).toMatch(/E11\.x/);
    expect(L7A_SYSTEM_PROMPT).toMatch(/E66\.x/);
    expect(L7A_SYSTEM_PROMPT).toMatch(/mandatory/i);
  });
});

describe('L7a prompt — Z76.89 last-resort escape', () => {
  it('instructs the model to emit Z76.89 with 0.3-0.4 confidence rather than returning empty codes', () => {
    expect(L7A_SYSTEM_PROMPT).toMatch(/Z76\.89/);
    expect(L7A_SYSTEM_PROMPT).toMatch(/0\.3-0\.4|0\.3 ?- ?0\.4/);
    expect(L7A_SYSTEM_PROMPT).toMatch(/preferable to returning `codes: \[\]`/);
  });

  it('Z76.89 will trigger the post-validation needsReview path', () => {
    // The prompt acknowledges that emitting Z76.89 won't silently
    // pass through — the post-validation layer flags it. Use a
    // whitespace-flexible regex because the prompt has line breaks
    // inside the bullet.
    expect(L7A_SYSTEM_PROMPT).toMatch(/post-validation layer/i);
    expect(L7A_SYSTEM_PROMPT).toMatch(/flag[\s\S]+?the visit for review/i);
  });
});

describe('Pre-G1 PR-#225 rules still present (no regression)', () => {
  it('preserves HFpEF/HFrEF + K21.9 GERD + Z86.7x history + Z90.x absence-of-stomach', () => {
    expect(L7A_SYSTEM_PROMPT).toMatch(/HFpEF/);
    expect(L7A_SYSTEM_PROMPT).toMatch(/HFrEF/);
    expect(L7A_SYSTEM_PROMPT).toMatch(/K21\.9/);
    expect(L7A_SYSTEM_PROMPT).toMatch(/Z86\.7/);
    expect(L7A_SYSTEM_PROMPT).toMatch(/Z90\.3/);
  });

  it('preserves NAFLD K76.0 + OSA G47.33 + chronic-meds Z79.x guidance', () => {
    expect(L7A_SYSTEM_PROMPT).toMatch(/K76\.0/);
    expect(L7A_SYSTEM_PROMPT).toMatch(/G47\.33/);
    expect(L7A_SYSTEM_PROMPT).toMatch(/Z79\.\d/);
  });

  it('preserves PREFER documented diagnosis over symptom codes (E43 / D51.9 reasoning)', () => {
    expect(L7A_SYSTEM_PROMPT).toMatch(/PREFER/);
    expect(L7A_SYSTEM_PROMPT).toMatch(/E43/);
    expect(L7A_SYSTEM_PROMPT).toMatch(/D51\.9/);
  });

  it('preserves final VALID JSON ONLY output contract', () => {
    expect(L7A_SYSTEM_PROMPT).toMatch(/VALID JSON ONLY/);
    expect(L7A_SYSTEM_PROMPT).toMatch(/no markdown fences/);
  });
});
