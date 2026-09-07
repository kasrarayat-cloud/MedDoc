/**
 * RULING #179(1) — THE ROS LEXICON IS CLOSED, AND THE SYMPTOM MUST BELONG TO
 * ITS OWN SYSTEM.
 *
 * ⚠️ THE LAST OF FOUR UNARMED #179 PARTS. Deleting the membership refinement —
 * `if (!allowed.includes(item.finding))` — redded **0 of 5922**. The guard was
 * present, commented, and proved by nothing.
 *
 * WHAT IT PREVENTS, in the schema's own words: a per-field enum cannot express
 * this, because the legal set DEPENDS on `system`. Without the refinement the
 * schema admits `{ system: 'cardiovascular', finding: 'heartburn' }` and the
 * projector emits `ros.cardiovascular.heartburn` — a concept the registry
 * admits by pattern and **no clause can honestly cover**. It would be a
 * finding filed under an organ system the doctor never said it about.
 *
 * ⚠️ AMENDED 2026-09-07 — THE GUARD NOW RESOLVES INSTEAD OF REFUSING, AND THE
 * REFUSAL IS WHY. Everything above is kept because it is still the reason the
 * closed set exists; what changed is the VERB.
 *
 * The membership check was a `.superRefine` over the ARRAY, so ONE off-lexicon
 * token failed the parse of the whole `ExtractedEntities` object — all 13 other
 * top-level clinical fields with it. MEASURED against the shipped schema, with
 * a populated payload:
 *
 *   lowercase "heartburn"       PARSE OK
 *   capitalised "Heartburn"     PARSE FAIL -> chief_complaint, medications AND
 *                                             ALLERGIES all discarded
 *   off-lexicon "burping"       PARSE FAIL -> same
 *   system alias "GI"           PARSE FAIL -> same
 *
 * ⚠️ AND THIS FILE COULD NOT SEE THAT, BY CONSTRUCTION. `MINIMAL` was
 * `{ chief_complaint: null, hpi: null }` — there was no other clinical content
 * in the payload, so "the parse failed" and "the parse failed AND took the
 * allergies with it" were indistinguishable here. The payload is now populated
 * for exactly that reason, and one arm asserts the surviving fields directly.
 *
 * ⚠️ THE CROSS-SYSTEM RULE IS NOT WEAKENED — it is enforced by COERCION rather
 * than refusal. `{cardiovascular, heartburn}` still never yields
 * `ros.cardiovascular.heartburn`; it yields `ros.cardiovascular.other` and
 * keeps "heartburn" in `finding_verbatim`, so the finding reaches the note
 * without claiming an organ system the doctor never named.
 *
 * Driven through the SHIPPED `ExtractedEntities` schema, not a reconstruction.
 */
import { describe, it, expect, vi } from 'vitest';

// ⚠️ THE SAME TWO MOCKS THE SIBLING ROS TEST CARRIES, AND FOR THE SAME REASON.
// `03-extract-entities` imports `@/lib/audit`, whose graph reaches next-auth
// and fails to resolve `next/server` under vitest. Without these the file does
// not IMPORT, and "no tests" is not a pass — it is an arm that never ran.
vi.mock('@meddoc/db', () => ({ default: {} }));
vi.mock('@/lib/audit', () => ({ logAudit: vi.fn() }));

import { ExtractedEntities, COMMON_CATEGORIES } from '../03-extract-entities';
import { ROS_SYSTEMS, symptomsFor, ROS_OTHER } from '@/lib/template-twin/ros-lexicon';

// ⚠️ POPULATED ON PURPOSE. A ROS defect used to discard every one of these,
// and a payload carrying only nulls cannot tell that apart from a clean
// refusal. `allergies` is here because this file's own subject once deleted it.
const MINIMAL = {
  chief_complaint: { statement: 'epigastric burning', evidence_quote: 'burning in my stomach' },
  hpi: null,
  medications: [{ name: 'omeprazole', evidence_quote: 'omeprazole 20 daily' }],
  allergies: [{ substance: 'penicillin', evidence_quote: 'allergic to penicillin' }],
};

function withRos(system: string, finding: string) {
  return ExtractedEntities.safeParse({
    ...MINIMAL,
    ros: [
      {
        system,
        finding,
        polarity: 'affirmed',
        evidence_quote: 'synthetic evidence for the arm',
      },
    ],
  });
}

