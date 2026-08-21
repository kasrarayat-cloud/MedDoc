// ============================================================================
// Stage 2 — DATE OF PROCEDURE metadata fill via traceable fact injection. The
// visit date is injected as an EncounterFact (never AI); the evidence resolver
// fills it and the INDEPENDENT validator accepts it (a bare resolution overlay
// would cite no real fact and flip validation to invalid). The integration test
// below is the load-bearing proof: resolve → validate must be VALID.
// ============================================================================
import { describe, expect, it } from 'vitest';

import { withProcedureDateFact, visitDateToIso } from '../procedure-date';
import { resolveTemplateFields } from '../resolver';
import { validateTemplateTwin } from '../validation';
import {
  TemplateFieldSchema,
  SemanticMappingSchema,
  type EncounterFact,
  type SemanticMapping,
  type TemplateField,
} from '../ir';

const SHA = 'a'.repeat(64);

function field(idSeed: string, kind: TemplateField['kind'], originalLabel: string): TemplateField {
  return TemplateFieldSchema.parse({
    fieldId: `ttf_${idSeed.repeat(24).slice(0, 24)}`,
    kind,
    originalLabel,
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
    criticality: 'date_duration',
    tableId: null,
    rowPrototype: false,
  });
}

function dateMapping(f: TemplateField, concept: string | null, status = 'certified'): SemanticMapping {
  return SemanticMappingSchema.parse({
    fieldId: f.fieldId,
    clinicalConcept: concept,
    expectedDataType: 'date',
    polarityBehavior: 'affirmative_only',
    temporality: 'current',
    laterality: 'not_applicable',
    unitPolicy: 'not_applicable',
    approvedSynonyms: [],
    required: false,
    blankPolicy: 'blank',
    unknownPolicy: 'blank',
    practiceDefault: null,
    status,
  });
}

const DOP = field('d', 'date', 'DATE OF PROCEDURE');
const VISIT = new Date('2026-07-23T18:00:00Z');

describe('withProcedureDateFact', () => {
  it('injects a traceable visit-date fact for a certified date-of-procedure control', () => {
    const facts = withProcedureDateFact({ fields: [DOP], mappings: [dateMapping(DOP, 'date of procedure')], facts: [], visitDate: VISIT });
    expect(facts).toHaveLength(1);
    expect(facts[0].concept).toBe('date of procedure');
    expect(facts[0].value).toBe('2026-07-23');
    expect(facts[0].evidenceAnchorIds).toEqual(['procedure-date-metadata']);
    expect(facts[0].factId).toMatch(/^ttfact_[a-f0-9]{24}$/);
  });

  it('does NOT inject for a non-procedure date control (Date of Birth)', () => {
    const dob = field('b', 'date', 'Date of Birth');
    expect(withProcedureDateFact({ fields: [dob], mappings: [dateMapping(dob, 'date of birth')], facts: [], visitDate: VISIT })).toHaveLength(0);
  });

  it('does NOT inject for a non-date control even if labelled procedure', () => {
    const sel = field('a', 'single_select', 'Date of Procedure Type');
    expect(withProcedureDateFact({ fields: [sel], mappings: [dateMapping(sel, 'x')], facts: [], visitDate: VISIT })).toHaveLength(0);
  });

  it('does NOT inject when the mapping is uncertified or has no concept', () => {
    expect(withProcedureDateFact({ fields: [DOP], mappings: [dateMapping(DOP, 'date of procedure', 'recognized')], facts: [], visitDate: VISIT })).toHaveLength(0);
    expect(withProcedureDateFact({ fields: [DOP], mappings: [dateMapping(DOP, null)], facts: [], visitDate: VISIT })).toHaveLength(0);
  });

  it('real evidence WINS — does not inject when a fact already speaks to the concept', () => {
    const existing: EncounterFact = {
      factId: `ttfact_${'c'.repeat(24)}`, sourceType: 'encounter_evidence', concept: 'date of procedure', value: '2026-01-01',
      polarity: 'affirmed', temporality: 'current', experiencer: 'patient', laterality: 'not_applicable', number: null, unit: null,
      speaker: null, sourceTranscriptOffsets: null, audioTimestampSeconds: null, evidenceAnchorIds: ['a1'], evidenceQuote: 'q', segment: null, quality: { asr: 'high', evidence: 'direct' },
    };
    expect(withProcedureDateFact({ fields: [DOP], mappings: [dateMapping(DOP, 'date of procedure')], facts: [existing], visitDate: VISIT })).toHaveLength(1); // just the existing
  });

  it('is a no-op when the visit date is absent/ambiguous', () => {
    for (const bad of [null, undefined, 'not-a-date']) {
      expect(withProcedureDateFact({ fields: [DOP], mappings: [dateMapping(DOP, 'date of procedure')], facts: [], visitDate: bad as never })).toHaveLength(0);
    }
  });
});

describe('procedure-date fill is INDEPENDENTLY VALID (resolve → validate)', () => {
  it('the injected fact resolves to a supported ISO date that passes validation', () => {
    const mapping = dateMapping(DOP, 'date of procedure');
    const facts = withProcedureDateFact({ fields: [DOP], mappings: [mapping], facts: [], visitDate: VISIT });
    const resolutions = resolveTemplateFields({ fields: [DOP], mappings: [mapping], facts, certifiedFieldIds: [DOP.fieldId] });
    const dop = resolutions.find((r) => r.fieldId === DOP.fieldId)!;
    expect(dop.status).toBe('supported');
    expect(dop.value).toBe('2026-07-23');

    const v = validateTemplateTwin({
      fields: [DOP], mappings: [mapping], facts, resolutions,
      tables: [], unsupported: [], certifiedFieldIds: [DOP.fieldId],
      allowUncertifiedForSyntheticTest: false, now: VISIT,
    });
    expect(v.issues.filter((i) => i.severity === 'blocking')).toEqual([]);
    expect(v.valid).toBe(true);
  });

  it('with NO visit date, the control stays unresolved and validation is still valid', () => {
    const mapping = dateMapping(DOP, 'date of procedure');
    const facts = withProcedureDateFact({ fields: [DOP], mappings: [mapping], facts: [], visitDate: null });
    const resolutions = resolveTemplateFields({ fields: [DOP], mappings: [mapping], facts, certifiedFieldIds: [DOP.fieldId] });
    const dop = resolutions.find((r) => r.fieldId === DOP.fieldId)!;
    expect(dop.value).toBeNull();
    const v = validateTemplateTwin({
      fields: [DOP], mappings: [mapping], facts, resolutions,
      tables: [], unsupported: [], certifiedFieldIds: [DOP.fieldId],
      allowUncertifiedForSyntheticTest: false, now: VISIT,
    });
    expect(v.valid).toBe(true);
  });
});

describe('visitDateToIso', () => {
  it('formats a Date / ISO string to YYYY-MM-DD (UTC); null for junk', () => {
    expect(visitDateToIso(new Date('2026-07-23T23:59:00Z'))).toBe('2026-07-23');
    expect(visitDateToIso('2026-02-28')).toBe('2026-02-28');
    expect(visitDateToIso('garbage')).toBeNull();
    expect(visitDateToIso(null)).toBeNull();
  });
});
