// ============================================================================
// F16 GATE — a DESIGNED refusal must name the remaining work, and must not
// name the customer's form.
// ----------------------------------------------------------------------------
// WHAT THIS GUARDS, stated as claims so a future reader can break them:
//
//   1. `MAPPINGS_NOT_READY` carries a COUNT the caller can render. Before F16
//      it carried nothing, because the first throw was inside a `.map()` and
//      exited on the first unmapped field — the count was UNKNOWABLE by
//      construction.
//   2. The count is of FIELDS, not of reasons. A field can be both
//      unconfirmed and concept-less; counting reasons reports 7 for six fields
//      and sends a physician hunting a seventh that does not exist.
//   3. The sentence is DERIVED. A hard-coded "6 of 80" passes a single-case
//      test and is wrong the moment a seventh field appears.
//   4. NO FIELD LABEL crosses to the doctor. The template is the customer's
//      own form. Only counts, and the opaque fieldIds that stay in the audit
//      row.
//
// ⚠️ WHAT THIS DOES **NOT** GUARD, said plainly so the gate is not read wider
// than it is:
//
//   · It does not assert the sentence is RENDERED. It asserts what the action
//     returns. A UI that drops `result.error` on the floor would leave this
//     green — the same honest limit #713's gate carries, recorded rather than
//     papered over.
//   · It does not exercise `runTemplateTwinSyntheticTest` end to end; that
//     needs the whole prisma + storage path. It asserts the ERROR CONTRACT the
//     refusal produces and the SENTENCE the action derives from it.
// ============================================================================

import { describe, it, expect } from 'vitest';
import {
  mappingsNotReadyMessage,
  mappingsNotReadyScope,
  MAPPINGS_NOT_READY_ROUTE_HINT,
} from '../mappings-not-ready-message';
// ⚠️ FROM THE LEAF, NOT THE RE-EXPORT. `synthetic-test.ts` re-exports this
// class and imports prisma; a test that reached for it through the re-export
// could not load at all. A grep that resolves a symbol through a barrel has
// not found its definition.
import { TemplateTwinSyntheticTestError } from '../synthetic-test-error';

describe('F16 — the refusal names how much is left', () => {
  // The production case, verbatim. 2026-08-17: 80 fields, 74 confirmed, 6 not.
  it('names the count and the total on the real production shape', () => {
    const msg = mappingsNotReadyMessage(6, 80);
    expect(msg).toContain('6 of 80 fields still need confirming');
    expect(msg).toContain(MAPPINGS_NOT_READY_ROUTE_HINT);
  });

  // ⚠️ NON-VACUITY / DERIVED-NOT-CONSTANT. If someone hard-codes the
  // production numbers to make the arm above pass, THIS arm reddens.
  it('is derived, not a constant — a different form gets different numbers', () => {
    expect(mappingsNotReadyScope(1, 12)).toBe('1 of 12 field still needs confirming');
    expect(mappingsNotReadyScope(7, 80)).toBe('7 of 80 fields still need confirming');
    expect(mappingsNotReadyScope(22, 80)).toBe('22 of 80 fields still need confirming');
    // and the production pair is not privileged in any way
    expect(mappingsNotReadyScope(6, 80)).toBe('6 of 80 fields still need confirming');
  });

  it('degrades to a vaguer TRUE sentence rather than a confident wrong one', () => {
    // total unknown -> drop the total, keep the count
    expect(mappingsNotReadyScope(3, null)).toBe('3 fields still need confirming');
    // a total SMALLER than the remainder cannot be true of one form: "7 of 6"
    // is worse than "7", so the total is dropped rather than printed
    expect(mappingsNotReadyScope(7, 6)).toBe('7 fields still need confirming');
    // a nonsensical count degrades; it must never crash on top of a refusal
    expect(mappingsNotReadyScope(0, 80)).toBe('some fields still need confirming');
    expect(mappingsNotReadyScope(-1, 80)).toBe('some fields still need confirming');
    expect(mappingsNotReadyScope(Number.NaN, 80)).toBe('some fields still need confirming');
  });

  // ⚠️ THE OLD SENTENCE IS THE REGRESSION TO WATCH FOR. This is what the
  // physician actually saw twice on 2026-08-17, from the unanticipated-throw
  // branch. If MAPPINGS_NOT_READY ever falls back there, the message stops
  // being derived and starts telling a doctor to wait for an engineer.
  it('never tells the doctor the refusal is somebody else\'s to fix', () => {
    const msg = mappingsNotReadyMessage(6, 80);
    expect(msg).not.toContain('could not be completed');
    expect(msg).not.toContain('will not succeed on a retry');
    expect(msg).not.toContain('MAPPINGS_NOT_READY');
    // it points at an action the doctor can take
    expect(msg.toLowerCase()).toContain('confirm');
  });
});

describe('F16 — the error contract carries ids and counts, never labels', () => {
  it('carries blocking ids and a total', () => {
    const err = new TemplateTwinSyntheticTestError(
      'MAPPINGS_NOT_READY',
      'Every field needs a physician-confirmed mapping before testing.',
      {
        blocking: ['ttf_aaa:unconfirmed', 'ttf_bbb:no_concept'],
        totalFields: 80,
      },
    );
    expect(err.code).toBe('MAPPINGS_NOT_READY');
    expect(err.blocking).toHaveLength(2);
    expect(err.totalFields).toBe(80);
  });

  // ⚠️ THE BACKWARD-COMPATIBILITY ARM. Every OTHER throw site constructs this
  // error with no detail at all. If `totalFields` had been made required, or
  // defaulted to 0, those sites would silently start claiming "0 fields".
  it('defaults to null rather than 0 when no detail is supplied', () => {
    const err = new TemplateTwinSyntheticTestError('CONFLICT', 'Mappings changed.');
    expect(err.blocking).toEqual([]);
    expect(err.totalFields).toBeNull();
    // and null is what makes the sentence drop the total instead of printing
    // a confident, wrong "of 0"
    expect(mappingsNotReadyScope(3, err.totalFields)).toBe('3 fields still need confirming');
  });

  // ⚠️ PHI / CUSTOMER-CONTENT BOUNDARY. The doctor-facing sentence is built
  // from COUNTS ONLY, so no field label can reach it even if one is present in
  // the ids. This is the constraint the action's own comment states as the
  // reason it withholds `err.message`.
  it('cannot leak a field label into the doctor-facing sentence', () => {
    const label = 'PATIENT NAME AND DATE OF BIRTH';
    const err = new TemplateTwinSyntheticTestError(
      'MAPPINGS_NOT_READY',
      `Field "${label}" needs a physician-confirmed mapping.`,
      { blocking: [`${label}:unconfirmed`], totalFields: 80 },
    );
    const msg = mappingsNotReadyMessage(err.blocking.length, err.totalFields);
    expect(msg).not.toContain(label);
    expect(msg).not.toContain(err.message);
    expect(msg).toContain('1 of 80 field still needs confirming');
  });
});
