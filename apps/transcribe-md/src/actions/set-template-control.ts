'use server';

// ============================================================================
// F24-S5 — setTemplateControlAction: the doctor corrects ONE form control.
// ----------------------------------------------------------------------------
// The 28 enumerated content controls on a certified twin were the whole of
// F24's remaining gap. They render from the fill's `selectedOptionOrdinal`, not
// from the note markdown, so no amount of note editing could reach them: the
// only surface that could was this one, and it did not exist.
//
// WHAT THIS IS NOT. It is not a note edit. `soapFinal` is untouched — a control
// value faked into the markdown would be a second, divergent record of the same
// selection, and the renderer would still ignore it. The correction is stored
// as an INPUT to the fill (`TemplateTwinFieldOverride`) and re-applied on every
// run, and the manifest's `overridesSha256` makes the export and sign gates SEE
// it — the two halves that only work together.
//
// ⚠️ VALIDATE-OR-REFUSE, AND NAME THE OPTIONS. A dropdown that accepts prose is
// a form that lies about being a form. The requested value must match one of
// THAT control's own compiled options; anything else is refused WITH the list,
// so the next turn can answer the question the refusal asks instead of guessing
// again. Matching is exact-then-case-insensitive over both the option's
// displayText and its value, and an ambiguous match REFUSES rather than picking.
// ============================================================================

import prisma from '@meddoc/db';

import { requireSession } from '@/lib/auth';
import { logAudit } from '@/lib/audit';
import { visitByIdScope, type PracticeId } from '@/lib/practice-scope';
import { invalidateVisitFills } from '@/lib/docx-preview/fill-cache';
import { TemplateDocIRSchema, type TemplateDocIR } from '@/lib/template-twin/ir';
import { isWordPlaceholderOption } from '@/lib/note-template-docx/placeholder-option';
import { SCAFFOLD_INSERTABLE_KINDS } from '@/lib/template-twin/clinician-override';
import { scaffoldDefaultOfferable } from '@/lib/template-twin/clinician-override';
import type { ProcessTemplateTwinVisitInput } from '@/lib/template-twin/fill-engine';
import { readAndPrepareTemplateTwinFill } from '@/lib/template-twin/fill-engine';

export interface SetTemplateControlResult {
  ok: boolean;
  /** Doctor-facing. PHI-free. */
  error?: string;
  /** The options this control actually allows, when the refusal is about the
   *  value. Present so the caller can NAME them rather than say "invalid". */
  options?: string[];
  /** The control's label and the option that was set, for the reply. */
  label?: string;
  value?: string;
}

/** Fold for matching. Deliberately conservative: case and surrounding space
 *  only. No stemming, no synonyms, no fuzzy distance — a near-miss on a
 *  clinical dropdown must refuse and show the list, not guess. */
function fold(s: string): string {
  return s.trim().toLowerCase();
}

/** What both doors need before they can decide anything: the visit, the
 *  certified twin, and the one field being addressed.
 *
 *  ⚠️ EXTRACTED SO THE TWO DOORS CANNOT DRIFT APART ON THE GUARDS THEY SHARE.
 *  REVIEW-DEFAULTS added a second writer to this table, and the shared half —
 *  practice scope, the sign-freeze, template binding, certification, field
 *  existence — is exactly the half where a second copy would eventually differ
 *  from the first by one line and nobody would notice which. The guards that
 *  are NOT shared stay in their own door, where the difference is visible.
 */
/**
 * ⚠️ THE VISIT SELECT CARRIES SIX COLUMNS FOR ONE CALLER —
 * `insertScaffoldDefaultAction`, which under ruling #204 must resolve the SAME
 * per-visit answer the preview does, through the SAME entry. They are the exact
 * inputs `preview-visit-document.ts` feeds `readAndPrepareTemplateTwinFill`;
 * fetching fewer would make the door ask a different question and agree with the
 * offer only by luck.
 *
 * ⚠️ AND THE EXPLANATION LIVES HERE RATHER THAN INSIDE THE SELECT FOR A REASON
 * WORTH KNOWING. `gate-practice-scope`'s ratchet decides a read is scoped by
 * looking back FORTY LINES for a scope accessor. Six columns plus a six-line
 * comment pushed `visitByIdScope` (line ~94) to 43 lines above the
 * `noteTemplate` read, and the gate reported a new UNSCOPED clinical read —
 * on a query whose text had not changed at all. Reddened by prose: the same
 * defect canon 117 records in the other direction, met here in a gate that
 * measures distance rather than meaning.
 */
async function resolveCertifiedTwinField(
  visitId: string,
  fieldId: string,
  practiceId: PracticeId,
): Promise<
  | { ok: false; error: string }
  | {
      ok: true;
      practiceId: string;
      compiledVersionId: string;
      field: TemplateDocIR['fields'][number];
      /** The visit row this function already read — see the select's note. */
      visit: {
        status: string;
        userId: string;
        inputMode: string | null;
        transcriptText: string | null;
        entities: unknown;
        soapFinal: string | null;
        createdAt: Date;
        // ⚠️ #267 — the VISIT'S OWN tenant, beside the author's practice.
        // Two different columns; the stored rows carry this one.
        practiceId: string;
        user: { practiceId: string };
      };
      noteTemplateId: string;
      noteTemplateVersion: number;
    }
