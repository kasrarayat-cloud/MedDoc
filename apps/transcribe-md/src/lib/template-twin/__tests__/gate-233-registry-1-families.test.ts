// ============================================================================
// #233 REGISTRY-1, families 1 / 2 / 4 — the concepts the acceptance needs.
// ----------------------------------------------------------------------------
// The eleven-row acceptance came back 🟡 with four rows blocked by one cause:
// the closed registry had no term for them. Three of the four are here
// (`past_surgical_history`, `social_history.marital_status`,
// `total_time_minutes`); the fourth, `visit_metadata.*`, is ruling #234's own
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
  REGISTRY_SUBCONCEPTS,
} from '../concept-registry';
import { projectEncounterFacts } from '../encounter-facts';
import { narrativeSentence } from '../verification-encounter';
import { isListValuedNarrative } from '../field-value-derivation';

const QUOTE = 'the doctor said so';
function project(entities: Record<string, unknown>) {
  return projectEncounterFacts({
    mode: 'dictation',
    contextText: QUOTE,
    entities: entities as unknown as Parameters<typeof projectEncounterFacts>[0]['entities'],
  });
}
const conceptOf = (facts: ReturnType<typeof project>, c: string) => facts.filter((f) => f.concept === c);

describe('#233 — the three families are REGISTERED', () => {
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

  it('⚠️ family 3 is NOT shipped here, and this file says so', () => {
    // #234 is its own change. If these ever pass without that change landing,
    // something registered them without their record-derived fact class.
    expect(isRegisteredConcept('visit_metadata.patient_name')).toBe(false);
    expect(isRegisteredConcept('visit_metadata.patient_age')).toBe(false);
    expect(isRegisteredConcept('visit_metadata.referring_physician')).toBe(false);
  });

  it('marital_status is a SUB-CONCEPT of social_history, beside occupation', () => {
    expect(REGISTRY_SUBCONCEPTS.social_history).toContain('social_history.marital_status');
    expect(REGISTRY_SUBCONCEPTS.social_history).toContain('social_history.occupation');
  });
});

describe('#233 — the projector emits them, and DISCRIMINATES', () => {
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
    // canon 131's trap: the resolver's number arm refuses a value carrying a
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

  it('an absent family projects nothing — no phantom facts', () => {
    const facts = project({});
    for (const c of ['past_surgical_history', 'social_history.marital_status', 'total_time_minutes']) {
      expect(conceptOf(facts, c), c).toHaveLength(0);
    }
  });
});

describe('#233 — the downstream lists moved with the registry', () => {
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

  it('⚠️ NON-VACUITY: an unregistered concept has no sentence', () => {
    expect(narrativeSentence('past_dental_history')).toBeNull();
  });

  it('the total-time sentence states a number the extractor may quote', () => {
    // The extractor is forbidden from COMPUTING a total, so the self-test must
    // say one aloud or the field can never fill.
    expect(narrativeSentence('total_time_minutes')).toMatch(/forty five minutes/i);
  });
});
