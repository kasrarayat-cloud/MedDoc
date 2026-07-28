// ============================================================================
// The CPT allowlist is a fail-closed safety floor, so its GAPS are silent.
// ----------------------------------------------------------------------------
// `07b-cpt-coding` drops any code not in this list and emits
// CODING_COACH_REJECTED_INVALID_CPT. That is the right posture — an invented
// procedure code is a False Claims Act vector — but it means a MISSING code and
// a WRONG code are indistinguishable to the doctor: their correctly-coded echo
// simply does not appear, with no explanation on screen.
//
// The Q1 audit (§03.3, §03.4, §03.7) found the list family-medicine-biased: two
// PILOT specialties, cardiology and pediatrics, had none of their commonest
// procedures. This pins the closure so the bias cannot quietly return.
// ============================================================================

import { describe, expect, it } from 'vitest';

import { CPT_ALLOWLIST, isValidCpt } from '../data/cpt-allowlist';

/** Codes the audit named as missing, by specialty. Each is publicly documented
 *  (CMS PFS RVU, AAPC public references) — the file's own licensing rationale. */
const AUDIT_GAPS: Record<string, readonly string[]> = {
  'cardiology (pilot)': ['93306', '93307', '93015', '93224', '93225', '93226', '93227'],
  'pediatrics (pilot)': ['96110', '99188', '92551'],
  'ob-gyn': ['59025', '76801', '76802'],
  'pain management': ['64483', '27096', '64493'],
};

describe('CPT allowlist — the Q1 audit gaps are closed', () => {
  for (const [specialty, codes] of Object.entries(AUDIT_GAPS)) {
    it(`${specialty}: every audit-cited code is allowed`, () => {
      const missing = codes.filter((c) => !CPT_ALLOWLIST.has(c));
      expect(
        missing,
        `${specialty} would have these dropped by the 07b validator: ${missing.join(', ')}`,
      ).toEqual([]);
    });
  }

  it('and they pass the real validator, modifier suffix included', () => {
    // isValidCpt strips a trailing "-NN" before lookup. A code that is in the
    // Set but fails the validator would be a lookup bug, not a coverage one.
    for (const code of Object.values(AUDIT_GAPS).flat()) {
      expect(isValidCpt(code), `${code} rejected by isValidCpt`).toBe(true);
      expect(isValidCpt(`${code}-26`), `${code}-26 rejected`).toBe(true);
    }
  });

  it('93970 is allowed — the code a prod smoke saw go missing', () => {
    // Logged in docs/backlog/q1-fixpack-carryover.md: a bilateral venous duplex
    // was dictated with 93970 spoken aloud and PROCEDURES came back empty.
    // The allowlist is NOT the cause — pinned here so the next investigation
    // starts upstream, at L3 extraction / L7b coding, instead of re-checking
    // this file.
    expect(CPT_ALLOWLIST.has('93970')).toBe(true);
  });

  it('carries no duplicate codes', () => {
    // The Set dedupes, so a duplicate changes no behaviour — it just misleads
    // the next person curating by hand into thinking a code is absent, or
    // adding it twice. Five crept in while closing the audit gaps.
    const { readFileSync } = require('node:fs') as typeof import('node:fs');
    const { join } = require('node:path') as typeof import('node:path');
    const src = readFileSync(join(__dirname, '../data/cpt-allowlist.ts'), 'utf8');
    const codes = [...src.matchAll(/^\s*'(\d{5})',/gm)].map((m) => m[1]);
    const seen = new Set<string>();
    const dupes = codes.filter((c) => (seen.has(c) ? true : (seen.add(c), false)));
    expect([...new Set(dupes)], 'duplicate CPT entries').toEqual([]);
    // Non-vacuity: the regex must actually be finding the list.
    expect(codes.length).toBeGreaterThan(250);
  });
});