> {
  const visit = await prisma.transcribeVisit.findFirst({
    where: {
      ...visitByIdScope(visitId, practiceId),
      deletedAt: null,
      archivedAt: null,
    },
    select: {
      id: true,
      status: true,
      noteTemplateId: true,
      noteTemplateVersion: true,
      // The six below serve insertScaffoldDefaultAction — see the note above.
      userId: true,
      inputMode: true,
      transcriptText: true,
      entities: true,
      soapFinal: true,
      createdAt: true,
      practiceId: true, // #267 — the VISIT'S tenant; `user.practiceId` is the AUTHOR'S.
      user: { select: { practiceId: true } },
    },
  });
  if (!visit) return { ok: false, error: 'Visit not found.' };

  // ⚠️ UNSIGNED ONLY, AND THIS IS THE GATE THAT MATTERS. A signed record serves
  // its document by frozen pointer, so a row landing afterwards would be inert
  // rather than merely wrong — but "inert" is not a thing to rely on. Refuse at
  // the door: the sign-freeze governs signed records unchanged.
  if (visit.status === 'SIGNED') {
    return {
      ok: false,
      error: 'This visit is signed — its document is frozen and cannot be changed.',
    };
  }
  if (!visit.noteTemplateId || typeof visit.noteTemplateVersion !== 'number') {
    return { ok: false, error: 'This visit is not bound to a form template.' };
  }

  // Ask the TWIN which controls exist and what each one allows. The compiled IR
  // is the authority for this question — it is the same structure the renderer
  // resolves the ordinal against.
  const row = await prisma.noteTemplate.findFirst({
    where: {
      id: visit.noteTemplateId,
      version: visit.noteTemplateVersion,
      // PRACTICE-SCOPED like every other clinical read. Derived from the
      // compiled version rather than threaded, so it cannot drift from the
      // visit's own scope.
      templateTwinCompiledVersion: { practiceId: visit.user.practiceId },
    },
    select: {
      templateTwinCompiledVersion: {
        select: { id: true, certificationStatus: true, compiledDocumentIr: true },
      },
    },
  });
  const compiled = row?.templateTwinCompiledVersion;
  if (!compiled || compiled.certificationStatus !== 'CERTIFIED') {
    return {
      ok: false,
      error: 'This visit’s form is not certified, so its controls cannot be set here.',
    };
  }
  const ir = TemplateDocIRSchema.parse(compiled.compiledDocumentIr);
  const field = ir.fields.find((f) => f.fieldId === fieldId);
  if (!field) return { ok: false, error: 'That control is not part of this form.' };

  return {
    ok: true,
    // ⚠️ RULING #267 — THE CHART OWNS THE NOTE. This returned `practiceId` is
    // what every row attached to this visit is STAMPED with, so it is the
    // VISIT'S own tenant column and never the author's practice.
    //
    // ⚠️ IT USED TO BE `visit.user.practiceId`, AND THAT IS THE `SF-1` DEFECT.
    // The schema states the rule this violated, at `TranscribeVisit.practiceId`:
    // "the visit's tenant, DERIVED FROM THE PATIENT, never from the author. A
    // locum from practice B seeing a patient of practice A creates a note in
    // A ... NOTHING kept them agreeing." So for a locum the override row was
    // stamped with B while `sign-freeze.ts` reads the table with A — the doctor
    // inserted a default, watched it appear in the preview, and signed a
    // document without it.
    //
    // ⚠️ AND THE TWO VALUES AGREEING ON PRODUCTION DATA IS THE COINCIDENCE, NOT
    // THE DEFENCE — this file already says so about the LOCK's argument ("58 of
    // 58 ... a property of the data, not of the code"). The same sentence was
    // simply never applied to what the row is stamped WITH.
    //
    // AUTHORIZATION IS A SEPARATE QUESTION AND IS ANSWERED ABOVE, by
    // `visitByIdScope(visitId, session.user.practiceId)`. That decides whether
    // this actor may touch this visit. It is not a source for a stored value.
    //
    // ⚠️ AND THE `practiceId: true` LINE IN THE SELECT ABOVE IS DELIBERATELY ONE
    // LINE — N8's RATCHET CAUGHT THIS BRANCH ON PROSE FOR THE SECOND TIME.
    // `gate-practice-scope` decides a read is scoped by looking back FORTY LINES
    // for an accessor call, and it FAILS SAFE: what it cannot see, it counts as
    // unscoped. The `noteTemplate.findFirst` below carries a real practice
    // predicate — a nested `templateTwinCompiledVersion: { practiceId }` — which
    // is not an accessor, so it has always depended on `visitByIdScope` being
    // inside that window. A five-line comment in the select pushed the distance
    // from 37 lines to 42 and the ratchet went 0 -> 1 on a change that moved no
    // read at all.
    //
    // ⚠️ SO THE EXPLANATION LIVES HERE AND THE SELECT KEEPS ONE LINE. If you
    // need to write more up there, scope that read through an accessor first —
    // do NOT raise the ratchet, and do not discover this by making it red.
    practiceId: visit.practiceId,
    compiledVersionId: compiled.id,
    field,
    // Returned rather than re-read: the fill needs the same row this function
    // already fetched, and a second read is a second chance to diverge.
    visit,
    noteTemplateId: visit.noteTemplateId,
    noteTemplateVersion: visit.noteTemplateVersion,
  };
}

/** The transactional client `prisma.$transaction` hands its callback. */
type Tx = Omit<typeof prisma, '$transaction' | '$connect' | '$disconnect' | '$on' | '$use' | '$extends'>;

/**
 * Run `write` with the visit row LOCKED and its status RE-ASSERTED under that
 * lock. Resolves to `null` when the visit is no longer writable.
 *
 * ⚠️ ONE COPY, THREE DOORS — AND THE THIRD IS WHY THIS IS A FUNCTION.
 * Round four found the insert door never re-checked the status it had read
 * seconds earlier, and the fix was written inline, there, only. Round five then
 * measured the obvious consequence: **the sign-window fix reached ONE of the
 * three writers in this file.** The shipped dropdown door and the undo door
 * were still read-then-act with no lock at all — the exact defect, in the exact
 * file, twice more.
 *
 * A rule with several readers is how this house gets bitten: change one and the
 * system contradicts itself while every arm stays green, because each arm points
 * at one reader. So the lock is a function and the doors call it.
 *
 * ⚠️ BOTH SPELLINGS ARE CHECKED. The door says `status === 'SIGNED'`, the offer
 * says `signedAt`. They agree in production today and the sign route sets both
 * atomically — but a guard that trusts that is resting on a coincidence it does
 * not assert.
 *
 * ⚠️ WHAT THIS DOES **NOT** CLOSE, stated so the comment cannot be read wider
 * than it is: it protects the visit's SIGNED **status**, not the signature's
 * frozen **pointer**. The sign path decides which document it freezes OUTSIDE
 * the transaction this lock contends with, so a correction committing in that
 * window is not visible to the manifest the signature pins. That is filed
 * separately as SIGN-PTR-1, it is pre-existing on `main`, and it is a PAIRED
 * fix that does not belong to this door alone.
 */
