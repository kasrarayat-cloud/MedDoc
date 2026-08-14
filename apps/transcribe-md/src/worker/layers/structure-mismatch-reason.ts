// ============================================================================
// The review banner's sentence, when L4's output misses the template's headings.
// ----------------------------------------------------------------------------
// ⚠️ WRITTEN AGAINST A REAL PRODUCTION VISIT. `cmssgh1w7000r01no7g394xpj`
// (gastroenterology, READY, unsigned) failed structure validation with SIX
// operative-note headings absent — PROCEDURE, PREOPERATIVE DIAGNOSIS,
// POSTOPERATIVE FINDINGS, CONSENT, DESCRIPTION OF PROCEDURE, RECOMMENDATIONS.
// An office-visit dictation against an operative-note template.
//
// THE SYSTEM BEHAVED CORRECTLY. It detected the mismatch, set `needsReview`,
// and drew the amber banner. What it said was:
//
//     "SOAP draft didn't match expected markdown structure — manual review
//      required."
//
// ⚠️ TRUE, AND NEARLY USELESS TO A CLINICIAN. It names a symptom in the
// system's own vocabulary ("markdown structure") and gives the doctor nothing
// to act on — while the validator already knew the six section names AND that
// the template is a different KIND of document from the dictation.
//
// A warning that does not say what to do about it is decoration. This says
// which sections are empty, what kind of document the template expects, and
// where to change it.
//
// PHI POSTURE: section HEADINGS and counts only. Never a value, never a line
// of the note, never the transcript. The same discipline as the
// MODEL_OUTPUT_VALIDATION_FAIL audit row this sits beside.
// ============================================================================

/** Heading sets that identify a template as a PROCEDURE / OPERATIVE note
 *  rather than an office visit. Matched case-insensitively against the
 *  template's own required headings.
 *
 *  ⚠️ A HEURISTIC, AND NAMED AS ONE. It changes only the WORDING of a banner —
 *  never a gate, never the note, never a code. When it does not fire the
 *  sentence degrades to the generic form, which is still better than what it
 *  replaces because it still lists the missing sections. */
const OPERATIVE_MARKERS = [
  'preoperative diagnosis',
  'postoperative diagnosis',
  'postoperative findings',
  'description of procedure',
  'operative findings',
  'specimens',
  'estimated blood loss',
];

const OFFICE_MARKERS = ['subjective', 'objective', 'assessment', 'plan'];

export type TemplateKind = 'operative' | 'office' | 'unknown';

/** What KIND of document the template's headings describe. */
export function templateKind(requiredHeadings: readonly string[]): TemplateKind {
  const lower = requiredHeadings.map((h) => h.toLowerCase().replace(/[:#]/g, '').trim());
  const op = OPERATIVE_MARKERS.filter((m) => lower.some((h) => h.includes(m))).length;
  const office = OFFICE_MARKERS.filter((m) => lower.some((h) => h === m)).length;
  // Two markers, not one: a single "plan" heading appears on operative notes
  // too, and one match is a coincidence rather than a shape.
  if (op >= 2) return 'operative';
  if (office >= 3) return 'office';
  return 'unknown';
}

/**
 * The banner sentence. Names the missing sections, and the document-kind
 * mismatch when it can be established.
 *
 * ⚠️ THE COUNT COMES FROM THE ARRAY, NEVER FROM A SEPARATE TALLY. "six
 * sections" and a list of five is the kind of contradiction a reader stops
 * trusting the whole banner over.
 */
export function structureMismatchReason(
  missingSections: readonly string[],
  requiredHeadings: readonly string[],
  validatorReason?: string | null,
): string {
  // ⚠️ THREE FAIL CLASSES SET `missingSections` TO **ALL** REQUIRED SECTIONS
  // WITHOUT THE DICTATION BEING AT FAULT — empty output, output-too-short, and
  // a JSON-shaped envelope (`soap-structure-validator.ts:117-149`). In those
  // the MODEL returned nothing usable; the doctor's template and their
  // dictation are both fine.
  //
  // Saying "4 sections had no content the dictation supported" there blames
  // the clinician's dictation for a model failure, and points them at the
  // Note-format picker to fix something that is not broken. Caught when the
  // empty-output test reddened with exactly that sentence.
  const r = (validatorReason ?? '').toLowerCase();
  if (r.startsWith('empty output') || r.startsWith('output too short') || r.startsWith('output is json')) {
    return (
      'The note did not come back in a usable form — this is a generation ' +
      'failure, not a problem with your template or your dictation. ' +
      'Regenerate, or review the note in full before signing.'
    );
  }
  const missing = missingSections.filter((s) => typeof s === 'string' && s.trim() !== '');
  const n = missing.length;
  const list = missing.join(', ');

  if (n === 0) {
    // Structure failed for a reason other than absent headings (empty output,
    // no headings at all). Say that rather than printing "0 sections".
    return (
      'This note did not come back in the shape your template asks for, and it ' +
      'could not be matched section by section. Review the whole note before signing.'
    );
  }

  const kind = templateKind(requiredHeadings);
  const noun = n === 1 ? 'section' : 'sections';
  const head =
    kind === 'operative'
      ? 'Your template is an OPERATIVE / PROCEDURE note, and this dictation did not fill it. '
      : kind === 'office'
        ? 'Your template is an OFFICE-VISIT note, and this dictation did not fill it. '
        : '';

  return (
    `${head}${n} ${noun} had no content the dictation supported: ${list}. ` +
    'Review the note before signing — and if this is the wrong template for ' +
    'this encounter, change it in Settings › My Note Format.'
  );
}
