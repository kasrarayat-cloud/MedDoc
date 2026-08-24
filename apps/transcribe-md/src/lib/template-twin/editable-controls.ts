// ============================================================================
// F24-S5 — THE FORM CONTROLS A DOCTOR MAY ADDRESS, AND HOW THEY ARE ADDRESSED.
// ----------------------------------------------------------------------------
// A doctor sees 28 dropdowns in their Word form. Until this slice none of them
// could be reached from the chat editor at all — they render from the fill's
// `selectedOptionOrdinal`, not from the note markdown, so no note edit could
// touch them.
//
// ⚠️ THEY CANNOT BE ADDRESSED BY LABEL, AND THIS IS MEASURED, NOT ASSUMED.
// Re-derived directly from the compiled IR of the one certified twin in
// production (2026-08-24), and the partition reconciles:
//
//     28 content controls  ->  14 distinct `originalLabel`s
//     ambiguous groups: 8 + 6 + 2 + 2 = 18 controls, in 4 groups
//     unique labels:                    10 controls
//                        18 + 10 = 28 ✔      4 + 10 = 14 ✔
//
// The labels are the surrounding SENTENCE with the dropdown sitting inside it,
// so one sentence carrying four dropdowns yields four controls with the SAME
// label.
//
// ⚠️ AND THE OPTION SETS DO NOT RESCUE IT EITHER. Within the 8-group the four
// controls of one sentence have genuinely different option sets (vein /
// junction / location / status) — but the group is TWO such sentences, and
// across them the sets are identical in pairs. So neither the label nor the
// options can separate the two. Only the control's POSITION IN THE DOCUMENT
// can.
//
// ⇒ ADDRESSING IS A SERVER-ISSUED NUMBER. The server builds this list, shows it
// to the model, and the model may only ever name a number the server just gave
// it — the same ECHO doctrine `rowOrdinal` carries, and for the same reason: a
// model that counts its own coordinates writes real values into the wrong
// control and reports success.
//
// ⚠️ THE LIST IS BUILT ONCE PER REQUEST AND USED FOR BOTH HALVES — the prompt
// the model reads and the resolution of what it returns. Deriving it twice
// would let the two orderings drift, and a drifted ordinal is a wrong-cell
// write that nothing downstream could detect.
// ============================================================================

import prisma from '@meddoc/db';

import { withoutPlaceholderOptions } from '../note-template-docx/placeholder-option';
import { TemplateDocIRSchema, type TemplateDocIR } from './ir';

export interface EditableFormControl {
  /** 1-based, stable within ONE request. The only thing the model may name. */
  ordinal: number;
  /** The twin's own addressing — what the write path actually keys on. */
  fieldId: string;
  /** The document's own label for this control, VERBATIM.
   *
   *  Deliberately not truncated or tidied. Two labels that differ only near
   *  their end would look identical if shortened, and a doctor recognises the
   *  sentence from their own form. The NUMBER is the addressing; the label is
   *  how a human confirms the machine and they mean the same control. */
  label: string;
  /**
   * Where this control sits among the controls sharing its label, 1-based —
   * or `null` when the label is unique on this form.
   *
   * ⚠️ THIS EXISTS BECAUSE THE MANDATED "ASK WHICH" WAS UNANSWERABLE FOR 18 OF
   * 28 CONTROLS. The prompt requires the model to quote the competing labels
   * and their numbers when a request is ambiguous — and for the four ambiguous
   * groups the labels are byte-identical and the option sets match in pairs, so
   * the question read *"did you mean #25 '<sentence>' or #30 '<the identical
   * sentence>'?"* That is `note-table-edit.test.ts:424`'s invariant — never ask
   * a question you offer no way to answer — arriving on a new carrier.
   *
   * An occurrence index is derived from document order, is always available,
   * and is answerable by a doctor reading their own form top to bottom: *"the
   * FIRST of the two identically-worded sentences, or the SECOND?"*
   */
  sameLabelIndex: number | null;
  /** How many controls share this label. `null` when the label is unique. */
  sameLabelTotal: number | null;
  /** What this control allows, in ordinal order. */
  options: string[];
}

/**
 * Every enumerated control on this form, in DOCUMENT ORDER.
 *
 * Document order is the ordering because it is the one a doctor can follow on
 * their own page ("the second treated-vein sentence"). `ir.fields` is already
 * ordered by `displayOrder`; this sorts explicitly rather than trusting that,
 * because the ordinal is load-bearing and an implicit ordering is exactly the
 * kind of assumption that holds until the day it does not.
 *
 * ⚠️ FILTERED TO CONTROLS THAT HAVE A CLOSED OPTION SET. A field with no
 * options cannot be validated against one, and this surface never free-texts
 * into a constrained field.
 *
 * ⚠️ WORD'S "Choose an item." PLACEHOLDER IS EXCLUDED **HERE**, BY THIS
 * FUNCTION, AND NOT INHERITED FROM THE COMPILER.
 *
 * *Previous wording, kept because the correction is the point:* "the option
 * sets no longer carry Word's placeholder — the compiler strips it."
 *
 * That was true for four hours and it was the wrong place for the filter. The
 * compiler now PERSISTS the document's option array verbatim, because
 * `renderer.ts:assertSourceMatchesIr` re-compiles the immutable source on every
 * fill and hashes `fields` — so shrinking the stored array made every
 * already-compiled twin unfillable, production's included. See the long note at
 * `compiler.ts`.
 *
 * So this filters for itself, like every other reader. The treatment lives on
 * each READER, where it cannot be forgotten by whoever changes the compiler
 * next. ⚠️ The full reader list is enumerated in `compiler.ts` beside the
 * persistence decision — **six**, not the three an earlier version of this
 * comment named. Do not restate the count here; a second copy drifts.
 *
 * ⚠️ AND THIS SURFACE IS NOT "the list offered to the model", THOUGH IT WAS
 * ONCE DESCRIBED THAT WAY. It is the list the CLINICIAN'S EDIT DOOR addresses
 * by ordinal. The mapping-proposal payload in `semantic-mapping/index.ts` is a
 * different surface with a different model on the other end — and it went
 * unfiltered precisely because one phrase covered both.
 *
 * ⚠️ AND THE FILTER GOVERNS ELIGIBILITY, NOT ONLY THE LIST SHOWN. `ordinal` is
 * this function's index over `eligible`, so a control admitted here that should
 * not be would shift EVERY LATER ORDINAL BY ONE — a wrong-control write
 * reported as success, which is precisely the failure `gate-f24-s5-control-
 * addressable-census`'s M2 mutation exists to catch. Both uses therefore read
 * the same computed set rather than re-deriving it.
 *
 * A control whose ONLY entry was the placeholder has an empty selectable set and
 * is filtered out, which is correct: it offers no clinical choice. (The compiler
 * already refuses such a control with `SELECT_OPTIONS_INVALID` so it never
 * reaches the IR — this does not depend on that.) Measured on production: every
 * one of the 28 retains 1..10 real options, so none is lost.
 */