type LockRefusal = 'signed' | 'gone' | 'not_ready';
type Locked<T> = { ok: true; value: T } | { ok: false; reason: LockRefusal };

async function underVisitLock<T>(
  visitId: string,
  // ⚠️ `string`, NOT the branded `PracticeId`, and deliberately. The brand
  // exists to force callers of the PRISMA scope helper through `asPracticeId`;
  // this is a raw-SQL binding, and every caller passes the very value its own
  // resolver was scoped with a few lines earlier. Widening the brand here would
  // be worse than not having it — it would let a NEW caller mint one.
  practiceId: string,
  write: (tx: Tx) => Promise<T>,
): Promise<Locked<T>> {
  return prisma.$transaction(async (tx): Promise<Locked<T>> => {
    // ⚠️ THE LOCKED RE-READ CARRIES THE SAME PREDICATE THE RESOLVER APPLIED —
    // RULING #253. It read `WHERE "id" = $1` and nothing else, while every
    // caller had reached this point through a resolver scoped on
    // `practiceId`, `deletedAt IS NULL` and `archivedAt IS NULL`.
    //
    // So the guard re-asserted `status` on a row it had not re-asserted the
    // TENANCY or the LIFECYCLE of: a visit soft-deleted or archived in the
    // window — the window this lock exists because it is seconds wide — was
    // still written to, and a visit belonging to ANOTHER PRACTICE would have
    // been locked and accepted had the id ever been guessed or reused.
    //
    // ⚠️ A LOCK THAT RE-CHECKS ONE OF THREE PREDICATES IS NOT A RE-CHECK. The
    // whole point of re-reading under the lock is that the earlier read is
    // stale; that applies to every term of it, not to the one that prompted
    // the fix.
    //
    // A row that fails any of them yields NO ROW, which is already the `gone`
    // cause — "this visit is no longer available" is the true sentence for a
    // soft-delete, an archive, and a tenancy miss alike.
    const [locked] = await tx.$queryRaw<{ status: string; signedAt: Date | null }[]>`
      SELECT "status", "signedAt" FROM "transcribe_visits"
       WHERE "id" = ${visitId}
         AND "practiceId" = ${practiceId}
         AND "deletedAt" IS NULL
         AND "archivedAt" IS NULL
       FOR UPDATE`;
    // ⚠️ THREE CAUSES, THREE ANSWERS — ROUND FIVE.
    // The first version of this returned a bare `null` and every caller said
    // "this visit was signed while your form was being checked". That sentence
    // is FALSE for two of the three exits: a visit that was re-queued (status
    // left READY) or deleted in the window was never signed, and telling a
    // doctor it was sends them looking for a signature that does not exist.
    // ⚠️ A refusal that names the wrong cause is worse than a vague one,
    // because it is actionable and wrong.
    if (!locked) return { ok: false, reason: 'gone' };
    if (locked.status === 'SIGNED' || locked.signedAt !== null) {
      return { ok: false, reason: 'signed' };
    }
    if (locked.status !== 'READY') return { ok: false, reason: 'not_ready' };
    return { ok: true, value: await write(tx as Tx) };
  });
}

/** What the doctor is told, per cause. Doctor-facing, PHI-free. */
function lockRefusalMessage(label: string, reason: LockRefusal): string {
  switch (reason) {
    case 'signed':
      return `${label} was not saved — this visit was signed while your form was being checked.`;
    case 'not_ready':
      return `${label} was not saved — this visit went back into processing while your form was being checked. Try again once the note is ready.`;
    case 'gone':
      return `${label} was not saved — this visit is no longer available.`;
  }
}

