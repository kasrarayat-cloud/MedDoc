// ============================================================================
// #319 REGISTRY-2 — the operative-note header's record-derived injector.
// ----------------------------------------------------------------------------
// `withOperativeRecordFacts` mints the visit record's own values (patient DOB,
// MRN, the signing clinician, the service/dictation/transcription dates) as
// `visit_record` facts — never dictated, never invented. These arms hold the
// properties the adversarial pass is entitled to demand of a PHI-sensitive
// injector on the fill path.
// ============================================================================
import { describe, expect, it } from 'vitest';

import {
  EncounterFactSchema,
  SemanticMappingSchema,
  TemplateFieldSchema,
  type EncounterFact,
  type RecordDerivedRefusal,
  type SemanticMapping,
  type TemplateField,
} from '../ir';
import { withOperativeRecordFacts } from '../operative-record';

const SHA = 'f'.repeat(64);
const DOB_ID = `ttf_${'1'.repeat(24)}`;
const MRN_ID = `ttf_${'2'.repeat(24)}`;
const DOS_ID = `ttf_${'3'.repeat(24)}`;
const DD_ID = `ttf_${'4'.repeat(24)}`;
const DT_ID = `ttf_${'5'.repeat(24)}`;
const SURGEON_ID = `ttf_${'6'.repeat(24)}`;

