// ============================================================================
// F24-S5 — THE CLINICIAN'S OWN CORRECTION TO AN ENUMERATED FORM CONTROL.
// ----------------------------------------------------------------------------
// A doctor looking at their own form says "SIDE OF EXAM should be Left". Until
// this module there was no way for that to reach the document: the 28 content
// controls were `no_editor_intent` — the whole of F24's remaining gap, and one
// class.
//
// ⚠️ THIS IS A SEPARATE OVERLAY, DELIBERATELY, AND IT DOES NOT TOUCH
// `mergeFieldResolutions`. That function's rule — an overlay applies ONLY where
// the baseline left the field unfilled — is correct and stays byte-for-byte as
// it was: it is what keeps the evidence resolver winning over the AI bridges.
// Widening it to admit a clinician value would let EVERY bridge overlay
// overwrite resolver-supported values, which is a clinical-safety regression
// well outside this slice.
//
// So precedence is expressed by ORDER, not by a flag: the bridges merge under
// their existing rule, and the clinician is applied AFTERWARDS and WINS.
//
// ⚠️ WHY WINNING IS THE WHOLE POINT, MEASURED RATHER THAN ASSUMED. On the two
// real production fills, the 28 controls resolve 43 `not_mentioned` / 13
// `supported` (= 56 = 28 x 2). `supported` is NOT a member of `UNFILLED`
// (`bridge-fill.ts`), so a clinician value routed through the existing overlay
// would be REFUSED for exactly the 13 — and 11 of those 13 are
// `criticality: laterality`. A developer testing "change the indication
// dropdown" hits the routine class (40 of 42 unfilled) and sees it work
// perfectly; a doctor saying "SIDE OF EXAM should be Left" hits the refused
// class and is silently ignored. A uniformly broken feature would have been
// safer than that.
//
// ⚠️ AND BEING AN INPUT IS NOT ENOUGH ON ITS OWN — THAT WAS THE REFUTED SLICE'S
// DEFECT. These rows are read on every fill, so a recompute re-applies them;
// but the two surfaces that decide WHETHER a fill runs gate on the note alone,
// and an override never touches `soapFinal`. The other half of the fix lives in
// `note-identity.ts` (`overridesIdentity`) and
// `TemplateTwinFillManifest.overridesSha256`: an override moves the bound
// identity, the manifest reads STALE, and the recompute actually happens.
// ============================================================================

import { canOmitWhenUnmentioned } from './unmentioned-policy';
import type { OmitFieldView, OmitMappingView } from './unmentioned-policy';
import { isWordPlaceholderOption } from '../note-template-docx/placeholder-option';
import { canonicalSha256 } from './canonical';
import {
  EncounterFactSchema,
  FieldResolutionSchema,
  type EncounterFact,
  type FieldResolution,
  type SemanticMapping,
  type TemplateDocIR,
  type TemplateField,
} from './ir';

/** One clinician correction, as stored.
 *
 *  ⚠️ A DISCRIMINATED UNION SINCE REVIEW-DEFAULTS, AND THE DISCRIMINANT IS
 *  REQUIRED RATHER THAN DEFAULTED. Two kinds now share this table and this
 *  overlay, and they have opposite precedence rules: an `option` correction
 *  WINS over whatever the bridges resolved, while a `scaffold_default` applies
 *  ONLY to a field that is still blank. Defaulting the discriminant would make
 *  a mis-shaped row silently take the winning arm — the more dangerous of the
 *  two — so it is stated at every construction site. */
export type ClinicianFieldOverride =
  | {
      kind: 'option';
      fieldId: string;
      /** The ORDINAL is the value — see the header. */
      selectedOptionOrdinal: number;
    }
  | {
      kind: 'scaffold_default';
      fieldId: string;
      /** The doctor's own compiled `scaffoldText`, as the writer read it from
       *  the IR. Never client-supplied. */
      insertedText: string;
    };

