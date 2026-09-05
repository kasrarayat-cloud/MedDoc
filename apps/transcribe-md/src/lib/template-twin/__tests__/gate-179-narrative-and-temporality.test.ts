/**
 * RULING #179(6) — TWO HALVES, BOTH FOUND UNARMED BY THE MANDATORY PASS.
 *
 * (a) NARRATIVE_SENTENCES may only carry concepts the extractor actually
 *     emits, and must cover the ROS lexicon it claims to serve.
 * (b) A NULL mapping temporality means `current`, NEVER `any`.
 *
 * ⚠️ (b) IS THE CLINICALLY SHARP ONE, AND IT REDDED NOTHING. Mutating "null
 * means current" into "null means any" passed **674 of 674** twin tests. The
 * shipped compiler emits null for scaffolded clauses, and the code's own
 * comment records what that cost: a refutation pass demonstrated a HISTORICAL,
 * resolved symptom matching a present-tense sentence — *"The patient denies
 * chest pain"* contradicted by chest pain the patient had in 2019.
 *
 * ⚠️ AND (a)'s SOURCE COMMENT CLAIMED AN ARM THAT DID NOT EXIST. It named
 * `gate-f5i2-narrative-encounter.test.ts` as asserting the table "with a
 * mutation that reddens both"; that file has ZERO references to it. The
 * load-time assertion is real and does fire — the claimed test was fiction.
 * A comment asserting coverage is what the next reader checks INSTEAD of the
 * tests, which is why it is corrected in source rather than quietly replaced.
 */
import { describe, it, expect } from 'vitest';
import { factMatchesMapping } from '../validation/index';
import { narrativeSentence } from '../verification-encounter';
import { isRegisteredConcept } from '../concept-registry';
import { ROS_SYSTEMS, symptomsFor, rosConcept, ROS_OTHER } from '../ros-lexicon';
import {
  SemanticMappingSchema,
  EncounterFactSchema,
  type SemanticMapping,
  type EncounterFact,
} from '../ir';

const FIELD_ID = 'ttf_0123456789abcdef01234567';
const CONCEPT = 'ros.gastrointestinal.heartburn';

function mapping(over: Partial<SemanticMapping> = {}): SemanticMapping {
  return SemanticMappingSchema.parse({
    fieldId: FIELD_ID,
    sourceType: 'extraction',
    clinicalConcept: CONCEPT,
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
    ...over,
  });
}

function fact(temporality: EncounterFact['temporality']): EncounterFact {
  return EncounterFactSchema.parse({
    factId: 'ttfact_000000000000000000000001',
    sourceType: 'encounter_evidence',
    concept: CONCEPT,
    value: 'yes',
    polarity: 'affirmed',
    temporality,
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
  });
}

describe('#179(6b) — a NULL mapping temporality means `current`, never `any`', () => {
  it('NON-VACUITY: a null-temporality mapping still matches a CURRENT fact', () => {
    // Without this the refusals below are consistent with a matcher that
    // rejects every null-temporality mapping, which would blank scaffolded
    // clauses entirely.
    expect(factMatchesMapping(fact('current'), mapping({ temporality: null }))).toBe(true);
  });

  it('⚠️ a HISTORICAL fact does NOT satisfy a null-temporality clause', () => {
    // The 2019 chest pain case. The compiler emits null for scaffolded
    // clauses, so this is the DEFAULT path, not an edge case.
    expect(factMatchesMapping(fact('historical'), mapping({ temporality: null }))).toBe(false);
  });

  it('⚠️ nor does a PLANNED fact — a symptom to watch for is not one reported', () => {
    expect(factMatchesMapping(fact('planned'), mapping({ temporality: null }))).toBe(false);
  });

  it('nor an UNKNOWN-temporality fact', () => {
    expect(factMatchesMapping(fact('unknown'), mapping({ temporality: null }))).toBe(false);
  });

  it('an EXPLICIT `any` still matches everything — null and `any` are different', () => {
    // This is the distinction the ruling turns on: `any` is a decision somebody
    // made; null is the absence of one, and absence must not be read as
    // permission.
    for (const t of ['current', 'historical', 'planned', 'unknown'] as const) {
      expect(factMatchesMapping(fact(t), mapping({ temporality: 'any' })), t).toBe(true);
    }
  });

  it('an EXPLICIT `historical` matches historical and not current', () => {
    expect(factMatchesMapping(fact('historical'), mapping({ temporality: 'historical' }))).toBe(true);
    expect(factMatchesMapping(fact('current'), mapping({ temporality: 'historical' }))).toBe(false);
  });
});

describe('#179(6a) — NARRATIVE_SENTENCES is bound to the registry and covers the lexicon', () => {
  it('NON-VACUITY: the lexicon is a real, populated set', () => {
    expect(ROS_SYSTEMS.length).toBeGreaterThanOrEqual(10);
    const total = ROS_SYSTEMS.reduce((n, s) => n + symptomsFor(s).length, 0);
    expect(total).toBeGreaterThanOrEqual(60);
  });

  it('every addressable ROS concept has a dictatable sentence', () => {
    // A concept the extractor can emit but the generator cannot dictate is a
    // field that can never be verified.
    const missing: string[] = [];
    for (const system of ROS_SYSTEMS) {
      for (const symptom of symptomsFor(system)) {
        if (symptom === ROS_OTHER) continue; // deliberately unaddressable
        const c = rosConcept(system, symptom);
        if (narrativeSentence(c) === null) missing.push(c);
      }
    }
    expect(missing, `concepts with no sentence: ${missing.slice(0, 8).join(', ')}`).toEqual([]);
  });

  it('⚠️ `ros.<system>.other` IS registered and IS dictatable — its exclusion is from SCOPES', () => {
    // ⚠️ CORRECTED BY MEASUREMENT. This arm first asserted `other` was not
    // dictatable; it is. The registry matches `ros.*` BY PATTERN, so every
    // `ros.<system>.<symptom>` is registered and the patterned generator
    // serves it. `other` exists precisely so a symptom outside the list is not
    // silently dropped — it must be speakable.
    const other = rosConcept(ROS_SYSTEMS[0], ROS_OTHER);
    expect(isRegisteredConcept(other)).toBe(true);
    expect(narrativeSentence(other)).not.toBeNull();
  });

  it('⚠️ and the REAL property: `other` cannot satisfy a clause scoped to named symptoms', () => {
    // This is what "excluded from every declared scope by construction" means,
    // and it is the half that carries clinical weight: a scaffolded clause
    // naming three symptoms must not be answered by a finding the extractor
    // could not place. Asserted through the shipped matcher.
    const scoped = mapping({
      conceptScope: [
        'ros.gastrointestinal.heartburn',
        'ros.gastrointestinal.dysphagia',
      ],
    });
    const otherFact = EncounterFactSchema.parse({
      ...fact('current'),
      concept: 'ros.gastrointestinal.other',
    });
    expect(factMatchesMapping(otherFact, scoped)).toBe(false);
  });

  it('a concept OUTSIDE the registry entirely has no sentence', () => {
    // The registry's pattern arm covers `ros.*`; something with no family at
    // all must still come back null, or the generator would dictate sentences
    // for fields no fact can ever fill.
    expect(isRegisteredConcept('completely.invented.concept')).toBe(false);
    expect(narrativeSentence('completely.invented.concept')).toBeNull();
  });
});
