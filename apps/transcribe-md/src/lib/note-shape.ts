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

// ============================================================================
// THE OFFICE COUNTERWEIGHT — and it is PRIOR ART IN THIS REPOSITORY, not a new
// idea. Found by F12-a's independent adversarial pass (ruling #126).
// ----------------------------------------------------------------------------
// ⚠️ `worker/layers/structure-mismatch-reason.ts:53-76` ALREADY SOLVED THIS
// CLASSIFICATION, ALREADY SHIPPED THE NAIVE VERSION, AND ALREADY RECORDED WHY
// IT WAS WRONG. Its comment names the four families a bare `op >= 2` rule gets
// CONFIDENTLY BACKWARDS — every one of them an ORDINARY BILLABLE OFFICE VISIT:
//
//     post-op office follow-up   S/O/A/P + POSTOPERATIVE DIAGNOSIS/FINDINGS
//     derm office w/ excision    S/O/A/P + SPECIMENS + ESTIMATED BLOOD LOSS
//     pre-op H&P (office)        S/O/A/P + PREOPERATIVE DIAGNOSIS
//     surgical consult (office)  S/O/A/P + DESCRIPTION OF PROCEDURE DISCUSSED
//
// A full SOAP skeleton is the STRONGER claim: an operative note does not carry
// all four. So office is tested FIRST and the markers cannot overrule it.
//
// ⚠️ WHY THIS MATTERS MORE HERE THAN THERE: `templateKind` only chooses the
// WORDING OF A BANNER. This predicate decides whether a billable level appears
// on a signed clinical document — the same mistake, with the consequence
// ruling #123 calls WORSE than the defect being fixed.
//
// ⚠️ AND THE PRIOR ART'S SECOND CLAUSE IS DELIBERATELY **NOT** COPIED.
// `templateKind` also declines to call a note operative when `office >= 3`.
// Measured against production 2026-08-18, that clause is wrong here: visit
// `cmrxxj1rn000h01pnoloiiajx` — SIGNED, `signedCode` 99214 — carries
// SUBJECTIVE · OBJECTIVE · ASSESSMENT (three, no PLAN) alongside PROCEDURE ·
// PREOPERATIVE DIAGNOSIS · DESCRIPTION OF PROCEDURE · POSTOPERATIVE FINDINGS ·
// CONSENT. It is an operative note whose generator also emitted S/O/A, and the
// `office >= 3` clause would hand it back its office E/M level. Requiring all
// FOUR keeps it suppressed. **Copying prior art verbatim would have been the
// error; measuring the corpus is what chose the threshold.**
//
// ⚠️ MEASURED IMPACT ON TODAY'S CORPUS: **ZERO verdicts change.** Of 46 notes,
// 18 are op-and-no-SOAP, 1 is op-and-three-SOAP (the row above), 7 are
// SOAP-and-no-markers, 20 are neither. Of 10 templates, 4 are op/no-SOAP and 1
// is SOAP/no-op. The counterweight is pure hardening against the four families
// above, which production has not yet produced.
// ============================================================================

/** The full SOAP skeleton. An operative note does not carry all four. */
export const OFFICE_SKELETON_SECTIONS: readonly string[] = [
  'SUBJECTIVE',
  'OBJECTIVE',
  'ASSESSMENT',
  'PLAN',
];

/** ALL FOUR. Not three — see the measured signed row named above. */
export const OFFICE_SKELETON_FLOOR = OFFICE_SKELETON_SECTIONS.length;

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

/** How many of `PROCEDURE_NOTE_SECTION_MARKERS` this label set contains.
 *  Factored out so the TEMPLATE arm and the NOTE-TEXT arm below count with one
 *  implementation — two copies of a marker count would drift the day either is
 *  edited, and the drift would be invisible because both would still return a
 *  number. */
function countMarkers(labels: Iterable<string>): number {
  const set = new Set(labels);
  let n = 0;
  for (const marker of PROCEDURE_NOTE_SECTION_MARKERS) {
    if (set.has(marker)) n++;
  }
  return n;
}

/** How many of the four SOAP sections this label set carries.
 *
 *  ⚠️ EXACT MATCH ON THE NORMALISED LABEL, NEVER `includes`. The prior art
 *  matches by substring, and that is not safe to copy: **`'IMPLANT'` contains
 *  `'plan'`**, so an `IMPLANT REMOVAL` heading on a genuine operative note
 *  would score an office point and, with three more, hand the note its office
 *  E/M level back. This repository has a canon section on exactly this family
 *  (`'dashboard'` contains `'board'`), and the counterweight is the one place
 *  a false positive costs a suppression.
 *
 *  ⚠️ HONEST LIMIT, STATED RATHER THAN DISCOVERED LATER: a note that spells its
 *  last two sections as ONE heading — `ASSESSMENT & PLAN` — scores 2, not 4,
 *  and so does not reach the counterweight. Production's seven SOAP notes all
 *  carry the four separately (measured 2026-08-18), and every combined-heading
 *  template in production carries ZERO operative markers, so nothing today
 *  depends on it. If that changes, the fix is to name the combined forms
 *  explicitly — never to loosen this to a substring scan. */