export interface ApplyClinicianOverridesInput {
  ir: TemplateDocIR;
  /** The post-merge resolutions — exactly one per `ir.fields`. */
  resolutions: readonly FieldResolution[];
  overrides: readonly ClinicianFieldOverride[];
  mappings: readonly SemanticMapping[];
  /** Identity of the note this fill is running against. Part of the fact's
   *  identity so a corrected value on a re-generated note is a different fact,
   *  exactly as `verifiedNoteSelectionFactId` does it. */
  noteSha256: string;
}

export interface ApplyClinicianOverridesResult {
  resolutions: FieldResolution[];
  /** Provenance minted for the applied overrides. MUST travel with the
   *  resolutions into the manifest's fact set — a citation to a fact the
   *  manifest does not carry is untraceable, and the validator says so. */
  facts: EncounterFact[];
  /**
   * Overrides that did NOT apply, with the reason.
   *
   * ⚠️ THIS HAS A CONSUMER, AND SAYING SO USED TO BE FALSE. An earlier draft's
   * header promised "the doctor is told through `declined` either way" while
   * `prepareTemplateTwinFill` destructured the result and dropped it — zero
   * consumers, one `console.info`, so a recompiled template silently lost a
   * correction the chat had already reported as `ok: true`. It is now turned
   * into a `warning` issue on the fill manifest by `finalizeTemplateTwinFill`.
   * Warning, never blocking: losing one correction must not strand the whole
   * document.
   */
  declined: { fieldId: string; reason: ClinicianOverrideDeclineReason }[];
}

export type ClinicianOverrideDeclineReason =
  /** The stored fieldId is not in this compiled IR at all. */
  | 'field_not_in_template'
  /** The field carries no closed option set, so there is nothing to validate
   *  against. Never free-text into a constrained field — and never into an
   *  unconstrained one from here either. */
  | 'field_has_no_options'
  /** The ordinal does not resolve in the CURRENT option set. The template was
   *  recompiled under the override. FAIL CLOSED — see the note below. */
  | 'ordinal_not_in_options'
  /** The ordinal resolves to Word's "Choose an item." placeholder. Furniture,
   *  never a clinical value — see the note at the check itself. */
  | 'option_is_placeholder'
  /** No approved mapping, so the minted fact has no concept to satisfy and the
   *  validator would have nothing to check the citation against. */
  | 'no_approved_concept'
  /** A scaffold-default insert addressed a field the CURRENT compile does not
   *  mark scaffolded. The template was recompiled under the insert. FAIL
   *  CLOSED, exactly as `ordinal_not_in_options` does for the other kind. */
  | 'not_scaffolded_in_current_compile'
  /**
   * ⚠️ THE RULE THAT KEEPS #194 TRUE, AND IT IS THE WHOLE REASON THIS KIND DOES
   * NOT SIMPLY WIN LIKE THE OTHER ONE.
   *
   * A scaffold default applies ONLY to a field that is still blank. The click
   * meant "there is nothing here, put my usual wording in" — it did not mean
   * "replace whatever was dictated". Because the overlay runs AFTER the bridges
   * and the row persists across every later fill, an unconditional apply would
   * mean: doctor inserts a default into a blank field, later dictates that
   * field for real, and the stored default OVERWRITES the dictation on the next
   * recompute. That is the machine printing an undictated default over
   * dictated content — the exact thing ruling #194 deleted, re-entering through
   * the door built to honour it.
   */
  | 'field_already_filled'
  /** A scaffold default addressed a control that cannot hold free text — a
   *  dropdown, date, checkbox, table. Writing one BLOCKS THE WHOLE DOCUMENT at
   *  validation, so this refuses rather than letting the fill fail. */
  | 'field_kind_not_insertable';

/** Stable provenance identity for one clinician correction.
 *
 *  Mirrors `verifiedNoteSelectionFactId` exactly, including the note identity:
 *  a corrected value against a re-generated note is a DIFFERENT selection and
 *  must never silently reuse the prior manifest's fact or anchor. */
export function clinicianOverrideFactId(input: {
  fieldId: string;
  optionValue: string;
  selectedOptionOrdinal: number;
  noteSha256: string;
}): string {
  return `ttfact_${canonicalSha256({
    kind: 'clinician_correction',
    fieldId: input.fieldId,
    optionValue: input.optionValue,
    selectedOptionOrdinal: input.selectedOptionOrdinal,
    noteSha256: input.noteSha256,
  }).slice(0, 24)}`;
}

