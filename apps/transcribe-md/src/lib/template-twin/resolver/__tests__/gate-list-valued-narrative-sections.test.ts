import { describe, expect, it } from 'vitest';

import type { EncounterFact, SemanticMapping, TemplateField } from '../../ir';
import { validateTemplateTwin } from '../../validation';
import { resolveTemplateFields } from '..';

// GATE — a narrative SECTION accumulates facts; it does not contradict itself.
//
// WHAT WOULD MAKE THIS FAIL, stated before it was made to fail: revert the
// `isListValuedNarrative` branch in resolver/index.ts and every `expect` about a
// joined section flips to `status: 'conflict'`. Revert the matching branch in
// validation/assertionSupported and the joined value is refused as
// ASSERTION_NOT_SUPPORTED instead -- which is why BOTH halves are asserted here.
// A test that only checked the resolver would go green while the fill still
// blocked, one code further down.
//
// THE PRODUCTION CASE THIS COMES FROM: the owner's own form could not certify.
// Its synthetic encounter carried two past-medical-history conditions
// (hypertension, type 2 diabetes) and two plan items (continue medications,
// review in three months). Each pair was reported as
// `multiple_distinct_supported_values` -> FIELD_CONFLICT -> blocking, so
// certification failed on evidence that was clinically correct.

const SHA = 'b'.repeat(64);

function field(
  idSeed: string,
  kind: TemplateField['kind'],
  overrides: Partial<TemplateField> = {},
): TemplateField {
  return {
    fieldId: `ttf_${idSeed.repeat(24).slice(0, 24)}`,
    kind,
    originalLabel: `Synthetic ${kind}`,
    labelSource: 'alias',
    displayOrder: 0,
    detectionStatus: 'certified',
    allowedOptions: [],
    rendererBinding: {
      partName: 'word/document.xml',
      bindingType: 'content_control',
      path: `/synthetic/${idSeed}`,
      ordinal: 0,
      sdtId: '1',
      tag: null,
      alias: null,
      legacyName: null,
      rowLaterality: 'unknown' as const,
      tableIndex: null,
      rowIndex: null,
      cellIndex: null,
      repeatAncestorPath: null,
      sourceControlSha256: SHA,
      originalContentSha256: SHA,
    },
    required: false,
    unknownPolicy: 'blank',
    clinicallyMaterial: false,
    criticality: 'routine',
    tableId: null,
    rowPrototype: false,
    ...overrides,
  };
}

function mapping(
  definition: TemplateField,
  concept: string,
  overrides: Partial<SemanticMapping> = {},
): SemanticMapping {
  return {
    fieldId: definition.fieldId,
    sourceType: 'extraction' as const,
    clinicalConcept: concept,
    expectedDataType: definition.kind === 'measurement' ? 'measurement' : 'text',
    polarityBehavior: 'value_only',
    temporality: 'current',
    laterality: 'optional',
    unitPolicy: definition.kind === 'measurement' ? 'required' : 'not_applicable',
    approvedSynonyms: [],
    required: false,
    blankPolicy: 'blank',
    unknownPolicy: 'blank',
    practiceDefault: null,
    status: 'certified',
    ...overrides,
  };
}

function fact(
  seed: string,
  concept: string,
  value: string | number,
  overrides: Partial<EncounterFact> = {},
): EncounterFact {
  return {
    factId: `ttfact_${seed.repeat(24).slice(0, 24)}`,
    sourceType: 'encounter_evidence',
    concept,
    value,
    polarity: 'affirmed',
    temporality: 'current',
    experiencer: 'patient',
    laterality: 'not_applicable',
    number: typeof value === 'number' ? value : null,
    unit: null,
    speaker: 'Doctor',
    sourceTranscriptOffsets: { start: 0, end: 10 },
    audioTimestampSeconds: null,
    evidenceAnchorIds: [`anchor-${seed}`],
    evidenceQuote: `Synthetic evidence ${seed}`,
    quality: { asr: 'high', evidence: 'direct' },
    ...overrides,
    segment: overrides.segment ?? null,
  };
}

