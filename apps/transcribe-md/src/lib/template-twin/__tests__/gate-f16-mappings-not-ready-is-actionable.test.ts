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

import { readFileSync } from 'node:fs';
import path from 'node:path';
import { describe, it, expect } from 'vitest';
import {
  mappingsNotReadyMessage,
  mappingsNotReadyScope,
  MAPPINGS_NOT_READY_ROUTE_HINT,
} from '../mappings-not-ready-message';
// ⚠️ THE READINESS RULE, FROM ITS LEAF. It was inline in `synthetic-test.ts`
// (which imports prisma) until the independent pass measured that nothing could
// execute it. See the header of `../mappings-readiness`.
import { unreadyReason, collectUnready } from '../mappings-readiness';
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
    expect(mappingsNotReadyScope(7, 80)).toBe('7 of 80 fields still need confirming');
    expect(mappingsNotReadyScope(22, 80)).toBe('22 of 80 fields still need confirming');
    // and the production pair is not privileged in any way
    expect(mappingsNotReadyScope(6, 80)).toBe('6 of 80 fields still need confirming');
  });

  // ⚠️ THE ARM THAT USED TO ENSHRINE A DEFECT, AND IS NOW THE ARM THAT GUARDS
  // AGAINST IT. This previously asserted
  // `toBe('1 of 12 field still needs confirming')` — the singular noun is
  // wrong, because in the "N of M" form the noun counts M. So the guard did not
  // merely miss the bug: correcting the sentence REDDENED it, which is how a
  // copy defect becomes permanent. Found by the independent adversarial pass,
  // which ran the real function instead of reading it.
  //
  // ONE FIELD LEFT OF EIGHTY IS THE MOST-READ INSTANCE OF THIS SENTENCE — it is
  // the last step before a physician succeeds.
  it('agrees the NOUN with the total and the VERB with the remainder', () => {
    expect(mappingsNotReadyScope(1, 80)).toBe('1 of 80 fields still needs confirming');
    expect(mappingsNotReadyScope(1, 12)).toBe('1 of 12 fields still needs confirming');
    // a one-field form: noun and verb agree because M === N === 1
    expect(mappingsNotReadyScope(1, 1)).toBe('1 of 1 field still needs confirming');
    // …and with no total at all the noun falls back to counting the remainder
    expect(mappingsNotReadyScope(1, null)).toBe('1 field still needs confirming');
    expect(mappingsNotReadyScope(2, null)).toBe('2 fields still need confirming');
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
    expect(msg).toContain('1 of 80 fields still needs confirming');
  });
});

// ============================================================================
// THE READINESS PREDICATE — newly executable, and that is the point.
// ----------------------------------------------------------------------------
// ⚠️ THE INDEPENDENT PASS MEASURED THAT **NO TEST ANYWHERE EXECUTED THIS
// PREDICATE.** It lived inline in `synthetic-test.ts`, which imports prisma,
// storage, the fill engine and the docx parser — so the header claim "the count
// is of FIELDS, not of reasons" guarded code nothing could load. It now lives
// in `../mappings-readiness`, a leaf, and these are the arms that claim was
// always meant to have.
// ============================================================================
describe('F16 — the readiness rule, executed rather than asserted about', () => {
  const CERTIFIED_OK = { status: 'certified', sourceType: 'extraction', clinicalConcept: 'gerd' };

  it('classifies each of the three reasons, and READY as null', () => {
    expect(unreadyReason(null)).toBe('no_mapping');
    expect(unreadyReason({ ...CERTIFIED_OK, status: 'needs_confirmation' })).toBe('unconfirmed');
    expect(unreadyReason({ ...CERTIFIED_OK, clinicalConcept: null })).toBe('no_concept');
    expect(unreadyReason(CERTIFIED_OK)).toBeNull();
  });

  // A manual field has no concept BY CONSTRUCTION and is ready once confirmed.
  it('a confirmed MANUAL field is ready with no concept', () => {
    expect(unreadyReason({ status: 'certified', sourceType: 'manual', clinicalConcept: null })).toBeNull();
    // …but an UNCONFIRMED manual field is still unconfirmed
    expect(
      unreadyReason({ status: 'needs_confirmation', sourceType: 'manual', clinicalConcept: null }),
    ).toBe('unconfirmed');
  });

  // ⚠️ ONE ENTRY PER FIELD, NOT PER REASON. A field that is BOTH unconfirmed
  // and concept-less must count ONCE. Counting reasons would tell a physician
  // with 6 blockers that there are 7 and send them hunting a seventh that does
  // not exist — the defect this item's own header names.
  it('counts FIELDS, not reasons — a doubly-blocked field is one entry', () => {
    const both = { status: 'needs_confirmation', sourceType: 'extraction', clinicalConcept: null };
    const out = collectUnready([
      { fieldId: 'ttf_a', mapping: both },
      { fieldId: 'ttf_b', mapping: both },
    ]);
    expect(out).toHaveLength(2);
    expect(out).toEqual(['ttf_a:unconfirmed', 'ttf_b:unconfirmed']);
  });

  // ⚠️ THE REASON CODE THE EARLY BRANCH USED TO GET WRONG. It classified with a
  // two-way `mapping ? 'unconfirmed' : 'no_mapping'` while filtering on the
  // three-way predicate, so a CERTIFIED field lacking only its concept was
  // reported as `unconfirmed` — sending the one reader of `blocking` to
  // re-confirm a field that was already confirmed. Both call sites now share
  // this function, so the two cannot drift again.
  it('a CERTIFIED field missing only its concept reports no_concept, never unconfirmed', () => {
    expect(
      collectUnready([{ fieldId: 'ttf_x', mapping: { ...CERTIFIED_OK, clinicalConcept: null } }]),
    ).toEqual(['ttf_x:no_concept']);
  });

  // ⚠️ NON-VACUITY. Every arm above asserts on something UNREADY; a predicate
  // that returned a reason for everything would satisfy them all. This proves
  // it discriminates — and pins the production partition while it does so.
  it('NON-VACUITY — the production shape reconciles to 6 of 80', () => {
    const fields = [
      // 74 confirmed with concepts, as production holds
      ...Array.from({ length: 74 }, (_, i) => ({
        fieldId: `ttf_ok_${i}`,
        mapping: CERTIFIED_OK,
      })),
      // 5 manual awaiting confirmation + 1 verified_note_selection, as measured
      ...Array.from({ length: 5 }, (_, i) => ({
        fieldId: `ttf_m_${i}`,
        mapping: { status: 'needs_confirmation', sourceType: 'manual', clinicalConcept: null },
      })),
      {
        fieldId: 'ttf_v_0',
        mapping: {
          status: 'needs_confirmation',
          sourceType: 'verified_note_selection',
          clinicalConcept: 'exam_side',
        },
      },
    ];
    expect(fields).toHaveLength(80);
    const out = collectUnready(fields);
    expect(out).toHaveLength(6);
    // and the sentence a physician would actually have read on 2026-08-17
    expect(mappingsNotReadyScope(out.length, fields.length)).toBe(
      '6 of 80 fields still need confirming',
    );
  });

  it('a fully ready form produces NOTHING — the gate can be satisfied', () => {
    expect(collectUnready([{ fieldId: 'ttf_a', mapping: CERTIFIED_OK }])).toEqual([]);
  });
});