export async function setTemplateControlAction(
  visitId: string,
  /** The twin's own addressing. NEVER a label: 18 of this form's 28 content
   *  controls share a label with at least one other (re-measured on production
   *  2026-08-24 — 28 controls, 14 distinct labels, groups of 8/6/2/2), so a
   *  label cannot identify a control and never could. */
  fieldId: string,
  /** What the doctor said. Matched against the control's compiled options. */
  requestedValue: string,
): Promise<SetTemplateControlResult> {
  const session = await requireSession();

  const resolved = await resolveCertifiedTwinField(
    visitId,
    fieldId,
    session.user.practiceId,
  );
  if (!resolved.ok) return resolved;
  const { field, compiledVersionId } = resolved;
  const compiled = { id: compiledVersionId };
  // ⚠️ #267 — NAMED FOR WHAT IT IS. This was `{ user: { practiceId: ... } }`,
  // a synthetic wrapper that made the resolver's value LOOK like the author's
  // practice at every use below. It is the VISIT's tenant and it now says so:
  // a shape that misnames its own contents is how the SF-1 confusion survived
  // review in the first place.
  const visitPracticeId = resolved.practiceId;

  // ⚠️ THE DOOR'S ADMISSION SET MUST MIRROR THE FILL'S, OR SUCCESS IS A LIE.
  //
  // `applyClinicianOverrides` declines on five reasons. This door already
  // mirrors three of them — `field_not_in_template` above, `field_has_no_options`
  // and `option_is_placeholder` below — and `ordinal_not_in_options` is a
  // genuine recompile race that can only be judged at fill time. That left
  // `no_approved_concept` as the one STATIC reason the door did not check, and
  // an unchecked static decline is not a race: it fails identically forever.
  //
  // Without this, the sequence was: the door stores the override and returns
  // `ok: true`, the chat reports the correction applied and redraws the page,
  // and then EVERY fill declines it — so the document never changes, on this
  // run and on every future one. The doctor is told their correction landed and
  // it provably cannot.
  //
  // ⚠️ AND IT IS REACHABLE ON THE ONLY CERTIFIED TWIN IN PRODUCTION, measured
  // read-only 2026-08-24 (counts only; no note text was read):
  //
  //     80 mappings = 52 extraction + 23 verified_note_selection
  //                 + 5 manual  (4 of them with clinicalConcept NULL)
  //
  // All four NULL-concept fields are `single_select` / `content_control` with
  // 5-8 options — Address, REFERRING PHYSICIAN, ULTRASOUND TECHNOLOGIST,
  // LOCATION — so all four sit inside the 28 controls this surface offers.
  // 4 of 28 addressable controls, reported as set and never applied.
  //
  // The cause is not a defect in certification: `mappings-readiness.ts` CERTIFIES
  // a `manual` field with a null concept deliberately ("nothing dictates who the
  // technologist on shift was"). So CERTIFIED does not imply every field carries
  // a concept, and any surface that assumed it does was assuming.
  //
  // ⚠️ REFUSED, NOT ADMITTED — the tighten-only direction. Letting a
  // concept-less override through would mint a fact the validator has nothing to
  // check a citation against, which is a LOOSENING of a clinical validation path
  // and not a call this layer may make. Whether these fields SHOULD become
  // settable is a product question, recorded in the ledger rather than decided
  // here.
  const definition = await prisma.templateTwinFieldDefinition.findUnique({
    where: { compiledVersionId_fieldId: { compiledVersionId: compiled.id, fieldId } },
    select: { mapping: { select: { clinicalConcept: true } } },
  });
  if (!definition?.mapping?.clinicalConcept) {
    return {
      ok: false,
      error: `${field.originalLabel} is filled in by hand on this form and cannot be set from chat.`,
      label: field.originalLabel,
    };
  }

  // ⚠️ WORD'S "Choose an item." IS FURNITURE AND IS NEVER SELECTABLE — THE THIRD
  // LAYER, AT THE DOOR, AND IT IS THE ONE THAT COVERS THE TWIN THAT EXISTS.
  //
  // `compiler.ts` strips the placeholder from every template compiled from here
  // on. The single certified twin in production was compiled 2026-08-17 and
  // still carries it at ordinal 0 on all 28 of its single-selects, so
  // compile-time exclusion alone would protect every form EXCEPT the only real
  // one. Filtering here means the option is never OFFERED and never MATCHED,
  // against the IR as it stands today, with no recompile required.
  const selectable = field.allowedOptions.filter(
    (o) => !isWordPlaceholderOption(o.displayText),
  );
  if (selectable.length === 0) {
    return { ok: false, error: 'That control has no fixed list of options.' };
  }

  const optionLabels = selectable.map((o) => o.displayText);
  const wanted = fold(requestedValue);
  // Exact (folded) match against BOTH the shown text and the stored value.
  // `displayText` and `value` are distinct within every one of this form's 28
  // controls, so no tie-breaker is needed — but a tie is still refused rather
  // than resolved by position, because that property is a fact about ONE form
  // and not a property of the compiler.
  const hits = selectable.filter(
    (o) => fold(o.displayText) === wanted || fold(o.value) === wanted,
  );
  if (hits.length === 0) {
    return {
      ok: false,
      error: `"${requestedValue}" is not one of the options for ${field.originalLabel}.`,
      options: optionLabels,
      label: field.originalLabel,
    };
  }
  if (hits.length > 1) {
    return {
      ok: false,
      error: `"${requestedValue}" matches more than one option for ${field.originalLabel}.`,
      options: optionLabels,
      label: field.originalLabel,
    };
  }
  const option = hits[0];

  // ⚠️ UNDER THE LOCK — ROUND FIVE. This was a bare upsert: the status was read
  // at the top of the action and never re-asserted, so a sign landing in the
  // window wrote a dropdown correction onto a SIGNED visit. A signed visit shows
  // no panel, so there is no Undo and the row is permanent.
  // ⚠️ RULING #267 — THE LOCK RE-ASSERTS THE **VISIT'S** TENANT, ONE DERIVATION.
  // The value is identical here — `visitByIdScope(visitId, session.user.
  // practiceId)` filtered on this very column, so any visit this door can reach
  // already has it — but it now comes from the SAME place the stored row does.
  // The failure this closes was never a wrong value, it was THREE SOURCES for
  // one fact with different subsystems reaching for different ones.
  const wroteOption = await underVisitLock(visitId, visitPracticeId, async (tx) => {
    await tx.templateTwinFieldOverride.upsert({
    where: { visitId_fieldId: { visitId, fieldId } },
    create: {
      // ⚠️ RULING #267 — the VISIT'S tenant, never the author's. See the
      // resolver's return above for the SF-1 account.
      practiceId: visitPracticeId,
      visitId,
      fieldId,
      overrideKind: 'option',
      selectedOptionOrdinal: option.ordinal,
      optionValue: option.value,
      overriddenBy: session.user.id,
    },
    // ⚠️ THE UPDATE ARM CLEARS `insertedText`, AND IT MUST. There is ONE row per
    // (visitId, fieldId) — the unique index says so — so correcting a control
    // that previously held a scaffold-default insert REPLACES that row rather
    // than adding one. Leaving `insertedText` populated would leave both arms of
    // the kind-shape CHECK unsatisfied and the database would refuse the write:
    // a doctor's dropdown correction failing with a constraint error because of
    // a click they made ten minutes earlier.
    update: {
      overrideKind: 'option',
      selectedOptionOrdinal: option.ordinal,
      optionValue: option.value,
      insertedText: null,
      overriddenBy: session.user.id,
    },
    });
    return true;
  });

  if (!wroteOption.ok) {
    return {
      ok: false,
      error: lockRefusalMessage(field.originalLabel, wroteOption.reason),
      label: field.originalLabel,
    };
  }

  // The document must not keep showing the value they just replaced. Same
  // reason `saveNoteSectionAction` does it: the preview and the export both
  // read a cached fill, and a correction the doctor cannot SEE is one they
  // will make twice.
  await invalidateVisitFills(visitId);

  // Field id, ordinal and template-derived text only. `originalLabel` and the
  // option text come from the doctor's own uploaded FORM, not from the patient.
  void logAudit({
    action: 'EDITED_NOTE',
    targetId: visitId,
    targetType: 'TranscribeVisit',
    metadata: {
      surface: 'template_control_override',
      fieldId,
      selectedOptionOrdinal: option.ordinal,
    },
    success: true,
  });

  return { ok: true, label: field.originalLabel, value: option.displayText };
}

