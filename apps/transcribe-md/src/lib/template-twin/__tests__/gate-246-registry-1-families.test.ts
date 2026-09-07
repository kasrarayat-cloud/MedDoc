// ============================================================================
// #246 REGISTRY-1, families 1 / 2 / 4 — the concepts the acceptance needs.
// ----------------------------------------------------------------------------
// The eleven-row acceptance came back 🟡 with four rows blocked by one cause:
// the closed registry had no term for them. Three of the four are here
// (`past_surgical_history`, `social_history.marital_status`,
// `total_time_minutes`); the fourth, `visit_metadata.*`, is ruling #247's own
// change and is asserted REFUSED below so this file records which half shipped.
//
// ⚠️ THE DEFECT THIS CLOSES IS NOT "A MISSING CONCEPT". It is that the proposer
// mapped the owner's `Past Surgical History` controls to `past_medical_history`
// and `Marital status` to `social_history.occupation` — the nearest registered
// terms. Certifying those would have printed the patient's CONDITIONS into a
// surgical field and their OCCUPATION into marital status, in a signed note.
// So the arms that matter are the DISCRIMINATION ones: the new concepts must be
// distinct from the neighbours the proposer would otherwise have reached for.
// ============================================================================
import { describe, expect, it, vi } from 'vitest';

vi.mock('@meddoc/db', () => ({ default: {} }));
vi.mock('@/lib/audit', () => ({ logAudit: vi.fn() }));

import {
  isRegisteredConcept,
  REGISTRY_CONCEPTS,
  REGISTRY_SUBCONCEPTS,
} from '../concept-registry';
import { TEMPLATE_TWIN_CANONICAL_CONCEPT_GUIDANCE } from '../semantic-mapping';
import { projectEncounterFacts } from '../encounter-facts';
import { narrativeSentence } from '../verification-encounter';
import { isListValuedNarrative } from '../field-value-derivation';
import { EncounterFactSchema } from '../ir';

const QUOTE = 'the doctor said so';
function project(entities: Record<string, unknown>) {
  return projectEncounterFacts({
    mode: 'dictation',
    contextText: QUOTE,
    entities: entities as unknown as Parameters<typeof projectEncounterFacts>[0]['entities'],
  });
}
const conceptOf = (facts: ReturnType<typeof project>, c: string) => facts.filter((f) => f.concept === c);

describe('#246 — the three families are REGISTERED', () => {
  it('all three are admitted', () => {
    expect(isRegisteredConcept('past_surgical_history')).toBe(true);
    expect(isRegisteredConcept('social_history.marital_status')).toBe(true);
    expect(isRegisteredConcept('total_time_minutes')).toBe(true);
  });

  it('⚠️ NON-VACUITY: the registry still REFUSES an unregistered concept', () => {
    // Without this every arm above is satisfied by a predicate that returns
    // true for everything.
    expect(isRegisteredConcept('past_dental_history')).toBe(false);
    expect(isRegisteredConcept('social_history.favourite_colour')).toBe(false);
  });

  it('⚠️ family 3 SHIPPED SEPARATELY, and the sentinel flipped WITH its fact class', () => {
    // This arm used to assert all three were ABSENT. That was correct while
    // #246 was the only change on the branch: registering a record-derived
    // concept without `sourceType: 'visit_record'` behind it would have let a
    // patient's name be filled and reported as dictation.
    //
    // ⚠️ IT IS INVERTED RATHER THAN DELETED, AND THE CONDITION IT GUARDED IS
    // RE-STATED AS THE THING THAT MUST NOW BE TRUE. The sentinel's real claim
    // was never "these are unregistered" — it was "these are never registered
    // WITHOUT their fact class". So the class is asserted here too, and a
    // future edit that drops `visit_record` while leaving the concepts
    // registered reddens exactly this arm.
    expect(isRegisteredConcept('visit_metadata.patient_name')).toBe(true);
    expect(isRegisteredConcept('visit_metadata.patient_age')).toBe(true);
    expect(isRegisteredConcept('visit_metadata.referring_physician')).toBe(true);
    expect(EncounterFactSchema.shape.sourceType.unwrap().options).toContain(
      'visit_record',
    );
  });

  it('marital_status is a SUB-CONCEPT of social_history, beside occupation', () => {
    expect(REGISTRY_SUBCONCEPTS.social_history).toContain('social_history.marital_status');
    expect(REGISTRY_SUBCONCEPTS.social_history).toContain('social_history.occupation');
  });
});