function field(fieldId: string, originalLabel: string): TemplateField {
  return TemplateFieldSchema.parse({
    fieldId,
    kind: 'narrative_text',
    originalLabel,
    labelSource: 'alias',
    displayOrder: 0,
    detectionStatus: 'certified',
    allowedOptions: [],
    rendererBinding: {
      partName: 'word/document.xml',
      bindingType: 'content_control',
      path: `/synthetic/${fieldId}`,
      ordinal: 0,
      sdtId: '1',
      tag: null,
      alias: null,
      legacyName: null,
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
  });
}

function mapping(
  fieldId: string,
  concept: string | null,
  over: Record<string, unknown> = {},
): SemanticMapping {
  return SemanticMappingSchema.parse({
    fieldId,
    clinicalConcept: concept,
    sourceType: 'visit_metadata',
    expectedDataType: 'text',
    polarityBehavior: 'value_only',
    temporality: null,
    laterality: 'not_applicable',
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

const ALL_FIELDS = [
  field(DOB_ID, 'Patient DOB'),
  field(MRN_ID, 'Patient ID'),
  field(DOS_ID, 'Date of Surgery'),
  field(DD_ID, 'DD'),
  field(DT_ID, 'DT'),
  field(SURGEON_ID, 'Surgeon'),
];
const ALL_MAPPINGS = [
  mapping(DOB_ID, 'visit_metadata.date_of_birth'),
  mapping(MRN_ID, 'visit_metadata.patient_id'),
  mapping(DOS_ID, 'visit_metadata.date_of_service'),
  mapping(DD_ID, 'visit_metadata.dictated_at'),
  mapping(DT_ID, 'visit_metadata.transcribed_at'),
  mapping(SURGEON_ID, 'procedure.surgeon'),
];
const VISIT = '2026-09-12T15:00:00.000Z';
const RECORD = {
  patientDateOfBirth: '1971-04-08',
  patientMrn: 'MRN-00421',
  clinicianName: 'Dr. Alex Rivera',
};

const byConcept = (facts: EncounterFact[]) =>
  new Map(facts.map((f) => [f.concept, f] as const));

describe('#319 — withOperativeRecordFacts', () => {
  it('mints one visit_record fact per concept, with the record/date value', () => {
    const facts = withOperativeRecordFacts({
      fields: ALL_FIELDS,
      mappings: ALL_MAPPINGS,
      facts: [],
      record: RECORD,
      visitDate: VISIT,
    });
    const m = byConcept(facts);
    // every fact is record-derived, never dictated
    expect(facts.every((f) => f.sourceType === 'visit_record')).toBe(true);
    expect(facts.every((f) => f.polarity === 'affirmed')).toBe(true);

    expect(m.get('visit_metadata.date_of_birth')?.value).toBe('1971-04-08');
    expect(m.get('visit_metadata.patient_id')?.value).toBe('MRN-00421');
    expect(m.get('visit_metadata.date_of_service')?.value).toBe('2026-09-12');
    expect(m.get('visit_metadata.dictated_at')?.value).toBe('2026-09-12');
    expect(m.get('visit_metadata.transcribed_at')?.value).toBe('2026-09-12');
    expect(m.get('procedure.surgeon')?.value).toBe('Dr. Alex Rivera');
    // the surgeon is the CLINICIAN, not the patient
    expect(m.get('procedure.surgeon')?.experiencer).toBe('other');
    expect(m.get('visit_metadata.date_of_birth')?.experiencer).toBe('patient');
  });

  it('is a NO-OP on the certification path — no record, no visit date, no facts', () => {
    const refusals: RecordDerivedRefusal[] = [];
    const facts = withOperativeRecordFacts({
      fields: ALL_FIELDS,
      mappings: ALL_MAPPINGS,
      facts: [],
      record: null,
      visitDate: null,
      refusals,
    });
    // ⚠️ THE CERTIFICATION GUARANTEE: no visit_record fact reaches the synthetic
    // test (assertNoRecordDerivedFacts would throw), and no blank is falsely
    // "named" for a record that was never supplied.
    expect(facts).toEqual([]);
    expect(refusals).toEqual([]);
  });

  it('names the blank when the record is PRESENT but the value is absent', () => {
    const refusals: RecordDerivedRefusal[] = [];
    const facts = withOperativeRecordFacts({
      fields: [field(DOB_ID, 'Patient DOB'), field(MRN_ID, 'Patient ID'), field(SURGEON_ID, 'Surgeon')],
      mappings: [
        mapping(DOB_ID, 'visit_metadata.date_of_birth'),
        mapping(MRN_ID, 'visit_metadata.patient_id'),
        mapping(SURGEON_ID, 'procedure.surgeon'),
      ],
      facts: [],
      record: { patientDateOfBirth: null, patientMrn: null, clinicianName: null },
      visitDate: VISIT,
      refusals,
    });
    expect(facts).toEqual([]);
    expect(refusals.map((r) => r.unfilled).sort()).toEqual([
      'date_of_birth_absent',
      'patient_id_absent',
      'surgeon_absent',
    ]);
  });

  it('real dictated evidence wins — never injects over an existing fact for the concept', () => {
    const dictated = EncounterFactSchema.parse({
      factId: `ttfact_${'9'.repeat(24)}`,
      sourceType: 'encounter_evidence',
      concept: 'procedure.surgeon',
      value: 'Dr. Someone Else',
      polarity: 'affirmed',
      temporality: 'current',
      experiencer: 'other',
      laterality: 'not_applicable',
      number: null,
      unit: null,
      speaker: null,
      sourceTranscriptOffsets: null,
      audioTimestampSeconds: null,
      evidenceAnchorIds: [`ttev_${'9'.repeat(24)}`],
      evidenceQuote: 'The surgeon was Dr. Someone Else.',
      quality: { asr: 'unknown', evidence: 'direct' },
    });
    const facts = withOperativeRecordFacts({
      fields: [field(SURGEON_ID, 'Surgeon')],
      mappings: [mapping(SURGEON_ID, 'procedure.surgeon')],
      facts: [dictated],
      record: RECORD,
      visitDate: VISIT,
    });
    // only the dictated fact remains — nothing injected over it
    expect(facts.filter((f) => f.concept === 'procedure.surgeon')).toHaveLength(1);
    expect(facts.find((f) => f.concept === 'procedure.surgeon')?.value).toBe('Dr. Someone Else');
  });

  it('ignores mappings that are not certified visit_metadata', () => {
    const facts = withOperativeRecordFacts({
      fields: [field(MRN_ID, 'Patient ID'), field(DOB_ID, 'Patient DOB')],
      mappings: [
        // not certified -> ignored
        mapping(MRN_ID, 'visit_metadata.patient_id', { status: 'needs_confirmation' }),
        // extraction source -> ignored (this injector only fills visit_metadata)
        mapping(DOB_ID, 'visit_metadata.date_of_birth', { sourceType: 'extraction' }),
      ],
      facts: [],
      record: RECORD,
      visitDate: VISIT,
    });
    expect(facts).toEqual([]);
  });
});