describe('#179(1) — the ROS lexicon is closed and per-system', () => {
  it('NON-VACUITY: a symptom that BELONGS to its system parses', () => {
    // Without this every rejection below is equally consistent with a schema
    // that rejects all ROS entries, which would blank the section entirely.
    const system = ROS_SYSTEMS.find((s) => symptomsFor(s).some((x) => x !== ROS_OTHER));
    expect(system, 'the lexicon must have at least one addressable symptom').toBeTruthy();
    const finding = symptomsFor(system as string).find((x) => x !== ROS_OTHER) as string;
    const r = withRos(system as string, finding);
    expect(r.success, `${system}/${finding} should parse: ${JSON.stringify(r.error?.issues?.[0])}`).toBe(true);
  });

  it('⚠️ a symptom from a DIFFERENT system NEVER yields that pair — it becomes `other`', () => {
    // The exact case the schema comment names. `heartburn` is real and
    // `cardiovascular` is real; the PAIR is the lie, and the lie is still
    // refused — by coercion rather than by discarding the visit.
    const gi = ROS_SYSTEMS.find((s) => symptomsFor(s).includes('heartburn'));
    expect(gi, 'the lexicon should carry heartburn somewhere').toBeTruthy();
    expect(gi).not.toBe('cardiovascular');
    const r = withRos('cardiovascular', 'heartburn');
    expect(r.success).toBe(true);
    const item = r.success ? r.data.ros[0] : null;
    expect(item?.system).toBe('cardiovascular');
    expect(item?.finding).toBe(ROS_OTHER);
    // The doctor's word is not lost — that is what makes coercion honest.
    expect(item?.finding_verbatim).toBe('heartburn');
  });

  it('an INVENTED symptom becomes `other` in every system, keeping the words', () => {
    for (const s of ROS_SYSTEMS) {
      const r = withRos(s, 'definitely_not_a_symptom');
      expect(r.success, s).toBe(true);
      const item = r.success ? r.data.ros[0] : null;
      expect(item?.system, s).toBe(s);
      expect(item?.finding, s).toBe(ROS_OTHER);
      expect(item?.finding_verbatim, s).toBe('definitely_not_a_symptom');
    }
  });

  it('an INVENTED SYSTEM resolves to `unspecified`, and the symptom with it', () => {
    const r = withRos('phrenology', 'heartburn');
    expect(r.success).toBe(true);
    const item = r.success ? r.data.ros[0] : null;
    expect(item?.system).toBe('unspecified');
    expect(item?.finding).toBe(ROS_OTHER);
    expect(item?.system_verbatim).toBe('phrenology');
  });

  it('⚠️ THE POINT: an off-lexicon ROS token does NOT take the allergies with it', () => {
    // This is the arm the whole cluster exists for. Before the change this
    // payload came back `success: false` with no `data` at all.
    const r = withRos('gastrointestinal', 'burping');
    expect(r.success).toBe(true);
    if (!r.success) return;
    expect(r.data.allergies[0]?.substance).toBe('penicillin');
    expect(r.data.medications[0]?.name).toBe('omeprazole');
    expect(r.data.chief_complaint?.statement).toBe('epigastric burning');
    expect(r.data.ros[0]?.finding_verbatim).toBe('burping');
  });

  it('⚠️ CASE ALONE NEVER COST A VISIT AGAIN — and the concept stays addressable', () => {
    // This repository's own comment records that L3 capitalises the finding
    // habitually, and the projector was ALREADY lower-casing it one layer down.
    // The schema was the only thing rejecting the capital letter.
    const r = withRos('gastrointestinal', 'Heartburn');
    expect(r.success).toBe(true);
    const item = r.success ? r.data.ros[0] : null;
    expect(item?.finding).toBe('heartburn');
    expect(r.success ? r.data.allergies.length : 0).toBe(1);
  });

  it('DISCRIMINATION: resolution is not a schema that accepts anything', () => {
    // Every arm above is satisfied by a schema with no ROS validation at all.
    // This is what says otherwise: the resolver's RANGE is the closed set, so
    // a nonsense symptom cannot arrive as itself.
    const r = withRos('gastrointestinal', 'definitely_not_a_symptom');
    expect(r.success).toBe(true);
    expect(r.success ? r.data.ros[0]?.finding : null).not.toBe('definitely_not_a_symptom');
    // ...and a required field is still required.
    expect(
      ExtractedEntities.safeParse({
        ...MINIMAL,
        ros: [{ system: 'gastrointestinal', finding: 'nausea', evidence_quote: 'x' }],
      }).success,
      'a missing polarity must still fail',
    ).toBe(false);
  });

  it('⚠️ THE MODEL IS ACTUALLY SHOWN THE VOCABULARY IT IS JUDGED AGAINST', () => {
    // The schema enforced this list; NOTHING ever showed it to the model.
    // Measured on the assembled prompt text before the fix: 0 of 13 system
    // names and 1 of 72 symptom tokens — and that single hit was a FALSE
    // POSITIVE, the word "frequency" appearing in the medications bullet.
    // The model's only exposure to the closed set was the Zod error replayed
    // AFTER a rejection, so attempt 1 of every call was guessing blind.
    const prompt = String(COMMON_CATEGORIES);
    const missingSystems = ROS_SYSTEMS.filter((s) => !new RegExp(`\\b${s}\\b`).test(prompt));
    expect(missingSystems, `systems absent from the prompt: ${missingSystems.join(', ')}`).toEqual([]);

    const missingTokens: string[] = [];
    for (const system of ROS_SYSTEMS) {
      for (const token of symptomsFor(system)) {
        if (!new RegExp(`\\b${token}\\b`).test(prompt)) missingTokens.push(`${system}.${token}`);
      }
    }
    expect(missingTokens, `tokens absent from the prompt: ${missingTokens.slice(0, 6).join(', ')}`).toEqual([]);
  });

  it('DISCRIMINATION: the prompt arm is not satisfied by any long string', () => {
    // Without this, the arm above passes against a prompt that happens to
    // contain every word for unrelated reasons. A token the lexicon does NOT
    // carry must be absent, so the assertion is about the lexicon and not
    // about the prompt being verbose.
    const prompt = String(COMMON_CATEGORIES);
    expect(prompt.length, 'the prompt must be non-trivial').toBeGreaterThan(500);
    expect(/\bdefinitely_not_a_symptom\b/.test(prompt)).toBe(false);
  });

  it('the lexicon is the size the ruling claims — one definition, not a copy', () => {
    // #179(1): 13 systems, 72 addressable symptoms, plus `other`. Asserted
    // against the SHIPPED lexicon so a silent edit to either side is visible.
    expect(ROS_SYSTEMS.length).toBe(13);
    const addressable = ROS_SYSTEMS.reduce(
      (n, s) => n + symptomsFor(s).filter((x) => x !== ROS_OTHER).length,
      0,
    );
    expect(addressable).toBe(72);
  });
});
