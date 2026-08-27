// ============================================================================
// F8-S2 — THE REJECTION REASON IS A CLOSED VOCABULARY. THE PURE GATE.
// ----------------------------------------------------------------------------
// Ruling #154 (PROVISIONAL). Split out of `gate-f8-s2-coding-view.test.tsx`
// deliberately, and the reason is a MEASURED constraint on this programme's own
// workflow rather than a matter of taste:
//
// ⚠️ A COMPONENT TEST CANNOT RUN IN A WORKTREE, BY CONFIG, NOT BY CHANCE.
// `vitest.config.ts:21` aliases react to
// `path.resolve(__dirname, '../../node_modules/react')` — a hard-coded root
// `node_modules` SIBLING. A `git worktree` has no root `node_modules`, so every
// `render()` test fails at import with "Failed to resolve import react".
// Verified with a CONTROL: a PRE-EXISTING component test
// (`em-level-card.test.tsx`) fails identically in the same tree, so this is the
// harness and not the new code. AGENTS.md requires the loop to work in an
// isolated worktree, so for the loop this is every React gate, always.
//
// ⚠️ AND THE ALIAS IS NOT A BUG TO CASUALLY FIX. Its own comment records why it
// is hard-coded: the monorepo hoists RTL's react peer to the root while the app
// installs its own, and two React copies in one process produce "useState is
// null". Re-pointing it is a change to how 380 test files resolve React, which
// is not a thing to do inside a clinical slice. Filed as a finding instead.
//
// Everything in THIS file is pure and runs anywhere. The render-based arms live
// next door and are proven by CI, which has the root install the alias assumes.
// Keeping the pure arms here means the substrate half of #154 is provable — and
// mutation-provable — locally, instead of both halves waiting on a pipeline.
// ============================================================================

import { describe, expect, it } from 'vitest';

import { ICD_REJECTION_REASONS, applyIcdDecision, readIcdDecisions } from '@/lib/icd-decisions';

const USER = 'user-1';
const AT = '2026-08-27T10:00:00.000Z';

const BLOB = {
  codes: [
    {
      code: 'K21.00',
      description: 'GERD without esophagitis',
      evidence_quote: 'reports reflux after meals',
      confidence: 0.92,
    },
    {
      code: 'E11.9',
      description: 'Type 2 diabetes mellitus without complications',
      evidence_quote: 'known T2DM',
      confidence: 0.81,
    },
  ],
  dropped: [{ code: 'Z48.815', reason: 'not_in_verified_allowlist' }],
};

