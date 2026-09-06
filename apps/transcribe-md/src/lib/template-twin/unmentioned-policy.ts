// ============================================================================
// UNMENTIONED POLICY — the ONE predicate that decides whether `omit` can fire.
// ----------------------------------------------------------------------------
// ⚠️ THIS FILE EXISTS SO THE OFFER AND THE HONOURING CANNOT DRIFT, and that is
// its whole justification. The resolver decides whether a doctor's `omit` is
// honoured; the confirm surface decides whether to OFFER it. Those are the same
// question asked from two sides, and a UI that re-derives the answer is a
// second copy of a rule — the shape that ships a control which looks like it
// works and silently does nothing.
//
// ⚠️ AND THE SILENT-NO-OP IS THE MEASURED FAILURE MODE HERE, NOT A THEORETICAL
// ONE. REVIEW-DEFAULTS item 1's adversarial pass found exactly this class one
// layer over: a control offered on a field kind the writer declines, which
// returned `ok: true` and wrote an audit row for an insert that could never
// happen. A doctor who ticks "do not ask me about this again" and is asked
// again every visit has been told something false by the interface.
//
// ⚠️ NO RUNTIME IMPORTS — TYPES ONLY. The confirm surface is a `'use client'`
// component. `import type` is erased at compile time, so naming the IR types
// here costs the client bundle nothing, while a value import from the resolver
// would pull Prisma and the extraction engine into the browser graph. Same
// boundary, and the same reasoning, as `lib/practice-roles.ts`.
// ============================================================================

import type { SemanticMapping, TemplateField } from './ir';

/** The field/mapping shape the reachability test reads. Narrow on purpose. */
export type OmitFieldView = Pick<TemplateField, 'required' | 'unknownPolicy' | 'detectionStatus'>;
export type OmitMappingView = Pick<
  SemanticMapping,
  'required' | 'unknownPolicy' | 'blankPolicy' | 'status' | 'sourceType' | 'clinicalConcept' | 'practiceDefault'
>;

/**
 * TRUE when the field must be put to the clinician rather than left blank.
 *
 * ⚠️ THIS IS THE RESOLVER'S OWN PREDICATE, LIFTED — not a re-statement of it.
 * `missingResolution` in `resolver/index.ts` imports this function; there is no
 * second copy to fall out of step. If a sixth input is ever added, it is added
 * HERE and both sides get it in the same commit.
 *
 * Five inputs, and every one of them is known at CONFIRM time — which is what
 * makes the offer decidable before a single visit exists.
 */
export function requiresClinicianInput(
  field: Pick<TemplateField, 'required' | 'unknownPolicy'>,
  mapping: Pick<SemanticMapping, 'required' | 'unknownPolicy' | 'blankPolicy'>,
): boolean {
  return (
    field.required ||
    mapping.required ||
    field.unknownPolicy === 'requires_input' ||
    mapping.unknownPolicy === 'requires_input' ||
    mapping.blankPolicy === 'requires_input'
  );
}

/**
 * The reason token the RESOLVER would return for this field before the `omit`
 * branch is ever consulted — or `null` when the branch is genuinely reachable.
 *
 * ⚠️ THIS IS A DELIBERATE MIRROR OF `resolveTemplateFields`' GUARD LADDER, AND
 * SAYING SO IS THE POINT. `requiresClinicianInput` above is a genuine single
 * copy — the resolver imports it. This one cannot be: each of the resolver's
 * guards returns a DIFFERENT resolution with its own long-standing rationale,
 * so collapsing them into one predicate would restructure a clinical path to
 * serve a settings screen. The mirror is admitted instead, and it is made safe
 * by an instrument rather than by care:
 * `gate-review-defaults-omit-door` drives the REAL resolver over the full
 * cross-product of these inputs and asserts a BICONDITIONAL —
 * `canOmitWhenUnmentioned(f, m)` is true exactly when the resolver emits
 * `omitted_unsupported_default` — and asserts this function names the SAME
 * token the resolver actually returned. A mirror nobody checks is a second
 * source of truth; a mirror a matrix checks is a cache.
 *
 * ⚠️ AND THE ORIGINAL SHIPPED WITH ONLY ONE OF THESE. The first cut negated
 * `requiresClinicianInput` alone, which is evaluated INSIDE `missingResolution`
 * — five guards further down than the offer needed to look. The control was
 * therefore offered on `manual` fields (the surface labels them "filled by hand
 * each visit" one line above), on `verified_note_selection` fields, on fields
 * showing "· no concept yet", on unsupported fields, and on fields already
 * carrying an `approved_practice_default`. In every one of those the resolver
 * returns before the policy is read, so the doctor ticks "do not ask me about
 * this again", pays a forced re-certification because the mapping hash moves,
 * and is asked again on every visit forever.
 *
 * Every clause below is knowable at CONFIRM time, which is what makes the offer
 * decidable before a visit exists. Each names the resolver line it mirrors.
 */