function countOfficeSkeleton(labels: Iterable<string>): number {
  const set = new Set(labels);
  let n = 0;
  for (const section of OFFICE_SKELETON_SECTIONS) {
    if (set.has(section)) n++;
  }
  return n;
}

/** THE ONE CLASSIFIER. Both arms — the template's labels and the note body's
 *  own headings — resolve through this, so the counterweight cannot be present
 *  on one and missing on the other.
 *
 *  OFFICE IS TESTED FIRST. That order is the whole correction. */
function labelsReadAsProcedureNote(labels: string[]): boolean {
  if (countOfficeSkeleton(labels) >= OFFICE_SKELETON_FLOOR) return false;
  return countMarkers(labels) >= PROCEDURE_NOTE_MARKER_FLOOR;
}

/** How many DISTINCT operative markers this template's labels carry.
 *  Exported so a guard can assert the margin rather than only the verdict —
 *  a template sitting exactly on the floor is a different fact from one
 *  carrying three markers, and a silent drift from 3 to 1 would flip the
 *  verdict with nothing to see. */
export function procedureNoteMarkerCount(sections: unknown): number {
  return countMarkers(normalizedSectionLabels(sections));
}

// ============================================================================
// THE NOTE'S OWN HEADINGS — the fallback source, added by F12-a's own
// adversarial pass (ruling #126).
// ----------------------------------------------------------------------------
// ⚠️ THE TEMPLATE IS NOT A DURABLE PLACE TO HANG A SUPPRESSION, AND THAT IS
// MEASURED RATHER THAN FEARED. `TranscribeVisit.noteTemplate` is
// `onDelete: SetNull` (`schema.prisma:2225`), so deleting a template nulls the
// relation, the template arm sees nothing, the classifier fails OPEN by design
// — and an office E/M level re-appears on a SIGNED operative record. The
// specialty axis does not have this weakness because `specialty` is a COLUMN.
//
// ⚠️ AND IT IS NOT A FUTURE HAZARD. Measured on production 2026-08-18, over all
// 46 visits: **30 carry no template at all**, and **9 of those 30 are operative
// notes by their own headings** (7 SIGNED). Four of the nine currently carry an
// office E/M code and two of those four have a frozen `signedCode`. So the
// template-only classifier suppresses ONE production row while four operative
// notes keep an office level — the hole is the common case, not the edge.
//
// The note text is the right fallback because it is THE RECORD ITSELF: the
// headings are there because the template put them there, and they survive the
// template's deletion. Nothing else on the visit carries the note's shape.
// ============================================================================

/** A markdown section heading. Optional leading whitespace · 1-6 `#` ·
 *  REQUIRED whitespace · the label.
 *
 *  ⚠️ THE `\s+` IS A CHOICE AND IT WAS CONTROLLED, NOT ASSUMED. Four heading
 *  regexes already exist in this app (`form-only.ts:34` `^##\s+`,
 *  `soap-format.ts:25` `^#{1,6}\s`, `suggestion-labels.ts:82` `^#{1,6}\s+`,
 *  `visit-export.ts:507` `^\s*#{1,6}\s`) and they disagree about the leading
 *  whitespace and the heading depth. Both the permissive form (`\s*`, which
 *  would also match `##HEADING`) and this stricter one were run against all 46
 *  production notes and returned the IDENTICAL distribution — 27 notes with 0
 *  markers, 19 with exactly 3, and nothing in between. So the choice is not
 *  load-bearing on the real corpus, and the stricter one is taken. */
const NOTE_SECTION_HEADING_RE = /^[ \t]*#{1,6}[ \t]+(.+?)[ \t]*$/;

/** The note body's own section labels, normalised the SAME way a template's
 *  are — `normalizeSectionLabel`, so the trailing-colon fixture protects both
 *  arms at once. Non-string input reads as no headings. */
export function normalizedNoteHeadings(noteText: unknown): string[] {
  if (typeof noteText !== 'string' || !noteText) return [];
  const out: string[] = [];
  for (const line of noteText.split('\n')) {
    const m = NOTE_SECTION_HEADING_RE.exec(line);
    if (!m) continue;
    const label = normalizeSectionLabel(m[1]);
    if (label) out.push(label);
  }
  return out;
}