// ============================================================================
// REVIEW-DEFAULTS item 1 — the doctor asserts THEIR OWN compiled default.
// ----------------------------------------------------------------------------
// Ruling #194 deleted the `keep` half: the machine never prints an undictated
// default. The doctor's defaults did not disappear — they became a HUMAN ACT AT
// REVIEW, and this is that act's writer.
//
// ⚠️ THE CLIENT NEVER SUPPLIES THE TEXT, AND THAT IS THE POINT OF THE SIGNATURE.
// This takes (visitId, fieldId) and NOTHING ELSE. The value written is read
// server-side from the compiled IR's own `scaffoldText`. A door that accepted
// the string from the caller would be a free-text writer into a clinical
// document wearing an "insert my default" label — one bug or one tampered
// request away from putting arbitrary prose into a note. The doctor is saying
// YES to a specific compiled string; they are not typing.
//
// ⚠️ AND IT IS REVERSIBLE, DELIBERATELY. `undoScaffoldDefaultAction` deletes the
// row. An irreversible one-click write into a document somebody is about to
// sign is the shape that has already cost this programme once — a promotion
// that could not be undone, found by an adversarial pass on the branch before
// this one. Reversibility here is cheap: the override is an INPUT to the fill,
// so removing it restores the blank exactly.
// ============================================================================

export interface InsertScaffoldDefaultResult {
  ok: boolean;
  /** Doctor-facing. PHI-free — the label and the default are the doctor's own
   *  form, never the patient's record. */
  error?: string;
  label?: string;
  /** What was written, so the caller can show it without re-reading the IR. */
  inserted?: string;
}

/**
 * Is this field one the doctor may insert their default into ON THIS VISIT?
 *
 * ⚠️ IT RESOLVES THE FILL RATHER THAN READING A CACHED ONE. Ruling #204 forbids
 * a cache here for a reason this branch already paid for once: the offer list
 * lives inside a cached preview payload, so a gate keyed on that would admit
 * whatever the doctor last SAW rather than what is true now.
 *
 * ⚠️ FAIL-CLOSED ON EVERY THROW, AND THE ASYMMETRY WITH THE PREVIEW IS
 * DELIBERATE. The preview degrades to a styled document when the fill throws,
 * because it WRITES NOTHING. This door writes a clinical override row and an
 * audit row claiming the doctor asserted something; it cannot degrade, so it
 * refuses. The catch is broad on purpose — `TemplateTwinFillError` is not the
 * only escape (Zod parse failures and the storage errors reach here too), and a
 * narrow `instanceof` would let those through into a write.
 *
 * ⚠️ COST, STATED RATHER THAN HIDDEN: one insert is now one full fill, render
 * included, and the panel's "insert all" is N of them in sequence. There is no
 * public entry that computes the manifest and skips the render. Adding a
 * `skipRender` seam is a production change that owes its own adversarial pass;
 * a cache is what #204 forbids, so the honest options are this or that seam.
 */