describe('⚠️ F8-S2 / #154 — the rejection reason is a TOKEN, and it is a BICONDITIONAL', () => {
  it('a rejection with NO reason is REFUSED', () => {
    const r = applyIcdDecision(
      { rawIcdCodes: BLOB, rawIcdDecisions: null },
      { code: 'K21.00', decision: 'rejected', userId: USER, at: AT },
    );
    expect(r.ok).toBe(false);
    if (r.ok) return;
    expect(r.reason).toBe('reason_required');
  });

  it('a rejection with a reason OUTSIDE the vocabulary is REFUSED', () => {
    // THE PHI HAZARD THIS RULING EXISTS FOR, written as the sentence a real
    // doctor would type. Free prose must not reach the column even by way of
    // the `reason` field.
    const r = applyIcdDecision(
      { rawIcdCodes: BLOB, rawIcdDecisions: null },
      {
        code: 'K21.00',
        decision: 'rejected',
        userId: USER,
        at: AT,
        reason: 'not relevant, patient’s mother had this not him',
      },
    );
    expect(r.ok).toBe(false);
    if (r.ok) return;
    expect(r.reason).toBe('reason_required');
  });

  it.each(['accepted', 'cleared'] as const)(
    'a reason attached to `%s` is REFUSED — the other half of the biconditional',
    (decision) => {
      const r = applyIcdDecision(
        { rawIcdCodes: BLOB, rawIcdDecisions: null },
        { code: 'K21.00', decision, userId: USER, at: AT, reason: 'wrong_specificity' },
      );
      expect(r.ok).toBe(false);
      if (r.ok) return;
      expect(r.reason).toBe('reason_not_allowed');
    },
  );

  it.each(ICD_REJECTION_REASONS)('`%s` is accepted and STORED verbatim', (reason) => {
    const r = applyIcdDecision(
      { rawIcdCodes: BLOB, rawIcdDecisions: null },
      { code: 'K21.00', decision: 'rejected', userId: USER, at: AT, reason },
    );
    expect(r.ok).toBe(true);
    if (!r.ok) return;
    expect(r.decisions['K21.00']?.reason).toBe(reason);
  });

  it('an ACCEPT stores no `reason` KEY at all — not `reason: undefined`', () => {
    // A present-but-undefined key serialises into JSONB as `"reason": null`,
    // a state-contradicting artefact with no reader.
    const r = applyIcdDecision(
      { rawIcdCodes: BLOB, rawIcdDecisions: null },
      { code: 'K21.00', decision: 'accepted', userId: USER, at: AT },
    );
    expect(r.ok).toBe(true);
    if (!r.ok) return;
    expect('reason' in r.decisions['K21.00']).toBe(false);
  });

  it('⚠️ CHANGING THE REASON IS A REAL CHANGE, NOT A NO-OP', () => {
    // `rejected(not_supported_by_note) -> rejected(wrong_specificity)` is a
    // DIFFERENT clinical statement about the same code. A state-only comparison
    // calls it unchanged: nothing written, no audit row, and the doctor's
    // correction discarded while the UI reports success.
    const first = applyIcdDecision(
      { rawIcdCodes: BLOB, rawIcdDecisions: null },
      {
        code: 'K21.00',
        decision: 'rejected',
        userId: USER,
        at: AT,
        reason: 'not_supported_by_note',
      },
    );
    expect(first.ok).toBe(true);
    if (!first.ok) return;

    const second = applyIcdDecision(
      { rawIcdCodes: BLOB, rawIcdDecisions: first.decisions },
      {
        code: 'K21.00',
        decision: 'rejected',
        userId: USER,
        at: '2026-08-27T11:00:00.000Z',
        reason: 'wrong_specificity',
      },
    );
    expect(second.ok).toBe(true);
    if (!second.ok) return;
    expect(second.changed, 'a reason correction was swallowed as a no-op').toBe(true);
    expect(second.decisions['K21.00']?.reason).toBe('wrong_specificity');
    expect(second.decisions['K21.00']?.at).toBe('2026-08-27T11:00:00.000Z');
  });

  it('re-asserting the SAME reason IS a no-op, and the timestamp does not move', () => {
    const first = applyIcdDecision(
      { rawIcdCodes: BLOB, rawIcdDecisions: null },
      { code: 'K21.00', decision: 'rejected', userId: USER, at: AT, reason: 'other' },
    );
    expect(first.ok).toBe(true);
    if (!first.ok) return;
    const again = applyIcdDecision(
      { rawIcdCodes: BLOB, rawIcdDecisions: first.decisions },
      { code: 'K21.00', decision: 'rejected', userId: USER, at: 'LATER', reason: 'other' },
    );
    expect(again.ok).toBe(true);
    if (!again.ok) return;
    expect(again.changed).toBe(false);
    expect(again.decisions['K21.00']?.at).toBe(AT);
  });

  it('⚠️ the REASON gate runs BEFORE the no-op check — on an ALREADY-ACCEPTED code', () => {
    // ⚠️ THIS ARM WAS ORIGINALLY AIMED AT THE WRONG CASE, AND THE MUTATION
    // PROOF IS WHAT FOUND IT. The first draft re-REJECTED an already-rejected
    // code with a garbage reason, and asserted a refusal — but that case
    // refuses under BOTH orderings, because a garbage reason differs from the
    // stored one, so `sameReason` is false and the early return never fires.
    // It was an arm that could not fail, dressed as an ordering guard.
    //
    // THE CASE THAT ACTUALLY DISCRIMINATES is a reason attached to an
    // ALREADY-ACCEPTED code. There `to !== 'rejected'`, so `sameReason` is
    // TRUE and `sameState` is TRUE — meaning a gate placed after the check
    // takes the early return and answers `ok:true, changed:false`. The illegal
    // payload is absorbed as a successful no-op, and the caller cannot tell it
    // from a legitimate re-assertion.
    const first = applyIcdDecision(
      { rawIcdCodes: BLOB, rawIcdDecisions: null },
      { code: 'K21.00', decision: 'accepted', userId: USER, at: AT },
    );
    expect(first.ok).toBe(true);
    if (!first.ok) return;

    const bad = applyIcdDecision(
      { rawIcdCodes: BLOB, rawIcdDecisions: first.decisions },
      {
        code: 'K21.00',
        decision: 'accepted',
        userId: USER,
        at: AT,
        reason: 'wrong_specificity',
      },
    );
    expect(bad.ok, 'an illegal reason was absorbed as a successful no-op').toBe(false);
    if (bad.ok) return;
    expect(bad.reason).toBe('reason_not_allowed');
  });

  it('no reason token is ever prose — every one is a lowercase snake_case slug', () => {
    for (const r of ICD_REJECTION_REASONS) {
      expect(r).toMatch(/^[a-z][a-z_]*$/);
      expect(r).not.toContain(' ');
    }
  });

  it('⚠️ the vocabulary is NON-EMPTY — the arms above are not vacuous', () => {
    // `it.each([])` silently registers ZERO tests and reports green. Two arms
    // above iterate the vocabulary, so an empty array would delete them both
    // without failing anything.
    expect(ICD_REJECTION_REASONS.length).toBeGreaterThanOrEqual(4);
  });
});