export function omitBranchUnreachable(
  field: OmitFieldView,
  mapping: OmitMappingView,
): string | null {
  // resolver: `mapping.status === 'unsupported' || field.detectionStatus === 'unsupported'`
  if (mapping.status === 'unsupported' || field.detectionStatus === 'unsupported') {
    return 'field_or_mapping_unsupported';
  }
  // resolver: `mapping.sourceType === 'manual'` — carries no concept BY
  // CONSTRUCTION and the certificate attests that it renders blank.
  if (mapping.sourceType === 'manual') return 'manual_source_not_filled';
  // resolver: `mapping.sourceType === 'verified_note_selection'` — answered by
  // the adopted note's own pick, which only the picks bridge can read.
  if (mapping.sourceType === 'verified_note_selection') return 'awaiting_note_selection';
  // resolver: `!mapping.clinicalConcept`
  if (!mapping.clinicalConcept) return 'clinical_concept_unmapped';
  // `practiceDefaultResolution` is the FIRST statement of `missingResolution`,
  // ahead of the policy entirely. ⚠️ Gated on `status === 'certified'` there, and
  // an uncertified mapping is unreachable at visit time anyway — so the honest
  // confirm-time test is simply "a default is set". Ruling #194(a) is separately
  // reducing the CLINICAL half of this path (T11); until it lands, a field
  // carrying one cannot reach the omit branch and must not be offered it.
  if (mapping.practiceDefault !== null) return 'approved_practice_default';
  // `missingResolution`'s own short-circuit, the one clause that was here first.
  if (requiresClinicianInput(field, mapping)) return 'required_fact_not_mentioned';
  return null;
}

/**
 * TRUE when `unmentionedPolicy: 'omit'` on this field could ever change what
 * the doctor is told.
 *
 * ⚠️ WHAT THIS DOES **NOT** GATE ON, and the distinction is the honest one:
 * the resolver also requires `conceptUnmatched && reason === undefined &&
 * facts.length > 0` — all three are properties of a PARTICULAR VISIT and are
 * unknowable at confirm time. So this predicate answers *"can this choice ever
 * matter?"* and never *"will it fire on the next visit?"*. Offering the control
 * where the answer to the first is NO is a lie; declining to offer it because
 * the second is unknowable would ship nothing at all.
 */
export function canOmitWhenUnmentioned(
  field: OmitFieldView,
  mapping: OmitMappingView,
): boolean {
  return omitBranchUnreachable(field, mapping) === null;
}

/**
 * The resolver reason tokens each guard above can actually emit, as PREFIXES.
 *
 * ⚠️ IT IS EXPORTED SO THE GATE COMPARES AGAINST A DECLARATION RATHER THAN A
 * LIST A TEST INVENTED. A test that writes its own expected tokens is a third
 * copy of the rule, and it agrees with whichever copy its author read last.
 *
 * ⚠️ AND ONE GUARD HAS THREE EXITS, WHICH IS WHY THIS IS PREFIXES AND NOT
 * VALUES. `practiceDefaultResolution` returns `approved_practice_default` on
 * success, `approved_practice_default_evidence_missing` when the synthetic fact
 * is absent, and `invalid_practice_default_<code>` when the stored default will
 * not convert. Naming any single one of those would have been a guess — and the
 * first draft of this file guessed, naming `approved_practice_default` while the
 * resolver returned `..._evidence_missing`. The matrix arm caught it before a
 * line of it shipped, which is the entire argument for comparing the TOKEN and
 * not only the boolean.
 */
export const OMIT_GUARD_TOKEN_PREFIXES: Readonly<Record<string, readonly string[]>> = {
  field_or_mapping_unsupported: ['field_or_mapping_unsupported'],
  manual_source_not_filled: ['manual_source_not_filled'],
  awaiting_note_selection: ['awaiting_note_selection'],
  clinical_concept_unmapped: ['clinical_concept_unmapped'],
  approved_practice_default: ['approved_practice_default', 'invalid_practice_default_'],
  required_fact_not_mentioned: ['required_fact_not_mentioned'],
};

export const OMIT_CONTROL_LABEL = 'Expected blank — do not ask me about this';

/** The one-line explanation shown under the control. */
export const OMIT_CONTROL_HINT =
  'The line still clears when nothing is dictated. This only stops it being counted as an unanswered blank.';
