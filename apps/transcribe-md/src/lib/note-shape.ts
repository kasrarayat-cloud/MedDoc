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

// ── F12-f: TWO USES, TWO NAMES, TWO FLOORS, ONE VOCABULARY ──────────────────
// `OFFICE_SKELETON_FLOOR` used to be one constant serving both the OPERATIVE
// COUNTERWEIGHT and the OFFICE ESCAPE, and `countOfficeSkeleton` used to be one
// function serving both. That is why F12-d could only widen the escape: moving
// the shared function would have moved the counterweight with it, in the
// UNDER-suppression direction, on a signed record.
//
// They are now two named floors at two named call sites. Neither can be moved
// by editing the other, and a divergence between them is a deliberate, visible
// act at one line rather than a side effect.

/** THE OPERATIVE COUNTERWEIGHT'S FLOOR. How many SOAP concepts a label set must
 *  carry before the operative markers are overruled.
 *
 *  ALL FOUR. Not three — see the measured signed row named above
 *  (`cmrxxj1rn000h01pnoloiiajx`, SUBJECTIVE · OBJECTIVE · ASSESSMENT and no
 *  PLAN, alongside three operative markers). LOWERING THIS IS AN
 *  UNDER-SUPPRESSION and hands that signed record its office E/M level back. */
export const OFFICE_COUNTERWEIGHT_FLOOR = OFFICE_SKELETON_SECTIONS.length;

/** THE OFFICE ESCAPE'S FLOOR. How many SOAP concepts a NOTE BODY must carry
 *  before it may overrule a template that says "operative".
 *
 *  Equal to the counterweight's today, and that equality is asserted rather
 *  than assumed — see `gate-f12f-counterweight-vocabulary.test.ts`. They are
 *  separate constants because they answer separate questions: the counterweight
 *  asks "can these labels belong to an operative note at all?", the escape asks
 *  "does this body affirmatively claim to be an office visit?". */
export const OFFICE_ESCAPE_FLOOR = OFFICE_SKELETON_SECTIONS.length;

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

/** How many of the four SOAP sections this label set carries **LITERALLY**.
 *
 *  ⚠️ EVIDENCE ONLY. THIS IS NO LONGER THE COUNTERWEIGHT — F12-f. Nothing in
 *  this module decides anything with it; it exists so a guard can assert the
 *  MARGIN and, specifically, so a fixture can assert the gap between the
 *  literal spelling and the concept it names (`ASSESSMENT & PLAN` reads 0 here
 *  and 2 in `officeConceptCount`). Do not reintroduce it into a verdict: that
 *  is precisely the coupling F12-f removed.
 *
 *  ⚠️ EXACT MATCH ON THE NORMALISED LABEL, NEVER `includes`. The prior art
 *  matches by substring, and that is not safe to copy: **`'IMPLANT'` contains
 *  `'plan'`**, so an `IMPLANT REMOVAL` heading on a genuine operative note
 *  would score an office point and, with three more, hand the note its office
 *  E/M level back. This repository has a canon section on exactly this family
 *  (`'dashboard'` contains `'board'`), and the counterweight is the one place
 *  a false positive costs a suppression. `officeConceptCount` inherits that
 *  rule unchanged — it adds NAMED spellings, never a substring scan. */
