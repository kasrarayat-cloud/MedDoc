/**
 * AUTO-CERTIFICATION ELIGIBILITY — which proposals may confirm themselves.
 *
 * OWNER RULING 2026-08-17: auto-certification by AI is the DEFAULT path. The
 * doctor uploads and runs visits; the model confirms its own proposals and the
 * template certifies, provided the round-trip proof passes.
 *
 * ⚠️ THE ONE THING THE MODEL MAY NEVER ASSERT IS LATERALITY. Left/Right on an
 * imaging report is the field whose loss deleted content from a signed record
 * earlier this month, and this house's standing rule is fail-closed on it. So
 * the ruling's structural-resolution clause governs:
 *
 *   A laterality-critical mapping auto-confirms ONLY when the DOCUMENT'S OWN
 *   STRUCTURE pins the side. That is the document asserting its side —
 *   deterministic, not a model judgement. Anything else stays unconfirmed and
 *   is named in the needs-review banner.
 *
 * The distinction is not cosmetic. On the customer form this was measured
 * against, it separates cleanly:
 *
 *   "Right deep venous system Choose an item."  -> structural, auto-confirms
 *   "Left Choose an item. is Choose an item."   -> structural, auto-confirms
 *   "SIDE OF EXAM: Choose an item."             -> NO anchor, refuses, named
 *
 * Six of seven resolve from the document; one genuinely does not, because
 * nothing in the document says which side that exam was. A model guessing there
 * would be inventing a clinical fact.
 */

/** Why a mapping was (or was not) auto-confirmed. Recorded on the audit row. */
export type AutoConfirmProvenance =
  /** The document's own structure pinned it — deterministic, no model judgement. */
  | 'structural'
  /** The model proposed it and it carries no laterality risk. */
  | 'model'
  /** A manual field: no concept exists to assert, it renders blank and is attested blank. */
  | 'manual';

export interface AutoConfirmDecision {
  confirm: boolean;
  provenance: AutoConfirmProvenance | null;
  /** Doctor-facing, PHI-free. Present exactly when confirm === false. */
  reason: string | null;
}

/**
 * ⚠️ WORD-BOUNDARY MATCHING, NOT SUBSTRING. "left" appears inside "cleft" and
 * "Bilateral" contains "lateral" — a substring test is the recorded trap family
 * and would silently anchor a field the document never sided.
 *
 * `bilateral` counts as an anchor: it names BOTH sides explicitly, which is a
 * determinate statement about laterality, not an absence of one.
 */
const SIDED_TOKEN = /\b(right|left|bilateral)\b/i;

/**
 * Does the document itself pin this field's side?
 *
 * @param originalLabel the field's own label, as the .docx wrote it
 * @param sectionHeading the nearest enclosing heading, when the compiler
 *        supplies one. On forms whose fields carry the side in their own label
 *        this is null and the label alone decides — which is the shape the
 *        measured customer form actually has.
 */
export function hasStructuralLateralityAnchor(
  originalLabel: string | null | undefined,
  sectionHeading?: string | null,
): boolean {
  // ⚠️ THE LABEL IS CHECKED FIRST AND IS SUFFICIENT. A field literally named
  // "Right deep venous system" is sided by the document more directly than by
  // any heading above it.
  if (originalLabel && SIDED_TOKEN.test(originalLabel)) return true;
  if (sectionHeading && SIDED_TOKEN.test(sectionHeading)) return true;
  return false;
}

export interface AutoConfirmCandidate {
  originalLabel: string | null;
  /** Field-definition criticality. 'laterality' is the fail-closed class. */
  criticality: string | null;
  /** 'extraction' | 'verified_note_selection' | 'manual' */
  sourceType: string | null;
  /** Whether a clinical concept is present. Required for non-manual fields. */
  hasClinicalConcept: boolean;
  /** Nearest enclosing sided heading, when the compiler supplies one. */
  sectionHeading?: string | null;
}

/**
 * THE DECISION, per mapping. Pure — no I/O, no model call, fully testable.
 *
 * ⚠️ ORDER MATTERS AND IS DELIBERATE. The laterality refusal is evaluated
 * BEFORE the generic model path, so a laterality field can never fall through
 * into 'model' provenance by satisfying the ordinary conditions.
 */
export function decideAutoConfirm(c: AutoConfirmCandidate): AutoConfirmDecision {
  // A manual field has no concept BY CONSTRUCTION — nothing dictates who the
  // technologist on shift was. It is ready when attested, renders blank.
  if (c.sourceType === 'manual') {
    return { confirm: true, provenance: 'manual', reason: null };
  }

  // Certification requires a concept for every non-manual field. Without one
  // there is nothing to confirm, whatever else is true.
  if (!c.hasClinicalConcept) {
    return {
      confirm: false,
      provenance: null,
      reason: 'no clinical concept was proposed for this field',
    };
  }

  if (c.criticality === 'laterality') {
    if (hasStructuralLateralityAnchor(c.originalLabel, c.sectionHeading)) {
      return { confirm: true, provenance: 'structural', reason: null };
    }
    return {
      confirm: false,
      provenance: null,
      reason:
        'the document does not say which side this field refers to — confirm it once',
    };
  }

  return { confirm: true, provenance: 'model', reason: null };
}
