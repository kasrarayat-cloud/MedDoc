/**
 * RULING #179(5) — A CHECKBOX ANSWERS FOR EXACTLY ONE SYMPTOM, AND A BOX WHOSE
 * DECLARED SCOPE COVERS SEVERAL IS REFUSED RATHER THAN GUESSED.
 *
 * ⚠️ THIS ARM EXISTS BECAUSE THE MANDATORY PASS FOUND THE GUARD HAD NONE.
 * Deleting the refusal — `if (mapping?.conceptScope && mapping.conceptScope
 * .length > 1) return null;` — redded **0 of 668** twin tests.
 *
 * WHAT IT PROTECTS, IN THE CODE'S OWN WORDS: the checkbox arm reads only
 * `fact.polarity` and DISCARDS the finding, which is correct only when the
 * fact could not have been about a different symptom. Before symptom-granular
 * concepts it could — every clause in a system shared `ros.<system>`, so one
 * affirmed heartburn ticked nausea, dysphagia and every other box. That is the
 * false assertion the owner reported.
 *
 * ⚠️ AND THE REFUSAL DIRECTION IS THE POINT. A null leaves the doctor's own
 * default standing; an unticked box a clinician can tick is recoverable, a
 * wrongly-ticked one is not. So the arm asserts NULL, never `false` — those
 * are different clinical claims, and `false` would be the engine asserting the
 * patient denied something nobody asked about.
 */
import { describe, it, expect } from 'vitest';
import { deriveFieldValueFromFact } from '../field-value-derivation';
import { resolveTemplateFields } from '../resolver/index';
import {
  TemplateFieldSchema,
  SemanticMappingSchema,
  EncounterFactSchema,
  type TemplateField,
  type SemanticMapping,
  type EncounterFact,
} from '../ir';

const FIELD_ID = 'ttf_0123456789abcdef01234567';

const SHA = 'a'.repeat(64);