describe('#246 — the projector emits them, and DISCRIMINATES', () => {
  it('a surgical history projects `past_surgical_history`, NOT `past_medical_history`', () => {
    const facts = project({
      past_surgical_history: [{ procedure: 'laparoscopic cholecystectomy', evidence_quote: QUOTE }],
    });
    expect(conceptOf(facts, 'past_surgical_history')).toHaveLength(1);
    expect(conceptOf(facts, 'past_surgical_history')[0]!.value).toBe('laparoscopic cholecystectomy');
    // ⚠️ THE ARM THAT MATTERS — the wrong concept must be EMPTY.
    expect(conceptOf(facts, 'past_medical_history')).toHaveLength(0);
  });

  it('and the two do not bleed the other way either', () => {
    const facts = project({
      past_medical_history: [{ condition: 'type 2 diabetes mellitus', evidence_quote: QUOTE }],
    });
    expect(conceptOf(facts, 'past_medical_history')).toHaveLength(1);
    expect(conceptOf(facts, 'past_surgical_history')).toHaveLength(0);
  });

  it('marital status projects its OWN sub-concept, never occupation', () => {
    const facts = project({
      social_history: { marital_status: { status: 'married', evidence_quote: QUOTE } },
    });
    expect(conceptOf(facts, 'social_history.marital_status')).toHaveLength(1);
    expect(conceptOf(facts, 'social_history.marital_status')[0]!.value).toBe('married');
    // ⚠️ occupation is what the proposer reached for before this existed.
    expect(conceptOf(facts, 'social_history.occupation')).toHaveLength(0);
  });

  it('⚠️ total_time_minutes carries NO UNIT in its value, and the number beside it', () => {
    // canon 134's trap: the resolver's number arm refuses a value carrying a
    // unit, so "45 minutes" would fail where "45" resolves.
    const facts = project({
      total_time_minutes: { minutes: 45, evidence_quote: QUOTE },
    });
    const [fact] = conceptOf(facts, 'total_time_minutes');
    expect(fact).toBeTruthy();
    expect(fact!.value).toBe('45');
    expect(String(fact!.value)).not.toMatch(/minute/i);
    expect(fact!.number).toBe(45);
  });

  it('⚠️ a TOTAL TIME is a QUANTITY — its polarity is STATED, never inferred from the prose', () => {
    // The adversarial pass demonstrated both routes by which `inferPolarity`
    // denied a plainly affirmative total. A denied fact is then WITHHELD for
    // every kind except checkbox, so the doctor's own billing figure renders
    // blank — and on a narrative control the reason is certification-exempt,
    // so it blanks SILENTLY and still certifies green.
    const polarityOf = (quote: string, minutes: number) => {
      const f = project({ total_time_minutes: { minutes, evidence_quote: quote } });
      return conceptOf(f, 'total_time_minutes')[0]?.polarity;
    };

    // Route 1 — the digits ARE locatable, but CLAUSE_BREAK is /[.;\n]/ and a
    // COMMA is not one, so an unrelated ROS denial used to govern the number.
    expect(polarityOf('No fever, total time 25 minutes.', 25)).toBe('affirmed');
    // Route 2 — the quote SPELLS the number, so String(40) is unlocatable and
    // polarity fell back to the UNSCOPED whole-quote denial test.
    expect(polarityOf('Total time of forty minutes spent, no separate procedure performed.', 40)).toBe('affirmed');
    // And a clean quote was always fine — this is the control that says the
    // arms above are about the denial routes, not about polarity in general.
    expect(polarityOf('Total time 25 minutes.', 25)).toBe('affirmed');
  });

  it('⚠️ DISCRIMINATION: polarity inference still WORKS everywhere else', () => {
    // Without this, the arm above is satisfied by having disabled inference
    // globally. A denied ROS finding must still come back denied.
    const facts = project({
      ros: [{ system: 'constitutional', finding: 'fever', polarity: 'denied', evidence_quote: 'Denies fever.' }],
    });
    const ros = facts.filter((f) => f.concept.startsWith('ros.'));
    expect(ros.length).toBeGreaterThan(0);
    expect(ros[0]!.polarity).toBe('denied');
  });

  it('an absent family projects nothing — no phantom facts', () => {
    const facts = project({});
    for (const c of ['past_surgical_history', 'social_history.marital_status', 'total_time_minutes']) {
      expect(conceptOf(facts, c), c).toHaveLength(0);
    }
  });
});