// ============================================================================
// ⚠️ THE DIRECTION WORD IS PINNED TO THE ACTUAL RENDER ORDER.
// ----------------------------------------------------------------------------
// The hint used to say "Open the field list ABOVE". Measured: the error banner
// renders at `native-template-manager.tsx:268-285` and `<ReviewWorkspace>` —
// which contains the field list — mounts at `:289`. The list is strictly BELOW
// the sentence that pointed above it.
//
// The old gate was GREEN on that, because it asserted only that the hint STRING
// was present in the message. A prose claim about layout is a wish until
// something asserts it, so this arm ties the word to the component: move the
// banner below the workspace and this reddens instead of silently inverting a
// physician's instructions.
// ============================================================================
// ============================================================================
// ⚠️ EVERY MAPPINGS_NOT_READY THROW SITE SUPPLIES ITS DETAIL.
// ----------------------------------------------------------------------------
// THIS ARM EXISTS BECAUSE THE FIX FOR THE GUARD HAD THE GUARD'S OWN DEFECT.
// The action-level gate mocks `runTemplateTwinSyntheticTest` wholesale, so it
// is BLIND to the partial landing where `synthetic-test.ts` regresses to
// throwing with no `{blocking, totalFields}` — the doctor silently drops back
// to "some fields still need confirming" with no number, which is F16's entire
// product. Writing the action arm did not close that; this does.
//
// ⚠️ HONEST LIMIT, STATED SO THIS IS NOT READ WIDER THAN IT IS: this is a
// SOURCE-TEXT assertion, not a membership one. `synthetic-test.ts` imports
// prisma, storage, the fill engine and the docx parser, so it cannot be loaded
// here at all — that is the whole reason the readiness rule was moved to a
// leaf. Text presence is not membership; this catches a throw site that stops
// passing detail, and would not catch one that passes a detail object built
// wrongly elsewhere.
// ============================================================================
describe('F16 — the refusal cannot ship without its numbers', () => {
  it('every MAPPINGS_NOT_READY throw carries totalFields', () => {
    const src = readFileSync(path.resolve(__dirname, '../synthetic-test.ts'), 'utf8');
    const sites = src.split("'MAPPINGS_NOT_READY',").slice(1);
    // ⚠️ NON-VACUITY. Three sites exist today; if a refactor collapses them the
    // count changes and this reddens rather than passing over an empty set —
    // the emptiness test that would otherwise assert nothing at all.
    expect(sites.length).toBe(3);
    for (const [i, tail] of sites.entries()) {
      // each throw's argument list, up to the closing of that `new …(…)`
      const args = tail.slice(0, tail.indexOf(');'));
      expect(args, `MAPPINGS_NOT_READY throw site ${i + 1} of ${sites.length}`).toContain(
        'totalFields',
      );
      expect(args, `MAPPINGS_NOT_READY throw site ${i + 1} of ${sites.length}`).toContain(
        'blocking',
      );
    }
  });
});

describe('F16 — the route hint points where the field list actually is', () => {
  const MANAGER = path.resolve(
    __dirname,
    '../../../app/settings/note-format/native-template-manager.tsx',
  );

  it('the error banner renders BEFORE the field list, which is what makes "below" true', () => {
    const src = readFileSync(MANAGER, 'utf8');
    const banner = src.indexOf('{error && (');
    const workspace = src.indexOf('<ReviewWorkspace');
    // positive control: both anchors exist. A -1 from either would otherwise
    // satisfy `banner < workspace` by accident and assert nothing.
    expect(banner).toBeGreaterThan(-1);
    expect(workspace).toBeGreaterThan(-1);
    expect(banner).toBeLessThan(workspace);
    expect(MAPPINGS_NOT_READY_ROUTE_HINT).toContain('below');
    expect(MAPPINGS_NOT_READY_ROUTE_HINT).not.toContain('above');
  });
});
