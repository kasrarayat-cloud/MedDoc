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
// ⚠️ ONE RUNTIME IMPORT, AND IT IS A LEAF WITH NO VALUE IMPORTS OF ITS OWN. The confirm surface is a `'use client'`
// component. `import type` is erased at compile time, so naming the IR types
// here costs the client bundle nothing, while a value import from the resolver
// would pull Prisma and the extraction engine into the browser graph. Same
// boundary, and the same reasoning, as `lib/practice-roles.ts`.
// ============================================================================

// ⚠️ FROM THE LEAF, NOT FROM `./ir`. `ir.ts` value-imports zod and builds ~105
// schemas at module scope; importing the switch from there put 320,991 bytes
// of zod into this client-imported module — 429x — while the header below
// still promised the opposite. See `field-kind-data-type.ts` for the numbers.
import { expectedDataTypeForFieldKind } from './field-kind-data-type';
import type { SemanticMapping, TemplateField } from './ir';

/** The field/mapping shape the reachability test reads. Narrow on purpose. */
export type OmitFieldView = Pick<
  TemplateField,
  'required' | 'unknownPolicy' | 'detectionStatus' | 'kind' | 'rowPrototype'
> & { rendererBinding?: { bindingType?: string } | null };
export type OmitMappingView = Pick<
  SemanticMapping,
  | 'required'
  | 'unknownPolicy'
  | 'blankPolicy'
  | 'status'
  | 'sourceType'
  | 'clinicalConcept'
  | 'practiceDefault'
  | 'expectedDataType'
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
  // resolver: `!isMappingTypeCompatible(field, mapping)` — the FIRST guard of
  // the ladder, and the one the mirror shipped without.
  //
  // ⚠️ FOUND BY MEASURING, NOT BY READING, AND IT IS THE SAME VACUITY ONE INPUT
  // OVER. The biconditional below is what makes this mirror safe — but its
  // cross-product held `expectedDataType` CONSTANT, so it could not see a guard
  // that only fires when the type disagrees. The arm that was written to stop a
  // matrix from pinning the bug repeated the shape at the next input.
  // Reproduced: a `checkbox` field mapped `expectedDataType: 'number'` gave
  // `canOmitWhenUnmentioned === true` while the resolver returned
  // `needs_clinician_input / semantic_mapping_type_mismatch`. The matrix now
  // varies compatibility, so this cannot recur silently.
  //
  // The comparison is not restated here — `expectedDataTypeForFieldKind` is
  // imported. It was MOVED to `ir.ts` for this: importing it from
  // `semantic-mapping/index.ts` would drag `@meddoc/ai` into the client bundle.
  if (expectedDataTypeForFieldKind(field.kind) !== mapping.expectedDataType) {
    return 'semantic_mapping_type_mismatch';
  }
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
  // ⚠️ ORDERED **AFTER** requires-input, AND THE MATRIX CAUGHT THE MIS-ORDER.
  // Placing it before produced `fixed_grid_cell_deferred` for a grid cell that
  // also requires input, while the resolver returned
  // `required_fact_not_mentioned` — the mirror refusing for the RIGHT field on
  // the WRONG grounds, which the token arm exists to catch. requires-input is
  // evaluated INSIDE `missingResolution`, so it wins whichever call site
  // arrived there.
  // ⚠️ THE FIXED GRID — AND THIS IS THE **SEVENTH** GUARD, FOUND BY A PEER
  // SESSION'S INDEPENDENT PASS AFTER I HAD ALREADY FOUND THE SIXTH.
  //
  // `resolver/index.ts:503` routes a fixed-grid `table_cell` to
  // `missingResolution` WITHOUT `conceptUnmatched`, so `unmentionedScaffold` is
  // false and the policy is never read. It is not one of the guards ABOVE — it
  // is a different CALL SITE of the same function, and the mirror was built by
  // walking the guard ladder rather than the call sites. `:475`'s own comment
  // says it plainly: *"The three other `missingResolution` sites are DEFERRALS
  // with facts in hand."* Three of the four cannot honour an omit.
  //
  // ⚠️ MEASURED ON THE LIVE PRODUCTION TEMPLATE, and the ordinary case is the
  // bad one: every cell of the venous grid shares ONE concept
  // (`measurement.reflux_time` x26, `measurement.diameter` x26), so a single
  // dictated reflux time makes `conceptCandidates` non-empty for ALL 52 and
  // sends every one of them to `:503`. Reported: 20 ticked cells, **0 of 20
  // honoured**. Change only the fact's concept and it is 20 of 20.
  //
  // ⚠️ THE ACCEPTED LOSS, NAMED. A grid cell on a visit where NOTHING in the
  // grid was dictated *does* reach the omit branch via `:475`, so withdrawing
  // the offer costs that narrow case. It is withdrawn anyway: a control whose
  // promise holds only on visits where the doctor dictated nothing in the grid
  // is not one they can reason about, and the hint says flatly "this only stops
  // it being counted as an unanswered blank". Better no control than a control
  // that is false on the ordinary visit.
  if (field.rendererBinding?.bindingType === 'table_cell' && field.rowPrototype !== true) {
    return 'fixed_grid_cell_deferred';
  }
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
  semantic_mapping_type_mismatch: ['semantic_mapping_type_mismatch'],
  // A deferred grid cell can surface under several reason tokens depending on
  // what the row-level resolver later does with it, so the family is listed
  // rather than a single token.
  fixed_grid_cell_deferred: ['fact_not_mentioned', 'table_', 'row_', 'measurement_'],
  field_or_mapping_unsupported: ['field_or_mapping_unsupported'],
  manual_source_not_filled: ['manual_source_not_filled'],
  awaiting_note_selection: ['awaiting_note_selection'],
  clinical_concept_unmapped: ['clinical_concept_unmapped'],
  approved_practice_default: ['approved_practice_default', 'invalid_practice_default_'],
  required_fact_not_mentioned: ['required_fact_not_mentioned'],
};

export const OMIT_CONTROL_LABEL = 'Expected blank — do not ask me about this';

/**
 * What a stored `omit` is called when the resolver could never read it.
 *
 * ⚠️ THIS EXISTS SO A CERTIFIED VERSION CANNOT LIE. The writer refuses to
 * persist an unreachable `omit`, so this should never render — but "should
 * never" is a claim about today's writers, and a certified version is immutable
 * for the life of the template. If one ever appears, the surface names it
 * rather than repeating the doctor-facing promise the resolver will not keep.
 */
export const OMIT_INERT_LABEL =
  'Marked expected-blank, but this field is answered before that setting is read — it has no effect here';

/** The one-line explanation shown under the control. */
export const OMIT_CONTROL_HINT =
  'The line still clears when nothing is dictated. This only stops it being counted as an unanswered blank.';
