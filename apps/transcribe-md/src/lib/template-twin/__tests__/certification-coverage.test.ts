import { describe, expect, it } from 'vitest';

import {
  evaluateTemplateTwinCertificationCoverage,
  type TemplateTwinFieldTestWaiverEvidence,
} from '../certification-coverage';
import {
  TemplateTwinFillManifestSchema,
  type EncounterFact,
  type FieldResolution,
  type SemanticMapping,
  type TemplateField,
} from '../ir';

const SHA = 'a'.repeat(64);
const SOAP_SHA = 'b'.repeat(64);
const MAPPINGS_SHA = 'c'.repeat(64);
const ACTOR = 'doctor-synthetic-coverage';

function field(
  seed: string,
  kind: TemplateField['kind'],
  overrides: Partial<TemplateField> = {},
): TemplateField {
  return {
    fieldId: `ttf_${seed.repeat(24).slice(0, 24)}`,
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
      path: `/synthetic/${seed}`,
      canonicalPath: `/synthetic/${seed}`,
      ordinal: 0,
      sdtId: seed,
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
    clinicalConcept: 'hpi.severity',
    expectedDataType: types[definition.kind],
    polarityBehavior:
      definition.kind === 'checkbox'
        ? 'explicit_denial_allowed'
        : 'value_only',
    temporality: 'current',
    laterality: 'not_applicable',
    unitPolicy:
      definition.kind === 'measurement' ? 'required' : 'not_applicable',
    approvedSynonyms: [],
    required: definition.required,
    blankPolicy: definition.unknownPolicy,
    unknownPolicy: definition.unknownPolicy,
    practiceDefault: null,
    status: 'certified',
    ...overrides,
  };
}

function fact(
  seed: string,
  value: string | number | boolean,
  overrides: Partial<EncounterFact> = {},
): EncounterFact {
  return {
    factId: `ttfact_${seed.repeat(24).slice(0, 24)}`,
    sourceType: 'encounter_evidence',
    concept: 'hpi.severity',
    value,
    polarity: 'affirmed',
    temporality: 'current',
    experiencer: 'patient',
    laterality: 'not_applicable',
    number: typeof value === 'number' ? value : null,
    unit: null,
    speaker: 'Synthetic physician',
    sourceTranscriptOffsets: { start: 0, end: 20 },
    audioTimestampSeconds: null,
    evidenceAnchorIds: [`synthetic-anchor-${seed}`],
    evidenceQuote: 'Synthetic test evidence only.',
    quality: { asr: 'high', evidence: 'direct' },
    ...overrides,
  };
}

function resolution(
  definition: TemplateField,
  source: EncounterFact | null,
  value: FieldResolution['value'],
  overrides: Partial<FieldResolution> = {},
): FieldResolution {
  return {
    fieldId: definition.fieldId,
    status: value === null ? 'not_mentioned' : 'supported',
    value,
    sourceFactIds: source ? [source.factId] : [],
    evidenceAnchorIds: source ? source.evidenceAnchorIds : [],
    selectedOptionOrdinal: null,
    reasonCode: value === null ? 'synthetic_not_mentioned' : 'synthetic_supported',
    clinicianReviewed: false,
    ...overrides,
  };
}

function manifest(
  facts: EncounterFact[],
  fields: FieldResolution[],
) {
  return TemplateTwinFillManifestSchema.parse({
    manifestVersion: 1,
    soapVersion: 1,
    soapSha256: SOAP_SHA,
    compiledVersionId: 'compiled-synthetic-coverage',
    noteTemplateId: 'template-synthetic-coverage',
    noteTemplateVersion: 1,
    compilerVersion: 'template-docx-compiler/1.0.0',
    resolverVersion: 'template-field-resolver/1.0.0',
    resolverModelVersion: 'synthetic-model',
    rendererVersion: 'template-docx-renderer/1.0.0',
    facts,
    fields,
    validation: {
      valid: true,
      issues: [],
      checkedAt: '2026-07-15T20:00:00.000Z',
      validatorVersion: 'template-field-validator/1.0.0',
    },
    counts: {
      filled: fields.filter((item) => item.value !== null).length,
      needsReview: 0,
      notMentioned: fields.filter((item) => item.value === null).length,
      conflicts: 0,
      criticalUnresolved: 0,
    },
  });
}

function waiver(
  fieldId: string,
  overrides: Partial<TemplateTwinFieldTestWaiverEvidence> = {},
): TemplateTwinFieldTestWaiverEvidence {
  return {
    fieldId,
    mappingsSha256: MAPPINGS_SHA,
    waivedById: ACTOR,
    reason: 'Optional display field is not used in this synthetic workflow.',
    waivedAt: '2026-07-15T20:00:00.000Z',
    ...overrides,
  };
}

function evaluate(input: {
  fields: TemplateField[];
  mappings: SemanticMapping[];
  facts: EncounterFact[];
  resolutions: FieldResolution[];
  waivers?: TemplateTwinFieldTestWaiverEvidence[];
}) {
  return evaluateTemplateTwinCertificationCoverage({
    fields: input.fields,
    mappings: input.mappings,
    manifest: manifest(input.facts, input.resolutions),
    waivers: input.waivers ?? [],
    currentMappingsSha256: MAPPINGS_SHA,
    actorUserId: ACTOR,
  });
}