export function clinicianOverrideAnchorId(fieldId: string, factId: string): string {
  return `ttco_${canonicalSha256({ factId, fieldId }).slice(0, 24)}`;
}

/**
 * The citable fact behind a clinician's correction.
 *
 * `sourceType: 'clinician_correction'` is NOT a new provenance class — it has
 * been declared in `EncounterFactSchema` since the twin shipped and has never
 * had a writer. This is the writer it was declared for.
 *
 * `value` is the template's option VERBATIM, so the validator re-derives the
 * rendered value by exact option lookup — the same check it makes of any cited
 * fact. Not one validator rule is relaxed to accommodate it.
 */
/**
 * The statuses a scaffold default may fill INTO.
 *
 * ⚠️ MIRRORS `UNFILLED` IN `bridge-fill.ts` DELIBERATELY, AND THE MIRROR IS
 * STATED SO THE NEXT READER CHECKS BOTH. It is a copy rather than an import
 * because the two answer different questions — that set decides whether a
 * BRIDGE may overlay, this one decides whether a HUMAN's default may land in a
 * gap — and collapsing them would tie a clinical-safety rule to a UI rule.
 * If a status is added there, decide here on purpose rather than inherit it.
 */
const SCAFFOLD_INSERTABLE_STATUSES: ReadonlySet<string> = new Set([
  'not_mentioned',
  'needs_clinician_input',
  'ambiguous',
]);

/**
 * The field KINDS a scaffold default may be written into.
 *
 * ⚠️ FREE TEXT INTO A CONSTRAINED CONTROL BREAKS THE WHOLE DOCUMENT, NOT ONE
 * FIELD. `isScaffolded` in the compiler is `no showingPlcHdr && visible text`
 * and never reads `kind`, so a dropdown, date or checkbox shipping with default
 * content compiles as scaffolded exactly like a narrative paragraph does. Write
 * a sentence into one and `validation/index.ts` raises a BLOCKING per-kind
 * issue (DROPDOWN_NOT_EXACT_OPTION, a date type error, …); `fill-engine`
 * returns `render: null` for the entire fill; the preview returns `no_render`;
 * and the surface unmounts — taking the panel, and therefore the UNDO button,
 * with it. For a date or checkbox there is then no product path left to delete
 * the row.
 *
 * So the kinds are named POSITIVELY and everything else is refused. A new kind
 * added to the vocabulary is excluded until somebody decides otherwise, which
 * is the direction that fails safe.
 */
export const SCAFFOLD_INSERTABLE_KINDS: ReadonlySet<string> = new Set(['narrative_text']);

/**
 * Is this field one the doctor may insert their own default into, RIGHT NOW?
 *
 * ⚠️ ONE DEFINITION, THREE CALLERS, AND THAT IS THE POINT. The panel decides
 * what to OFFER, the server action decides what to ACCEPT, and this overlay
 * decides what to APPLY. An adversarial pass found all three asking different
 * questions: the panel offered fields the door accepted and the fill then
 * declined forever, and offered constrained controls that broke the document.
 * A surface must never offer an act its writer would refuse.
 */
