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

/** One clinician correction, as stored. The ORDINAL is the value — see below. */
export interface ClinicianFieldOverride {
  fieldId: string;
  selectedOptionOrdinal: number;
}

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
  | 'no_approved_concept';

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