describe('Template Twin field-level certification coverage', () => {
  it('does not let one generic test certify an unexercised required field', () => {
    const first = field('a1', 'narrative_text', { required: true });
    const second = field('b2', 'narrative_text', { required: true });
    const source = fact('a1', 'Synthetic exercised statement');
    const result = evaluate({
      fields: [first, second],
      mappings: [mapping(first), mapping(second)],
      facts: [source],
      resolutions: [
        resolution(first, source, source.value),
        resolution(second, null, null),
      ],
    });

    expect(result.ready).toBe(false);
    expect(result.issues).toContainEqual(
      expect.objectContaining({
        fieldId: second.fieldId,
        code: 'CERT_REQUIRED_FIELD_UNTESTED',
      }),
    );
  });

  it('never permits a waiver for a required or clinically meaningful field', () => {
    const definition = field('c3', 'checkbox', {
      clinicallyMaterial: true,
    });
    const result = evaluate({
      fields: [definition],
      mappings: [mapping(definition)],
      facts: [],
      resolutions: [resolution(definition, null, null)],
      waivers: [waiver(definition.fieldId)],
    });

    expect(result.ready).toBe(false);
    expect(result.issues.map((issue) => issue.code)).toEqual(
      expect.arrayContaining([
        'CERT_WAIVER_NOT_ALLOWED',
        'CERT_MATERIAL_FIELD_UNTESTED',
      ]),
    );
  });

  it('requires an actor-bound, reasoned, current-mapping waiver for an optional untested field', () => {
    const definition = field('d4', 'narrative_text');
    const semantic = mapping(definition);
    const missing = resolution(definition, null, null);

    expect(
      evaluate({
        fields: [definition],
        mappings: [semantic],
        facts: [],
        resolutions: [missing],
      }).issues.map((issue) => issue.code),
    ).toContain('CERT_OPTIONAL_FIELD_NEEDS_WAIVER');

    const accepted = evaluate({
      fields: [definition],
      mappings: [semantic],
      facts: [],
      resolutions: [missing],
      waivers: [waiver(definition.fieldId)],
    });
    expect(accepted.ready).toBe(true);
    expect(accepted.fields[0]).toMatchObject({ disposition: 'waived' });

    const stale = evaluate({
      fields: [definition],
      mappings: [semantic],
      facts: [],
      resolutions: [missing],
      waivers: [
        waiver(definition.fieldId, {
          mappingsSha256: 'd'.repeat(64),
          waivedById: 'doctor-synthetic-other',
          reason: 'short',
        }),
      ],
    });
    expect(stale.issues.map((issue) => issue.code)).toEqual(
      expect.arrayContaining([
        'CERT_WAIVER_STALE_MAPPING',
        'CERT_WAIVER_ACTOR_MISMATCH',
        'CERT_WAIVER_REASON_INVALID',
      ]),
    );
  });

  it('independently recognizes exact select, checkbox, date, unit, laterality, polarity, and table exercises', () => {
    const select = field('e5', 'single_select', { required: true });
    const checkbox = field('f6', 'checkbox', { required: true });
    const date = field('a7', 'date', { required: true });
    const measurement = field('b8', 'measurement', { required: true });
    const repeated = field('c9', 'narrative_text', {
      required: true,
      tableId: `ttb_${'c'.repeat(20)}`,
      rowPrototype: true,
    });
    const selectFact = fact('e5', 'Severe');
    const checkboxFact = fact('f6', 'No synthetic finding', {
      polarity: 'denied',
    });
    const dateFact = fact('a7', '2026-07-15');
    const measurementFact = fact('b8', '12 mm', {
      number: 12,
      unit: 'mm',
      laterality: 'left',
    });
    const repeatedFact = fact('c9', 'Synthetic row');
    const facts = [
      selectFact,
      checkboxFact,
      dateFact,
      measurementFact,
      repeatedFact,
    ];
    const fields = [select, checkbox, date, measurement, repeated];
    const mappings = [
      mapping(select),
      mapping(checkbox),
      mapping(date),
      mapping(measurement, { laterality: 'required' }),
      mapping(repeated),
    ];
    const resolutions: FieldResolution[] = [
      resolution(select, selectFact, 'Severe', { selectedOptionOrdinal: 1 }),
      resolution(checkbox, checkboxFact, false, { status: 'explicitly_denied' }),
      resolution(date, dateFact, '2026-07-15'),
      resolution(measurement, measurementFact, '12 mm'),
      resolution(repeated, repeatedFact, [
        {
          value: 'Synthetic row',
          sourceFactId: repeatedFact.factId,
          evidenceAnchorId: repeatedFact.evidenceAnchorIds[0]!,
          optionOrdinal: null,
        },
      ]),
    ];

    const result = evaluate({ fields, mappings, facts, resolutions });
    expect(result.ready).toBe(true);
    expect(result.fields).toEqual(
      expect.arrayContaining([
        expect.objectContaining({ checks: expect.arrayContaining(['exact_option_1']) }),
        expect.objectContaining({ checks: expect.arrayContaining(['checkbox_explicit_false']) }),
        expect.objectContaining({ checks: expect.arrayContaining(['unambiguous_date']) }),
        expect.objectContaining({ checks: expect.arrayContaining(['explicit_number_and_unit', 'explicit_laterality']) }),
        expect.objectContaining({ checks: expect.arrayContaining(['table_row_behavior']) }),
      ]),
    );
  });
});
