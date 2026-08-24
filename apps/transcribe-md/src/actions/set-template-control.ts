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
import { visitByIdScope } from '@/lib/practice-scope';
import { invalidateVisitFills } from '@/lib/docx-preview/fill-cache';
import { TemplateDocIRSchema } from '@/lib/template-twin/ir';
import { isWordPlaceholderOption } from '@/lib/note-template-docx/placeholder-option';

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

  const visit = await prisma.transcribeVisit.findFirst({
    where: {
      ...visitByIdScope(visitId, session.user.practiceId),
      deletedAt: null,
      archivedAt: null,
    },
    select: {
      id: true,
      status: true,
      noteTemplateId: true,
      noteTemplateVersion: true,
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

  await prisma.templateTwinFieldOverride.upsert({
    where: { visitId_fieldId: { visitId, fieldId } },
    create: {
      practiceId: visit.user.practiceId,
      visitId,
      fieldId,
      selectedOptionOrdinal: option.ordinal,
      optionValue: option.value,
      overriddenBy: session.user.id,
    },
    update: {
      selectedOptionOrdinal: option.ordinal,
      optionValue: option.value,
      overriddenBy: session.user.id,
    },
  });

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