export function scaffoldDefaultOfferable(input: {
  // ⚠️ `OmitFieldView`, NOT a three-property structural shape. The omit clause
  // below calls the resolver's own reachability predicate, which reads SIX
  // field properties; typing this loosely is what let a cast stand in for them.
  field: OmitFieldView & { scaffolded?: boolean; scaffoldText?: string | null };
  // ⚠️ `string | null` for `unmentionedPolicy`, NOT `'omit' | null`. That column
  // is read straight off Prisma as a plain nullable string, and narrowing it
  // would force a cast at the call site — a cast is how a column that later
  // holds an unexpected value stops being checked. The comparison below is exact.
  //
  // ⚠️ AND THE REST OF THE SHAPE IS `OmitMappingView`, WHICH IS THE FIX. The
  // previous type named TWO properties and the predicate reads EIGHT, so the
  // call below cast with `as never` and every missing property arrived
  // `undefined`. `toOmitMappingView` in `unmentioned-policy.ts` is how a Prisma
  // row becomes this — it is not the same shape and never was.
  mapping:
    | (OmitMappingView & { unmentionedPolicy?: string | null })
    | null
    | undefined;
  /** The field's CURRENT resolution, or null when none has been computed. */
  current: { status?: string; value?: unknown } | null | undefined;
}): boolean {
  const { field, mapping, current } = input;
  if (field.scaffolded !== true) return false;
  if (!(field.scaffoldText ?? '').trim()) return false;
  if (!SCAFFOLD_INSERTABLE_KINDS.has(field.kind ?? '')) return false;
  // The fill declines forever without a concept — see the overlay's own note.
  if (!mapping?.clinicalConcept) return false;
  // ⚠️ ONLY WHEN THE RESOLVER WOULD ACTUALLY HONOUR IT — AND THE FIRST CUT OF
  // THIS CLAUSE DID NOT ASK. A peer session measured the consequence and it is
  // strictly worse than not ticking at all: on a field the resolver refuses the
  // omit for (a `manual` source, a fixed-grid cell), the count does NOT move —
  // the blank stays in `notMentioned` and the doctor is still prompted — while
  // this clause removed their remedy anyway. Reproduced before fixing:
  //
  //   MANUAL field, stored omit:   canOmitWhenUnmentioned false
  //                                scaffoldDefaultOfferable false   <- remedy gone
  //   EXTRACTION control:          canOmitWhenUnmentioned true
  //
  // ⚠️ AND IT WAS A FOURTH SPELLING OF THE RULE. This file's own header says
  // ONE DEFINITION, THREE CALLERS; I added a bare `=== 'omit'` test beside a
  // shared predicate written precisely so nobody would. The predicate is called
  // instead — one definition, one more caller.
  
  //
  // REVIEW-DEFAULTS item 2's control says, in the doctor's own words,
  // "Expected blank — do not ask me about this". Without this clause the field
  // is still listed in the "Your blanks" panel under the heading "Nothing was
  // dictated for these" — because an `omit` resolution is `not_mentioned` with
  // `value: null`, and `scaffoldTargetIsBlank` is true for exactly that shape.
  // So the control's label was false: the doctor ticked it and was asked again
  // on the very next visit.
  //
  // ⚠️ IT IS THE **OFFER** THAT IS WITHDRAWN, NOT AN APPLIED DEFAULT. The
  // caller keeps an ALREADY-INSERTED default listed (`inserted ||` in
  // `preview-visit-document.ts`) so Undo stays reachable for a doctor who
  // inserted before setting the policy, and `applyClinicianOverrides` is
  // deliberately NOT given this clause — a stored override the doctor did
  // assert must still apply, or the fill silently drops their own words.
  // ⚠️ NO CAST. The two `as never`s that used to be here were load-bearing in
  // the worst sense: they existed so a two-column Prisma row could be passed to
  // an eight-property view, and they simultaneously switched off the only thing
  // that would have objected. `tsc` was silent while this clause was dead.
  if (mapping.unmentionedPolicy === 'omit' && canOmitWhenUnmentioned(field, mapping))
    return false;
  return scaffoldTargetIsBlank(current);
}

/**
 * ⚠️ A WITHHELD DENIAL IS NULL BY CONSTRUCTION, AND IT IS NOT BLANK.
 *
 * This clause is copied from `bridge-fill.ts`, which learned it the expensive
 * way, and its absence here was found by an adversarial pass with a full
 * reproduction: `FieldResolutionSchema`'s superRefine FORCES `value === null`
 * on every `denial_withheld` resolution, so a `value === null` test is true for
 * 100% of them and any status allow-list placed after it never runs.
 *
 * The measured consequence: an encounter dictated as *"There are no varicose
 * veins"* resolved `denial_withheld`; the stored default then applied, the
 * document asserted *"Varicosities present in the great saphenous
 * distribution"*, the FIELD_DENIAL_WITHHELD warning vanished, `needsReview`
 * went 1 → 0, validation returned CLEAN — and sign-freeze would have frozen it
 * into the signed record.
 *
 * **Withholding is a DECISION; absence is not.**
 */