/** Mirrors the shipped factory in validation/__tests__/validation.test.ts. */
function checkbox(): TemplateField {
  return TemplateFieldSchema.parse({
    fieldId: FIELD_ID,
    kind: 'checkbox',
    originalLabel: 'Heartburn',
    labelSource: 'left_cell',
    displayOrder: 0,
    detectionStatus: 'certified',
    allowedOptions: [],
    rendererBinding: {
      partName: 'word/document.xml',
      bindingType: 'content_control',
      path: '/document/heartburn',
      ordinal: 0,
      sdtId: '1',
      tag: 'synthetic',
      alias: null,
      legacyName: null,
      rowLaterality: 'unknown',
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

function mapping(scope: string[] | undefined): SemanticMapping {
  return SemanticMappingSchema.parse({
    fieldId: FIELD_ID,
    sourceType: 'extraction',
    clinicalConcept: 'ros.gastrointestinal.heartburn',
    expectedDataType: 'boolean',
    polarityBehavior: 'explicit_denial_allowed',
    temporality: 'current',
    laterality: 'optional',
    unitPolicy: 'not_applicable',
    approvedSynonyms: [],
    required: false,
    blankPolicy: 'blank',
    unknownPolicy: 'blank',
    practiceDefault: null,
    status: 'certified',
    ...(scope === undefined ? {} : { conceptScope: scope }),
  });
}

function fact(polarity: EncounterFact['polarity']): EncounterFact {
  return EncounterFactSchema.parse({
    factId: 'ttfact_000000000000000000000001',
    sourceType: 'encounter_evidence',
    concept: 'ros.gastrointestinal.heartburn',
    value: true,
    polarity,
    temporality: 'current',
    experiencer: 'patient',
    laterality: 'not_applicable',
    number: null,
    unit: null,
    speaker: 'Doctor',
    sourceTranscriptOffsets: { start: 0, end: 20 },
    audioTimestampSeconds: null,
    evidenceAnchorIds: ['anchor-1'],
    evidenceQuote: 'Synthetic evidence',
    quality: { asr: 'high', evidence: 'direct' },
    segment: null,
  });
}

const MULTI = [
  'ros.gastrointestinal.heartburn',
  'ros.gastrointestinal.dysphagia',
  'ros.gastrointestinal.odynophagia',
];

describe('#179(5) — a checkbox with a multi-symptom scope is REFUSED', () => {
  it('NON-VACUITY: a SINGLE-symptom scope still ticks and unticks normally', () => {
    // Without this the refusal below is equally consistent with a derivation
    // that returns null for every checkbox, which would break every form.
    const single = mapping(['ros.gastrointestinal.heartburn']);
    expect(deriveFieldValueFromFact(checkbox(), single, fact('affirmed'))).toBe(true);
    expect(deriveFieldValueFromFact(checkbox(), single, fact('denied'))).toBe(false);
  });

  it('an ABSENT scope also behaves normally — the refusal is opt-in', () => {
    const none = mapping(undefined);
    expect(deriveFieldValueFromFact(checkbox(), none, fact('affirmed'))).toBe(true);
    expect(deriveFieldValueFromFact(checkbox(), none, fact('denied'))).toBe(false);
  });

  it('⚠️ a MULTI-symptom scope returns NULL for an affirmed fact', () => {
    // "Affirmed" is ambiguous across three symptoms. Ticking would assert the
    // patient reported all three.
    expect(deriveFieldValueFromFact(checkbox(), mapping(MULTI), fact('affirmed'))).toBeNull();
  });

  it('⚠️ and NULL — never false — for a DENIED fact', () => {
    // `false` is not a safe default here: it would assert the patient DENIED
    // symptoms nobody asked about. Null leaves the doctor's own default
    // standing. These are different clinical claims and the arm pins which.
    const got = deriveFieldValueFromFact(checkbox(), mapping(MULTI), fact('denied'));
    expect(got).toBeNull();
    expect(got).not.toBe(false);
  });

  it('the refusal is by SCOPE SIZE, not by polarity — uncertain is null either way', () => {
    // Guards against a fix that "passes" by collapsing every non-affirmed case.
    expect(deriveFieldValueFromFact(checkbox(), mapping(MULTI), fact('uncertain'))).toBeNull();
    expect(deriveFieldValueFromFact(checkbox(), mapping(['ros.gastrointestinal.heartburn']), fact('uncertain'))).toBeNull();
  });

  it('a TWO-symptom scope is already multi — the boundary is >1, not >2', () => {
    const two = mapping(['ros.gastrointestinal.heartburn', 'ros.gastrointestinal.nausea']);
    expect(deriveFieldValueFromFact(checkbox(), two, fact('affirmed'))).toBeNull();
  });
});

/**
 * ⚠️ AND THE REFUSAL MUST HOLD WHERE THE VALUE IS ACTUALLY WRITTEN.
 *
 * Every arm above drives `deriveFieldValueFromFact`, which honours the
 * multi-scope refusal correctly and always did. The RESOLVER does not call it —
 * it carries its own inline `case 'checkbox'` reading only `fact.polarity`, the
 * finding discarded. So #179(5) was implemented, commented, and tested against
 * a helper the fill path never reaches.
 *
 * MEASURED, both trees, one multi-scope mapping and one affirmed fact:
 *   before   resolver value=true  status=supported     | helper=null
 *   after    resolver value=null  status=not_mentioned | helper=null
 * The single-scope control ticks in BOTH trees, so this measures the refusal
 * and not a resolver that stopped filling checkboxes.
 */
describe('#179(5) — the multi-scope refusal reaches the RESOLVER, not just the helper', () => {
  const HEARTBURN = 'ros.gastrointestinal.heartburn';
  const MULTI = [HEARTBURN, 'ros.gastrointestinal.nausea'];

  function resolveWith(scope: string[]) {
    const [resolution] = resolveTemplateFields({
      fields: [checkbox()],
      mappings: [mapping(scope)],
      facts: [fact('affirmed')],
      certifiedFieldIds: [FIELD_ID],
    });
    return resolution;
  }

  it('⚠️ a multi-scope box is NOT ticked by one affirmed fact', () => {
    const r = resolveWith(MULTI);
    expect(r.value).toBeNull();
    expect(r.status).not.toBe('supported');
  });

  it('NON-VACUITY: a SINGLE-scope box IS still ticked by the same fact', () => {
    // Without this the arm above passes against a resolver that stopped
    // filling checkboxes altogether, which would blank every ROS clause.
    const r = resolveWith([HEARTBURN]);
    expect(r.value).toBe(true);
    expect(r.status).toBe('supported');
  });

  it('AGREEMENT: the resolver and the derivation helper now give the same answer', () => {
    // The defect was not that either was wrong on its own — the helper was
    // right all along. It was that they disagreed and the resolver won.
    for (const scope of [MULTI, [HEARTBURN]]) {
      const viaResolver = resolveWith(scope).value;
      const viaHelper = deriveFieldValueFromFact(checkbox(), mapping(scope), fact('affirmed'));
      expect(viaResolver, `scope=${scope.join('|')}`).toBe(viaHelper);
    }
  });
});
