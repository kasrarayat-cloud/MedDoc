// ============================================================================
// Template Twin — THE OPERATIVE-NOTE HEADER'S RECORD-DERIVED FILL (#319).
// ----------------------------------------------------------------------------
// The colon operative note's header is not dictated: the patient's date of
// birth and MRN, the date of service, the dictation/transcription dates, and
// the SIGNING DOCTOR'S name are all facts of the visit record. This module is
// the only place they become facts, and it is modelled on `visit-metadata.ts`
// (patient name/age) and `procedure-date.ts` (the visit date) for the reason
// those state: the fill path resolves cited `EncounterFact`s that an independent
// validator re-checks, so a record value must travel as a FACT — a resolution
// overlay would cite nothing and flip validation to invalid, suppressing the
// native render.
//
// ⚠️ IT IS A SEPARATE INJECTOR, NOT AN EXTENSION OF `withVisitMetadataFacts`.
// That module is scarred by #247/#264/#275 around the EXACT two concepts it
// mints (name, age) — the per-tense keying, the age timezone refusal. Widening
// it to eight concepts would put this new code inside that proven path; keeping
// it here isolates the risk and leaves name/age untouched.
//
// ⚠️ EVERY VALUE WEARS `sourceType: 'visit_record'` — the whole of #247. A record
// value carrying `encounter_evidence` would make the frozen manifest say the
// clinician DICTATED the patient's MRN or their own name, and there is no way
// back from a provenance answer that is wrong.
//
// WHAT IT WILL NOT DO:
//   - it never invents. No record, no date of birth, no MRN, no clinician name,
//     no unambiguous visit date -> nothing injected and the control renders
//     blank, with a NAMED reason where the record was consulted and empty.
//   - it never overrides. A fact already speaking to the concept wins, always.
//   - it fills ONLY what a CERTIFIED mapping asked for, keyed on the mapping's
//     own `sourceType`/`clinicalConcept` and NEVER on the label (the label was
//     read once already, by `classifyFieldSource`).
// ============================================================================
import { createHash } from 'node:crypto';

import {
  EncounterFactSchema,
  type EncounterFact,
  type SemanticMapping,
  type TemplateField,
  type RecordDerivedRefusal,
  type RecordDerivedRefusalReason,
} from './ir';
import {
  conceptMatches,
  normalizeConcept,
  requiredFactTemporality,
} from './fact-mapping-match';
import { visitDateToIso } from './procedure-date';

const ANCHOR = 'operative-record-metadata';

/** The visit-record values this module may read. Every field optional — a null
 *  or absent value renders the control blank (with a named reason where the
 *  record was present and the value was not). */
export interface OperativeVisitRecord {
  /** The patient's date of birth, off the patient record. */
  patientDateOfBirth?: Date | string | null;
  /** The patient's MRN, off the patient record (NOT the SSN). */
  patientMrn?: string | null;
  /** The SIGNING DOCTOR'S name — the signer when signed, else the visit's
   *  author. A clinician's name is permitted here (#319): it is record-derived,
   *  not model-asserted, so #127 holds. */
  clinicianName?: string | null;
}

/** How each handled concept is sourced, and the token to name a blank it leaves
 *  when the record was present but the value was not. `null` reason = a value
 *  (the visit date) that is present by construction at fill time, so its absence
 *  is the certification path and is silently skipped, never named. */
type Sourced = {
  value: string | null;
  experiencer: EncounterFact['experiencer'];
  /** True when the SOURCE record for this datum was supplied at all. Absence of
   *  the source is the synthetic-certification path — skip, never refuse. */
  sourcePresent: boolean;
  absentReason: RecordDerivedRefusalReason | null;
};

/** A stable 24-hex fact id for one record-derived value. */
function recordFactId(
  concept: string,
  value: string,
  temporality: EncounterFact['temporality'],
): string {
  return `ttfact_${createHash('sha256')
    .update(`visit_record ${concept} ${temporality} ${value}`, 'utf8')
    .digest('hex')
    .slice(0, 24)}`;
}

/**
 * Return the fact set with the operative-note header's record-derived values
 * injected, for the concepts this template's CERTIFIED mappings actually ask
 * for. Pure; returns a NEW array. A no-op for name/age (owned by
 * `withVisitMetadataFacts`) and for the referring physician (dictated).
 *
 * ⚠️ ONE FACT PER CONCEPT, NOT ONE PER FIELD — facts match fields by concept, so
 * a single `visit_metadata.date_of_service` fact satisfies every date-of-service
 * control at once, and minting one per field would give
 * `multiple_distinct_supported_values` something to trip on.
 */
