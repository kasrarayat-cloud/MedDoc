// ============================================================================
// A REGEX ADMITTING A CONCEPT IS NOT A FACT REACHING A MAPPING.
// ----------------------------------------------------------------------------
// ⚠️ THIS ARM EXISTS BECAUSE THE CHEAPER ONE WOULD HAVE LIED. Asserting
// `isRegisteredConcept('ros.gastrointestinal') === true` proves a pattern
// compiles. It says nothing about whether a doctor's dictated symptom can
// reach a field on his form — and that gap is exactly where the defect lived:
// the extractor stated ROS with polarity, the projector emitted it, and the
// registry threw it away one step before a mapping could hold it.
//
// MEASURED BEFORE THE FIX, driving a GI-shaped dictation through the real
// projector:
//     ros.gastrointestinal  affirmed  registered=FALSE
//     ros.gastrointestinal  denied    registered=FALSE
//     exam.abdomen          affirmed  registered=true
//
// `isRegisteredConcept` gates which concept a MAPPING may be assigned
// (`semantic-mapping/index.ts:243,495`), and `factMatchesMapping` returns false
// on a null concept. So an unregistered concept is not a cosmetic gap: it is a
// field that can never be filled, by any dictation, ever.
//
// ⚠️ AND `exam.*` GETS THE SAME PROOF THOUGH IT WAS ALREADY REGISTERED.
// "Registered and emitted" had never been observed reaching a mapping on a
// consult-shaped field either — it was believed because two halves were each
// true separately, which is the same reasoning that hid the ROS gap.
// ============================================================================
import { describe, expect, it } from 'vitest';

import { isRegisteredConcept } from '../concept-registry';
import { projectEncounterFacts } from '../encounter-facts/index';
import { factMatchesMapping } from '../validation/index';

/** The owner's GI consult, in miniature: one symptom AFFIRMED (which would
 *  contradict his template's printed denial), one DENIED (which agrees with
 *  it), one exam finding. */
function giDictationFacts() {
  return projectEncounterFacts({
    mode: 'dictation',
    contextText: [
      'Doctor: The patient reports heartburn three times a week for two months.',
      'Doctor: He denies nausea or vomiting.',
      'Doctor: On exam the abdomen is tender in the right upper quadrant.',
    ].join('\n'),
    entities: {
      ros: [
        {
          system: 'gastrointestinal',
          finding: 'heartburn',
          polarity: 'affirmed',
          evidence_quote: 'The patient reports heartburn three times a week for two months.',
        },
        {
          system: 'gastrointestinal',
          finding: 'nausea',
          polarity: 'denied',
          evidence_quote: 'He denies nausea or vomiting.',
        },
        {
          system: 'gastrointestinal',
          finding: 'vomiting',
          polarity: 'denied',
          evidence_quote: 'He denies nausea or vomiting.',
        },
      ],
      exam_findings: [
        {
          system: 'abdomen',
          finding: 'tender in the right upper quadrant',
          evidence_quote: 'On exam the abdomen is tender in the right upper quadrant.',
        },
      ],
    },
  });
}

/** A mapping as the compiler would build one for a scaffolded clause. */
function mappingFor(concept: string) {
  return {
    fieldId: `ttf_${'a'.repeat(24)}`,
    sourceType: 'extraction',
    clinicalConcept: concept,
    expectedDataType: 'text',
    polarityBehavior: 'explicit_denial_allowed',
    temporality: 'current',
    laterality: 'not_applicable',
    unitPolicy: 'not_applicable',
    approvedSynonyms: [],
    required: false,
    blankPolicy: 'blank',
    unknownPolicy: 'blank',
    practiceDefault: null,
    status: 'supported',
  } as never;
}

/** The SHIPPED matcher, driven. No fallback, no reimplementation. */
function matches(fact: unknown, concept: string): boolean {
  return factMatchesMapping(fact as never, mappingFor(concept));
}

