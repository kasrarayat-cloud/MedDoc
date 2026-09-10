// ============================================================================
// VERIFIED NOTE SELECTION — provenance for an enumerated dropdown pick.
// ----------------------------------------------------------------------------
// A vein-diameter cell cites an extracted measurement. A dropdown cannot: the
// template's options are protocol language ("Bilateral Detailed", "Swelling,
// Heaviness"), and no extractor emits a fact that reads like that. Requiring one
// left fourteen dropdowns permanently blank on every real visit, which blocked
// the native export — while the note itself had already selected them correctly.
//
// The evidence for a pick is the product's OWN existing chain: transcript ->
// constrained CHOICE_SLOT fill (the model may only emit one of the template's
// listed options) -> anchored-verifier grounding -> the doctor adopting the note.
// That chain is real and already enforced upstream; what was missing was a way
// to CITE it. This module is that citation — a first-class fact whose identity
// is the selection itself.
//
// Its strict checks are enforced by the picks bridge, not here (see
// picks-bridge.ts): verbatim option only, the adopted note only, never a
// set-aside section. This file supplies the provenance the validator then checks
// exactly as it checks any other citation — the same shape approved practice
// defaults have used since they shipped, and not one validator rule is relaxed
// to accommodate it.
// ============================================================================

import { canonicalSha256 } from './canonical';
import { requiredFactTemporality } from './fact-mapping-match';
import {
  EncounterFactSchema,
  type EncounterFact,
  type SemanticMapping,
  type TemplateField,
} from './ir';

/** Stable provenance identity for one adopted pick.
 *
 * The NOTE VERSION is part of the identity on purpose: a re-generated or edited
 * note is a different selection, and must never silently reuse the prior
 * manifest's fact or anchor. So is the option value — changing the pick changes
 * the fact. This mirrors approvedPracticeDefaultFactId exactly. */
export function verifiedNoteSelectionFactId(input: {
  fieldId: string;
  optionValue: string;
  markerOrdinal: number;
  noteSha256: string;
}): string {
  return `ttfact_${canonicalSha256({
    kind: 'verified_note_selection',
    fieldId: input.fieldId,
    optionValue: input.optionValue,
    markerOrdinal: input.markerOrdinal,
    noteSha256: input.noteSha256,
  }).slice(0, 24)}`;
}

/** The side the field's own label names, or 'unknown' when it names none.
 *  Read from the document, never inferred from position or from the model. */
export function fieldLateralityFromLabel(originalLabel: string): 'right' | 'left' | 'unknown' {
  const t = originalLabel.trim().toLowerCase();
  const right = /\bright\b/.test(t);
  const left = /\bleft\b/.test(t);
  // A label naming BOTH sides names neither for this purpose — fail closed
  // rather than pick one.
  if (right === left) return 'unknown';
  return right ? 'right' : 'left';
}

export function verifiedNoteSelectionAnchorId(fieldId: string, factId: string): string {
  return `ttvns_${canonicalSha256({ factId, fieldId }).slice(0, 24)}`;
}

/**
 * The citable fact behind an adopted pick.
 *
 * `value` is the template's option VERBATIM, so the validator can re-derive the
 * rendered value from it by exact option lookup — the same check it makes of any
 * cited fact, unchanged. The mapping's own temporality and laterality are
 * mirrored so `factMatchesMapping` holds without special-casing.
 */
export function buildVerifiedNoteSelectionFact(input: {
  field: Pick<TemplateField, 'fieldId'>;
  mapping: SemanticMapping;
  /** The template option, verbatim. Never a paraphrase, never fuzzy. */
  optionValue: string;
  /** Which {{one of}} marker this pick came from, in document order. */
  markerOrdinal: number;
  /** Identity of the note the pick was read from — the ADOPTED note. */
  noteSha256: string;
  /** The side the FIELD ITSELF names, read from the document's own label
   *  ("Right <choose> is <choose>"). Same doctrine as row laterality stamped
   *  from the leg headings: the document says which side, never the model. */
  fieldLaterality: 'right' | 'left' | 'unknown';
}): EncounterFact {
  const factId = verifiedNoteSelectionFactId({
    fieldId: input.field.fieldId,
    optionValue: input.optionValue,
    markerOrdinal: input.markerOrdinal,
    noteSha256: input.noteSha256,
  });
  return EncounterFactSchema.parse({
    factId,
    sourceType: 'verified_note_selection',
    // The mapping's concept, so the citation satisfies the approved mapping the
    // same way an extracted fact must.
    concept: input.mapping.clinicalConcept,
    value: input.optionValue,
    polarity: 'affirmed',
    temporality: requiredFactTemporality(input.mapping),
    experiencer: 'patient',
    laterality:
      input.fieldLaterality !== 'unknown'
        ? input.fieldLaterality
        : input.mapping.laterality === 'not_applicable'
          ? 'not_applicable'
          : 'unknown',
    number: null,
    unit: null,
    speaker: 'Verified note selection',
    sourceTranscriptOffsets: null,
    audioTimestampSeconds: null,
    evidenceAnchorIds: [verifiedNoteSelectionAnchorId(input.field.fieldId, factId)],
    // PHI-safe and auditable: which marker, which note version. The option text
    // is the template's own language, never patient narrative.
    evidenceQuote:
      `Selected from the template's enumerated options in the adopted note ` +
      `(marker #${input.markerOrdinal}, note ${input.noteSha256.slice(0, 12)}).`,
    quality: { asr: 'unknown', evidence: 'direct' },
  });
}