export function withOperativeRecordFacts(input: {
  fields: ReadonlyArray<TemplateField>;
  mappings: ReadonlyArray<SemanticMapping>;
  facts: ReadonlyArray<EncounterFact>;
  record: OperativeVisitRecord | null | undefined;
  visitDate: Date | string | null | undefined;
  refusals?: RecordDerivedRefusal[];
}): EncounterFact[] {
  const facts = [...input.facts];
  const fieldIds = new Set(input.fields.map((f) => f.fieldId));
  const record = input.record ?? null;
  const iso = visitDateToIso(input.visitDate);
  const recordPresent = record !== null;
  const datePresent = iso !== null;

  const trimmed = (v: string | null | undefined): string | null => {
    const t = v?.trim();
    return t && t.length > 0 ? t : null;
  };

  // The four visit-date members share one ISO value; the record members read
  // the record. Anatomy of one datum: its value, who it is about, whether its
  // source was supplied at all, and how to name a blank.
  const sourcedFor = (concept: string): Sourced | null => {
    switch (concept) {
      case 'visit_metadata.date_of_birth':
        return {
          value: recordPresent ? visitDateToIso(record?.patientDateOfBirth) : null,
          experiencer: 'patient',
          sourcePresent: recordPresent,
          absentReason: 'date_of_birth_absent',
        };
      case 'visit_metadata.patient_id':
        return {
          value: recordPresent ? trimmed(record?.patientMrn) : null,
          experiencer: 'patient',
          sourcePresent: recordPresent,
          absentReason: 'patient_id_absent',
        };
      case 'procedure.surgeon':
        return {
          value: recordPresent ? trimmed(record?.clinicianName) : null,
          // The subject is the clinician, not the patient — the same
          // `experiencer: 'other'` the projector gives the referring physician.
          experiencer: 'other',
          sourcePresent: recordPresent,
          absentReason: 'surgeon_absent',
        };
      case 'visit_metadata.date_of_service':
      case 'visit_metadata.dictated_at':
      case 'visit_metadata.transcribed_at':
        return {
          value: iso,
          experiencer: 'patient',
          sourcePresent: datePresent,
          absentReason: null,
        };
      default:
        // name/age (withVisitMetadataFacts), referring_physician (dictated),
        // and everything else are not this module's business.
        return null;
    }
  };

  const quoteFor = (concept: string): string => {
    switch (concept) {
      case 'visit_metadata.date_of_birth':
        return 'Patient date of birth from the patient record.';
      case 'visit_metadata.patient_id':
        return 'Patient MRN from the patient record.';
      case 'procedure.surgeon':
        return 'Signing clinician from the visit record.';
      case 'visit_metadata.date_of_service':
        return 'Date of service derived from the visit (encounter) date.';
      case 'visit_metadata.dictated_at':
        return 'Dictation date derived from the visit (encounter) date.';
      case 'visit_metadata.transcribed_at':
        return 'Transcription date derived from the visit (encounter) date.';
      default:
        return 'Value from the visit record.';
    }
  };

  // Real dictated evidence wins — never inject when a fact already speaks to the
  // mapping, judged the resolver's own way (`conceptMatches`) rather than by
  // string equality, which the two guards must not answer differently.
  const alreadySpokenTo = (mapping: SemanticMapping): boolean =>
    input.facts.some((f) => conceptMatches(f, mapping));

  // One fact per concept: the first certified mapping per concept mints it, and
  // the fact then matches every control that shares the concept.
  const mintedConcepts = new Set<string>();

  for (const mapping of input.mappings) {
    if (!fieldIds.has(mapping.fieldId)) continue;
    if (mapping.sourceType !== 'visit_metadata') continue;
    if (mapping.status !== 'certified') continue;
    const rawConcept = mapping.clinicalConcept;
    if (!rawConcept) continue;
    const concept = normalizeConcept(rawConcept);
    const sourced = sourcedFor(concept);
    if (!sourced) continue;

    if (sourced.value === null) {
      // ⚠️ #264/#319 — NAME THE BLANK, but ONLY when the source record was
      // supplied and lacked the value. When the source is absent entirely (the
      // synthetic-certification path), skip silently: there is no record to
      // accuse of missing an MRN.
      if (input.refusals && sourced.sourcePresent && sourced.absentReason) {
        if (!alreadySpokenTo(mapping)) {
          input.refusals.push({
            fieldId: mapping.fieldId,
            unfilled: sourced.absentReason,
            required: `required_${sourced.absentReason}`,
          });
        }
      }
      continue;
    }

    if (alreadySpokenTo(mapping)) continue;
    if (mintedConcepts.has(concept)) continue;
    mintedConcepts.add(concept);

    const temporality = requiredFactTemporality(mapping);
    facts.push(
      EncounterFactSchema.parse({
        factId: recordFactId(concept, sourced.value, temporality),
        sourceType: 'visit_record',
        concept,
        value: sourced.value,
        // Stated, never inferred — canon 135. There is no denied MRN or denied
        // service date, and `inferPolarity` reading "no" out of an evidence line
        // would blank a control with nothing wrong with it.
        polarity: 'affirmed',
        temporality,
        experiencer: sourced.experiencer,
        laterality: 'not_applicable',
        // The digits/name travel as the printed string; no numeric attribute.
        number: null,
        unit: null,
        speaker: 'Visit record',
        sourceTranscriptOffsets: null,
        audioTimestampSeconds: null,
        evidenceAnchorIds: [`${ANCHOR}:${concept}`],
        evidenceQuote: quoteFor(concept),
        quality: { asr: 'unknown', evidence: 'direct' },
      }),
    );
  }

  return facts;
}
