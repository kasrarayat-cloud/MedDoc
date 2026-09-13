// ============================================================================
// OWNER FINDING (blocking) — THE SURGEON IS A CLINICIAN SUBJECT.
// ----------------------------------------------------------------------------
// A certified Operative Note visit came back with the SOAP editor and no
// PDF/Word export. Root: `procedure.surgeon` is record-derived and minted
// `experiencer: 'other'` (the signing clinician, exactly as the referrer is),
// but the resolver's experiencer gate hard-coded the SINGLE concept
// `visit_metadata.referring_physician`. So the Surgeon field resolved
// `ambiguous / experiencer_not_approved` → FIELD_AMBIGUOUS (blocking) → the
// native render was withheld → the whole document surface fell back to the
// editor and the export went with it.
//
// The synthetic round-trip could never catch it: record-derived fields do not
// fill synthetically (there is no record), so the surgeon fact — and this gate —
// were never exercised until a real visit.
//
// This proves the FIX and plants the OPPOSITE case, per the adversarial rule:
//   • a `procedure.surgeon` fact (experiencer 'other') RESOLVES;
//   • an 'other' fact on a PATIENT-subject concept is STILL refused;
//   • the shared set is the single source of truth and actually holds the
//     surgeon — so a future edit that drops it reds here, not on a doctor's
//     screen.
// ============================================================================
import { describe, expect, it, vi } from 'vitest';

// resolver/index.ts pulls @/lib/audit -> next-auth via nothing here, but the
// db barrel is `any`-typed and imported transitively; stub both so the module
// graph loads without a runtime (mirrors gate-247's own mocks).
vi.mock('@meddoc/db', () => ({ default: {} }));
vi.mock('@/lib/audit', () => ({ logAudit: vi.fn() }));

import {
  EncounterFactSchema,
  SemanticMappingSchema,
  TemplateFieldSchema,
  type EncounterFact,
  type SemanticMapping,
  type TemplateField,
} from '../ir';
import { resolveTemplateFields } from '../resolver';
import { OTHER_EXPERIENCER_CLINICIAN_CONCEPTS } from '../concept-registry';

const SURGEON_ID = `ttf_${'e'.repeat(24)}`;
const PATIENT_FIELD_ID = `ttf_${'f'.repeat(24)}`;
const SHA = 'a'.repeat(64);

// Parsed through the SHIPPED schemas, never hand-shaped — a cast fixture proves
// the injector and dies one function later (gate-247's recorded lesson).
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
  concept: string,
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

function fact(over: Record<string, unknown> = {}): EncounterFact {
  return EncounterFactSchema.parse({
    factId: `ttfact_${'c'.repeat(24)}`,
    concept: 'chief_complaint',
    value: 'chest pain',
    polarity: 'affirmed',
    temporality: 'current',
    experiencer: 'patient',
    laterality: 'not_applicable',
    number: null,
    unit: null,
    speaker: 'Clinician',
    sourceTranscriptOffsets: null,
    audioTimestampSeconds: null,
    evidenceAnchorIds: ['a1'],
    evidenceQuote: 'the doctor said so',
    quality: { asr: 'unknown', evidence: 'direct' },
    ...over,
  });
}

describe('OWNER FINDING — the operating surgeon resolves, and the export is not hidden', () => {
  it('⚠️ a `procedure.surgeon` fact with experiencer `other` RESOLVES (was FIELD_AMBIGUOUS)', () => {
    // Exactly the shape `withOperativeRecordFacts` mints: record-derived, the
    // signing clinician, experiencer 'other'. Before the fix this returned
    // `ambiguous / experiencer_not_approved`; the shared clinician-subject set
    // now admits it. A visit_record fact promotes 'supported' → 'record_derived'
    // inside makeResolution, so that is the honest status here.
    const f = field(SURGEON_ID, 'Surgeon');
    // The MAPPING sourceType is the field's mapping provenance (mirrors the
    // referrer arm's 'extraction'); the record-derived signal lives on the FACT
    // (`sourceType: 'visit_record'` below), which is what makeResolution reads.
    const m = mapping(SURGEON_ID, 'procedure.surgeon', { sourceType: 'extraction' });
    const surgeon = fact({
      concept: 'procedure.surgeon',
      value: 'Dr. Alvarez',
      experiencer: 'other',
      sourceType: 'visit_record',
    });
    const [r] = resolveTemplateFields({
      fields: [f],
      mappings: [m],
      facts: [surgeon],
      certifiedFieldIds: [SURGEON_ID],
    });
    expect(r!.reasonCode).not.toBe('experiencer_not_approved');
    expect(r!.status).toBe('record_derived');
    expect(r!.value).toBe('Dr. Alvarez');
  });

  it('⚠️ NON-VACUITY: an `other` experiencer on a PATIENT-subject concept is STILL refused', () => {
    // The widening is by CONCEPT, not by value. A fact about someone other than
    // the patient must never fill a field about the patient — an unconditional
    // relaxation would let a brother's chest pain fill the chief complaint.
    const f = field(PATIENT_FIELD_ID, 'Chief complaint');
    const m = mapping(PATIENT_FIELD_ID, 'chief_complaint', { sourceType: 'extraction' });
    const other = fact({ concept: 'chief_complaint', value: 'chest pain', experiencer: 'other' });
    const [r] = resolveTemplateFields({
      fields: [f],
      mappings: [m],
      facts: [other],
      certifiedFieldIds: [PATIENT_FIELD_ID],
    });
    expect(r!.reasonCode).toBe('experiencer_not_approved');
  });

  it('⚠️ the shared set is the source of truth — surgeon + referrer in, patients out', () => {
    // Assert membership directly, so dropping the surgeon (or the referrer) from
    // the registry set reds HERE. Patient-subject concepts must never be members.
    expect(OTHER_EXPERIENCER_CLINICIAN_CONCEPTS.has('procedure.surgeon')).toBe(true);
    expect(OTHER_EXPERIENCER_CLINICIAN_CONCEPTS.has('visit_metadata.referring_physician')).toBe(true);
    expect(OTHER_EXPERIENCER_CLINICIAN_CONCEPTS.has('chief_complaint')).toBe(false);
    expect(OTHER_EXPERIENCER_CLINICIAN_CONCEPTS.has('visit_metadata.patient_name')).toBe(false);
  });
});
