/**
 * RULING #179(3) — A DECLARED `conceptScope` MATCHES BY SET MEMBERSHIP, AND IT
 * REPLACES `clinicalConcept` RATHER THAN WIDENING IT.
 *
 * ⚠️ THIS ARM EXISTS BECAUSE THE MANDATORY PASS FOUND THE GUARD HAD NONE.
 * Deleting the membership test — `if (!scope.has(...)) return false;`, the
 * whole of #179(3) — redded **0 of 660** twin tests, and no test anywhere in
 * the repository so much as mentioned `conceptScope`. The code was present,
 * reviewed and unproven.
 *
 * ⚠️ AND THE MATCHER IS DRIVEN, NEVER REIMPLEMENTED. `factMatchesMapping` is
 * exported for exactly this, and its own comment says why: an arm that
 * reproduced the rule inline is a control that passes whatever the shipped
 * matcher happens to do.
 *
 * ⚠️ FIXTURES ARE PARSED THROUGH THE SHIPPED SCHEMAS. A hand-built literal that
 * drifts from `SemanticMappingSchema` would still typecheck and would silently
 * stop describing the thing under test.
 */
import { describe, it, expect } from 'vitest';
import { factMatchesMapping } from '../index';
import {
  EncounterFactSchema,
  SemanticMappingSchema,
  type EncounterFact,
  type SemanticMapping,
} from '../../ir';

/** The clause under test scopes THREE symptoms out of its system's fourteen. */
const SCOPE = [
  'ros.gastrointestinal.heartburn',
  'ros.gastrointestinal.dysphagia',
  'ros.gastrointestinal.odynophagia',
] as const;

function mapping(over: Partial<SemanticMapping> = {}): SemanticMapping {
  return SemanticMappingSchema.parse({
    fieldId: 'ttf_0123456789abcdef01234567',
    sourceType: 'extraction',
    clinicalConcept: 'ros.gastrointestinal',
    expectedDataType: 'text',
    polarityBehavior: 'value_only',
    temporality: 'current',
    laterality: 'optional',
    unitPolicy: 'not_applicable',
    approvedSynonyms: [],
    required: false,
    blankPolicy: 'blank',
    unknownPolicy: 'blank',
    practiceDefault: null,
    status: 'certified',
    conceptScope: [...SCOPE],
    ...over,
  });
}

function fact(concept: string, over: Partial<EncounterFact> = {}): EncounterFact {
  return EncounterFactSchema.parse({
    factId: 'ttfact_000000000000000000000001',
    sourceType: 'encounter_evidence',
    concept,
    value: 'yes',
    polarity: 'affirmed',
    temporality: 'current',
    experiencer: 'patient',
    laterality: 'not_applicable',
    number: null,
    unit: null,
    speaker: 'Doctor',
    sourceTranscriptOffsets: { start: 0, end: 20 },
    audioTimestampSeconds: null,
    evidenceAnchorIds: ['anchor-1'],
    evidenceQuote: 'Synthetic evidence',
    quality: { asr: 'high', evidence: 'direct' },
    segment: null,
    ...over,
  });
}

describe('#179(3) — conceptScope is set membership', () => {
  it('NON-VACUITY: a fact INSIDE the scope matches', () => {
    // Without this, every refusal below is equally consistent with a matcher
    // that simply always returns false.
    for (const c of SCOPE) {
      expect(factMatchesMapping(fact(c), mapping()), c).toBe(true);
    }
  });

  it('a fact OUTSIDE the scope does NOT match, even in the same system', () => {
    // `nausea` is a real member of the same ROS system and is NOT scoped.
    expect(factMatchesMapping(fact('ros.gastrointestinal.nausea'), mapping())).toBe(false);
  });

  it('⚠️ THE SYSTEM-LEVEL CONCEPT DOES NOT SATISFY A SCOPED CLAUSE', () => {
    // This is the defect #179(3) exists to end: a clause covering three of a
    // system's fourteen symptoms must not be answered by a fact that names the
    // system. Letting it through asserts the doctor addressed eleven symptoms
    // they never mentioned.
    expect(factMatchesMapping(fact('ros.gastrointestinal'), mapping())).toBe(false);
  });

  it('the scope REPLACES clinicalConcept — it does not widen it', () => {
    // The mapping's own clinicalConcept is `ros.gastrointestinal`. If the
    // matcher fell THROUGH to the concept check after a scope miss, this would
    // pass — which is precisely the fall-through the code warns about.
    const m = mapping({ clinicalConcept: 'ros.gastrointestinal.nausea' });
    expect(factMatchesMapping(fact('ros.gastrointestinal.nausea'), m)).toBe(false);
  });

  it('approvedSynonyms cannot smuggle a fact into a scoped clause either', () => {
    const m = mapping({ approvedSynonyms: ['ros.gastrointestinal.nausea'] });
    expect(factMatchesMapping(fact('ros.gastrointestinal.nausea'), m)).toBe(false);
  });

  it('temporality still applies INSIDE the scope', () => {
    // Membership is necessary, not sufficient. "The patient denies chest pain"
    // must not be answered by chest pain the patient had in 2019.
    const historical = fact(SCOPE[0], { temporality: 'historical' });
    expect(factMatchesMapping(historical, mapping())).toBe(false);
    expect(factMatchesMapping(historical, mapping({ temporality: 'historical' }))).toBe(true);
  });

  it('an ABSENT scope falls through to ordinary clinicalConcept matching', () => {
    // The scope is opt-in: unscoped mappings must behave exactly as before, or
    // this ruling would have silently changed every existing template.
    const unscoped = mapping({ conceptScope: undefined, clinicalConcept: 'ros.gastrointestinal' });
    expect(factMatchesMapping(fact('ros.gastrointestinal'), unscoped)).toBe(true);
    expect(factMatchesMapping(fact('ros.gastrointestinal.nausea'), unscoped)).toBe(false);
  });

  it('an EMPTY scope array also falls through — length 0 is not "matches nothing"', () => {
    const empty = mapping({ conceptScope: [] });
    expect(factMatchesMapping(fact('ros.gastrointestinal'), empty)).toBe(true);
  });
});
