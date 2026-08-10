// ============================================================================
// B4's CLOSING STEP — the L5 critique variant, and the two things it must be.
// ----------------------------------------------------------------------------
// `MOCK_CRITIQUE_ISSUES=true` swaps the empty `tm_critique` fixture for one
// carrying a single MINOR issue, so that L6 calls its model instead of taking
// the passthrough at `06-polish.ts:186`. Without it, `tm_polish` and
// `tm_polish_gate` cannot be COUNTED on any mocked run — the stage never runs,
// which is indistinguishable from a stage whose meter was deleted.
//
// Two assertions, and the second is the one that protects everybody else:
//
//   1. WITH the flag, the populated variant is returned.
//   2. WITHOUT it, the fixture is byte-for-byte the empty one. Every spec that
//      signs a visit depends on `issues: []`, and a variant that leaked into
//      the default would change what several suites see while every one of
//      them still passed — right up until one of them didn't.
//
// ⚠️ AND THE FIX'S SHAPE IS ASSERTED, NOT JUST ITS PRESENCE. `isAdditiveFix`
// (06-polish.ts:127) DEFERS any suggested fix that would need content the draft
// lacks, and a deferred fix is not a fixable one. So a variant phrased as
// "add …" would leave `fixable.length === 0`, L6 would still pass through, and
// this whole mechanism would be an elaborate no-op that looked correct. The
// removal verb is load-bearing.
// ============================================================================

import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { z } from 'zod';

import { MOCK_CRITIQUE_WITH_ISSUES, mockComplete } from '../mock';

// `mockComplete` is a THIN WRAPPER over the same `rawCompleteFixture` the
// production mock path uses (see its header), so testing selection through it
// is testing what production selects. The schema is `z.any()` because this file
// asserts WHICH fixture comes back, not that it satisfies `CritiqueReport` —
// that schema lives in the app and cannot be imported from here. The real
// parse is exercised end-to-end by the QA coverage run, which would fail loudly
// on an invalid fixture.
const ANY = z.any();
const critique = () => mockComplete({ purpose: 'tm_critique', schema: ANY }) as any;

const prevFlag = process.env.MOCK_CRITIQUE_ISSUES;

beforeEach(() => {
  delete process.env.MOCK_CRITIQUE_ISSUES;
});
afterEach(() => {
  if (prevFlag === undefined) delete process.env.MOCK_CRITIQUE_ISSUES;
  else process.env.MOCK_CRITIQUE_ISSUES = prevFlag;
});

describe('mock tm_critique — the polish-reachability variant', () => {
  it('DEFAULT is the empty critique — nothing else’s behaviour moves', () => {
    const fixture = critique();
    expect(fixture.issues).toEqual([]);
    expect(fixture.safe_to_sign_without_review).toBe(true);
  });

  it('WITH the flag, the populated variant is returned', () => {
    process.env.MOCK_CRITIQUE_ISSUES = 'true';
    const fixture = critique();
    expect(fixture.issues).toHaveLength(1);
    expect(fixture).toEqual(MOCK_CRITIQUE_WITH_ISSUES);
  });

  it('the flag is EXACT-MATCH — a truthy-looking value does not switch it', () => {
    // `=== 'true'`, like every other mock flag in this file. Asserted because a
    // loose check is how a stray `MOCK_CRITIQUE_ISSUES=1` in somebody's shell
    // would silently change what the whole QA stack generates.
    process.env.MOCK_CRITIQUE_ISSUES = '1';
    expect(critique().issues).toEqual([]);
    process.env.MOCK_CRITIQUE_ISSUES = 'TRUE';
    expect(critique().issues).toEqual([]);
  });

  it('the issue is MINOR and its fix is a REMOVAL — both are load-bearing', () => {
    const issue = MOCK_CRITIQUE_WITH_ISSUES.issues[0];
    // MINOR: a critical issue would gate signing and break the suites that
    // sign visits, which is the exact blast radius this variant must not have.
    expect(issue.severity).toBe('minor');
    // REMOVAL: `isAdditiveFix` defers additive fixes, and a deferred fix leaves
    // `fixable.length === 0` — the passthrough this variant exists to avoid.
    expect(issue.suggested_fix.toLowerCase()).toMatch(/\bremove\b/);
    expect(issue.suggested_fix.toLowerCase()).not.toMatch(/\badd\b/);
  });

  it('does NOT change any other purpose’s fixture', () => {
    process.env.MOCK_CRITIQUE_ISSUES = 'true';
    expect((mockComplete({ purpose: 'tm_icd_coding', schema: ANY }) as any).codes).toEqual([]);
    expect(mockComplete({ purpose: 'tm_rx_drafting', schema: ANY })).toEqual({});
  });
});