describe('a dictated ROS symptom reaches a mapped field, with polarity intact', () => {
  it('⚠️ NON-VACUITY: the dictation actually produces the three facts', () => {
    const facts = giDictationFacts();
    // ⚠️ FOUR, NOT THREE, AND THE EXTRA ONE IS THE RULING. "nausea or vomiting"
    // was ONE free-text finding; #179 addresses each symptom separately, so it
    // is now two facts. A doctor who denies both has denied both.
    expect(facts.length, 'the projector produced nothing — the arm cannot run').toBe(4);
  });

  it('⚠️ ros.* is ASSIGNABLE to a mapping — the gate that was closed', () => {
    // this is the line that was missing, expressed as the thing it gates:
    // `semantic-mapping` sets clinicalConcept to null unless this is true, and
    // a null concept can never match any fact.
    expect(isRegisteredConcept('ros.gastrointestinal.heartburn')).toBe(true);
    expect(isRegisteredConcept('ros.constitutional.fever')).toBe(true);
    // ⚠️ AND THE SYSTEM-LEVEL FORM IS NOW REFUSED, WHICH IS #179 ITSELF.
    // `ros.<system>` is what let ONE dictated symptom tick every clause in the
    // system: the checkbox arm reads only `fact.polarity`, so a concept that
    // cannot ADDRESS a specific clause affirms all of them alike. Keeping this
    // representable is the defect; refusing it is the fix.
    expect(isRegisteredConcept('ros.gastrointestinal')).toBe(false);
    // and the pattern must not have opened the door to anything
    expect(isRegisteredConcept('ros')).toBe(false);
    expect(isRegisteredConcept('rosacea.face')).toBe(false);
    expect(isRegisteredConcept('rosacea.face.itch')).toBe(false);
  });

  it('⚠️ the AFFIRMED symptom reaches a ros mapping, still affirmed', () => {
    const facts = giDictationFacts();
    const affirmed = facts.find(
      (f) => String(f.concept) === 'ros.gastrointestinal.heartburn' && f.polarity === 'affirmed',
    );
    expect(affirmed, 'no affirmed ROS fact was produced').toBeDefined();
    expect(matches(affirmed, 'ros.gastrointestinal.heartburn')).toBe(true);
    // THE CLINICAL POINT: this is the fact that must be able to OVERRIDE a
    // template's printed "the patient denies heartburn".
    expect(affirmed!.polarity).toBe('affirmed');
    expect(String(affirmed!.value)).toContain('heartburn');
  });

  it('⚠️ the DENIED symptom reaches the same mapping, still denied', () => {
    const facts = giDictationFacts();
    const denied = facts.find(
      (f) => String(f.concept) === 'ros.gastrointestinal.nausea' && f.polarity === 'denied',
    );
    expect(denied, 'no denied ROS fact was produced').toBeDefined();
    expect(matches(denied, 'ros.gastrointestinal.nausea')).toBe(true);
    // and it must NOT have been flattened into the affirmed one: two facts,
    // one concept, opposite polarity, both reaching the same mapping
    expect(denied!.polarity).toBe('denied');
  });

  it("⚠️ L3's STATED polarity wins over what the prose would imply", () => {
    // ⚠️ THE DISTINGUISHING INPUT, AND THE FIRST DRAFT LACKED IT. Removing the
    // projector's `polarity: item.polarity` pass-through redded ZERO, because
    // the fallback INFERS polarity from the quote and my quotes agreed with
    // what L3 stated. So the arm could not tell "stated by L3" from "guessed
    // back out of the prose" — which is the entire product of §02.9.
    //
    // Here they DISAGREE: the quote reads like an affirmation, L3 states a
    // denial. Only the pass-through can produce `denied`.
    const facts = projectEncounterFacts({
      mode: 'dictation',
      contextText: 'Doctor: Heartburn was discussed at length today.',
      entities: {
        ros: [
          {
            system: 'gastrointestinal',
            finding: 'heartburn',
            polarity: 'denied',
            evidence_quote: 'Heartburn was discussed at length today.',
          },
        ],
      },
    });
    expect(facts).toHaveLength(1);
    expect(
      facts[0]!.polarity,
      "the projector inferred polarity from the prose instead of using L3's",
    ).toBe('denied');
  });

  it('⚠️ a fact does NOT reach a mapping for a DIFFERENT concept', () => {
    // ⚠️ WITHOUT THIS, DELETING THE MATCHER'S CONCEPT CHECK REDS NOTHING —
    // every mapping in the arms above already carried the matching concept, so
    // a matcher that ignored concepts entirely passed all of them. A rule about
    // matching needs an input that must NOT match.
    const facts = giDictationFacts();
    const exam = facts.find((f) => String(f.concept) === 'exam.abdomen');
    expect(exam).toBeDefined();
    expect(
      matches(exam, 'ros.gastrointestinal.heartburn'),
      'an exam fact matched a ROS mapping',
    ).toBe(false);
    const ros = facts.find((f) => String(f.concept) === 'ros.gastrointestinal.heartburn');
    expect(matches(ros, 'exam.abdomen'), 'a ROS fact matched an exam mapping').toBe(false);
    expect(matches(ros, 'past_medical_history')).toBe(false);
    // ⚠️ THE INPUT THAT ONLY EXISTS AFTER #179, AND IT IS THE CLINICAL ONE.
    // Affirmed heartburn must NOT satisfy a clause about nausea. Under the old
    // `ros.<system>` concept both were the same string, so this could not even
    // be expressed — one symptom answered for the whole system.
    expect(
      matches(ros, 'ros.gastrointestinal.nausea'),
      'affirmed heartburn satisfied a nausea clause — the #179 defect',
    ).toBe(false);
  });

  it('⚠️ exam.* reaches a consult-shaped mapping too — proven, not assumed', () => {
    const facts = giDictationFacts();
    const exam = facts.find((f) => String(f.concept) === 'exam.abdomen');
    expect(exam, 'no exam fact was produced').toBeDefined();
    expect(isRegisteredConcept('exam.abdomen')).toBe(true);
    expect(matches(exam, 'exam.abdomen')).toBe(true);
    expect(String(exam!.value)).toContain('right upper quadrant');
  });
});
