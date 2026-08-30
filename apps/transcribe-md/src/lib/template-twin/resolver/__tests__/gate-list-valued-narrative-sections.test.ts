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
