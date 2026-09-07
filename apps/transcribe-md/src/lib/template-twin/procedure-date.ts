// ============================================================================
// Template Twin — DATE OF PROCEDURE metadata fill (native path, Stage 2).
// ----------------------------------------------------------------------------
// A "DATE OF PROCEDURE" date content control is metadata, not clinical dictation
// — it is the encounter date, known deterministically from the visit. We fill it
// the SAME way approved practice defaults are filled: by INJECTING a traceable
// EncounterFact (never AI), which the evidence resolver then resolves + the
// independent validator accepts (a resolution-overlay would cite no real fact
// and flip validation to invalid, suppressing native render).
//
// Deliberately conservative — it injects a fact ONLY for:
//   • a `date`-kind control whose ORIGINAL label unambiguously reads
//     "date of procedure", with a CERTIFIED semantic mapping + clinical concept;
//   • when the visit date resolves to an unambiguous ISO YYYY-MM-DD;
//   • when NO existing fact already speaks to that concept (real dictated
//     evidence always wins — this never overrides or conflicts).
// Anything else is left untouched → the control renders blank. Never invents.
// ============================================================================
import {
  EncounterFactSchema,
  type EncounterFact,
  type SemanticMapping,
  type TemplateField,
} from './ir';
import { normalizeConcept, requiredFactTemporality } from './fact-mapping-match';

const DATE_OF_PROCEDURE_LABEL_RE = /\bdate\s+of\s+procedure\b/i;
const METADATA_ANCHOR = 'procedure-date-metadata';

/** ISO YYYY-MM-DD (UTC) from a Date or ISO-ish string; null when not an
 *  unambiguous calendar date (leave the control blank rather than guess). */
export function visitDateToIso(visitDate: Date | string | null | undefined): string | null {
  if (visitDate == null) return null;
  const d = visitDate instanceof Date ? visitDate : new Date(visitDate);
  if (Number.isNaN(d.getTime())) return null;
  return d.toISOString().slice(0, 10);
}

/** True when the visit date is a real DATE OF PROCEDURE control we may fill. */
function isFillableProcedureDate(
  field: TemplateField,
  mapping: SemanticMapping | undefined,
): mapping is SemanticMapping {
  return (
    field.kind === 'date' &&
    DATE_OF_PROCEDURE_LABEL_RE.test(field.originalLabel) &&
    !!mapping &&
    mapping.status === 'certified' &&
    !!mapping.clinicalConcept
  );
}

/**
 * Return the fact set with a synthetic visit-date fact injected for a DATE OF
 * PROCEDURE control (when fillable). Pure; returns a NEW array. A no-op when the
 * visit date is absent/ambiguous, no such control exists, or the concept is
 * already spoken to by a real fact. Mirrors withApprovedPracticeDefaultFacts.
 */
export function withProcedureDateFact(input: {
  fields: ReadonlyArray<TemplateField>;
  mappings: ReadonlyArray<SemanticMapping>;
  facts: ReadonlyArray<EncounterFact>;
  visitDate: Date | string | null | undefined;
}): EncounterFact[] {
  const iso = visitDateToIso(input.visitDate);
  const facts = [...input.facts];
  if (!iso) return facts;
  const mappingById = new Map(input.mappings.map((m) => [m.fieldId, m]));
  const existingConcepts = new Set(facts.map((f) => normalizeConcept(f.concept)));

  for (const field of input.fields) {
    const mapping = mappingById.get(field.fieldId);
    if (!isFillableProcedureDate(field, mapping)) continue;
    const concept = mapping.clinicalConcept!;
    // Real evidence wins — never inject when a fact already speaks to the concept.
    if (existingConcepts.has(normalizeConcept(concept))) continue;
    // A 24-hex fact id derived from the field id (which is `ttf_<24hex>`) — a
    // stable, real (in-set) fact id, so the resolution is traceable.
    const factId = `ttfact_${field.fieldId.replace(/^ttf_/, '').slice(0, 24)}`;
    const temporality = requiredFactTemporality(mapping);
    facts.push(
      EncounterFactSchema.parse({
        factId,
        // ⚠️ #234 — WAS `encounter_evidence`, AND THAT WAS A LIE ABOUT
        // PROVENANCE. This value is the visit's own encounter date read off the
        // record; nobody said it. The frozen manifest recorded it as dictated
        // for as long as this line read otherwise, which is the defect the
        // `visit_record` class exists to prevent — so its one existing
        // precedent moves onto it rather than being grandfathered.
        sourceType: 'visit_record',
        concept,
        value: iso,
        polarity: 'affirmed',
        temporality,
        experiencer: 'patient',
        laterality: 'not_applicable',
        number: null,
        unit: null,
        speaker: 'Visit metadata',
        sourceTranscriptOffsets: null,
        audioTimestampSeconds: null,
        evidenceAnchorIds: [METADATA_ANCHOR],
        evidenceQuote: 'Procedure date derived from the visit (encounter) date.',
        quality: { asr: 'unknown', evidence: 'direct' },
      }),
    );
    existingConcepts.add(normalizeConcept(concept));
  }
  return facts;
}