async function scaffoldDefaultAdmissible(input: {
  visitId: string;
  fieldId: string;
  /**
   * The text the caller is ABOUT TO WRITE. Present for an insert, absent for a
   * read-only admissibility question.
   *
   * ⚠️ ROUND FOUR FOUND THAT THE GUARD BELOW COULD NOT SEE ITS OWN WRITE, and
   * two independent lenses reached it by different routes. Without this the
   * gate answers *"does the document render today?"* — which is not the
   * question. The question is *"will it render after I write this?"*
   */
  pendingText?: string;
  field: TemplateDocIR['fields'][number];
  resolved: {
    practiceId: string;
    compiledVersionId: string;
    visit: {
      status: string;
      userId: string;
      inputMode: string | null;
      transcriptText: string | null;
      entities: unknown;
      soapFinal: string | null;
      createdAt: Date;
      // ⚠️ #267 — the VISIT'S OWN tenant, beside the author's practice.
      practiceId: string;
      user: { practiceId: string };
    };
    noteTemplateId: string;
    noteTemplateVersion: number;
  };
}): Promise<{ ok: true } | { ok: false; error: string }> {
  const { visitId, fieldId, field, resolved } = input;
  const { visit } = resolved;

  // ⚠️ READY, NOT MERELY UNSIGNED — FOUND BY ROUND THREE, BY TWO LENSES.
  // The door's only status gate was `SIGNED`. The offer's is
  // `status !== 'READY' && !signedAt -> miss('not_template_visit')`
  // (preview-visit-document.ts:286), and its comment says exactly why: "A visit
  // still processing (or failed) may carry a stale note from a previous run; it
  // does not get a document."
  //
  // That window is REACHABLE IN ORDINARY USE, not theoretical: the manual retry
  // route sets a READY visit back to QUEUED and leaves `soapFinal` in place. So
  // on eight statuses — QUEUED, TRANSCRIBING, EXTRACTING, DRAFTING, CRITIQUING,
  // POLISHING, AUTOMATING, FAILED — the offer showed the doctor nothing at all
  // while the door wrote the override row and a DEFAULT_INSERTED_BY_DOCTOR
  // audit row, against a resolution computed on the STALE note. Measured on all
  // eight: ok=true, upsert=1, audit=1.
  //
  // SIGNED is refused earlier, so requiring READY here is the whole remainder.
  if (visit.status !== 'READY') {
    return {
      ok: false,
      error: `${field.originalLabel} cannot take a default while this visit is still being prepared.`,
    };
  }

  // The preview never offers this panel before the note exists, so refusing
  // here is AGREEMENT with the offer rather than a tightening of it.
  if (typeof visit.soapFinal !== 'string' || !visit.soapFinal) {
    return {
      ok: false,
      error: `${field.originalLabel} cannot take a default until this visit has a note.`,
    };
  }

  let current: { status?: string; value?: unknown; reasonCode?: string | null } | null = null;
  try {
    // ⚠️ ONE ARGUMENT OBJECT, SHARED BY BOTH FILLS. The post-write simulation
    // below must differ from this call in EXACTLY ONE WAY — the pending row —
    // and a second hand-written copy of fifteen fields would drift from this
    // one the day either is edited, while every arm stayed green.
    const fillInput: ProcessTemplateTwinVisitInput = {
      visitId,
      // ⚠️ RULING #267 — the VISIT'S tenant, never the author's. See the
      // resolver's return above for the SF-1 account.
      tenantPracticeId: visit.practiceId,
      // THE VISIT'S OWN DOCTOR, NOT THE REQUESTER — the same actor rule the
      // preview states: a colleague acting on the record must not restamp it.
      authorUserId: visit.userId,
      noteTemplateId: resolved.noteTemplateId,
      noteTemplateVersion: resolved.noteTemplateVersion,
      inputMode:
        visit.inputMode === 'voice_dictation'
          ? 'dictation'
          : visit.inputMode === 'text_notes'
            ? 'text'
            : 'conversation',
      contextText: visit.transcriptText ?? '',
      entities: visit.entities,
      generatedNote: visit.soapFinal,
      validationNow: new Date(),
      visitDate: visit.createdAt,
      resolverModelVersion: null,
    };
    const { prepared } = await readAndPrepareTemplateTwinFill(fillInput);
    // ⚠️ THE WHOLE-DOCUMENT REFUSAL — FOUND BY ROUND THREE, BY TWO LENSES.
    // One blocking validation issue on ANY field makes `finalizeTemplateTwinFill`
    // return `render: null` for the ENTIRE fill. The offer then returns
    // `miss('no_render')` (preview-visit-document.ts:366), the surface says it
    // could not draw the form, and NO panel is shown — so there is no offer, no
    // field, and no Undo button. The door read only `manifest.fields` and wrote
    // anyway, which is verbatim the state clinician-override.ts:203-216 calls
    // fatal: for a date or checkbox there is then no product path left to
    // delete the row.
    if (!prepared.render?.document) {
      return {
        ok: false,
        error: `${field.originalLabel} could not be placed on your form for this visit, so nothing was inserted.`,
      };
    }

    // ══════════════════════════════════════════════════════════════════════
    // ⚠️ AND NOW THE SAME QUESTION ABOUT THE POST-WRITE STATE. ROUND FOUR.
    //
    // The check above proves the document renders TODAY. That is not the
    // question the door is asking. Two independent lenses reached the same
    // defect by different routes:
    //
    //   · an insert onto a `rowPrototype` narrative_text field — the writer
    //     stores a SCALAR, `validation/index.ts` demands a ROW ARRAY, and it
    //     raises ASSERTION_NOT_SUPPORTED + REPEATING_ROW_SHAPE_INVALID;
    //   · an insert onto a `laterality: 'required'` mapping.
    //
    // Either makes `finalizeTemplateTwinFill` return `render: null` for the
    // WHOLE fill. The offer then returns `miss('no_render')`, the surface draws
    // no panel — and WITH NO PANEL THERE IS NO UNDO BUTTON. The row is
    // permanent and the doctor's document never renders again.
    //
    // The pre-write fill cannot see this BY CONSTRUCTION: it is computed from
    // the rows in the database, and the row that breaks it is the one we have
    // not written yet. So the fill is re-driven WITH the pending row merged in.
    // Canon 120: after a fix, re-drive the WHOLE chain.
    //
    // ⚠️ THE COST IS A SECOND FULL FILL — an object-storage read, a
    // docx-to-text pass and a render. It runs ONLY on the write path, only
    // after admissibility has already passed, and only for an explicit doctor
    // action. A permanently unrenderable document is not a price worth paying
    // for one avoided render.
    if (input.pendingText !== undefined) {
      const { prepared: after } = await readAndPrepareTemplateTwinFill({
        ...fillInput,
        simulateOverrides: [
          {
            fieldId,
            overrideKind: 'scaffold_default',
            insertedText: input.pendingText,
            selectedOptionOrdinal: null,
          },
        ],
      });
      if (!after.render?.document) {
        return {
          ok: false,
          error: `${field.originalLabel} cannot take a default on this visit — inserting it would stop your form from being produced, so nothing was inserted.`,
        };
      }
    }
    current = prepared.manifest.fields.find((f) => f.fieldId === fieldId) ?? null;
  } catch (err) {
    // Constructor name only — never the message, which can carry document text.
    const cls = err instanceof Error ? err.constructor.name : 'Unknown';
    console.warn(`[insert-default] visit=${visitId} field=${fieldId} fill failed (${cls})`);
    return {
      ok: false,
      error: `${field.originalLabel} could not be checked against this visit just now, so nothing was inserted. Try again in a moment.`,
    };
  }

  // ⚠️ THE CALLER'S WHOLE DISJUNCTION, NOT JUST `scaffoldDefaultOfferable`.
  // `preview-visit-document.ts` offers a field when `inserted || offerable`,
  // where `inserted` means the resolution is already this doctor's applied
  // default. Gating on `offerable` alone would refuse a RE-INSERT over an
  // existing row — a state the panel can reach — so the two surfaces would
  // disagree again, in the opposite direction from the one #204 is about.
  const inserted = current?.reasonCode === 'clinician_scaffold_default';
  const admissible =
    inserted ||
    scaffoldDefaultOfferable({
      field,
      // The concept was already proved present by the caller's own guard, which
      // reads the same column off the same compiled version. Passing a sentinel
      // rather than re-fetching keeps ONE fetch and one decision.
      mapping: { clinicalConcept: 'checked-by-the-callers-own-guard' },
      current,
    });
  if (!admissible) {
    return {
      ok: false,
      error: `${field.originalLabel} is not blank on this visit, so your default was not inserted.`,
    };
  }
  return { ok: true };
}