describe('#246 — the downstream lists moved with the registry', () => {
  it('a surgical history ACCUMULATES, like the medical one', () => {
    // A form with three "Past Surgical History" bullets must get three
    // procedures, not one procedure and two blanks.
    //
    // ⚠️ DRIVEN THROUGH THE SHIPPED PREDICATE. The first version of this arm
    // imported `isAccumulatingNarrativeConcept`, WHICH DOES NOT EXIST — the
    // real entry point is `isListValuedNarrative(field, mapping)` and it takes
    // the field too, because a `single_select` bound to the same concept must
    // NOT accumulate. An arm calling a symbol that is not there is canon 119's
    // shape: it measures the test, not the code.
    const narrative = { kind: 'narrative_text' } as unknown as Parameters<typeof isListValuedNarrative>[0];
    const select = { kind: 'single_select' } as unknown as Parameters<typeof isListValuedNarrative>[0];
    const mapping = (c: string) => ({ clinicalConcept: c }) as unknown as Parameters<typeof isListValuedNarrative>[1];

    expect(isListValuedNarrative(narrative, mapping('past_surgical_history'))).toBe(true);
    expect(isListValuedNarrative(narrative, mapping('past_medical_history'))).toBe(true);
    // ⚠️ NON-VACUITY, both ways: an unlisted concept does not accumulate, and
    // neither does a NON-narrative field on a listed one.
    expect(isListValuedNarrative(narrative, mapping('exam.general'))).toBe(false);
    expect(isListValuedNarrative(select, mapping('past_surgical_history'))).toBe(false);
  });

  it('the self-test can SAY each of them', () => {
    // ⚠️ A concept with no sentence is a control the certification self-test
    // leaves not_mentioned — it would prove nothing about the new concept.
    for (const c of ['past_surgical_history', 'social_history.marital_status', 'total_time_minutes']) {
      expect(narrativeSentence(c), c).toBeTruthy();
    }
  });

  it('⚠️ REGISTERED **AND** OFFERED — a concept the proposer is never told about is unmappable', () => {
    // The pass found `total_time_minutes` in REGISTRY_CONCEPTS but NOT in the
    // guidance list that reaches the proposer's prompt, so a "Total minutes"
    // control could only ever have been mapped by hand.
    //
    // ⚠️ SCOPED TO THE THREE THIS CHANGE ADDED, DELIBERATELY. Guidance is
    // partial BY DESIGN — it lists sub-concepts (`medication.name`) rather than
    // families (`medication`), and omits the measurement kinds — so a
    // "every registry concept appears here" arm would red on arrival. Measured
    // before writing this: 11 registry concepts are legitimately absent.
    for (const c of ['past_surgical_history', 'social_history.marital_status', 'total_time_minutes']) {
      expect(REGISTRY_CONCEPTS.includes(c) || Object.values(REGISTRY_SUBCONCEPTS).flat().includes(c), `${c} registered`).toBe(true);
      expect(TEMPLATE_TWIN_CANONICAL_CONCEPT_GUIDANCE, `${c} offered to the proposer`).toContain(c);
    }
  });

  it('⚠️ NON-VACUITY: an unregistered concept has no sentence', () => {
    expect(narrativeSentence('past_dental_history')).toBeNull();
  });

  it('the total-time sentence states a number the extractor may quote', () => {
    // The extractor is forbidden from COMPUTING a total, so the self-test must
    // say one aloud or the field can never fill.
    expect(narrativeSentence('total_time_minutes')).toMatch(/forty five minutes/i);
  });
});
