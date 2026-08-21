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
      ordinal: 0,
      sdtId: '1',
      tag: null,
      alias: null,
      legacyName: null,
      rowLaterality: 'unknown' as const,
      tableIndex: overrides.tableId ? 0 : null,
      rowIndex: overrides.tableId ? 1 : null,
      cellIndex: overrides.tableId ? 0 : null,
      repeatAncestorPath: overrides.rowPrototype ? '/synthetic/table/row' : null,
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
    sourceType: 'extraction' as const,
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
    // F5-e. `Partial<EncounterFact>` types `segment` as `string | null |
    // undefined`, so spreading overrides could reintroduce `undefined` over a
    // field the fact type requires. Resolve it AFTER the spread — an override
    // that omits the key means "no segment", never "unset it".
    segment: overrides.segment ?? null,
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

  it('resolves multi-select values in native option order and rejects partial near-matches', () => {
    const definition = field('a', 'multi_select');
    const semantic = mapping(definition, 'ros.synthetic');
    const severe = fact('b', 'ros.synthetic', 'Severe');
    const mild = fact('c', 'ros.synthetic', 'Mild');
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
      facts: [mild, fact('d', 'ros.synthetic', 'moderate')],
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
  });

  it('does not infer a missing unit or laterality', () => {
    const measurement = field('3', 'measurement', {
      criticality: 'number_unit',
    });
    const measureMapping = mapping(measurement, 'exam.lesion_size', {
      laterality: 'required',
      unitPolicy: 'required',
    });
    const missingUnit = fact('5', 'exam.lesion_size', 12, {
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

    const missingLaterality = fact('6', 'exam.lesion_size', '12 mm', {
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

  /**
   * ⚠️ THIS ARM EXISTS BECAUSE AN UPSTREAM GATE WAS REMOVED ON ITS STRENGTH.
   *
   * Ruling #127 first blocked auto-certification of any laterality-critical
   * field the document did not structurally side. That blocker was removed once
   * it was measured that certification NEVER encodes a side — the mapping
   * declares what a field MEANS; the side is derived per visit from the
   * dictation. Removing an upstream gate on the strength of downstream
   * enforcement is legitimate only if that enforcement is ASSERTED, never
   * quoted from a comment.
   *
   * `required_laterality_missing` was already covered directly above.
   * `laterality_conflict` had ZERO test files — measured, not assumed. This is
   * that leg.
   */
  it('CONFLICTING sides in one encounter are REFUSED, never silently picked', () => {
    const sided = field('7', 'measurement', {});
    const sidedMapping = mapping(sided, 'exam.lesion_size', {
      laterality: 'required',
      unitPolicy: 'required',
    });
    const left = fact('8', 'exam.lesion_size', '12 mm', {
      number: 12,
      unit: 'mm',
      laterality: 'left',
    });
    const right = fact('9', 'exam.lesion_size', '12 mm', {
      number: 12,
      unit: 'mm',
      laterality: 'right',
    });
    const [conflicted] = resolveTemplateFields({
      fields: [sided],
      mappings: [sidedMapping],
      facts: [left, right],
    });
    expect(conflicted).toMatchObject({
      status: 'conflict',
      reasonCode: 'laterality_conflict',
    });
    // ⚠️ AND IT MUST NOT HAVE PICKED ONE. A conflict that still emits a value is
    // worse than no enforcement — it looks resolved.
    expect(conflicted.value ?? null).toBeNull();
  });

  it('NON-VACUITY: the same field with ONE side resolves cleanly', () => {
    const sided = field('7', 'measurement', {});
    const sidedMapping = mapping(sided, 'exam.lesion_size', {
      laterality: 'required',
      unitPolicy: 'required',
    });
    const onlyRight = fact('9', 'exam.lesion_size', '12 mm', {
      number: 12,
      unit: 'mm',
      laterality: 'right',
    });
    const [ok] = resolveTemplateFields({
      fields: [sided],
      mappings: [sidedMapping],
      facts: [onlyRight],
    });
    expect(ok.status).not.toBe('conflict');
    expect(ok.status).not.toBe('needs_clinician_input');
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
});