export async function insertScaffoldDefaultAction(
  visitId: string,
  fieldId: string,
): Promise<InsertScaffoldDefaultResult> {
  const session = await requireSession();

  const resolved = await resolveCertifiedTwinField(
    visitId,
    fieldId,
    session.user.practiceId,
  );
  if (!resolved.ok) return resolved;
  const { field, practiceId } = resolved;

  // ⚠️ SCAFFOLDED IS A COMPILED FACT, NOT A GUESS, AND IT IS CHECKED HERE RATHER
  // THAN TRUSTED FROM THE PANEL. `scaffolded` is set by the compiler from the
  // document's own bytes (ruling #192 falsified three attempts to INFER it from
  // content, one of which printed "Enter assessment" onto a rendered note). A
  // door that accepted the panel's word for which fields are scaffolded would
  // re-open exactly that hole from the other side.
  const text = (field.scaffoldText ?? '').trim();
  if (field.scaffolded !== true || !text) {
    return {
      ok: false,
      error: `${field.originalLabel} has no default of yours to insert.`,
      label: field.originalLabel,
    };
  }

  // ⚠️ THE DOOR MIRRORS THE FILL'S STATIC DECLINES, OR SUCCESS IS A LIE — the
  // same rule the option door above already follows, in its own words: "an
  // unchecked static decline is not a race: it fails identically forever."
  //
  // An adversarial pass found this door checking neither. The sequence was:
  // store the row, return ok:true, write a DEFAULT_INSERTED_BY_DOCTOR audit row
  // claiming the doctor asserted something, re-render — and then every fill
  // declines it, on this run and on every future one. Worse for a constrained
  // control: the fill does not decline, it BLOCKS the whole document.
  if (!SCAFFOLD_INSERTABLE_KINDS.has(field.kind)) {
    return {
      ok: false,
      error: `${field.originalLabel} is a fixed control on this form, so a written default cannot go in it.`,
      label: field.originalLabel,
    };
  }

  const definition = await prisma.templateTwinFieldDefinition.findUnique({
    where: {
      compiledVersionId_fieldId: { compiledVersionId: resolved.compiledVersionId, fieldId },
    },
    // ⚠️ `clinicalConcept` ONLY — `unmentionedPolicy` was fetched for the
    // static refusal removed below, and a column fetched for a decision nobody
    // makes is how the offer side's dead guard went unnoticed for a commit.
    select: { mapping: { select: { clinicalConcept: true } } },
  });
  if (!definition?.mapping?.clinicalConcept) {
    return {
      ok: false,
      error: `${field.originalLabel} is filled in by hand on this form, so a default cannot be inserted for it.`,
      label: field.originalLabel,
    };
  }
  // ══════════════════════════════════════════════════════════════════════════
  // ⚠️ THE PER-VISIT GATE — OWNER RULING #204.
  //
  // The door and the offer now share ONE answer, obtained through the SAME
  // entry the preview uses. Not a static mapping property, and NOT A CACHE.
  //
  // WHAT THIS REPLACES, AND WHY BOTH EARLIER SHAPES WERE WRONG. Round one
  // refused on `mapping.unmentionedPolicy === 'omit'` — a CONFIRM-TIME property
  // deciding a PER-VISIT question, so on a visit where the omit did not fire the
  // panel listed the field and this branch refused the click. Round two deleted
  // the refusal outright and justified it on #194 (an insert is a human act,
  // audited). The second adversarial pass falsified that too: with no gate at
  // all the door ADMITS acts the offer REFUSES, writing an override row and a
  // `DEFAULT_INSERTED_BY_DOCTOR` audit row asserting a claim the doctor was
  // never shown. A door wrong in both directions does not need a third static
  // rule — it needs the per-visit answer.
  const gate = await scaffoldDefaultAdmissible({ visitId, fieldId, field, resolved, pendingText: text });
  if (!gate.ok) return { ok: false, error: gate.error, label: field.originalLabel };

  // ══════════════════════════════════════════════════════════════════════════
  // ⚠️ THE STATUS IS RE-ASSERTED AT THE WRITE, UNDER A LOCK ON THE VISIT ROW.
  //
  // `visit.status` was read at the top of this action. Between that read and
  // this write the door performs TWO full fills — each an object-storage read,
  // a docx-to-text pass and a render — so the window is seconds wide, not
  // microseconds. Round four found the door never re-checked; and the
  // post-write simulation added by this very change WIDENED that window from
  // one fill to two, which makes fixing it part of the same change rather than
  // a follow-up.
  //
  // What lands in the window is a SIGN. `POST /api/visits/[id]/sign` is the
  // sole SIGNED-writer and it updates this visit row, so `FOR UPDATE` here
  // makes the two mutually exclusive: either the sign commits first and the
  // re-read below sees SIGNED, or this transaction holds the row and the sign
  // waits. Without it an insert lands on a SIGNED visit — and a signed visit
  // shows no panel, so there is no Undo button and the row is permanent.
  //
  // A read-then-act check cannot see this by construction, which is the same
  // sentence the ADMIN-5 guard carries one lane over.
  // ⚠️ THE SAME LOCK THE OTHER TWO DOORS TAKE — one function, three callers.
  // Round four wrote this inline here and round five measured the cost: the fix
  // reached ONE of the three writers in this file. `underVisitLock` is that
  // fix, hoisted, so the next writer added to this file cannot be the fourth.
  // ⚠️ `session.user.practiceId`, NOT the resolver's RETURNED `practiceId` — and
  // I passed the wrong one here for an hour. The two are DIFFERENT COLUMNS:
  //
  //   · the resolver FILTERS `transcribe_visits."practiceId"` — via
  //     `visitByIdScope(visitId, practiceId)` — with the value it was CALLED
  //     with, which is `session.user.practiceId` at all three doors;
  //   · the resolver RETURNS `practiceId: visit.user.practiceId`, the visit
  //     AUTHOR's user record's practice, which is a different column entirely.
  //
  // This door destructures the RETURNED one and handed it to a lock that filters
  // the FILTERED one. The other two doors pass the session's value, so two of
  // three agreed and the odd one out was the one this fix had a local variable
  // conveniently in scope for.
  //
  // ⚠️ THE LOCK MUST RE-ASSERT THE SAME PREDICATE THE RESOLVER APPLIED, WITH THE
  // SAME VALUE. Re-asserting the right column with the wrong value is not a
  // narrower check, it is a different one — and it fails CLOSED into the `gone`
  // cause, telling a doctor their visit "is no longer available".
  //
  // Latent today: measured read-only against production, 58 of 58 visits have
  // `transcribe_visits."practiceId"` equal to their author's, so the two values
  // never diverge on current data. That is a property of the data, not of the
  // code, and it is exactly the kind of coincidence a guard must not rest on.
  // ⚠️ RULING #267 — THE LOCK RE-ASSERTS THE **VISIT'S** TENANT, ONE DERIVATION.
  // The value is identical here — `visitByIdScope(visitId, session.user.
  // practiceId)` filtered on this very column, so any visit this door can reach
  // already has it — but it now comes from the SAME place the stored row does.
  // The failure this closes was never a wrong value, it was THREE SOURCES for
  // one fact with different subsystems reaching for different ones.
  const wrote = await underVisitLock(visitId, practiceId, async (tx) => {
    await tx.templateTwinFieldOverride.upsert({
      where: { visitId_fieldId: { visitId, fieldId } },
      create: {
        practiceId,
        visitId,
        fieldId,
        overrideKind: 'scaffold_default',
        insertedText: text,
        overriddenBy: session.user.id,
      },
      // ⚠️ CLEARS THE OPTION ARM FOR THE SAME REASON THE OPTION DOOR CLEARS
      // THIS ONE: one row per (visitId, fieldId), and a row satisfying neither
      // arm of the kind-shape CHECK is refused by the database.
      update: {
        overrideKind: 'scaffold_default',
        insertedText: text,
        selectedOptionOrdinal: null,
        optionValue: null,
        overriddenBy: session.user.id,
      },
    });
    return true;
  });

  if (!wrote.ok) {
    return {
      ok: false,
      error: lockRefusalMessage(field.originalLabel, wrote.reason),
      label: field.originalLabel,
    };
  }

  await invalidateVisitFills(visitId);

  // ⚠️ ITS OWN ACTION, NOT `EDITED_NOTE`. The whole product claim of #194 is
  // that a default reaching a note is a HUMAN act; a trail that cannot tell
  // that act apart from any other edit cannot evidence the claim. The metadata
  // carries the field id and the LENGTH of what was inserted — never the text,
  // which is the doctor's form and does not belong in an audit row.
  void logAudit({
    action: 'DEFAULT_INSERTED_BY_DOCTOR',
    targetId: visitId,
    targetType: 'TranscribeVisit',
    metadata: {
      surface: 'review_defaults_panel',
      fieldId,
      insertedLength: text.length,
    },
    success: true,
  });

  return { ok: true, label: field.originalLabel, inserted: text };
}