describe('list-valued narrative sections', () => {
  it('joins two past-medical-history facts instead of calling them a conflict', () => {
    const definition = field('a', 'narrative_text');
    const semantic = mapping(definition, 'past_medical_history');
    const facts = [
      fact('a', 'past_medical_history', 'Hypertension'),
      fact('b', 'past_medical_history', 'Type 2 diabetes mellitus'),
    ];

    const [resolved] = resolveTemplateFields({
      fields: [definition],
      mappings: [semantic],
      facts,
    });

    expect(resolved).toMatchObject({
      status: 'supported',
      value: 'Hypertension; Type 2 diabetes mellitus',
      reasonCode: 'list_valued_narrative_joined',
    });
    // BOTH facts must stay cited. A join that quietly dropped one would look
    // identical here without this row.
    expect(resolved?.sourceFactIds).toHaveLength(2);
  });

  it('accepts the joined value in validation — not merely in the resolver', () => {
    const definition = field('a', 'narrative_text');
    const semantic = mapping(definition, 'plan');
    const facts = [
      fact('a', 'plan', 'Continue current medications'),
      fact('b', 'plan', 'Follow-up in three months'),
    ];
    const resolutions = resolveTemplateFields({
      fields: [definition],
      mappings: [semantic],
      facts,
    });

    const result = validateTemplateTwin({
      fields: [definition],
      mappings: [semantic],
      facts,
      resolutions,
    });

    const blocking = result.issues.filter((i) => i.severity === 'blocking');
    expect(blocking).toEqual([]);
  });

  // ── REGISTRY-3 (#323) — SPECIMENS COUNT IS PRESERVED ────────────────────────
  // Found by the adversarial pass: two polyps sent to pathology in two separate
  // containers, both dictated "Sigmoid polyp", are TWO specimens a pathologist
  // numbers separately. Every OTHER accumulating narrative de-dups (a PMH must not
  // read "Hypertension; Hypertension"), so specimens is a count-preserving subset.
  //
  // WHAT WOULD MAKE THIS FAIL: remove 'procedure.specimens' from
  // COUNT_PRESERVING_NARRATIVE_CONCEPTS, and the two identical facts collapse — the
  // resolver's distinct-value gate takes the single-value path and prints ONE
  // specimen, silently dropping the other from a signed operative note.
  it('preserves TWO identical specimens rather than collapsing them to one', () => {
    const definition = field('a', 'narrative_text');
    const semantic = mapping(definition, 'procedure.specimens');
    const facts = [
      fact('a', 'procedure.specimens', 'Sigmoid polyp'),
      fact('b', 'procedure.specimens', 'Sigmoid polyp'),
    ];

    const resolutions = resolveTemplateFields({
      fields: [definition],
      mappings: [semantic],
      facts,
    });
    const [resolved] = resolutions;

    expect(resolved).toMatchObject({
      status: 'supported',
      value: 'Sigmoid polyp; Sigmoid polyp', // BOTH containers, not one
      reasonCode: 'list_valued_narrative_joined',
    });
    expect(resolved?.sourceFactIds).toHaveLength(2);

    // And validation accepts the count-preserving join (both readers agree).
    const result = validateTemplateTwin({
      fields: [definition],
      mappings: [semantic],
      facts,
      resolutions,
    });
    expect(result.issues.filter((i) => i.severity === 'blocking')).toEqual([]);
  });

  it('a NON-specimens list still de-dups two identical items (the contrast)', () => {
    // Two identical PMH facts are one condition, not two — count is NOT preserved.
    const definition = field('a', 'narrative_text');
    const semantic = mapping(definition, 'past_medical_history');
    const facts = [
      fact('a', 'past_medical_history', 'Hypertension'),
      fact('b', 'past_medical_history', 'Hypertension'),
    ];

    const [resolved] = resolveTemplateFields({
      fields: [definition],
      mappings: [semantic],
      facts,
    });

    expect(resolved?.status).toBe('supported');
    expect(resolved?.value).toBe('Hypertension'); // collapsed to one
  });

  it('STILL conflicts on two distinct measurements — the arm that must not regress', () => {
    const definition = field('c', 'measurement');
    const semantic = mapping(definition, 'measurement.diameter');
    const facts = [
      fact('c', 'measurement.diameter', 3.1, { number: 3.1, unit: 'cm' }),
      fact('d', 'measurement.diameter', 4.2, { number: 4.2, unit: 'cm' }),
    ];

    const [resolved] = resolveTemplateFields({
      fields: [definition],
      mappings: [semantic],
      facts,
    });

    expect(resolved?.status).toBe('conflict');
  });

  // ── EVERY ROW BELOW WAS A DEFECT FOUND BY THE ADVERSARIAL PASS ──────────────
  // The first version of this guard was a DENYLIST (`!concept.startsWith
  // ('measurement.')`). Each of these joined on a doctor's form with ZERO
  // blocking issues, and each was a FIELD_CONFLICT before the change. They are
  // pinned individually so no future "simplification" back to a prefix rule can
  // pass this file.

  it.each([
    // The CONCEPT arm alone. The original fixture was kind:'measurement' AND
    // concept:'measurement.*', failing BOTH arms — so either could be deleted
    // with the gate still green. This one is narrative_text, so only the
    // concept arm can hold it.
    ['measurement.diameter', '3.1 cm', '4.2 cm'],
    // Registry SYNONYMS of a measurement. concept-registry.ts's own docstring
    // records that a raw startsWith() test already shipped this bug once.
    ['exam.vascular.diameter', '3.1 mm', '4.2 mm'],
    ['exam.vascular.reflux_time', '2.4 seconds', '0.4 seconds'],
    // A severity is one value; an onset is one time.
    ['hpi.severity', 'moderate', 'severe'],
    ['hpi.onset', 'three days ago', 'two weeks ago'],
    // A study is one study, and a result is one result. "Normal; Abnormal" is a
    // contradiction wearing the costume of prose.
    ['test.name', 'Bilateral Detailed', 'Unilateral - Right Leg Limited'],
    ['test.venous_duplex.result', 'Normal', 'Abnormal'],
    // One coarse concept per exam system fans into EVERY field bound to it.
    ['exam.vascular', 'Vein patent and compressible', 'Vein shows chronic thickening'],
    // Reachable through the mapping editor, which does not registry-check.
    ['medication.dose', '10 mg', '20 mg'],
  ])('refuses to join %s — it is not an accumulating section', (concept, a, b) => {
    const definition = field('f', 'narrative_text');
    const semantic = mapping(definition, concept);
    const [resolved] = resolveTemplateFields({
      fields: [definition],
      mappings: [semantic],
      facts: [fact('a', concept, a), fact('b', concept, b)],
    });
    expect(resolved?.status).toBe('conflict');
  });

  it('canonicalises INTO the allowlist — a synonym of a listed section joins', () => {
    // ⚠️ THIS IS THE ROW THAT PINS canonicalConcept(), AND IT POINTS THE OTHER
    // WAY. Under an allowlist, a synonym of an EXCLUDED concept conflicts
    // whether or not you canonicalise — so the excluded rows above cannot see
    // the call at all. Mutating canonicalConcept() away left them all green.
    // `impression` is a REGISTRY_SYNONYMS entry for `assessment`, an ordinary
    // mapping on a consult form; without canonicalisation it falls out of the
    // allowlist and the section silently goes back to blocking.
    const definition = field('5', 'narrative_text');
    const semantic = mapping(definition, 'impression');
    const [resolved] = resolveTemplateFields({
      fields: [definition],
      mappings: [semantic],
      facts: [
        fact('a', 'impression', 'Chronic venous insufficiency'),
        fact('b', 'impression', 'Superficial reflux, left leg'),
      ],
    });
    expect(resolved).toMatchObject({
      status: 'supported',
      value: 'Chronic venous insufficiency; Superficial reflux, left leg',
      reasonCode: 'list_valued_narrative_joined',
    });
  });

  it('classifies by canonical concept, not raw text — NFKC included', () => {
    // A full-width 'm'. The fact matcher NFKC-normalises, so these facts DO
    // match the mapping; a classifier that does not would read a different
    // vocabulary from the one that fills.
    const concept = '\uFF4Deasurement.diameter';
    const definition = field('1', 'narrative_text');
    const semantic = mapping(definition, concept);
    const [resolved] = resolveTemplateFields({
      fields: [definition],
      mappings: [semantic],
      facts: [
        fact('a', 'measurement.diameter', '3.1 cm'),
        fact('b', 'measurement.diameter', '4.2 cm'),
      ],
    });
    expect(resolved?.status).toBe('conflict');
  });

  it('refuses to join across DIFFERENT lateralities, even in a listed section', () => {
    // The resolver's own laterality guard only fires when the mapping demands
    // laterality, and narrative mappings are 'optional' or null — so the refusal
    // inside joinListValuedNarrative is the only thing standing here. Without
    // it, a right-leg control asserts the left leg's finding.
    const definition = field('2', 'narrative_text');
    const semantic = mapping(definition, 'assessment', { laterality: 'optional' });
    const [resolved] = resolveTemplateFields({
      fields: [definition],
      mappings: [semantic],
      facts: [
        fact('a', 'assessment', 'Reflux present', { laterality: 'right' }),
        fact('b', 'assessment', 'No reflux', { laterality: 'left' }),
      ],
    });
    expect(resolved?.status).toBe('conflict');
  });

  it('does not write two DENIED facts into the form as an affirmative section', () => {
    const definition = field('3', 'narrative_text');
    const semantic = mapping(definition, 'past_medical_history', {
      polarityBehavior: 'explicit_denial_allowed',
    });
    const [resolved] = resolveTemplateFields({
      fields: [definition],
      mappings: [semantic],
      facts: [
        fact('a', 'past_medical_history', 'Hypertension', { polarity: 'denied' }),
        fact('b', 'past_medical_history', 'Type 2 diabetes', { polarity: 'denied' }),
      ],
    });
    expect(resolved?.value).not.toBe('Hypertension; Type 2 diabetes');
  });

  it('keeps byte-identity strict for a SINGLE-fact narrative (the join trims)', () => {
    // The validator arm is gated on citedFacts.length > 1 precisely so a
    // one-fact section cannot be accepted merely because it TRIMS to the fact.
    const definition = field('4', 'narrative_text');
    const semantic = mapping(definition, 'assessment');
    const untrimmed = fact('a', 'assessment', 'Chronic venous insufficiency ');
    const [resolved] = resolveTemplateFields({
      fields: [definition],
      mappings: [semantic],
      facts: [untrimmed],
    });
    const result = validateTemplateTwin({
      fields: [definition],
      mappings: [semantic],
      facts: [untrimmed],
      resolutions: [{ ...resolved!, value: 'Chronic venous insufficiency' }],
    });
    expect(
      result.issues.some((i) => i.code === 'ASSERTION_NOT_SUPPORTED'),
    ).toBe(true);
  });

  it('leaves a single-fact narrative exactly as it was', () => {
    const definition = field('e', 'narrative_text');
    const semantic = mapping(definition, 'assessment');
    const only = fact('e', 'assessment', 'Chronic venous insufficiency');

    const [resolved] = resolveTemplateFields({
      fields: [definition],
      mappings: [semantic],
      facts: [only],
    });

    expect(resolved).toMatchObject({
      status: 'supported',
      value: 'Chronic venous insufficiency',
    });
    expect(resolved?.reasonCode).not.toBe('list_valued_narrative_joined');
  });
});