export function scaffoldTargetIsBlank(
  current: { status?: string; value?: unknown } | null | undefined,
): boolean {
  if (current == null) return true;
  if (current.status === 'denial_withheld') return false;
  return (
    current.value === null ||
    current.value === undefined ||
    current.value === '' ||
    SCAFFOLD_INSERTABLE_STATUSES.has(current.status ?? '')
  );
}

/** Stable provenance identity for one inserted default.
 *
 *  Includes `noteSha256` for the same reason the correction fact does: the same
 *  default asserted against a re-generated note is a DIFFERENT assertion and
 *  must not silently reuse the prior manifest's fact or anchor. */
export function scaffoldDefaultFactId(input: {
  fieldId: string;
  insertedText: string;
  noteSha256: string;
}): string {
  return `ttfact_${canonicalSha256({
    kind: 'clinician_scaffold_default',
    fieldId: input.fieldId,
    insertedText: input.insertedText,
    noteSha256: input.noteSha256,
  }).slice(0, 24)}`;
}

/**
 * Provenance for a default the DOCTOR asserted.
 *
 * ⚠️ `sourceType: 'clinician_correction'` IS REUSED ON PURPOSE, AND IT IS NOT
 * LAZINESS. The fact schema's source vocabulary is a clinical-provenance axis,
 * and what happened here is exactly what that value means: a human, looking at
 * their own form, asserted this value. Minting a new source type would widen a
 * validated clinical enum for a UI distinction that the AUDIT trail already
 * carries (`DEFAULT_INSERTED_BY_DOCTOR`) and that `reasonCode` already carries
 * on the resolution.
 *
 * ⚠️ IT CARRIES THE MAPPING'S `clinicalConcept`, AND A CONCEPT IS REQUIRED —
 * WHICH IS A BOUNDARY, NOT A LIMITATION. `factMatchesMapping` returns FALSE
 * whenever the mapping has no `clinicalConcept` (validation/index.ts:188) and
 * `SOURCE_FACT_CONCEPT_MISMATCH` is unconditional, so ANY cited fact on a
 * concept-less mapping blocks — while `POPULATED_WITHOUT_EVIDENCE` blocks a
 * populated value that cites nothing. There is therefore NO
 * populated-with-evidence path for an administrative, concept-less field at
 * all, and inventing one would mean a new status with its own validator arm.
 *
 * It is also the RIGHT boundary under the owner's split of ruling #194:
 * administrative fields (identity, credentials, addresses, boilerplate) keep
 * `approved_practice_default`, where certification-time approval is the human
 * act and no dictation can contradict them. CLINICAL fields — the ones that
 * carry concepts — are the ones a pre-approved sentence must never print on,
 * and they are exactly the ones this door serves.
 */
export function buildScaffoldDefaultFact(input: {
  field: Pick<TemplateField, 'fieldId' | 'originalLabel'>;
  mapping: SemanticMapping;
  insertedText: string;
  noteSha256: string;
}): EncounterFact {
  const factId = scaffoldDefaultFactId({
    fieldId: input.field.fieldId,
    insertedText: input.insertedText,
    noteSha256: input.noteSha256,
  });
  return EncounterFactSchema.parse({
    factId,
    sourceType: 'clinician_correction',
    concept: input.mapping.clinicalConcept,
    value: input.insertedText,
    polarity: 'affirmed',
    // ⚠️ MIRRORS THE OPTION ARM RATHER THAN HARDCODING. `factMatchesMapping`
    // checks a declared temporality, so a fact that ignores the declaration
    // blocks the whole document.
    temporality:
      input.mapping.temporality === 'historical' ||
      input.mapping.temporality === 'planned' ||
      input.mapping.temporality === 'current'
        ? input.mapping.temporality
        : 'current',
    experiencer: 'patient',
    laterality:
      input.mapping.laterality === 'not_applicable' ? 'not_applicable' : 'unknown',
    number: null,
    unit: null,
    speaker: null,
    sourceTranscriptOffsets: null,
    audioTimestampSeconds: null,
    evidenceAnchorIds: [clinicianOverrideAnchorId(input.field.fieldId, factId)],
    // ⚠️ THE DOCTOR'S OWN CLICK IS THE EVIDENCE, AND THE QUOTE SAYS SO PLAINLY.
    // Deliberately NOT a transcript quote — there is no utterance to cite, and
    // inventing one would be a fabricated provenance for a real decision. The
    // wording names the ACT rather than paraphrasing the value, because the
    // value is already the fact's `value` and repeating it here would put the
    // doctor's form text in two fields that can drift apart.
    evidenceQuote: 'Clinician inserted their own default for this field at review.',
    // `direct` for the same reason the correction fact is: a human said so, in
    // the application, about their own form. `SUPPORTED_STATUS_CONFLICTS_WITH_QUALITY`
    // blocks a supported field whose evidence is anything else.
    quality: { asr: 'high', evidence: 'direct' },
  });
}