/** Undo one inserted default. Deletes the override row, which restores the
 *  blank exactly — the override is an INPUT to the fill, never a mutation of
 *  the note. */
export async function undoScaffoldDefaultAction(
  visitId: string,
  fieldId: string,
): Promise<InsertScaffoldDefaultResult> {
  const session = await requireSession();

  const resolved = await resolveCertifiedTwinField(
    visitId,
    fieldId,
    session.user.practiceId,
  );
  if (!resolved.ok) return resolved;

  // ⚠️ SCOPED BY KIND AS WELL AS BY KEY, so an undo cannot silently delete a
  // DROPDOWN correction that happens to share the field. `deleteMany` takes the
  // predicate; `delete` would take only the unique key and would not be able to
  // say "only if it is mine".
  // ⚠️ UNDER THE LOCK — ROUND FIVE. Round four locked the INSERT and left the
  // UNDO read-then-act, so a sign landing in this window deleted the doctor's
  // row against a record that was, by then, signed.
  // ⚠️ RULING #267 — THE LOCK RE-ASSERTS THE **VISIT'S** TENANT, ONE DERIVATION.
  // The value is identical here — `visitByIdScope(visitId, session.user.
  // practiceId)` filtered on this very column, so any visit this door can reach
  // already has it — but it now comes from the SAME place the stored row does.
  // The failure this closes was never a wrong value, it was THREE SOURCES for
  // one fact with different subsystems reaching for different ones.
  const deleted = await underVisitLock(visitId, resolved.practiceId, async (tx) =>
    (
      await tx.templateTwinFieldOverride.deleteMany({
        where: { visitId, fieldId, overrideKind: 'scaffold_default' },
      })
    ).count,
  );
  if (!deleted.ok) {
    return {
      ok: false,
      error: lockRefusalMessage(resolved.field.originalLabel, deleted.reason),
      label: resolved.field.originalLabel,
    };
  }
  const count = deleted.value;
  if (count === 0) {
    return {
      ok: false,
      error: 'That default is not currently inserted.',
      label: resolved.field.originalLabel,
    };
  }

  await invalidateVisitFills(visitId);

  // ⚠️ ITS OWN ACTION, NOT THE INSERT'S WITH A FLAG. An adversarial pass
  // measured the consequence of the flag: `DEFAULT_INSERTED_BY_DOCTOR` counts 2
  // for one insert that was reverted, and no action-level rollup can tell an
  // assertion from its own withdrawal. A metadata key is not a discriminator
  // for anything that groups by action.
  void logAudit({
    action: 'DEFAULT_INSERT_UNDONE',
    targetId: visitId,
    targetType: 'TranscribeVisit',
    metadata: { surface: 'review_defaults_panel', fieldId },
    success: true,
  });

  return { ok: true, label: resolved.field.originalLabel };
}
