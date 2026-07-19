import { describe, expect, it } from 'vitest';

import type {
  EncounterFact,
  SemanticMapping,
  TemplateField,
} from '../../ir';
import {
  resolveTemplateFields,
  withApprovedPracticeDefaultFacts,
} from '..';

const SHA = 'b'.repeat(64);

function field(
  idSeed: string,
  kind: TemplateField['kind'],
  overrides: Partial<TemplateField> = {},
): TemplateField {
  const fieldId = `ttf_${idSeed.repeat(24).slice(0, 24)}`;
  return {
    fieldId,
    kind,
    originalLabel: `Synthetic ${kind}`,
    labelSource: 'alias',
    displayOrder: 0,
    detectionStatus: 'certified',
    allowedOptions:
      kind === 'single_select' || kind === 'multi_select'
        ? [
            { ordinal: 0, displayText: 'Mild', value: 'Mild' },
            { ordinal: 1, displayText: 'Severe', value: 'Severe' },
          ]
        : [],
    rendererBinding: {
      partName: 'word/document.xml',
      bindingType: overrides.tableId ? 'table_cell' : 'content_control',
      path: `/synthetic/${idSeed}`,
      canonicalPath: `/synthetic/${idSeed}`,
      ordinal: 0,
      sdtId: '1',
      tag: null,
      alias: null,
      legacyName: null,
      tableIndex: overrides.tableId ? 0 : null,
      rowIndex: overrides.tableId ? 1 : null,
      cellIndex: overrides.tableId ? 0 : null,
      repeatAncestorPath: overrides.rowPrototype ? '/synthetic/table/row' : null,
      canonicalRepeatAncestorPath: overrides.rowPrototype
        ? '/synthetic/table/row'
        : null,
      sourceControlSha256: SHA,
      sourceBindingIdentitySha256: SHA,
      certifiedBindingSha256: SHA,
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
  const dataType: Record<TemplateField['kind'], SemanticMapping['expectedDataType']> = {
    narrative_text: 'text',
    single_select: 'single_select',
    multi_select: 'multi_select',
    checkbox: 'boolean',
    date: 'date',
    number: 'number',
    measurement: 'measurement',
  };
  return {
    fieldId: definition.fieldId,
    clinicalConcept: concept,
    expectedDataType: dataType[definition.kind],
    polarityBehavior:
      definition.kind === 'checkbox'
        ? 'affirmative_only'
        : 'value_only',
    temporality: 'current',
    laterality: 'optional',
    unitPolicy:
      definition.kind === 'measurement' ? 'required' : 'not_applicable',
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
  value: string | number | boolean,
  overrides: Partial<EncounterFact> = {},
): EncounterFact {
  const evidenceQuote = `Synthetic evidence ${seed}`;
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
    sourceTranscriptOffsets: { start: 0, end: evidenceQuote.length },
    audioTimestampSeconds: null,
    evidenceAnchorIds: [`anchor-${seed}`],
    evidenceQuote,
    quality: { asr: 'high', evidence: 'direct' },
    ...overrides,
  };
}

describe('resolveTemplateFields', () => {
  it('selects only an exact native dropdown option and retains evidence', () => {
    const definition = field('1', 'single_select');
    const semantic = mapping(definition, 'hpi.severity');
    const exact = fact('1', 'hpi.severity', 'Severe');
    const [resolved] = resolveTemplateFields({
      fields: [definition],
      mappings: [semantic],
      facts: [exact],
    });
    expect(resolved).toMatchObject({
      status: 'supported',
      value: 'Severe',
      selectedOptionOrdinal: 1,
      sourceFactIds: [exact.factId],
      evidenceAnchorIds: exact.evidenceAnchorIds,
    });

    const [nearMiss] = resolveTemplateFields({
      fields: [definition],
      mappings: [semantic],
      facts: [fact('2', 'hpi.severity', 'severe')],
    });
    expect(nearMiss).toMatchObject({
      status: 'needs_clinician_input',
      value: null,
      reasonCode: 'select_value_not_exact_option',
    });
  });

  it.each([
    {
      case: 'missing',
      sourceTranscriptOffsets: null,
    },
    {
      case: 'empty',
      sourceTranscriptOffsets: { start: 7, end: 7 },
    },
    {
      case: 'quote-length-inconsistent',
      sourceTranscriptOffsets: { start: 0, end: 3 },
    },
  ])('refuses to populate core evidence with a $case source span', ({
    sourceTranscriptOffsets,
  }) => {
    const definition = field('0', 'narrative_text');
    const semantic = mapping(definition, 'chief_complaint');
    const unanchored = fact('0', 'chief_complaint', 'Synthetic concern', {
      sourceTranscriptOffsets,
      // Resolver must not trust a provider/model quality label when the
      // independently checkable span contract is absent.
      quality: { asr: 'high', evidence: 'direct' },
    });

    const [resolved] = resolveTemplateFields({
      fields: [definition],
      mappings: [semantic],
      facts: [unanchored],
    });

    expect(resolved).toMatchObject({
      status: 'ambiguous',
      value: null,
      sourceFactIds: [unanchored.factId],
      evidenceAnchorIds: unanchored.evidenceAnchorIds,
      reasonCode: 'source_evidence_span_unresolved',
    });
  });

  it('resolves multi-select values in native option order and rejects partial near-matches', () => {
    const definition = field('a', 'multi_select');
    const semantic = mapping(definition, 'ros.respiratory');
    const severe = fact('b', 'ros.respiratory', 'Severe');
    const mild = fact('c', 'ros.respiratory', 'Mild');
    const [resolved] = resolveTemplateFields({
      fields: [definition],
      mappings: [semantic],
      facts: [severe, mild],
    });
    expect(resolved).toMatchObject({
      status: 'supported',
      value: ['Mild', 'Severe'],
    });

    const [nearMatch] = resolveTemplateFields({
      fields: [definition],
      mappings: [semantic],
      facts: [mild, fact('d', 'ros.respiratory', 'moderate')],
    });
    expect(nearMatch).toMatchObject({
      status: 'needs_clinician_input',
      value: null,
      reasonCode: 'multi_select_value_not_exact_option',
    });
  });

  it('requires approved checkbox polarity and blocks conflicting evidence', () => {
    const definition = field('2', 'checkbox');
    const semantic = mapping(definition, 'ros.respiratory', {
      polarityBehavior: 'explicit_denial_allowed',
    });
    const denied = fact('3', 'ros.respiratory', 'No cough', {
      polarity: 'denied',
    });
    const [resolved] = resolveTemplateFields({
      fields: [definition],
      mappings: [semantic],
      facts: [denied],
    });
    expect(resolved).toMatchObject({
      status: 'explicitly_denied',
      value: false,
    });

    const [conflict] = resolveTemplateFields({
      fields: [definition],
      mappings: [semantic],
      facts: [denied, fact('4', 'ros.respiratory', 'Cough', { polarity: 'affirmed' })],
    });
    expect(conflict).toMatchObject({ status: 'conflict', value: null });

    const [notMentioned] = resolveTemplateFields({
      fields: [definition],
      mappings: [semantic],
      facts: [],
    });
    expect(notMentioned).toMatchObject({
      status: 'not_mentioned',
      value: null,
    });

    const [affirmed] = resolveTemplateFields({
      fields: [definition],
      mappings: [semantic],
      facts: [fact('e', 'ros.respiratory', 'Cough reviewed', { polarity: 'affirmed' })],
    });
    expect(affirmed).toMatchObject({ status: 'supported', value: true });

    const [uncertifiedFalse] = resolveTemplateFields({
      fields: [definition],
      mappings: [
        mapping(definition, 'ros.respiratory', {
          polarityBehavior: 'affirmative_only',
        }),
      ],
      facts: [denied],
    });
    expect(uncertifiedFalse).toMatchObject({
      status: 'needs_clinician_input',
      value: null,
      reasonCode: 'checkbox_false_semantics_not_certified',
    });
  });

  it.each([
    { seed: 'a1', kind: 'narrative_text' as const, value: 'No synthetic concern', rowPrototype: false },
    { seed: 'b2', kind: 'single_select' as const, value: 'Mild', rowPrototype: false },
    { seed: 'c3', kind: 'multi_select' as const, value: 'Mild', rowPrototype: false },
    { seed: 'd4', kind: 'date' as const, value: '2026-07-15', rowPrototype: false },
    { seed: 'e5', kind: 'narrative_text' as const, value: 'No synthetic item', rowPrototype: true },
  ])(
    'keeps denied $kind evidence unresolved without an exact negative rendering policy (repeating=$rowPrototype)',
    ({ seed, kind, value, rowPrototype }) => {
      const definition = field(seed, kind, {
        ...(rowPrototype
          ? {
              tableId: `ttb_${'d'.repeat(20)}`,
              rowPrototype: true,
            }
          : {}),
      });
      const semantic = mapping(definition, 'hpi.severity', {
        polarityBehavior: 'explicit_denial_allowed',
      });
      const denied = fact(seed, 'hpi.severity', value, {
        polarity: 'denied',
      });
      const [resolved] = resolveTemplateFields({
        fields: [definition],
        mappings: [semantic],
        facts: [denied],
      });

      expect(resolved).toMatchObject({
        status: 'needs_clinician_input',
        value: null,
        reasonCode: 'negative_rendering_policy_missing',
        sourceFactIds: [denied.factId],
      });
    },
  );

  it('does not infer a missing unit or laterality', () => {
    const measurement = field('3', 'measurement', {
      criticality: 'number_unit',
    });
    const measureMapping = mapping(measurement, 'hpi.duration', {
      laterality: 'required',
      unitPolicy: 'required',
    });
    const missingUnit = fact('5', 'hpi.duration', 12, {
      number: 12,
      laterality: 'left',
    });
    const [unitResult] = resolveTemplateFields({
      fields: [measurement],
      mappings: [measureMapping],
      facts: [missingUnit],
    });
    expect(unitResult).toMatchObject({
      status: 'needs_clinician_input',
      reasonCode: 'measurement_unit_missing',
    });

    const missingLaterality = fact('6', 'hpi.duration', '12 mm', {
      number: 12,
      unit: 'mm',
      laterality: 'unknown',
    });
    const [lateralityResult] = resolveTemplateFields({
      fields: [measurement],
      mappings: [measureMapping],
      facts: [missingLaterality],
    });
    expect(lateralityResult).toMatchObject({
      status: 'needs_clinician_input',
      reasonCode: 'required_laterality_missing',
    });
  });

  it('resolves repeating table cells independently with row evidence keys', () => {
    const definition = field('4', 'narrative_text', {
      tableId: `ttb_${'4'.repeat(20)}`,
      rowPrototype: true,
      criticality: 'medication',
    });
    const semantic = mapping(definition, 'medication.name');
    const first = fact('7', 'medication.name', 'syntheticmed-a', {
      evidenceAnchorIds: ['med-row-a'],
    });
    const second = fact('8', 'medication.name', 'syntheticmed-b', {
      evidenceAnchorIds: ['med-row-b'],
    });
    const [resolved] = resolveTemplateFields({
      fields: [definition],
      mappings: [semantic],
      facts: [first, second],
    });
    expect(resolved.status).toBe('supported');
    expect(resolved.value).toEqual([
      {
        value: 'syntheticmed-a',
        sourceFactId: first.factId,
        evidenceAnchorId: 'med-row-a',
        optionOrdinal: null,
      },
      {
        value: 'syntheticmed-b',
        sourceFactId: second.factId,
        evidenceAnchorId: 'med-row-b',
        optionOrdinal: null,
      },
    ]);
  });

  it('uses only certified exact practice defaults with deterministic provenance evidence', () => {
    const definition = field('5', 'single_select');
    const semantic = mapping(definition, 'hpi.severity', {
      practiceDefault: 'Mild',
    });
    const facts = withApprovedPracticeDefaultFacts({
      fields: [definition],
      mappings: [semantic],
      facts: [],
    });
    const [resolved] = resolveTemplateFields({
      fields: [definition],
      mappings: [semantic],
      facts,
    });
    expect(resolved).toMatchObject({
      status: 'approved_practice_default',
      value: 'Mild',
      sourceFactIds: [facts[0]?.factId],
      evidenceAnchorIds: [facts[0]?.evidenceAnchorIds[0]],
    });
    expect(facts[0]?.sourceType).toBe('approved_practice_default');
  });

  it('fails closed for uncertified mappings outside synthetic certification tests', () => {
    const definition = field('6', 'narrative_text', {
      detectionStatus: 'recognized',
    });
    const semantic = mapping(definition, 'chief_complaint', {
      status: 'recognized',
    });
    const source = fact('9', 'chief_complaint', 'Synthetic symptom');
    const [production] = resolveTemplateFields({
      fields: [definition],
      mappings: [semantic],
      facts: [source],
    });
    expect(production.reasonCode).toBe('field_or_mapping_not_certified');

    const [synthetic] = resolveTemplateFields({
      fields: [definition],
      mappings: [semantic],
      facts: [source],
      allowUncertifiedForSyntheticTest: true,
    });
    expect(synthetic.status).toBe('supported');
  });

  it.each([
    'gad_7.total_score',
    'pregnancy.status',
    'exam.monofilament',
    'measurement.custom_ankle_width',
  ])('never resolves unsupported safe-alpha concept %s', (concept) => {
    const definition = field('f7', 'narrative_text');
    const [resolved] = resolveTemplateFields({
      fields: [definition],
      mappings: [mapping(definition, concept)],
      facts: [fact('f7', concept, 'Synthetic unsupported value')],
    });
    expect(resolved).toMatchObject({
      status: 'needs_clinician_input',
      value: null,
      reasonCode: 'tt_concept_unsupported_v1',
    });
  });
});