function countLiteralSkeletonLabels(labels: Iterable<string>): number {
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
 *  OFFICE IS TESTED FIRST. That order is the whole correction.
 *
 *  ⚠️ THE COUNTERWEIGHT COUNTS **CONCEPTS**, NOT HEADINGS — F12-f. It used to
 *  count the four literal SOAP words, and F12-d could not widen it without
 *  moving the escape too, so the escape was widened alone and this was left
 *  behind. The asymmetry was a live over-suppression:
 *
 *      SUBJECTIVE · OBJECTIVE · ASSESSMENT & PLAN
 *        + POSTOPERATIVE DIAGNOSIS · POSTOPERATIVE FINDINGS
 *
 *  is a POST-OP OFFICE FOLLOW-UP — the first of the four families ruling
 *  #126(b) names — and the literal counterweight scored it **3**, so the
 *  markers won and an ordinary billable office visit lost its level. Measured
 *  through this classifier before and after: `operative true -> false`. The
 *  derm-office-with-excision family flips the same way. **The number of
 *  headings a doctor used to spell four concepts is not a clinical fact.**
 *
 *  ⚠️ AND THE WIDENING IS BOUNDED TO SPELLINGS OF THE **SAME FOUR CONCEPTS** —
 *  see `REFUSED_OFFICE_CONCEPT_SYNONYMS`, which records the direction that was
 *  measured and rejected. */
function labelsReadAsProcedureNote(labels: string[]): boolean {
  if (officeConceptCount(labels) >= OFFICE_COUNTERWEIGHT_FLOOR) return false;
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

/** DOES THE NOTE BODY AFFIRMATIVELY READ AS AN OFFICE VISIT? — F12-d.
 *
 *  ⚠️ THIS IS NOT `!isProcedureNoteShapeFromText(...)`, AND THE DIFFERENCE IS
 *  THE WHOLE POINT. That predicate has THREE outcomes collapsed into a boolean:
 *  *operative*, *affirmatively office*, and *says nothing either way* (a stub,
 *  a note with one heading, a body still being written). Only the SECOND is
 *  strong enough to overrule a template, so it needs its own name.
 *
 *  The claim is the one ruling #126(b) already made and measured: **the full
 *  SOAP skeleton is the STRONGER claim, because an operative note does not
 *  carry all four.** It uses the same vocabulary and the same floor value as
 *  the counterweight — `officeConceptCount >= OFFICE_ESCAPE_FLOOR` — so the
 *  counterweight cannot be strong in one place and weak in another. Since
 *  F12-f the two floors are separate CONSTANTS carrying the same value, and a
 *  guard asserts they still agree; that is what makes a future divergence a
 *  decision rather than an accident. */
export function noteReadsAsOfficeVisitFromText(noteText: unknown): boolean {
  return officeConceptCount(normalizedNoteHeadings(noteText)) >= OFFICE_ESCAPE_FLOOR;
}

/** Headings that satisfy TWO of the four SOAP concepts at once.
 *
 *  ⚠️ SINCE F12-f THIS VOCABULARY SERVES **BOTH** THE ESCAPE AND THE
 *  COUNTERWEIGHT, AND THAT CONVERGENCE IS THE ITEM. F12-d added it for the
 *  escape only, with the note *"`countOfficeSkeleton` is deliberately not
 *  changed"* — correct at the time, because the counterweight and the escape
 *  shared one function and one floor, so widening either moved both. The
 *  separation now lives in two named floors at two named call sites, so the
 *  vocabulary can be shared without the coupling that forced the split.
 *
 *  The measured consequence of the convergence: a post-op office follow-up or a
 *  derm office excision whose `ASSESSMENT & PLAN` is one heading is no longer
 *  read as an operative note. Both are families ruling #126(b) exists to
 *  protect, and both were defeated by orthography alone.
 *
 *  ⚠️ AND IT IS WHAT MAKES THE ESCAPE STABLE UNDER AN ORDINARY EDIT.
 *  Found by F12-d's adversarial pass: with a literal count, a doctor merging
 *  `## Assessment` and `## Plan` into `## Assessment & Plan` drops the count
 *  4 -> 2 and FLIPS the verdict mid-visit — stranding `emPendingChange`, and
 *  (under Rounds) leaving a visit with no sign control and a banner whose text
 *  is false. The concepts are what the doctor documented; the number of
 *  headings they used to spell them is not a clinical fact. */
const OFFICE_CONCEPT_PAIRS: ReadonlyArray<readonly [string, readonly string[]]> = [
  // label spelled by the doctor        -> the concepts it satisfies
  ['ASSESSMENT & PLAN', ['ASSESSMENT', 'PLAN']],
  ['ASSESSMENT AND PLAN', ['ASSESSMENT', 'PLAN']],
  ['ASSESSMENT/PLAN', ['ASSESSMENT', 'PLAN']],
  ['IMPRESSION & PLAN', ['ASSESSMENT', 'PLAN']],
  ['IMPRESSION AND PLAN', ['ASSESSMENT', 'PLAN']],
  ['IMPRESSION/PLAN', ['ASSESSMENT', 'PLAN']],
  ['SUBJECTIVE & OBJECTIVE', ['SUBJECTIVE', 'OBJECTIVE']],
  ['SUBJECTIVE AND OBJECTIVE', ['SUBJECTIVE', 'OBJECTIVE']],
];

/** SINGLE-CONCEPT SYNONYMS THAT WERE MEASURED AND **REFUSED** — F12-f.
 *
 *  ⚠️ THIS IS A RECORD OF A REJECTED DIRECTION, NOT A TODO LIST. Every label
 *  here is a plausible office-visit heading, and adding any of them to
 *  `OFFICE_CONCEPT_PAIRS` would weaken the operative counterweight. The
 *  temptation is concrete: production's ACTIVE template
 *  `cmpz63jsw000501tayag818lq` spells its sections `CHIEF COMPLAINT · INTERVAL
 *  HISTORY · EXAM · IMPRESSION & PLAN · PATIENT INSTRUCTIONS`, so an office
 *  note in that vocabulary reaches only TWO concepts and, under an operative
 *  template, is still over-suppressed. That residual is real and it is
 *  **forward-only** — measured 2026-08-19, that template is bound to **0**
 *  visits.
 *
 *  ⚠️ AND THE OBVIOUS CURE WAS RUN AGAINST THE CORPUS AND CAME BACK WORSE.
 *  Teaching the counterweight these synonyms **un-suppresses a SIGNED
 *  operative record**: visit `cmrxxj1rn000h01pnoloiiajx`, bariatric surgery,
 *  SIGNED with a FROZEN `signedCode` 99214, whose body is
 *
 *      PROCEDURE · PREOPERATIVE DIAGNOSIS · POSTOPERATIVE FINDINGS · CONSENT
 *      · DESCRIPTION OF PROCEDURE · RECOMMENDATIONS · SUBJECTIVE · OBJECTIVE
 *      · ASSESSMENT
 *
 *  — three operative markers and three SOAP concepts. `RECOMMENDATIONS -> PLAN`
 *  takes it to FOUR, the counterweight fires, and the note that ruling #126(b)
 *  calibrated the floor of FOUR against gets its office E/M level back.
 *  Measured: `+0 newly suppressed, +1 newly APPLIED`, and that one row is it.
 *
 *  ⚠️ AND `RECOMMENDATIONS` IS NOT AN EDGE CASE — IT IS THE OPERATIVE NOTE'S
 *  OWN PLAN SECTION. Census over the production corpus: it appears in **4 of 4**
 *  operative templates and **19 of 19** operative note bodies, and on **no**
 *  record without operative markers. The label that looks most like an office
 *  synonym is the one most reliably attached to an operative note.
 *
 *  ⚠️ AND REMOVING THE ONE PROVEN OFFENDER IS NOT A FIX. With
 *  `RECOMMENDATIONS` dropped, the remaining synonyms move **0** corpus rows —
 *  and that zero is worth nothing, because the corpus holds exactly ONE
 *  operative vocabulary, emitted 19 times by one generator. A clean diff over
 *  a monoculture is not evidence of safety; it is evidence that the corpus
 *  cannot discriminate. `DIAGNOSIS · FINDINGS · CHIEF COMPLAINT · PATIENT
 *  INSTRUCTIONS` is an entirely ordinary operative-note heading set that would
 *  score FOUR under those synonyms, and nothing in today's data would object.
 *
 *  **WHAT WOULD RETIRE THIS REFUSAL:** a production corpus containing office
 *  notes written in a non-SOAP vocabulary *under an operative template* — i.e.
 *  the residual acquiring its first real instance — measured per label, with
 *  the corpus diff run in both directions. Not a feeling that it is safe, and
 *  not the absence of a counterexample in a corpus with one operative
 *  vocabulary in it. */
export const REFUSED_OFFICE_CONCEPT_SYNONYMS: readonly string[] = [
  'RECOMMENDATIONS',
  'CHIEF COMPLAINT',
  'INTERVAL HISTORY',
  'HISTORY OF PRESENT ILLNESS',
  'HPI',
  'EXAM',
  'PHYSICAL EXAM',
  'PHYSICAL EXAMINATION',
  'FINDINGS',
  'IMPRESSION',
  'DIAGNOSIS',
  'PATIENT INSTRUCTIONS',
  'PLAN OF CARE',
];

/** How many of the four SOAP CONCEPTS the labels carry, counting the combined
 *  spellings above.
 *
 *  ⚠️ IT ONLY EVER ADDS **SPELLINGS OF THE SAME FOUR CONCEPTS**, never a fifth
 *  concept and never a synonym for one of them. That bound is what keeps
 *  #126(b)'s claim intact: *an operative note does not carry all four SOAP
 *  concepts*, however the doctor spells them. See
 *  `REFUSED_OFFICE_CONCEPT_SYNONYMS` for the direction that breaks it, and the
 *  signed record that proves it does.
 *
 *  Exact match on the normalised label throughout — never `includes`, for the
 *  reason `countLiteralSkeletonLabels` records (`'IMPLANT'` contains
 *  `'plan'`). */
function officeConceptCount(labels: Iterable<string>): number {
  const set = new Set(labels);
  const satisfied = new Set<string>();
  for (const section of OFFICE_SKELETON_SECTIONS) {
    if (set.has(section)) satisfied.add(section);
  }
  for (const [label, concepts] of OFFICE_CONCEPT_PAIRS) {
    if (set.has(label)) for (const c of concepts) satisfied.add(c);
  }
  return satisfied.size;
}

/** The concept count, exported for the same margin reason as its siblings — a
 *  guard can assert WHY a body did or did not reach the escape. */
export function officeConceptCountFromText(noteText: unknown): number {
  return officeConceptCount(normalizedNoteHeadings(noteText));
}

/** How many of the four SOAP sections the NOTE BODY's own headings carry
 *  **LITERALLY**. Exported for the same reason as
 *  `procedureNoteMarkerCountFromText`: the COUNT is evidence and the VERDICT is
 *  the function, and a fixture sitting at 0 is a different fact from one
 *  sitting at 3 — which is precisely the distinction that let a test fixture
 *  stand in for a production row it did not resemble (F12-d). A guard can now
 *  assert the MARGIN, not only the answer.
 *
 *  ⚠️ SINCE F12-f THIS IS NOT THE QUANTITY ANY VERDICT USES. Both the
 *  counterweight and the escape read `officeConceptCount`. The gap between the
 *  two is exactly the point of the pair — on `## Assessment & Plan` this reads
 *  **0** and the concept count reads **2** — so a guard asserting only this one
 *  would be asserting a number nothing consults. */
export function officeSkeletonCountFromText(noteText: unknown): number {
  return countLiteralSkeletonLabels(normalizedNoteHeadings(noteText));
}

/** DID THE TEMPLATE SAY ANYTHING AT ALL?
 *
 *  ⚠️ STILL LOAD-BEARING. F12-d PROPOSED UNGATING THE ARM THIS GUARDS INTO AN
 *  OR AND THE ADVERSARIAL PASS KILLED THAT — see the comment beside the
 *  fallback in `emAppliesToVisit`. Do not "simplify" it away.
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
  const labels = normalizedSectionLabels(sections);
  // No template at all, or a malformed one: nothing said.
  if (labels.length === 0) return true;
  // ⚠️ AND A TEMPLATE THAT SAYS NOTHING BUT "SOAP" HAS ALSO SAID NOTHING ABOUT
  // THE ENCOUNTER — it has described the document's SKELETON, not its KIND.
  //
  // THIS IS THE HOLE THE INDEPENDENT ADVERSARIAL PASS FOUND, AND WITHOUT IT
  // #126a IS INERT FOR EVERY FUTURE VISIT. `worker/layers/04-generate-soap.ts`
  // writes `noteTemplateId: template.id` UNCONDITIONALLY on both of its paths
  // (`:523` and `:562`), and `template` falls back to
  // `SYSTEM_DEFAULT_NOTE_TEMPLATE` when resolution fails — whose sections are
  // exactly `Subjective · Objective · Assessment · Plan`. Four labels, zero
  // markers. So a bariatric surgeon with no operative template dictates an
  // op note, the resolver binds the system default, the template arm sees no
  // markers, `templateIsSilent` would have been FALSE, the note body would
  // never be read, and the operative note keeps its office E/M level.
  //
  // ⚠️ AND THE DOCTOR CANNOT CONFIGURE THEIR WAY OUT. `note_templates` carries
  // a PARTIAL unique on `(doctorId, encounterType) WHERE status='active'`, and
  // the resolver keys `encounterType` on the SPECIALTY — so one doctor cannot
  // hold an active office template AND an active operative template for one
  // specialty. That is the very split this module exists for.
  //
  // MEASURED: `tmpl_system_default_soap` is bound on 2 production visits
  // (2026-06-15 and 2026-08-14), both carrying ZERO operative markers, so this
  // changes no verdict today — it is the forward population it saves.
  //
  // ⚠️ THE ALTERNATIVE WAS TO THREAD `isSystemDefault` FROM THE DATABASE, and
  // it was NOT taken. It is the more direct statement of the mechanism, and it
  // requires a new column at all seven call sites plus a new prop; this form
  // needs none, and it gives the SAME answer wherever it differs — because
  // whenever it fires, the NOTE BODY decides, and the body carries the office
  // counterweight. A bare-SOAP template on an office note reads office from the
  // body; on an operative note it reads operative. Both correct.
  //
  // ⚠️ AND "BARE SOAP" MEANS BARE **CONCEPTS**, NOT BARE LITERAL WORDS — F12-f,
  // AND THIS CLAUSE WAS A HALF-LANDED FIX UNTIL THE REFUTATION PASS RAN ON IT.
  // F12-f moved the counterweight from literal labels to CONCEPTS and did not,
  // at first, move this. The two then disagreed about the same template, and the
  // disagreement had a concrete wrong output — verified, not reasoned:
  //
  //     template SUBJECTIVE · OBJECTIVE · ASSESSMENT · PLAN     silent -> body
  //       + an OPERATIVE note body            E/M applies = FALSE   ✔ suppressed
  //     template SUBJECTIVE · OBJECTIVE · ASSESSMENT & PLAN     NOT silent
  //       + the SAME operative note body      E/M applies = TRUE    ✘
  //
  // **An operative note kept an office E/M level purely because the doctor
  // merged two headings in their TEMPLATE.** That is the identical defect F12-f
  // exists to remove, one function over — and it is exactly the shape canon
  // warns about: the failure that ships is the first edit the code's own comment
  // invites, with the other layer still missing.
  //
  // The clause's own stated reason settles the direction: a template that names
  // only the document's SKELETON has said nothing about the ENCOUNTER, and
  // `ASSESSMENT & PLAN` names skeleton exactly as much as `ASSESSMENT` and
  // `PLAN` do. So silence is judged on the concepts, and a label carrying no
  // office concept at all still makes the template speak.
  //
  // ⚠️ DIRECTION AND BLAST RADIUS, BECAUSE THIS ONE LOOSENS `templateIsSilent`
  // AND THEREFORE **TIGHTENS** SUPPRESSION. More templates read as silent, so
  // the note body is consulted more often — and the body only suppresses when it
  // affirmatively reads operative (2+ markers AND fewer than four concepts). It
  // cannot strip a level from an office-shaped body, because such a body reaches
  // the counterweight first. MEASURED over all 48 production visits: **+0 in
  // either direction** — no production template spells its skeleton with a
  // merged heading, so this is forward-only, like the rest of F12-f.
  return labels.every((l) => officeConceptCount([l]) > 0);
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

  // ── THE PROXY DOES NOT OVERRULE AN AFFIRMATIVELY OFFICE-SHAPED RECORD ────
  // F12-d. This is the ONLY thing F12-d changes, and its scope was cut down to
  // this by the mandatory adversarial pass — see the two rejected halves below.
  //
  // ⚠️ WITHOUT THIS CONJUNCT A **SIGNED** OFFICE VISIT LOSES ITS BILLABLE
  // LEVEL, AND THAT IS LIVE IN PRODUCTION, NOT A HYPOTHETICAL. Measured
  // 2026-08-18: visit `cmsu1mhrp000h01nsxpvxxshk`, SIGNED, `gastroenterology`,
  // body headings `CHIEF COMPLAINT · SUBJECTIVE · OBJECTIVE · ASSESSMENT ·
  // PLAN`, `cptCodes.em.code` 99215 and a FROZEN `signedCode` 99214 — an
  // unambiguous office visit whose export F12-a suppresses. Ruling #123 names
  // over-suppression as WORSE than the defect being fixed.
  //
  // ⚠️ AND THE MECHANISM IS NOT THE ONE THIS COMMENT FIRST CLAIMED — CORRECTED
  // BY THE ADVERSARIAL PASS, WHICH READ THE ROW INSTEAD OF ASSUMING IT.
  // The first draft said "because that GI doctor's ACTIVE template is
  // colonoscopy-shaped", and reasoned from the partial unique on
  // `(doctorId, encounterType) WHERE status='active'` that the doctor could not
  // configure their way out. **Both halves are false for this row.** Measured:
  //
  //     bound template  cmsu1jsls000901ns6y1aeoy6  "Operative Note"  INACTIVE
  //     that doctor's ONE active template          "Venous Duplex …"  IMAGING
  //
  // The visit's `noteTemplateId` FK is FROZEN to a template that has since been
  // RETIRED, and every read path joins it **without a status filter**. So a
  // retired template goes on classifying signed visits forever, and the doctor
  // has already reconfigured — which is a STRONGER argument for reading the
  // record rather than the proxy, not a weaker one. Read to form a hypothesis;
  // RUN something to name a mechanism.
  //
  // ⚠️ THE ESCAPE IS AFFIRMATIVE ON BOTH LEGS, AND THE SECOND LEG WAS ADDED BY
  // A REFUTER. `noteReadsAsOfficeVisitFromText` is a bare `countOfficeSkeleton
  // >= 4` with NO marker check, so a body carrying the full SOAP skeleton
  // **and** three operative markers satisfied it — `isProcedureNoteShapeFromText`
  // returns false there because the office counterweight is tested first, so
  // nothing else objected either. Verified: that input flipped `false -> true`,
  // which would freeze an office E/M onto a signed operative record at
  // `sign/route.ts:538` — the exact state that conjunction exists to prevent.
  // Requiring ZERO operative markers costs nothing (the rescued row has none)
  // and closes it.
  if (
    isProcedureNoteShape(input.templateSections) &&
    !(
      noteReadsAsOfficeVisitFromText(input.noteText) &&
      procedureNoteMarkerCountFromText(input.noteText) === 0
    )
  ) {
    return false;
  }

  // THE FALLBACK, AND IT FIRES ONLY INTO SILENCE — see `templateIsSilent`.
  // A template that carries labels and no markers has said "office visit", and
  // the note text does not get to overrule it.
  //
  // ⚠️ F12-d DELIBERATELY DID **NOT** UNGATE THIS INTO AN OR, AND THE FIRST
  // DRAFT DID. Ruling #126 names the OR as "a TIGHTENING and therefore the
  // legal direction to be wrong in", and the corpus says it changes ZERO
  // production verdicts — so it guards a hole with no instance. A refuter then
  // showed it INTRODUCES one: production template `cmpz63jsw000501tayag818lq`
  // is ACTIVE and spells its sections `CHIEF COMPLAINT · INTERVAL HISTORY ·
  // EXAM · IMPRESSION & PLAN · PATIENT INSTRUCTIONS`, so a body written in that
  // vocabulary cannot reach the office counterweight while an in-room excision
  // supplies two operative markers. Verified: `true -> false` — an ordinary
  // billable office visit silently loses its level, which is precisely the
  // "derm office w/ excision" family #126(b)'s counterweight exists to protect,
  // defeated because the counterweight is unreachable for that wording.
  //
  // ⚠️ F12-f RE-MEASURED THAT COUNTEREXAMPLE AND IT SURVIVES, WITH A CORRECTED
  // NUMBER. The refuter's figure was "scores **0**", which was true of the
  // literal counterweight. The counterweight now counts CONCEPTS, so
  // `IMPRESSION & PLAN` is seen and that body scores **2** — `CHIEF COMPLAINT`,
  // `INTERVAL HISTORY` and `EXAM` are refused synonyms, deliberately, and
  // supply nothing. Two is still short of the floor of four, so the OR remains
  // unshippable for exactly the reason recorded here. **The count moved; the
  // conclusion did not** — and re-reading it was the point, because an
  // exemption's reason is prose and prose decays silently.
  //
  // F12-f DID split the two uses and DID name the combined-heading forms. What
  // it did NOT do is teach the counterweight single-concept synonyms, which is
  // what this arm would additionally need — see
  // `REFUSED_OFFICE_CONCEPT_SYNONYMS` and the signed record that refused it.
  if (templateIsSilent(input.templateSections) && isProcedureNoteShapeFromText(input.noteText)) {
    return false;
  }

  return true;
}