/** How many DISTINCT operative markers the NOTE BODY's own headings carry.
 *  Exported for the same margin reason as the template counterpart. */
export function procedureNoteMarkerCountFromText(noteText: unknown): number {
  return countMarkers(normalizedNoteHeadings(noteText));
}

/** Does the note BODY read as an operative / procedure report? Same marker
 *  list, same floor, same normalisation as the template arm. */
export function isProcedureNoteShapeFromText(noteText: unknown): boolean {
  return labelsReadAsProcedureNote(normalizedNoteHeadings(noteText));
}

/** DID THE TEMPLATE SAY ANYTHING AT ALL?
 *
 *  ⚠️ THIS IS THE WHOLE NARROWNESS OF THE FALLBACK, AND IT IS DELIBERATE.
 *  There are two different states that both produce "not an operative note"
 *  from the template arm, and collapsing them is what would make this fix
 *  dangerous:
 *
 *    SILENT      — no template, or a template with no usable labels.
 *                  The template has NO OPINION. The note text may speak.
 *    NOT-OPERATIVE — a template with labels, none of them markers.
 *                  The template said OFFICE VISIT. The note text may NOT
 *                  overrule it.
 *
 *  Ruling #123 states that over-suppression — silently stripping a billable
 *  level from an office visit — is WORSE than the defect being fixed. So the
 *  note-text arm is a fallback for silence, never a second vote. On the
 *  production corpus the two shapes are indistinguishable (there is no visit
 *  whose template says office while its note text says operative), so this
 *  costs nothing today and cannot bite later. Widening it to an OR across both
 *  sources is a TIGHTENING and is therefore the legal direction to be wrong
 *  in; narrowing after shipping an OR would not be. */
export function templateIsSilent(sections: unknown): boolean {
  return normalizedSectionLabels(sections).length === 0;
}

/** IS THIS NOTE AN OPERATIVE / PROCEDURE REPORT?
 *
 *  A template with NO sections, or no template at all, is NOT an operative
 *  note. That default is deliberate and it is the safe direction: an
 *  unclassified visit keeps whatever its specialty already decided, so a
 *  template this classifier has never seen cannot silently delete a
 *  documentation level from an office visit. The failure mode it leaves open —
 *  an operative note nobody classified keeps its level — is the state that
 *  exists TODAY, and is visible, whereas the inverse is silent.
 *
 *  ⚠️ AND IT IS NOT A BARE `markers >= FLOOR` ANY MORE. The OFFICE
 *  COUNTERWEIGHT is tested first — a full SOAP skeleton means office visit and
 *  the markers cannot overrule it. See the block above `OFFICE_SKELETON_SECTIONS`.
 *  `procedureNoteMarkerCount` still returns the raw margin, so the two are no
 *  longer interchangeable: the COUNT is evidence, the VERDICT is this function.
 *
 *  ⚠️ THAT FAIL-OPEN IS STILL RIGHT FOR *THIS* FUNCTION AND IS NO LONGER THE
 *  END OF THE STORY. `emAppliesToVisit` now consults the NOTE BODY's own
 *  headings when the template is silent (ruling #126), because a template can
 *  be DELETED out from under a signed operative record — and on production
 *  most operative notes have no template at all. Read this predicate as "does
 *  the TEMPLATE say operative", never as "is this an operative note". */
export function isProcedureNoteShape(sections: unknown): boolean {
  return labelsReadAsProcedureNote(normalizedSectionLabels(sections));
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
   *  has no template. */
  templateSections: unknown;
  /** THE NOTE BODY ITSELF — `signedSoap ?? soapFinal` for a signed visit,
   *  `soapFinal` otherwise, which is the rule every caller already uses to
   *  decide what text to render.
   *
   *  REQUIRED, not optional, and for the same reason `templateSections` is: a
   *  caller that has not thought about it must fail to TYPECHECK rather than
   *  inherit a permissive default. An optional `noteText` would have let the
   *  `onDelete: SetNull` hole re-open one un-updated call site at a time, and
   *  nothing would have said so. */
  noteText: unknown;
}): boolean {
  if (!emAppliesToSpecialty(input.specialtyId)) return false;
  if (isProcedureNoteShape(input.templateSections)) return false;
  // THE FALLBACK, AND IT FIRES ONLY INTO SILENCE — see `templateIsSilent`.
  // A template that carries labels and no markers has said "office visit", and
  // the note text does not get to overrule it.
  if (templateIsSilent(input.templateSections) && isProcedureNoteShapeFromText(input.noteText)) {
    return false;
  }
  return true;
}