export function buildClinicianOverrideFact(input: {
  field: Pick<TemplateField, 'fieldId' | 'originalLabel'>;
  mapping: SemanticMapping;
  optionValue: string;
  selectedOptionOrdinal: number;
  noteSha256: string;
  fieldLaterality: 'right' | 'left' | 'unknown';
}): EncounterFact {
  const factId = clinicianOverrideFactId({
    fieldId: input.field.fieldId,
    optionValue: input.optionValue,
    selectedOptionOrdinal: input.selectedOptionOrdinal,
    noteSha256: input.noteSha256,
  });
  return EncounterFactSchema.parse({
    factId,
    sourceType: 'clinician_correction',
    concept: input.mapping.clinicalConcept,
    value: input.optionValue,
    polarity: 'affirmed',
    temporality:
      input.mapping.temporality === 'historical' ||
      input.mapping.temporality === 'planned' ||
      input.mapping.temporality === 'current'
        ? input.mapping.temporality
        : 'current',
    experiencer: 'patient',
    laterality:
      input.fieldLaterality !== 'unknown'
        ? input.fieldLaterality
        : input.mapping.laterality === 'not_applicable'
          ? 'not_applicable'
          : 'unknown',
    number: null,
    unit: null,
    speaker: null,
    sourceTranscriptOffsets: null,
    audioTimestampSeconds: null,
    evidenceAnchorIds: [clinicianOverrideAnchorId(input.field.fieldId, factId)],
    // The doctor's own act is the evidence. Deliberately NOT a transcript
    // quote: there is no utterance to cite, and inventing one would be a
    // fabricated provenance for a real decision.
    evidenceQuote: `Clinician set this control to "${input.optionValue}".`,
    segment: null,
    quality: { asr: 'high', evidence: 'direct' },
  });
}

/**
 * The side the field's own label names, or 'unknown'.
 *
 * ⚠️ IDENTICAL DOCTRINE TO `fieldLateralityFromLabel`, AND A LABEL NAMING BOTH
 * SIDES NAMES NEITHER. Two of this form's content-control labels are literally
 * "Left <choose> is <choose>" and "Right <choose> is <choose>"; a label
 * mentioning both would be ambiguous and must fail closed rather than pick one.
 */
function lateralityFromLabel(originalLabel: string): 'right' | 'left' | 'unknown' {
  const t = originalLabel.trim().toLowerCase();
  const right = /\bright\b/.test(t);
  const left = /\bleft\b/.test(t);
  if (right === left) return 'unknown';
  return right ? 'right' : 'left';
}

/**
 * Apply the clinician's corrections on top of an already-merged resolution set.
 *
 * WIN precedence, for the fields it names and no others. Returns exactly one
 * resolution per `ir.fields` — the cardinality the renderer enforces — in
 * `ir.fields` order.
 *
 * ⚠️ EVERY REFUSAL PATH LEAVES THE PRIOR RESOLUTION EXACTLY AS IT WAS. An
 * override that cannot be applied must not blank the cell: a value the resolver
 * legitimately derived is better than the hole a half-applied correction would
 * leave, and the decline is reported as a manifest warning.
 */
