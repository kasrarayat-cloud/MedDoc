// ============================================================================
// THE RESOLVER PROBE — one field, one encounter, shared by every arm that needs
// to ask the REAL resolver a question.
// ----------------------------------------------------------------------------
// ⚠️ EXTRACTED BECAUSE THREE FILES NEEDED IT AND TWO OF THEM HAD SETTLED FOR
// READING THE RESOLVER'S SOURCE INSTEAD — RULING #258's SECOND COST.
//
// `row-laterality` and `verified-note-selection` each asserted their guard by
// `expect(src).toContain("if (mapping.sourceType === 'verified_note_selection')")`
// — a string match on the resolver's own text. When ruling #258 replaced the
// inline ladder with a table walk, those two arms were the ONLY things in a
// 6,316-test suite that noticed, and what they noticed was the SPELLING. The
// behaviour they were named for was unchanged and they could not tell.
//
// ⚠️ THAT IS #237's RETIRED CLASS, FOUND IN TWO MORE FILES: a text scanner is a
// proof about source, and it reds on a refactor while staying green through a
// behavioural regression that keeps the spelling. Both arms now drive the
// resolver, which is why this fixture had to become shared rather than copied a
// third and fourth time.
// ============================================================================

import { resolveTemplateFields } from '../resolver';
import type { EncounterFact, SemanticMapping, TemplateField } from '../ir';

export const SHA = 'a'.repeat(64);

export function field(idSeed: string, overrides: Partial<TemplateField> = {}): TemplateField {
  return {
    fieldId: `ttf_${idSeed.repeat(24).slice(0, 24)}`,
    kind: 'narrative_text',
    scaffolded: true,
    scaffoldText: 'The patient consents to a telehealth consultation.',
    originalLabel: 'Telehealth consent',
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

export function mapping(
  definition: TemplateField,
  concept: string,
  overrides: Partial<SemanticMapping> = {},
): SemanticMapping {
  return {
    fieldId: definition.fieldId,
    sourceType: 'extraction' as const,
    clinicalConcept: concept,
    expectedDataType: 'text',
    polarityBehavior: 'value_only',
    temporality: 'current',
    laterality: 'optional',
    unitPolicy: 'not_applicable',
    approvedSynonyms: [],
    required: false,
    blankPolicy: 'blank',
    unknownPolicy: 'blank',
    practiceDefault: null,
    status: 'certified',
    ...overrides,
  };
}

export function factFor(seed: string, concept: string, sentence: string): EncounterFact {
  return {
    factId: `ttfact_${seed.repeat(24).slice(0, 24)}`,
    sourceType: 'encounter_evidence',
    concept,
    value: sentence,
    polarity: 'affirmed',
    temporality: 'current',
    experiencer: 'patient',
    laterality: 'not_applicable',
    number: null,
    unit: null,
    speaker: 'Doctor',
    sourceTranscriptOffsets: { start: 0, end: 10 },
    audioTimestampSeconds: null,
    evidenceAnchorIds: [`anchor-${seed}`],
    evidenceQuote: sentence,
    segment: null,
    quality: { asr: 'high', evidence: 'direct' },
  };
}

/**
 * One field the encounter never speaks to, on a visit that said something REAL
 * about a DIFFERENT concept — which is the only shape where `conceptUnmatched`,
 * `reason === undefined` and `facts.length > 0` all hold.
 */
export function resolveOne(
  fieldOverrides: Partial<TemplateField> = {},
  mappingOverrides: Partial<SemanticMapping> = {},
) {
  const f = field('1', fieldOverrides);
  const m = mapping(f, 'ros.cardiovascular', mappingOverrides);
  const resolutions = resolveTemplateFields({
    fields: [f],
    mappings: [m],
    facts: [factFor('2', 'chief_complaint', 'Patient here for a rash.')],
    allowUncertifiedForSyntheticTest: true,
  });
  return { field: f, mapping: m, resolution: resolutions[0]!, resolutions };
}

/**
 * The SAME field on a visit that DID speak to it — one fact carrying the field's
 * own approved concept.
 *
 * ⚠️ WITHOUT THIS THE DEFERRAL GUARDS CANNOT BE CONTROLLED AT ALL, AND I WROTE
 * THE CONTROL BEFORE NOTICING. `resolveOne`'s encounter deliberately carries a
 * NON-matching concept, which is the only shape where the omit branch is
 * reachable — so under it a fixed-grid cell and a multi-scope checkbox both
 * route to `:490` and ARE honoured. A control asserting they are honoured
 * therefore passes whether or not the deferral exists, and would have passed
 * against a stub.
 *
 * The deferrals are reached only when facts ARE in hand. That is this probe.
 */
export function resolveOneDictated(
  fieldOverrides: Partial<TemplateField> = {},
  mappingOverrides: Partial<SemanticMapping> = {},
) {
  const f = field('1', fieldOverrides);
  const m = mapping(f, 'ros.cardiovascular', mappingOverrides);
  const resolutions = resolveTemplateFields({
    fields: [f],
    mappings: [m],
    facts: [
      factFor('3', m.clinicalConcept ?? 'ros.cardiovascular', 'The patient reports palpitations.'),
    ],
    allowUncertifiedForSyntheticTest: true,
  });
  return { field: f, mapping: m, resolution: resolutions[0]! };
}

/**
 * The same probe with the synthetic-certification escape hatch OFF.
 *
 * ⚠️ EVERY OTHER PROBE HERE PASSES `allowUncertifiedForSyntheticTest: true`,
 * which SKIPS the resolver's certification guard entirely — so the 870,912-row
 * biconditional never executes that branch, and a control for it written on
 * `resolveOne` would witness the guard it is named for exactly never.
 */
export function resolveOneCertifying(
  fieldOverrides: Partial<TemplateField> = {},
  mappingOverrides: Partial<SemanticMapping> = {},
) {
  const f = field('1', fieldOverrides);
  const m = mapping(f, 'ros.cardiovascular', mappingOverrides);
  const resolutions = resolveTemplateFields({
    fields: [f],
    mappings: [m],
    facts: [factFor('2', 'chief_complaint', 'Patient here for a rash.')],
  });
  return { field: f, mapping: m, resolution: resolutions[0]! };
}
