// ============================================================================
// F24-S5 — THE FORM CONTROLS A DOCTOR MAY ADDRESS, AND HOW THEY ARE ADDRESSED.
// ----------------------------------------------------------------------------
// A doctor sees 28 dropdowns in their Word form. Until this slice none of them
// could be reached from the chat editor at all — they render from the fill's
// `selectedOptionOrdinal`, not from the note markdown, so no note edit could
// touch them.
//
// ⚠️ THEY CANNOT BE ADDRESSED BY LABEL, AND THIS IS MEASURED, NOT ASSUMED.
// On the one certified twin in production (2026-08-24):
//
//     28 content controls  ->  14 distinct `originalLabel`s
//
// The labels are the surrounding SENTENCE with "Choose an item." sitting where
// each dropdown goes, so one sentence carrying four dropdowns yields four
// controls with the SAME label. The partition:
//
//     8 share one label · 6 share one · 2 · 2   = 18 ambiguous
//     10 unique                                 = 10
//                                                 28 ✔   (4 + 10 = 14 ✔)
//
// ⚠️ AND THE OPTION SETS DO NOT RESCUE IT EITHER. Within the 8-group the four
// controls of one sentence have genuinely different option sets (vein / junction
// / location / status) — but the group is TWO such sentences, and across them
// the sets are identical in pairs (displayOrder 25≡30, 26≡31, 27≡32, 28≡33).
// So neither the label nor the options can separate 25 from 30. Only the
// control's POSITION IN THE DOCUMENT can.
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
 */
export function listEditableFormControls(ir: TemplateDocIR): EditableFormControl[] {
  return ir.fields
    .filter(
      (f) =>
        f.rendererBinding.bindingType === 'content_control' &&
        f.allowedOptions.length > 0,
    )
    .slice()
    .sort((a, b) => a.displayOrder - b.displayOrder)
    .map((f, i) => ({
      ordinal: i + 1,
      fieldId: f.fieldId,
      label: f.originalLabel,
      options: f.allowedOptions
        .slice()
        .sort((a, b) => a.ordinal - b.ordinal)
        .map((o) => o.displayText),
    }));
}

/**
 * What the MODEL is shown for each control.
 *
 * ⚠️ `fieldId` IS DELIBERATELY ABSENT. A model that never sees one cannot
 * invent one, and the server never accepts one from the model — the ordinal is
 * the only address that crosses the boundary, in either direction.
 */
export function formControlsForModel(
  controls: readonly EditableFormControl[],
): { n: number; label: string; options: string[] }[] {
  return controls.map((c) => ({ n: c.ordinal, label: c.label, options: c.options }));
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
  /** ⚠️ PRACTICE-SCOPED, and the T5 guard caught this read unscoped on its
   *  first full run. The compiled version carries `practiceId`, so the scope is
   *  DERIVED in the query rather than threaded as a value that could drift —
   *  a template belonging to another practice simply does not resolve, and the
   *  chat is offered nothing rather than another tenant's form structure. */
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