export function applyClinicianOverrides(
  input: ApplyClinicianOverridesInput,
): ApplyClinicianOverridesResult {
  const { ir, overrides, mappings, noteSha256 } = input;
  const byId = new Map<string, FieldResolution>();
  for (const r of input.resolutions) byId.set(r.fieldId, r);

  const fieldById = new Map<string, TemplateField>(ir.fields.map((f) => [f.fieldId, f]));
  const mappingById = new Map<string, SemanticMapping>(mappings.map((m) => [m.fieldId, m]));

  const facts: EncounterFact[] = [];
  const declined: { fieldId: string; reason: ClinicianOverrideDeclineReason }[] = [];
  // A duplicate fieldId cannot arrive from the database (@@unique on
  // (visitId, fieldId)) but this function is also called directly. Last write
  // would otherwise win silently; refuse to be order-dependent instead.
  const applied = new Set<string>();

  const decline = (fieldId: string, reason: ClinicianOverrideDeclineReason) => {
    declined.push({ fieldId, reason });
    console.info(
      `[template-twin:clinician-override] declined field=${fieldId} reason=${reason}`,
    );
  };

  for (const override of overrides) {
    if (applied.has(override.fieldId)) continue;
    const field = fieldById.get(override.fieldId);
    if (!field) {
      decline(override.fieldId, 'field_not_in_template');
      continue;
    }

    // ── REVIEW-DEFAULTS item 1: the doctor's own default, asserted at review ──
    if (override.kind === 'scaffold_default') {
      // ⚠️ RE-CHECKED AGAINST THE CURRENT COMPILE, NOT TRUSTED FROM THE ROW.
      // Same discipline as `ordinal_not_in_options` on the other arm: the row
      // was written against one compiled version and is being applied against
      // whatever is compiled now.
      if (field.scaffolded !== true) {
        decline(override.fieldId, 'not_scaffolded_in_current_compile');
        continue;
      }

      // ⚠️ BLANK-ONLY, AND THIS IS THE LINE THAT KEEPS RULING #194 TRUE.
      // See `field_already_filled` for the full argument. In short: this row
      // persists across every later fill, so an unconditional apply would let a
      // default the doctor inserted into an empty field later OVERWRITE the
      // dictation that filled it.
      if (!SCAFFOLD_INSERTABLE_KINDS.has(field.kind)) {
        decline(override.fieldId, 'field_kind_not_insertable');
        continue;
      }

      if (!scaffoldTargetIsBlank(byId.get(field.fieldId))) {
        decline(override.fieldId, 'field_already_filled');
        continue;
      }

      // ⚠️ THE SAME CONCEPT REQUIREMENT AS THE OPTION ARM, AND FOR A STRONGER
      // REASON. Without a concept the minted fact cannot satisfy
      // `factMatchesMapping`, so the fill would be REFUSED at validation with
      // `SOURCE_FACT_CONCEPT_MISMATCH` — a BLOCKING issue on the whole document
      // caused by one click. Declining here costs the doctor one field; the
      // alternative costs them the note.
      const scaffoldMapping = mappingById.get(override.fieldId);
      if (!scaffoldMapping?.clinicalConcept) {
        decline(override.fieldId, 'no_approved_concept');
        continue;
      }
      const fact = buildScaffoldDefaultFact({
        field,
        mapping: scaffoldMapping,
        insertedText: override.insertedText,
        noteSha256,
      });
      facts.push(fact);
      byId.set(
        field.fieldId,
        FieldResolutionSchema.parse({
          fieldId: field.fieldId,
          status: 'supported',
          value: override.insertedText,
          sourceFactIds: [fact.factId],
          evidenceAnchorIds: [...fact.evidenceAnchorIds],
          // ⚠️ NULLABLE BUT NOT OPTIONAL — the schema is `.strict()` and
          // `.nullable()`, so an omitted key is a parse ERROR while an explicit
          // null is the correct answer. A scaffold default selects no option.
          selectedOptionOrdinal: null,
          reasonCode: 'clinician_scaffold_default',
          clinicianReviewed: true,
        }),
      );
      applied.add(field.fieldId);
      continue;
    }

    if (field.allowedOptions.length === 0) {
      decline(override.fieldId, 'field_has_no_options');
      continue;
    }
    // ⚠️ RESOLVE BY ORDINAL AGAINST THE CURRENT OPTION SET, AND FAIL CLOSED.
    // If the template has been recompiled and this ordinal no longer exists,
    // the correct answer is to drop the override — NOT to fall back to the
    // stored `optionValue` text. Matching stale text into a renumbered option
    // set is precisely the wrong-cell write this arc has already paid for
    // twice, and the failure would be silent because the render would succeed.
    const option = field.allowedOptions.find(
      (o) => o.ordinal === override.selectedOptionOrdinal,
    );
    if (!option) {
      decline(override.fieldId, 'ordinal_not_in_options');
      continue;
    }
    // ⚠️ THE SECOND LAYER OF THE PLACEHOLDER EXCLUSION, AND IT IS NOT
    // REDUNDANT WITH THE COMPILER'S.
    //
    // `compiler.ts` now strips "Choose an item." from `allowedOptions`, which
    // protects every template compiled from here on. It does NOTHING for a
    // compiled version that ALREADY EXISTS — and the only certified twin in
    // production was compiled 2026-08-17 and carries the placeholder at ordinal
    // 0 on all 28 of its single-selects, measured. Compile-time exclusion alone
    // would therefore have left the one real twin exactly as exposed as before:
    // the fix would have been correct about every template except the one that
    // exists. This check is what covers it, today, without a recompile.
    if (isWordPlaceholderOption(option.displayText)) {
      decline(override.fieldId, 'option_is_placeholder');
      continue;
    }
    const mapping = mappingById.get(override.fieldId);
    if (!mapping?.clinicalConcept) {
      decline(override.fieldId, 'no_approved_concept');
      continue;
    }
    const fact = buildClinicianOverrideFact({
      field,
      mapping,
      optionValue: option.value,
      selectedOptionOrdinal: option.ordinal,
      noteSha256,
      fieldLaterality: lateralityFromLabel(field.originalLabel),
    });
    facts.push(fact);
    byId.set(
      field.fieldId,
      FieldResolutionSchema.parse({
        fieldId: field.fieldId,
        status: 'supported',
        value: option.value,
        sourceFactIds: [fact.factId],
        evidenceAnchorIds: [...fact.evidenceAnchorIds],
        selectedOptionOrdinal: option.ordinal,
        reasonCode: 'clinician_override',
        // THE DORMANT SEAM'S WRITER. `clinicianReviewed` has been `false` at
        // all six construction sites and `true` nowhere since it shipped.
        clinicianReviewed: true,
      }),
    );
    applied.add(field.fieldId);
  }

  return {
    // Preserve ir.fields order — the same stable, renderer-friendly array
    // contract `mergeFieldResolutions` returns.
    resolutions: ir.fields.map((f) => byId.get(f.fieldId)!),
    facts,
    declined,
  };
}

/**
 * Turn declined corrections into manifest issues.
 *
 * ⚠️ `warning`, NEVER `blocking`. A correction that could not be applied is a
 * real loss and the clinician must see it — but blocking would strand the
 * entire document over one control, which is strictly worse than serving the
 * document with the loss named on it.
 */
export function declinedOverrideIssues(
  declined: readonly { fieldId: string; reason: ClinicianOverrideDeclineReason }[],
): { fieldId: string | null; code: string; severity: 'warning'; message: string }[] {
  return declined.map((d) => ({
    // The schema constrains `fieldId` to the `ttf_…` shape; a `fieldId` that is
    // not in this template cannot satisfy it, and `null` is the honest answer
    // rather than a shape-violating string.
    fieldId: /^ttf_[a-f0-9]{24}$/.test(d.fieldId) ? d.fieldId : null,
    code: 'CLINICIAN_OVERRIDE_DECLINED',
    severity: 'warning' as const,
    message:
      `A clinician correction to control ${d.fieldId} was not applied ` +
      `(${d.reason}). The control shows the value the evidence resolver derived.`,
  }));
}
