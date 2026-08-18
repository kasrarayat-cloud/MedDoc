// ============================================================================
// NOTE SHAPE — the SECOND AXIS of E/M applicability (F12, ruling #123)
// ----------------------------------------------------------------------------
// `emAppliesToSpecialty(id)` answers "does this SPECIALTY bill office E/M?".
// It cannot answer "is this particular note an operative report?", because a
// GI doctor does office visits AND colonoscopies under ONE specialty id.
// Measured on production while F12 was built: the operative-note visits sit
// under `bariatric-surgery` and `gastroenterology`, and BOTH of those also
// hold office visits. A specialty-keyed predicate is structurally incapable of
// separating them, so this is a second axis rather than another specialty.
//
// ⚠️ IT IS NOT HUNG ON `note_templates.encounterType`, AND THAT IS MEASURED
// RATHER THAN ASSUMED. That column LOOKS like the note-shape slot and is not:
// it is NULL on all 10 production rows, and `worker.ts` resolves templates with
// `encounterType: visit.specialty` — it IS the specialty slot under another
// name. Hanging the axis there would collide with the resolver and would still
// leave every existing row unclassified, so the shape is read from the
// template's own SECTION LABELS, which classify the rows that already exist
// with no migration at all.
// ============================================================================

// LIVES IN THE APP, NOT IN `packages/shared`, AND THAT IS A MEASURED CHOICE
// RATHER THAN A TASTE ONE. Every consumer of this axis is inside
// `apps/transcribe-md` (export loader, worker L4, the visit page, three store
// paths, three gates), so `packages/shared` buys nothing — and it costs
// something real: a `git worktree` checks out TRACKED FILES ONLY and has no
// `node_modules`, so `@meddoc/shared/*` resolves by walking UP to
// `/opt/meddoc-pro/node_modules/@meddoc/shared`, which is a symlink to the
// SHARED TREE's copy. A new file added to that package under a worktree is
// therefore invisible to `tsc` and to every `@meddoc/*` import — silently, and
// it resolves to another tree's code rather than failing loudly.
import { emAppliesToSpecialty } from '@meddoc/shared/specialties';

/** Section labels that only an OPERATIVE / PROCEDURE report carries.
 *
 *  ⚠️ `PROCEDURE` AND `CONSENT` ARE DELIBERATELY ABSENT FROM THIS LIST, and
 *  that omission is the guard against over-suppression — which ruling #123
 *  names as worse than the defect being fixed. An office visit legitimately
 *  carries a `PROCEDURE` section when a biopsy or an injection is done in the
 *  room, and it legitimately carries `CONSENT`; neither makes the encounter an
 *  operative note, and neither may be allowed to strip a billable level from an
 *  office visit on its own. Every marker below names a thing that happens only
 *  in an operating room or an endoscopy suite.
 *
 *  Compared AFTER `normalizeSectionLabel`, never raw. */
export const PROCEDURE_NOTE_SECTION_MARKERS: readonly string[] = [
  'PREOPERATIVE DIAGNOSIS',
  'PRE-OPERATIVE DIAGNOSIS',
  'POSTOPERATIVE DIAGNOSIS',
  'POST-OPERATIVE DIAGNOSIS',
  'POSTOPERATIVE FINDINGS',
  'POST-OPERATIVE FINDINGS',
  'DESCRIPTION OF PROCEDURE',
  'OPERATIVE FINDINGS',
  'ESTIMATED BLOOD LOSS',
  'SPECIMENS REMOVED',
  'INDICATIONS FOR PROCEDURE',
];

/** How many distinct markers must be present before a note counts as
 *  operative. TWO, not one, and the reason is the same asymmetry as the
 *  omissions above: a single borrowed heading on an otherwise ordinary office
 *  template must not silently delete that visit's documentation level.
 *  Every operative template in production carries THREE. */
export const PROCEDURE_NOTE_MARKER_FLOOR = 2;