describe('⚠️ F8-S2 — the narrower enforces the biconditional on READ, not only on WRITE', () => {
  it('a REJECTED record with an unknown reason is DROPPED, not repaired', () => {
    // Dropping returns the code to UNDECIDED, so it surfaces to the doctor
    // again — over-shooting to the edge, where there is a fence. Inventing a
    // reason would assert a clinical rationale nobody gave.
    const m = readIcdDecisions({
      'K21.00': { state: 'rejected', at: AT, byUserId: USER, reason: 'because_i_said_so' },
    });
    expect(m['K21.00']).toBeUndefined();
  });

  it('a REJECTED record with NO reason is DROPPED', () => {
    const m = readIcdDecisions({ 'K21.00': { state: 'rejected', at: AT, byUserId: USER } });
    expect(m['K21.00']).toBeUndefined();
  });

  it('a stray reason on an ACCEPTED record is STRIPPED and the decision SURVIVES', () => {
    // The asymmetry is deliberate: the state is well formed and is a real
    // clinical decision, so the uninterpretable annotation goes and the
    // decision stays. Deleting the record would destroy a doctor's accept in
    // order to punish a stray field beside it.
    const m = readIcdDecisions({
      'K21.00': { state: 'accepted', at: AT, byUserId: USER, reason: 'not_supported_by_note' },
    });
    expect(m['K21.00']?.state).toBe('accepted');
    expect('reason' in (m['K21.00'] as object)).toBe(false);
  });

  it('a well-formed REJECTED record round-trips with its reason intact', () => {
    // The non-vacuity control for the three drops above: if the narrower
    // dropped everything, all four would pass and mean nothing.
    const m = readIcdDecisions({
      'K21.00': { state: 'rejected', at: AT, byUserId: USER, reason: 'duplicate_of_another_code' },
    });
    expect(m['K21.00']?.reason).toBe('duplicate_of_another_code');
  });
});
