// ============================================================================
// OWNER FINDING — the certified operative note exported BLANK Preoperative
// Diagnosis and Description of Procedure although L3 extracted both.
// ----------------------------------------------------------------------------
// Cause: the compiled mapping narrowed procedure.preop_diagnosis /
// procedure.description to `temporality: 'current'`, but the extracted facts
// carried `historical` (the indication is a "history of…") and `planned`. The
// temporality reader (`temporalityMatches`) then failed and the control blanked.
//
// The operative body MIXES tenses, so the whole family is TEMPORALITY_AGNOSTIC.
// The check lives in `temporalityMatches` — the ONE reader consulted by BOTH the
// resolver's candidate filter AND the validator's `factMatchesMapping`.
//
// ⚠️ THIS GATE RESOLVES **AND VALIDATES**. A first cut patched only the resolver;
// its test called only resolveTemplateFields and was green while the validator
// still refused the cited off-tense fact (SOURCE_FACT_CONCEPT_MISMATCH) and
// `finalizeTemplateTwinFill` withheld the WHOLE native note — strictly worse than
// the blank. So this gate asserts the END STATE: resolved supported AND the
// validation is clean, which is what makes the document render.
// ============================================================================
import { describe, expect, it, vi } from 'vitest';

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
import { validateTemplateTwin } from '../validation';
import { TEMPORALITY_AGNOSTIC_CONCEPTS } from '../concept-registry';

const PREOP_ID = `ttf_${'1'.repeat(24)}`;
const DESC_ID = `ttf_${'2'.repeat(24)}`;
const CC_ID = `ttf_${'3'.repeat(24)}`;
const SHA = 'a'.repeat(64);
const NOW = '2026-09-13T14:00:00.000Z';

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

function mapping(fieldId: string, concept: string, over: Record<string, unknown> = {}): SemanticMapping {
  return SemanticMappingSchema.parse({
    fieldId,
    clinicalConcept: concept,
    sourceType: 'extraction',
    expectedDataType: 'text',
    polarityBehavior: 'value_only',
    temporality: 'current', // ⚠️ the bug shape — the auto-mapper narrowed to 'current'
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
    value: 'a statement',
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
    evidenceQuote: 'the surgeon said so',
    quality: { asr: 'unknown', evidence: 'direct' },
    ...over,
  });
}

/** Resolve THEN validate — the end-to-end shape a first cut skipped. */
function resolveAndValidate(f: TemplateField, m: SemanticMapping, facts: EncounterFact[]) {
  const resolutions = resolveTemplateFields({
    fields: [f], mappings: [m], facts, certifiedFieldIds: [f.fieldId],
  });
  const validation = validateTemplateTwin({
    fields: [f], mappings: [m], facts, resolutions,
    tables: [], unsupported: [], certifiedFieldIds: [f.fieldId],
    allowUncertifiedForSyntheticTest: false, now: NOW,
  });
  return { resolution: resolutions[0]!, validation };
}

const REFUSAL_CODES = ['SOURCE_FACT_CONCEPT_MISMATCH', 'ASSERTION_NOT_SUPPORTED', 'FIELD_AMBIGUOUS'];

describe('OWNER FINDING — the operative body is temporality-agnostic (resolve AND validate)', () => {
  it('⚠️ a HISTORICAL procedure.preop_diagnosis RESOLVES supported AND VALIDATES clean', () => {
    const preop = fact({
      concept: 'procedure.preop_diagnosis',
      value: 'personal history of adenomatous colon polyps',
      temporality: 'historical',
    });
    const { resolution, validation } = resolveAndValidate(
      field(PREOP_ID, 'Preoperative Diagnosis'),
      mapping(PREOP_ID, 'procedure.preop_diagnosis'),
      [preop],
    );
    // resolve
    expect(resolution.reasonCode).not.toBe('temporality_not_approved');
    expect(resolution.status).toBe('supported');
    expect(resolution.value).toBe('personal history of adenomatous colon polyps');
    // validate — the END STATE. No off-tense refusal, and the fill is valid so
    // finalizeTemplateTwinFill renders the native note instead of withholding it.
    const offending = validation.issues.filter((i) => REFUSAL_CODES.includes(i.code));
    expect(offending, JSON.stringify(offending)).toEqual([]);
    expect(validation.valid).toBe(true);
  });

  it('⚠️ a PLANNED procedure.description RESOLVES supported AND VALIDATES clean', () => {
    const desc = fact({ concept: 'procedure.description', value: 'time-out performed; scope advanced to cecum', temporality: 'planned' });
    const { resolution, validation } = resolveAndValidate(
      field(DESC_ID, 'Description of Procedure'),
      mapping(DESC_ID, 'procedure.description'),
      [desc],
    );
    expect(resolution.status).toBe('supported');
    expect(validation.issues.filter((i) => REFUSAL_CODES.includes(i.code))).toEqual([]);
    expect(validation.valid).toBe(true);
  });

  it('⚠️ NON-VACUITY: a NON-operative concept STILL tense-gates — a historical fact is refused at resolve', () => {
    const stale = fact({ concept: 'chief_complaint', value: 'old complaint', temporality: 'historical' });
    const { resolution } = resolveAndValidate(
      field(CC_ID, 'Chief complaint'),
      mapping(CC_ID, 'chief_complaint'),
      [stale],
    );
    expect(resolution.reasonCode).toBe('temporality_not_approved');
  });

  it('⚠️ the agnostic set is the operative family, and holds patient concepts OUT', () => {
    expect(TEMPORALITY_AGNOSTIC_CONCEPTS.has('procedure.preop_diagnosis')).toBe(true);
    expect(TEMPORALITY_AGNOSTIC_CONCEPTS.has('procedure.description')).toBe(true);
    expect(TEMPORALITY_AGNOSTIC_CONCEPTS.has('procedure.performed')).toBe(true);
    expect(TEMPORALITY_AGNOSTIC_CONCEPTS.has('chief_complaint')).toBe(false);
    expect(TEMPORALITY_AGNOSTIC_CONCEPTS.has('visit_metadata.patient_name')).toBe(false);
  });
});