/** Trim · strip a trailing colon · collapse inner whitespace · upper-case.
 *
 *  ⚠️ THE TRAILING COLON IS LOAD-BEARING AND IT IS IN THE REAL DATA. One of
 *  the four production operative templates spells every label with a trailing
 *  `:` (`PROCEDURE:`, `CONSENT:`, `DESCRIPTION OF PROCEDURE:` …). An
 *  exact-match classifier finds 3 of 4 and reports a confident, wrong answer —
 *  so the fourth template is a FIXTURE in the guard, and this normalisation
 *  cannot be dropped later without that fixture going red. */
export function normalizeSectionLabel(label: unknown): string {
  if (typeof label !== 'string') return '';
  return label
    .trim()
    .replace(/:+$/, '')
    .trim()
    .replace(/\s+/g, ' ')
    .toUpperCase();
}

/** Pull the normalised label set out of a `note_templates.sections` JSONB
 *  value. Tolerant by construction: the column is `Json`, so every element is
 *  `unknown` until proven otherwise, and a malformed row must read as "no
 *  markers" rather than throwing inside an export. */
export function normalizedSectionLabels(sections: unknown): string[] {
  if (!Array.isArray(sections)) return [];
  const out: string[] = [];
  for (const s of sections) {
    if (!s || typeof s !== 'object') continue;
    const label = normalizeSectionLabel((s as { label?: unknown }).label);
    if (label) out.push(label);
  }
  return out;
}

/** How many DISTINCT operative markers this template's labels carry.
 *  Exported so a guard can assert the margin rather than only the verdict —
 *  a template sitting exactly on the floor is a different fact from one
 *  carrying three markers, and a silent drift from 3 to 1 would flip the
 *  verdict with nothing to see. */
export function procedureNoteMarkerCount(sections: unknown): number {
  const labels = new Set(normalizedSectionLabels(sections));
  let n = 0;
  for (const marker of PROCEDURE_NOTE_SECTION_MARKERS) {
    if (labels.has(marker)) n++;
  }
  return n;
}

/** IS THIS NOTE AN OPERATIVE / PROCEDURE REPORT?
 *
 *  A template with NO sections, or no template at all, is NOT an operative
 *  note. That default is deliberate and it is the safe direction: an
 *  unclassified visit keeps whatever its specialty already decided, so a
 *  template this classifier has never seen cannot silently delete a
 *  documentation level from an office visit. The failure mode it leaves open —
 *  an operative note nobody classified keeps its level — is the state that
 *  exists TODAY, and is visible, whereas the inverse is silent. */
export function isProcedureNoteShape(sections: unknown): boolean {
  return procedureNoteMarkerCount(sections) >= PROCEDURE_NOTE_MARKER_FLOOR;
}

/** DOES AN OFFICE-VISIT E/M LEVEL APPLY TO THIS VISIT AT ALL — BOTH AXES.
 *
 *  ⚠️ THIS IS THE ONLY PLACE THE TWO AXES ARE CONJOINED, AND THAT IS THE WHOLE
 *  POINT. `emAppliesToSpecialty`'s own doc-comment records what happened last
 *  time this conjunction was open-coded: `!(ultrasoundSpecialtyEnabled() &&
 *  isImagingReportSpecialty(x))` lived in SEVEN places, one of them spelled
 *  with a display label instead of an id, and every ultrasound visit computed
 *  and stored an office E/M level for it. Adding a second axis multiplies that
 *  surface, so callers get one named function and never the `&&`.
 *
 *  Both axes SUPPRESS — the result is true only when neither objects. */
export function emAppliesToVisit(input: {
  /** The specialty **ID** (`visit.specialty`), never a display label.
   *  `findSpecialty('Ultrasound').id` is `'unspecified'` — quietly the wrong
   *  specialty, with no throw. */
  specialtyId: string | null | undefined;
  /** The bound template's `sections` JSONB, or null/undefined when the visit
   *  has no template. Untemplated visits are not operative notes — see
   *  `isProcedureNoteShape`. */
  templateSections: unknown;
}): boolean {
  if (!emAppliesToSpecialty(input.specialtyId)) return false;
  if (isProcedureNoteShape(input.templateSections)) return false;
  return true;
}
