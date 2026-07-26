import { describe, expect, it } from 'vitest';

import type {
  EncounterFact,
  FieldResolution,
  SemanticMapping,
  TemplateField,
  TemplateTable,
} from '../../ir';
import {
  resolveTemplateFields,
  withApprovedPracticeDefaultFacts,
} from '../../resolver';
import { validateTemplateTwin } from '..';

const SHA = 'c'.repeat(64);
const NOW = '2026-07-15T12:00:00.000Z';

function field(
  seed: string,
  kind: TemplateField['kind'],
  overrides: Partial<TemplateField> = {},
): TemplateField {
  return {
    fieldId: `ttf_${seed.repeat(24).slice(0, 24)}`,
    kind,
    originalLabel: `Synthetic ${kind}`,
    labelSource: 'tag',
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
      path: `/document/${seed}`,
      ordinal: 0,
      sdtId: '1',
      tag: 'synthetic',
      alias: null,
      legacyName: null,
      rowLaterality: 'unknown' as const,
      tableIndex: overrides.tableId ? 0 : null,
      rowIndex: overrides.tableId ? 1 : null,
      cellIndex: overrides.tableId ? 0 : null,
      repeatAncestorPath: overrides.rowPrototype ? '/document/table/row' : null,
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
  const types: Record<TemplateField['kind'], SemanticMapping['expectedDataType']> = {
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
    expectedDataType: types[definition.kind],
    polarityBehavior:
      definition.kind === 'checkbox'
        ? 'explicit_denial_allowed'
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
    sourceTranscriptOffsets: { start: 0, end: 20 },
    audioTimestampSeconds: null,
    evidenceAnchorIds: [`anchor-${seed}`],
    evidenceQuote: `Synthetic evidence ${seed}`,
    quality: { asr: 'high', evidence: 'direct' },
    ...overrides,
  };
}

function validateOne(
  definition: TemplateField,
  semantic: SemanticMapping,
  facts: EncounterFact[],
  resolutions?: FieldResolution[],
) {
  const resolved =
    resolutions ??
    resolveTemplateFields({
      fields: [definition],
      mappings: [semantic],
      facts,
    });
  return validateTemplateTwin({
    fields: [definition],
    mappings: [semantic],
    facts,
    resolutions: resolved,
    now: NOW,
  });
}

describe('validateTemplateTwin', () => {
  it('accepts a fully supported exact dropdown resolution', () => {
    const definition = field('1', 'single_select');
    const semantic = mapping(definition, 'hpi.severity');
    const source = fact('1', 'hpi.severity', 'Severe');
    const result = validateOne(definition, semantic, [source]);
    expect(result).toEqual({
      valid: true,
      issues: [],
      checkedAt: NOW,
      validatorVersion: 'template-field-validator/1.0.0',
    });
  });

  it('uses persisted certification without mutating the immutable compiler IR', () => {
    const definition = field('a', 'single_select', {
      detectionStatus: 'recognized',
    });
    const semantic = mapping(definition, 'hpi.severity');
    const source = fact('a', 'hpi.severity', 'Severe');
    const uncertified = resolveTemplateFields({
      fields: [definition],
      mappings: [semantic],
      facts: [source],
    });
    expect(uncertified[0]?.status).toBe('needs_clinician_input');

    const certifiedFieldIds = [definition.fieldId];
    const resolved = resolveTemplateFields({
      fields: [definition],
      mappings: [semantic],
      facts: [source],
      certifiedFieldIds,
    });
    const result = validateTemplateTwin({
      fields: [definition],
      mappings: [semantic],
      facts: [source],
      resolutions: resolved,
      certifiedFieldIds,
      now: NOW,
    });

    expect(result.valid).toBe(true);
    expect(result.issues).toEqual([]);
    expect(definition.detectionStatus).toBe('recognized');
  });

  it('requires deterministic provenance facts for approved practice defaults', () => {
    const definition = field('f', 'single_select');
    const semantic = mapping(definition, 'hpi.severity', {
      practiceDefault: 'Mild',
    });
    const facts = withApprovedPracticeDefaultFacts({
      fields: [definition],
      mappings: [semantic],
      facts: [],
    });
    const resolutions = resolveTemplateFields({
      fields: [definition],
      mappings: [semantic],
      facts,
    });
    expect(
      validateTemplateTwin({
        fields: [definition],
        mappings: [semantic],
        facts,
        resolutions,
        now: NOW,
      }).valid,
    ).toBe(true);

    expect(
      validateTemplateTwin({
        fields: [definition],
        mappings: [semantic],
        facts: [],
        resolutions,
        now: NOW,
      }).issues.map((issue) => issue.code),
    ).toEqual(
      expect.arrayContaining([
        'SOURCE_FACT_MISSING',
        'EVIDENCE_ANCHOR_UNTRACEABLE',
        'PRACTICE_DEFAULT_INVALID',
      ]),
    );
  });

  it('independently rejects a non-option dropdown value and evidence tampering', () => {
    const definition = field('2', 'single_select');
    const semantic = mapping(definition, 'hpi.severity');
    const source = fact('2', 'hpi.severity', 'Severe');
    const tampered: FieldResolution = {
      fieldId: definition.fieldId,
      status: 'supported',
      value: 'Moderate',
      sourceFactIds: [source.factId],
      evidenceAnchorIds: ['untraceable-anchor'],
      selectedOptionOrdinal: null,
      reasonCode: 'synthetic_tamper',
      clinicianReviewed: false,
    };
    const result = validateOne(definition, semantic, [source], [tampered]);
    expect(result.valid).toBe(false);
    expect(result.issues.map((issue) => issue.code)).toEqual(
      expect.arrayContaining([
        'EVIDENCE_COVERAGE_INCOMPLETE',
        'EVIDENCE_ANCHOR_UNTRACEABLE',
        'ASSERTION_NOT_SUPPORTED',
        'DROPDOWN_NOT_EXACT_OPTION',
      ]),
    );
  });

  it('requires affirmative checkbox evidence', () => {
    const definition = field('3', 'checkbox', {
      criticality: 'allergy',
    });
    const semantic = mapping(definition, 'allergy.substance');
    const denied = fact('3', 'allergy.substance', 'No synthetic allergy', {
      polarity: 'denied',
    });
    const forged: FieldResolution = {
      fieldId: definition.fieldId,
      status: 'supported',
      value: true,
      sourceFactIds: [denied.factId],
      evidenceAnchorIds: denied.evidenceAnchorIds,
      selectedOptionOrdinal: null,
      reasonCode: 'synthetic_forged_checkbox',
      clinicianReviewed: false,
    };
    const result = validateOne(definition, semantic, [denied], [forged]);
    expect(result.valid).toBe(false);
    expect(result.issues.map((issue) => issue.code)).toContain(
      'CHECKBOX_AFFIRMATION_MISSING',
    );
  });

  it('blocks missing units, unresolved laterality, and invalid dates', () => {
    const measure = field('4', 'measurement', {
      criticality: 'number_unit',
      clinicallyMaterial: true,
    });
    const measureMap = mapping(measure, 'exam.synthetic_size', {
      unitPolicy: 'required',
      laterality: 'required',
    });
    const measureFact = fact('4', 'exam.synthetic_size', 12, {
      number: 12,
      unit: null,
      laterality: 'unknown',
    });
    const measureResolution: FieldResolution = {
      fieldId: measure.fieldId,
      status: 'supported',
      value: 12,
      sourceFactIds: [measureFact.factId],
      evidenceAnchorIds: measureFact.evidenceAnchorIds,
      selectedOptionOrdinal: null,
      reasonCode: 'synthetic_missing_unit',
      clinicianReviewed: false,
    };
    const measureResult = validateOne(
      measure,
      measureMap,
      [measureFact],
      [measureResolution],
    );
    expect(measureResult.issues.map((issue) => issue.code)).toEqual(
      expect.arrayContaining([
        'MEASUREMENT_UNIT_MISSING',
        'LATERALITY_UNRESOLVED',
      ]),
    );

    const date = field('5', 'date', { criticality: 'date_duration' });
    const dateMap = mapping(date, 'hpi.onset');
    const dateFact = fact('5', 'hpi.onset', '2026-02-30');
    const invalidDate: FieldResolution = {
      fieldId: date.fieldId,
      status: 'supported',
      value: '2026-02-30',
      sourceFactIds: [dateFact.factId],
      evidenceAnchorIds: dateFact.evidenceAnchorIds,
      selectedOptionOrdinal: null,
      reasonCode: 'synthetic_invalid_date',
      clinicianReviewed: false,
    };
    expect(
      validateOne(date, dateMap, [dateFact], [invalidDate]).issues.map(
        (issue) => issue.code,
      ),
    ).toContain('DATE_INVALID');
  });

  it('makes critical conflicts blocking while routine ambiguity remains visible', () => {
    const critical = field('6', 'narrative_text', {
      criticality: 'medication',
    });
    const criticalMap = mapping(critical, 'medication.name');
    const source = fact('6', 'medication.name', 'syntheticmed');
    const conflict: FieldResolution = {
      fieldId: critical.fieldId,
      status: 'conflict',
      value: null,
      sourceFactIds: [source.factId],
      evidenceAnchorIds: source.evidenceAnchorIds,
      selectedOptionOrdinal: null,
      reasonCode: 'synthetic_conflict',
      clinicianReviewed: true,
    };
    const criticalResult = validateOne(
      critical,
      criticalMap,
      [source],
      [conflict],
    );
    expect(criticalResult.valid).toBe(false);
    expect(criticalResult.issues).toContainEqual(
      expect.objectContaining({ code: 'FIELD_CONFLICT', severity: 'blocking' }),
    );

    const routine = field('7', 'narrative_text');
    const routineMap = mapping(routine, 'plan');
    const routineFact = fact('7', 'plan', 'Synthetic follow-up');
    const ambiguous: FieldResolution = {
      fieldId: routine.fieldId,
      status: 'ambiguous',
      value: null,
      sourceFactIds: [routineFact.factId],
      evidenceAnchorIds: routineFact.evidenceAnchorIds,
      selectedOptionOrdinal: null,
      reasonCode: 'synthetic_ambiguous',
      clinicianReviewed: false,
    };
    const routineResult = validateOne(
      routine,
      routineMap,
      [routineFact],
      [ambiguous],
    );
    expect(routineResult.valid).toBe(true);
    expect(routineResult.issues).toContainEqual(
      expect.objectContaining({ code: 'FIELD_AMBIGUOUS', severity: 'warning' }),
    );
  });

  it('blocks repeating-table overflow and clinically material unsupported elements', () => {
    const tableId = `ttb_${'8'.repeat(20)}`;
    const definition = field('8', 'narrative_text', {
      tableId,
      rowPrototype: true,
      criticality: 'medication',
    });
    const semantic = mapping(definition, 'medication.name');
    const facts = [
      fact('8', 'medication.name', 'syntheticmed-a'),
      fact('9', 'medication.name', 'syntheticmed-b'),
      fact('a', 'medication.name', 'syntheticmed-c'),
    ];
    const resolutions = resolveTemplateFields({
      fields: [definition],
      mappings: [semantic],
      facts,
    });
    const table: TemplateTable = {
      tableId,
      partName: 'word/document.xml',
      path: '/document/table[1]',
      kind: 'repeating_table',
      displayOrder: 0,
      gridColumnWidths: [2000],
      rowCount: 2,
      repeatPrototypeRow: 1,
      maxRows: 2,
      cells: [],
    };
    const result = validateTemplateTwin({
      fields: [definition],
      mappings: [semantic],
      facts,
      resolutions,
      tables: [table],
      unsupported: [
        {
          code: 'OLE_OBJECT',
          partName: 'word/document.xml',
          path: '/document/object[1]',
          label: null,
          detail: 'Synthetic embedded object.',
          clinicallyMaterial: true,
          blocksCertification: true,
        },
      ],
      now: NOW,
    });
    expect(result.valid).toBe(false);
    expect(result.issues.map((issue) => issue.code)).toEqual(
      expect.arrayContaining(['TABLE_ROW_OVERFLOW', 'OLE_OBJECT']),
    );
  });

  it('validates medication dose completeness and allergy conflicts', () => {
    const dose = field('b', 'measurement', {
      criticality: 'medication',
    });
    const doseMap = mapping(dose, 'medication.dose', {
      unitPolicy: 'required',
    });
    const doseFact = fact('b', 'medication.dose', 10, {
      number: 10,
      unit: null,
    });
    const doseResolution: FieldResolution = {
      fieldId: dose.fieldId,
      status: 'supported',
      value: 10,
      sourceFactIds: [doseFact.factId],
      evidenceAnchorIds: doseFact.evidenceAnchorIds,
      selectedOptionOrdinal: null,
      reasonCode: 'synthetic_dose',
      clinicianReviewed: false,
    };
    expect(
      validateOne(dose, doseMap, [doseFact], [doseResolution]).issues.map(
        (issue) => issue.code,
      ),
    ).toContain('MEDICATION_DOSE_INCOMPLETE');

    const allergy = field('d', 'narrative_text', {
      criticality: 'allergy',
    });
    const allergyMap = mapping(allergy, 'allergy.substance');
    const allergyFact = fact('d', 'allergy.substance', 'Synthetic allergen', {
      quality: { asr: 'high', evidence: 'conflicting' },
    });
    const allergyResolution: FieldResolution = {
      fieldId: allergy.fieldId,
      status: 'supported',
      value: 'Synthetic allergen',
      sourceFactIds: [allergyFact.factId],
      evidenceAnchorIds: allergyFact.evidenceAnchorIds,
      selectedOptionOrdinal: null,
      reasonCode: 'synthetic_allergy',
      clinicianReviewed: false,
    };
    expect(
      validateOne(
        allergy,
        allergyMap,
        [allergyFact],
        [allergyResolution],
      ).issues.map((issue) => issue.code),
    ).toContain('ALLERGY_EVIDENCE_UNRESOLVED');
  });
});
