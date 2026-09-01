// ============================================================================
// #163 RULE (2) — TEMPLATE HYGIENE IS A COMPILE-TIME FINDING, NOT A RUNTIME
// DELETION.
// ----------------------------------------------------------------------------
// ⚠️ WHY THIS EXISTS, AND WHY IT LIVES AT UPLOAD RATHER THAN AT RENDER.
//
// Ruling #162 spent three formulations trying to make the RENDERER clear an
// unfilled field's leftover content, and each was falsified a layer deeper:
// paragraph scope, part scope, field balance, element type. The fourth layer is
// the one that ended the approach — `w:sym`, `w:pict` and `w:delText` survived
// EVERY version, because a renderer that deletes what it can classify will
// always miss what it cannot. Measured at its worst, the widened clearing walk
// ERASED a patient's allergy line from a document that would be signed, with
// every guard green.
//
// So #163 inverts it. Runtime NEVER deletes what it cannot classify: a null is
// left unpatched and the field keeps the doctor's own blank representation.
// Leftover content is real, and it is answered HERE — at upload, once, where
// the doctor can act on it:
//
//     "this field contains leftover content and will print on every note —
//      clean it or accept it."
//
// The asymmetry is deliberate and is the whole design. A wrong deletion is
// silent and unrecoverable — it removes clinical text nobody notices is gone.
// A wrong FLAG is loud, costs a doctor ten seconds, and is fixed once at the
// template rather than every time a note renders.
//
// ⚠️ IT DETECTS, IT NEVER JUDGES. This module reports what WILL PRINT. Whether
// that is acceptable is the doctor's call — a placeholder like "Enter
// assessment" and a stale drug name are both leftover content, and only the
// person who owns the form can say which is which.
// ============================================================================
import { descendants, localName, tagOf, visibleText, type OrderedXmlNode } from './xml';

/**
 * The finding's code, in ONE place. It is exported because three files must
 * agree on it — the compiler that raises it, the validator that grades it, and
 * the gate that proves the grade — and a string literal repeated three times is
 * a string literal that disagrees with itself after the first refactor.
 */
export const FIELD_LEFTOVER_CONTENT = 'FIELD_LEFTOVER_CONTENT';

/** What a doctor would SEE in an unfilled field's locus. */
export interface FieldHygieneFinding {
  /** `text` — characters will print. `object` — a glyph, image or drawing will. */
  readonly kind: 'text' | 'object';
  /** The offending element's local name for `object`; `w:t` for text. */
  readonly element: string;
  /** A short, truncated sample of what prints. Empty for `object`. */
  readonly sample: string;
}

/**
 * Elements that put marks on the page but carry no `w:t`, so no amount of text
 * clearing reaches them. This list is the reason #162's approach could not work
 * and is why the finding is raised rather than the content removed.
 *
 * ⚠️ IT IS A DETECTION LIST, NEVER A DELETION LIST — an incomplete detection
 * list under-reports and the doctor still sees the page; an incomplete deletion
 * list silently ships the thing it missed while a proof says the field is
 * empty. That asymmetry is why this is the safe place to enumerate.
 */
const VISIBLE_OBJECTS = ['sym', 'pict', 'object', 'drawing', 'delText'] as const;

/**
 * What will print if this field is never filled?
 *
 * `locus` is the field's OWN content region as its emitter knows it — the
 * `w:sdtContent` of a content control, the `w:tc` of a table cell, the
 * `w:ffData` of a legacy form field. The caller passes it rather than this
 * module re-deriving it, deliberately: a second implementation of "where does
 * this field live" is exactly the drift that produced #162(b)'s production
 * regression, where a copied helper read a different property from the one it
 * was copied from.
 */
export function detectFieldHygiene(
  locus: OrderedXmlNode | null | undefined,
): FieldHygieneFinding | null {
  if (!locus) return null;

  // TEXT FIRST, and through the SHARED `visibleText` rather than a local walk —
  // it is already this codebase's definition of what renders as characters, and
  // a second definition would answer differently the day either is fixed.
  const text = visibleText(locus).trim();
  if (text.length > 0) {
    return {
      kind: 'text',
      element: 't',
      sample: text.length > 60 ? `${text.slice(0, 59)}…` : text,
    };
  }

  // ⚠️ THEN THE THINGS THAT PRINT WITHOUT BEING TEXT. Checked SECOND, not
  // instead: a field can carry both, and the text sample is the more useful
  // thing to show a doctor when it exists.
  for (const name of VISIBLE_OBJECTS) {
    if (descendants(locus, name).length > 0) {
      return { kind: 'object', element: name, sample: '' };
    }
    // `descendants` does not consider the node itself.
    if (localName(tagOf(locus)) === name) {
      return { kind: 'object', element: name, sample: '' };
    }
  }
  return null;
}

/** The doctor-facing sentence. One place, so the wording cannot drift. */
export function fieldHygieneDetail(
  label: string | null,
  finding: FieldHygieneFinding,
): string {
  const where = label ? `"${label}"` : 'this field';
  const what =
    finding.kind === 'text'
      ? `leftover content (${finding.sample})`
      : `a leftover ${finding.element === 'delText' ? 'tracked deletion' : finding.element} that prints as a mark on the page`;
  return (
    `${where} contains ${what} and will print on every note where the field is ` +
    `left unfilled. Clean it in the template, or accept it.`
  );
}
