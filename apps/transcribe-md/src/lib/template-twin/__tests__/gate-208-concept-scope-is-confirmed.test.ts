/**
 * ⚠️ RULING #208 — `conceptScope` IS A MAPPING, NOT A RENDER POLICY, SO IT IS
 * PROPOSED, VALIDATED, SURFACED AND CONFIRMED — NEVER SILENTLY ACCEPTED.
 *
 * The distinction the ruling turns on, and which a session missed badly enough
 * to escalate the question as undecidable:
 *
 *   `unmentionedPolicy` (keep/omit)  a RENDER POLICY  the model may NEVER author
 *   `clinicalConcept`                a MAPPING        model proposes, human confirms
 *   `conceptScope`                   a MAPPING        model proposes, human confirms
 *
 * #192/#193 forbid the model a render policy. #179(3) hands it a scope to
 * propose. Those are not in conflict; they are about different categories.
 *
 * ⚠️ WHAT WAS ACTUALLY BROKEN: `planAutoConfirm` spreads the whole mapping into
 * `status: 'certified'`, and `decideAutoConfirm` could not see `conceptScope` at
 * all — so a proposed scope was carried into a certified mapping by a decision
 * function that never looked at it. MEASURED, both trees, four cases:
 *
 *   before   no scope / valid scope / UNREGISTERED token / `.other`  -> confirm ALL FOUR
 *   after    no scope / valid scope                                  -> confirm
 *            UNREGISTERED token / `.other`                           -> DECLINE, with a reason
 *
 * The two good rows confirm in both trees, so this measures the new refusal and
 * not a decision function that stopped confirming.
 */
import { describe, it, expect } from 'vitest';
import { decideAutoConfirm } from '../auto-certify-eligibility';
import { isRegisteredConcept } from '../concept-registry';
import { isUnnamedRosConcept, rosConcept, ROS_OTHER, ROS_SYSTEMS } from '../ros-lexicon';

const NAMED = 'ros.gastrointestinal.heartburn';
const NAMED_2 = 'ros.gastrointestinal.nausea';
const UNREGISTERED = 'totally.invented.concept';
const UNNAMED = rosConcept('gastrointestinal', ROS_OTHER);

function decide(conceptScope?: readonly string[]) {
  return decideAutoConfirm({
    originalLabel: 'GI symptoms',
    criticality: 'routine',
    sourceType: 'extraction',
    hasClinicalConcept: true,
    conceptScope,
  });
}

describe('#208 — a declared conceptScope is confirmed, never silently accepted', () => {
  it('NON-VACUITY: the predicates this gate rests on actually discriminate', () => {
    // Without this, every refusal below is consistent with predicates that
    // answer the same way for everything.
    expect(isRegisteredConcept(NAMED)).toBe(true);
    expect(isRegisteredConcept(UNREGISTERED)).toBe(false);
    expect(isUnnamedRosConcept(NAMED)).toBe(false);
    expect(isUnnamedRosConcept(UNNAMED)).toBe(true);
    expect(ROS_SYSTEMS.length).toBeGreaterThanOrEqual(10);
  });

  it('CONTROL: a mapping with NO scope still auto-confirms', () => {
    // The overwhelming majority of fields carry no scope. If this reds, the
    // guard has blocked ordinary certification rather than a bad claim.
    expect(decide(undefined).confirm).toBe(true);
    expect(decide([]).confirm).toBe(true);
  });

  it('CONTROL: a scope naming only real symptoms still auto-confirms', () => {
    const d = decide([NAMED, NAMED_2]);
    expect(d.confirm, d.reason ?? '').toBe(true);
  });

  it('⚠️ a scope naming an UNREGISTERED concept is DECLINED, with a reason that names it', () => {
    // A concept no fact can carry makes the clause's coverage claim
    // undeliverable — certifying it would attest to something unreachable.
    const d = decide([NAMED, UNREGISTERED]);
    expect(d.confirm).toBe(false);
    expect(d.reason ?? '').toContain(UNREGISTERED);
  });

  it('⚠️ a scope containing `ros.<system>.other` is DECLINED — #179 rules it out of every scope', () => {
    // The lexicon's own header says `other` is "excluded from every declared
    // scope by construction", and `conceptMatches` refuses it at MATCH time.
    // Refusing it here makes the two readers agree instead of leaving a token
    // that certifies and can never match.
    const d = decide([UNNAMED]);
    expect(d.confirm).toBe(false);
    expect(d.reason ?? '').toContain(UNNAMED);
  });

  it('DISCRIMINATION: the refusal is about the SCOPE, not about the field', () => {
    // Same field, same everything, one differing scope entry — opposite
    // answers. Without this pair the refusals above are consistent with a
    // guard that declines this field for an unrelated reason.
    expect(decide([NAMED]).confirm).toBe(true);
    expect(decide([NAMED, UNREGISTERED]).confirm).toBe(false);
  });

  it('a manual field is unaffected — it has no concept BY CONSTRUCTION', () => {
    // `manual` short-circuits before any concept or scope question. A guard
    // that reached it would block the attest class, which certifies blank.
    const d = decideAutoConfirm({
      originalLabel: 'Technologist',
      criticality: 'routine',
      sourceType: 'manual',
      hasClinicalConcept: false,
      conceptScope: [UNREGISTERED],
    });
    expect(d.confirm).toBe(true);
  });
});
