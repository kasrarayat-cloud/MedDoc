// ============================================================================
// Template Twin — VISIT METADATA fill (#247 family 3, Stage B).
// ----------------------------------------------------------------------------
// The patient's NAME and AGE are printed on the owner's consult letter, and no
// dictation contains them: the doctor does not say his own patient's name into
// the microphone. They are read off the PATIENT RECORD, and this module is the
// only place that happens.
//
// ⚠️ IT IS MODELLED ON `withProcedureDateFact` ON PURPOSE, AND FOR THE REASON
// THAT MODULE STATES: the fill path is built on cited `EncounterFact`s that the
// evidence resolver resolves and an INDEPENDENT validator re-checks. A
// resolution overlay would cite no real fact and flip validation to invalid,
// suppressing the native render — so metadata is injected as a FACT and then
// travels the ordinary road.
//
// ⚠️ AND IT WEARS `sourceType: 'visit_record'`, WHICH IS THE WHOLE OF #247.
// A record value carrying `encounter_evidence` makes the frozen manifest say
// the clinician SAID it. That is not a style point — the manifest is what a
// later reader consults to find out where a sentence on a signed document came
// from, and there is no way back from an answer that is wrong.
//
// WHAT IT WILL NOT DO, each one a decision rather than an omission:
//   - it never invents. No record, no name, no date of birth, no unambiguous
//     visit date -> nothing is injected and the control renders blank.
//   - it never overrides. A fact already speaking to the concept wins, always.
//   - it fills ONLY what the certified mapping asked for, keyed on the
//     mapping's own `sourceType`/`clinicalConcept` — never on the label. The
//     label was already read once, by `classifyFieldSource`, and reading it a
//     second time here is how one rule acquires two readers that disagree.
//   - it carries NOTHING but name and age. `visit_metadata.referring_physician`
//     is DICTATED and is emitted by the projector as ordinary evidence; the
//     registry deliberately has no term for an address, an MRN or a birth date,
//     so this module has nothing to reach for even if somebody asked it to.
// ============================================================================
import { createHash } from 'node:crypto';

import {
  EncounterFactSchema,
  type EncounterFact,
  type SemanticMapping,
  type TemplateField,
} from './ir';
import { normalizeConcept, requiredFactTemporality } from './fact-mapping-match';

/** The two concepts this module may inject. Referring physician is NOT here. */
export const RECORD_DERIVED_CONCEPTS = {
  name: 'visit_metadata.patient_name',
  age: 'visit_metadata.patient_age',
} as const;

const METADATA_ANCHOR = 'visit-record-metadata';

/** The patient record, narrowed to the two columns this module may read. */
export interface VisitPatientRecord {
  name: string | null | undefined;
  dateOfBirth: Date | string | null | undefined;
}

/**
 * WHOLE YEARS AT A GIVEN DATE, OR NULL.
 *
 * ⚠️ CALENDAR ARITHMETIC, NOT DIVISION BY 365.25. A year length is not a
 * constant and the answer is read by a human as a fact about a person: the
 * patient whose birthday is tomorrow is not yet a year older, and a rounding
 * scheme that says otherwise puts a wrong age on a clinical letter roughly one
 * day in three hundred and sixty five. Compared on UTC calendar parts, so a
 * server timezone cannot move a birthday across midnight.
 *
 * Returns null — never 0, never a guess — for an unparseable date, a birth date
 * in the future, or an implausible result. `0` is a legitimate age (an infant),
 * so it cannot double as the failure value.
 */
export function ageAtDate(
  dateOfBirth: Date | string | null | undefined,
  at: Date | string | null | undefined,
): number | null {
  if (dateOfBirth == null || at == null) return null;
  const dob = dateOfBirth instanceof Date ? dateOfBirth : new Date(dateOfBirth);
  const on = at instanceof Date ? at : new Date(at);
  if (Number.isNaN(dob.getTime()) || Number.isNaN(on.getTime())) return null;
  let years = on.getUTCFullYear() - dob.getUTCFullYear();
  const monthDelta = on.getUTCMonth() - dob.getUTCMonth();
  if (monthDelta < 0 || (monthDelta === 0 && on.getUTCDate() < dob.getUTCDate())) {
    years -= 1;
  }
  // A negative age means the record and the visit disagree about time; an age
  // past the verified human maximum means the column holds something that is
  // not this patient's birth date. Both are refusals, not clamps.
  if (years < 0 || years > 130) return null;
  return years;
}

/** A stable 24-hex fact id for one record-derived value. */
function recordFactId(concept: string, value: string): string {
  return `ttfact_${createHash('sha256')
    .update(`visit_record ${concept} ${value}`, 'utf8')
    .digest('hex')
    .slice(0, 24)}`;
}

