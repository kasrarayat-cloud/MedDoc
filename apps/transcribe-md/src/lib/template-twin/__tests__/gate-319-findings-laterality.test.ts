// ============================================================================
// #319 REGISTRY-2 — an operative-note findings list spans both sides of the
// colon WITHOUT conflicting.
// ----------------------------------------------------------------------------
// ⚠️ THIS GATE EXISTS BECAUSE AN ADVERSARIAL PASS FOUND THE DOCUMENT-LOSS.
// The `procedure.findings` projector emit once left laterality to inference, so
// "polyp in the RIGHT colon; diverticulosis of the LEFT colon" gave two facts on
// opposite sides; `joinListValuedNarrative` refuses a list carrying >1
// laterality, the resolver turned that into `multiple_distinct_supported_values`
// -> FIELD_CONFLICT (blocking) -> the WHOLE native operative note was withheld.
// And the certification self-test could not see it: its fixture uses
// sigmoid/descending/cecum, none of which carry a side. So this is a UNIT gate,
// not a reliance on the model-driven round-trip.
// ============================================================================
import { describe, expect, it } from 'vitest';

import { projectEncounterFacts } from '../encounter-facts';
import {
  isListValuedNarrative,
  joinListValuedNarrative,
} from '../field-value-derivation';
import {
  SemanticMappingSchema,
  TemplateFieldSchema,
  type SemanticMapping,
  type TemplateField,
} from '../ir';

const SHA = 'a'.repeat(64);

function findingsField(): TemplateField {
  return TemplateFieldSchema.parse({
    fieldId: `ttf_${'7'.repeat(24)}`,
    kind: 'narrative_text',
    originalLabel: 'Findings',
    labelSource: 'alias',
    displayOrder: 0,
    detectionStatus: 'certified',
    allowedOptions: [],
    rendererBinding: {
      partName: 'word/document.xml',
      bindingType: 'content_control',
      path: '/synthetic/findings',
      ordinal: 0,
      sdtId: '1',
      tag: 'findings',
      alias: 'Findings',
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

function findingsMapping(): SemanticMapping {
  return SemanticMappingSchema.parse({
    fieldId: `ttf_${'7'.repeat(24)}`,
    clinicalConcept: 'procedure.findings',
    sourceType: 'extraction',
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
  });
}

// A findings list that names BOTH sides of the colon — clinically routine.
const CONTEXT =
  'Postoperative findings: a five millimetre sessile polyp in the right colon, removed by snare; ' +
  'scattered diverticulosis of the left colon; otherwise normal mucosa to the cecum.';

const MIXED_LATERALITY_PROCEDURE = {
  procedure: {
    findings: [
      {
        finding: 'A five millimetre sessile polyp in the right colon, removed by snare',
        polarity: 'affirmed' as const,
        evidence_quote:
          'a five millimetre sessile polyp in the right colon, removed by snare',
      },
      {
        finding: 'Scattered diverticulosis of the left colon',
        polarity: 'affirmed' as const,
        evidence_quote: 'scattered diverticulosis of the left colon',
      },
      {
        finding: 'Otherwise normal mucosa to the cecum',
        polarity: 'affirmed' as const,
        evidence_quote: 'otherwise normal mucosa to the cecum',
      },
    ],
  },
};

describe('#319 — operative findings span both sides of the colon without conflict', () => {
  it('the projector states laterality not_applicable, never inferring a side', () => {
    const facts = projectEncounterFacts({
      mode: 'dictation',
      contextText: CONTEXT,
      asrQuality: 'unknown',
      entities: MIXED_LATERALITY_PROCEDURE as never,
    });
    const findings = facts.filter((f) => f.concept === 'procedure.findings');
    expect(findings).toHaveLength(3);
    // ⚠️ THE FIX: not one of them carries an inferred right/left, even though the
    // text says "right colon" and "left colon".
    expect(findings.every((f) => f.laterality === 'not_applicable')).toBe(true);
  });

  it('the findings JOIN instead of refusing — the document is NOT withheld', () => {
    const facts = projectEncounterFacts({
      mode: 'dictation',
      contextText: CONTEXT,
      asrQuality: 'unknown',
      entities: MIXED_LATERALITY_PROCEDURE as never,
    });
    const findings = facts.filter((f) => f.concept === 'procedure.findings');
    const field = findingsField();
    const mapping = findingsMapping();

    // procedure.findings is a list-valued narrative...
    expect(isListValuedNarrative(field, mapping)).toBe(true);
    // ...and the join now SUCCEEDS across the mixed-anatomy list (non-null), where
    // before the fix >1 inferred laterality made it refuse (null) -> FIELD_CONFLICT.
    const joined = joinListValuedNarrative(field, mapping, findings);
    expect(joined).not.toBeNull();
    expect(joined).toContain('right colon');
    expect(joined).toContain('left colon');
    expect(joined).toContain('cecum');
  });
});