export function listEditableFormControls(ir: TemplateDocIR): EditableFormControl[] {
  const selectableByFieldId = new Map(
    ir.fields.map((f) => [f.fieldId, withoutPlaceholderOptions(f.allowedOptions)]),
  );
  const eligible = ir.fields
    .filter(
      (f) =>
        f.rendererBinding.bindingType === 'content_control' &&
        (selectableByFieldId.get(f.fieldId)?.length ?? 0) > 0,
    )
    .slice()
    .sort((a, b) => a.displayOrder - b.displayOrder);

  // How many controls share each label, computed over the SAME eligible set the
  // ordinals are issued from — not over `ir.fields`, or a control filtered out
  // above would inflate a group the doctor is never shown.
  const labelCounts = new Map<string, number>();
  for (const f of eligible) {
    labelCounts.set(f.originalLabel, (labelCounts.get(f.originalLabel) ?? 0) + 1);
  }
  const seen = new Map<string, number>();

  return eligible.map((f, i) => {
    const total = labelCounts.get(f.originalLabel) ?? 1;
    const index = (seen.get(f.originalLabel) ?? 0) + 1;
    seen.set(f.originalLabel, index);
    return {
      ordinal: i + 1,
      fieldId: f.fieldId,
      label: f.originalLabel,
      sameLabelIndex: total > 1 ? index : null,
      sameLabelTotal: total > 1 ? total : null,
      options: (selectableByFieldId.get(f.fieldId) ?? [])
        .slice()
        .sort((a, b) => a.ordinal - b.ordinal)
        .map((o) => o.displayText),
    };
  });
}

/**
 * What the MODEL is shown for each control.
 *
 * ⚠️ `fieldId` IS DELIBERATELY ABSENT. A model that never sees one cannot
 * invent one, and the server never accepts one from the model — the ordinal is
 * the only address that crosses the boundary, in either direction.
 *
 * ⚠️ `occurrence` IS PRESENT ONLY WHEN IT DISCRIMINATES. Emitting "1 of 1" for
 * the 10 unique-label controls would be noise the model has to reason past, and
 * would invite it to quote an occurrence where the label already settles the
 * question.
 */
export function formControlsForModel(
  controls: readonly EditableFormControl[],
): { n: number; label: string; occurrence?: string; options: string[] }[] {
  return controls.map((c) => ({
    n: c.ordinal,
    label: c.label,
    ...(c.sameLabelIndex && c.sameLabelTotal
      ? { occurrence: `${c.sameLabelIndex} of ${c.sameLabelTotal} with this wording` }
      : {}),
    options: c.options,
  }));
}

/**
 * This visit's editable controls, or an empty list.
 *
 * Empty is the ORDINARY case and never an error: production holds ten note
 * templates and exactly one compiled twin, so all but one bind to a template
 * with no controls to offer. An empty list simply gives the model nothing to
 * address, which is the correct behaviour rather than a degraded one.
 */
export async function listVisitFormControls(
  noteTemplateId: string | null,
  noteTemplateVersion: number | null,
  /** ⚠️ PRACTICE-SCOPED. The compiled version carries `practiceId`, so the
   *  scope is DERIVED in the query rather than threaded as a value that could
   *  drift — a template belonging to another practice simply does not resolve,
   *  and the chat is offered nothing rather than another tenant's form
   *  structure. */
  practiceId: string,
): Promise<EditableFormControl[]> {
  if (!noteTemplateId || typeof noteTemplateVersion !== 'number') return [];
  const row = await prisma.noteTemplate.findFirst({
    where: {
      id: noteTemplateId,
      version: noteTemplateVersion,
      templateTwinCompiledVersion: { practiceId },
    },
    select: {
      templateTwinCompiledVersion: {
        select: { certificationStatus: true, compiledDocumentIr: true },
      },
    },
  });
  const compiled = row?.templateTwinCompiledVersion;
  // UNCERTIFIED OFFERS NOTHING. An uncertified twin's field set is not the one
  // the renderer will use, so addressing into it would be addressing into a
  // structure that does not ship.
  if (!compiled || compiled.certificationStatus !== 'CERTIFIED') return [];
  const parsed = TemplateDocIRSchema.safeParse(compiled.compiledDocumentIr);
  if (!parsed.success) return [];
  return listEditableFormControls(parsed.data);
}