/**
 * Return the fact set with the patient record's name and age injected, for the
 * concepts this template's CERTIFIED mappings actually ask for. Pure; returns a
 * NEW array. A no-op when there is no patient record, no such mapping, or the
 * concept is already spoken to.
 *
 * ⚠️ ONE FACT PER CONCEPT, NOT ONE PER FIELD. Facts are matched to fields by
 * concept, so a single `visit_metadata.patient_name` fact satisfies the header
 * control AND the letter's opening line. Minting one per field would put N
 * identical values in the manifest and give `multiple_distinct_supported_values`
 * something to trip over the day two controls disagree about nothing.
 */
export function withVisitMetadataFacts(input: {
  fields: ReadonlyArray<TemplateField>;
  mappings: ReadonlyArray<SemanticMapping>;
  facts: ReadonlyArray<EncounterFact>;
  patient: VisitPatientRecord | null | undefined;
  visitDate: Date | string | null | undefined;
}): EncounterFact[] {
  const facts = [...input.facts];
  const patient = input.patient;
  if (!patient) return facts;

  const fieldIds = new Set(input.fields.map((field) => field.fieldId));
  const existingConcepts = new Set(facts.map((f) => normalizeConcept(f.concept)));

  // The concepts this template ASKS FOR, with the mapping that asked, so the
  // injected fact can inherit that mapping's approved temporality rather than
  // guessing one the resolver will then refuse.
  const wanted = new Map<string, SemanticMapping>();
  for (const mapping of input.mappings) {
    if (!fieldIds.has(mapping.fieldId)) continue;
    if (mapping.sourceType !== 'visit_metadata') continue;
    if (mapping.status !== 'certified') continue;
    const concept = mapping.clinicalConcept;
    if (!concept) continue;
    const normalized = normalizeConcept(concept);
    if (
      normalized !== RECORD_DERIVED_CONCEPTS.name &&
      normalized !== RECORD_DERIVED_CONCEPTS.age
    ) {
      // A `visit_metadata` mapping citing anything else is not this module's
      // business. Ignoring it is right: the registry closes the family at
      // three, and the third member is dictated.
      continue;
    }
    if (!wanted.has(normalized)) wanted.set(normalized, mapping);
  }
  if (wanted.size === 0) return facts;

  const patientName = patient.name?.trim();
  const age = ageAtDate(patient.dateOfBirth, input.visitDate);
  // Both quotes are written to be TRUE OF THE ACT and to carry no identifier of
  // their own. The value carries the name; the evidence line says where it came
  // from, and that sentence is what a doctor reads in the manifest.
  const values: ReadonlyArray<readonly [string, string | null, string]> = [
    [
      RECORD_DERIVED_CONCEPTS.name,
      patientName && patientName.length > 0 ? patientName : null,
      'Patient name from the patient record.',
    ],
    [
      RECORD_DERIVED_CONCEPTS.age,
      age === null ? null : String(age),
      'Patient age in whole years, computed from the date of birth in the patient record at the date of this visit.',
    ],
  ];

  for (const [concept, value, quote] of values) {
    const mapping = wanted.get(concept);
    if (!mapping || value === null) continue;
    // Real evidence wins — never inject when a fact already speaks to it.
    if (existingConcepts.has(concept)) continue;
    facts.push(
      EncounterFactSchema.parse({
        factId: recordFactId(concept, value),
        // ⚠️ #247 — THE CLASS, AND THE ONLY REASON THIS MODULE EXISTS.
        sourceType: 'visit_record',
        concept,
        value,
        // Stated, never inferred — canon 135. There is no such thing as a
        // denied patient name, and `inferPolarity` reading the word "no" out of
        // a name or an evidence sentence would blank the control on a document
        // with nothing wrong with it.
        polarity: 'affirmed',
        temporality: requiredFactTemporality(mapping),
        // The subject IS the patient. (The referring physician, the one member
        // of this family that is not, is emitted by the projector with
        // `experiencer: 'other'` and is not injected here at all.)
        experiencer: 'patient',
        laterality: 'not_applicable',
        // ⚠️ `number` STAYS NULL FOR THE AGE, AND THAT IS DELIBERATE. The
        // controls this fills compile `narrative_text` (canon 134 — kind and
        // concept are independent axes), and the resolver's number arm refuses
        // a value whose unit policy it cannot satisfy. The digits travel as the
        // string that is actually printed.
        number: null,
        unit: null,
        speaker: 'Patient record',
        sourceTranscriptOffsets: null,
        audioTimestampSeconds: null,
        evidenceAnchorIds: [`${METADATA_ANCHOR}:${concept}`],
        evidenceQuote: quote,
        quality: { asr: 'unknown', evidence: 'direct' },
      }),
    );
    existingConcepts.add(concept);
  }
  return facts;
}
