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
  // ⚠️ ADDED BY THE EIGHTH DIVERGENCE. `conceptScope` is what makes a checkbox
  // unanswerable by one fact, and this view had never named it — so the offer
  // could not have consulted it even if somebody had thought to.
  | 'conceptScope'
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
/**
 * ⚠️ NO MIRROR — RULING #258. THIS TABLE IS THE ONLY COPY OF THE LADDER, AND
 * `resolver/index.ts` WALKS IT RATHER THAN CARRYING ITS OWN.
 *
 * The docblock that stood here said the opposite: *"THIS IS A DELIBERATE MIRROR
 * OF `resolveTemplateFields`' GUARD LADDER, AND SAYING SO IS THE POINT … the
 * mirror is admitted instead, and it is made safe by an instrument rather than
 * by care."* It was admitted honestly, instrumented seriously, and it still
 * shipped **eight** divergences in seven rounds — five in the first cut, a
 * sixth and a seventh found by two independent passes, and an eighth (a
 * `checkbox` whose `conceptScope` covers several symptoms) found by round seven
 * after the matrix had already been widened three times to catch the previous
 * one.
 *
 * ⚠️ **THE INSTRUMENT WAS BEING ASKED TO DO THE JOB THE CODE SHOULD DO.** Every
 * repair widened the matrix so the mirror's CURRENT divergences became visible;
 * none of them made the NEXT divergence impossible. A second implementation of
 * a rule is a defect a test can only ever FIND.
 *
 * ⚠️ AND THE OBVIOUS FIX IS MEASURABLY THE WRONG ONE HERE, WHICH IS WHY THE
 * DEPENDENCY POINTS THIS WAY. The offer cannot import the resolver: this module
 * is value-imported by a `'use client'` component, and `resolver/index.ts`
 * value-imports `ir.ts`, whose ~105 module-scope zod schemas measured **746 →
 * 320,991 bytes** when that mistake was made one function ago (see
 * `field-kind-data-type.ts` for the numbers). So the ladder lives in the LEAF,
 * where both sides can reach it, and the resolver — which already imports
 * `requiresClinicianInput` from here — imports this too.
 *
 * Each row carries the status and reason token the RESOLVER returns at that
 * exit, so there is nothing left for a mirror to get wrong: the offer withholds
 * on exactly the rows the resolver returns on, because they are the same rows.
 */
export interface OmitLadderGuard {
  /** Stable name. This is what the offer withholds under and what
   *  `OMIT_GUARD_TOKEN_PREFIXES` is keyed by. */
  readonly guard: string;
  /** The resolution status the resolver returns at this exit. */
  readonly status: 'needs_clinician_input' | 'not_mentioned';
  /** The resolver's own reason token — not a restatement of it. */
  readonly reasonCode: string;
  readonly test: (field: OmitFieldView, mapping: OmitMappingView) => boolean;
}

/**
 * The exits taken BEFORE the encounter's facts are consulted at all, in the
 * resolver's own order.
 *
 * ⚠️ ORDER IS BEHAVIOUR, NOT PRESENTATION. A field that is both uncertified and
 * unsupported returns whichever guard comes first, and that token reaches the
 * confirm surface. The array is the order.
 */
export const OMIT_LADDER_PRE_CONCEPT: readonly OmitLadderGuard[] = [
  {
    // ⚠️ FOUND BY MEASURING, NOT BY READING, AND IT IS THE SAME VACUITY ONE
    // INPUT OVER. The biconditional was what made the old mirror safe — but its
    // cross-product held `expectedDataType` CONSTANT, so it could not see a
    // guard that only fires when the type disagrees. The arm written to stop a
    // matrix pinning the bug repeated the shape at the next input.
    // Reproduced: a `checkbox` field mapped `expectedDataType: 'number'` gave
    // `canOmitWhenUnmentioned === true` while the resolver returned
    // `needs_clinician_input / semantic_mapping_type_mismatch`.
    //
    // The comparison is not restated — `expectedDataTypeForFieldKind` is
    // imported. It was MOVED to `field-kind-data-type.ts` for this: importing it
    // from `semantic-mapping/index.ts` would drag `@meddoc/ai` into the client
    // bundle, and importing it from `ir.ts` dragged zod.
    guard: 'semantic_mapping_type_mismatch',
    status: 'needs_clinician_input',
    reasonCode: 'semantic_mapping_type_mismatch',
    test: (field, mapping) =>
      expectedDataTypeForFieldKind(field.kind) !== mapping.expectedDataType,
  },
  {
    guard: 'field_or_mapping_unsupported',
    status: 'needs_clinician_input',
    reasonCode: 'field_or_mapping_unsupported',
    test: (field, mapping) =>
      mapping.status === 'unsupported' || field.detectionStatus === 'unsupported',
  },
  {
    // A MANUAL field carries no concept BY CONSTRUCTION — nothing in any
    // encounter can say who the technologist on shift was — and the certificate
    // attests that it renders blank. Reporting it as an unmapped field turned a
    // designed state into a configuration error, and at visit time that error is
    // BLOCKING: four such fields refused the native document on every visit,
    // forever, and the export fell back to the styled path. Nothing was made
    // safer by that — the fields are blank in both documents — so the only
    // effect was that the doctor never got their own form back.
    guard: 'manual_source_not_filled',
    status: 'not_mentioned',
    reasonCode: 'manual_source_not_filled',
    test: (_field, mapping) => mapping.sourceType === 'manual',
  },
  {
    // A VERIFIED NOTE SELECTION is answered by the adopted note's own pick, which
    // only the picks bridge can read. Resolving it here from raw facts produced
    // `select_value_not_exact_option` — needs-clinician-input, and BLOCKING at
    // visit time — for fourteen dropdowns the note had already answered. Same
    // shape as the fixed-grid rule: the component that can address it, addresses
    // it; the baseline is honestly blank.
    guard: 'awaiting_note_selection',
    status: 'not_mentioned',
    reasonCode: 'awaiting_note_selection',
    test: (_field, mapping) => mapping.sourceType === 'verified_note_selection',
  },
  {
    guard: 'clinical_concept_unmapped',
    status: 'needs_clinician_input',
    reasonCode: 'clinical_concept_unmapped',
    test: (_field, mapping) => !mapping.clinicalConcept,
  },
];

/**
 * The resolver's certification guard runs immediately AFTER this row.
 *
 * ⚠️ IT CANNOT LIVE IN THE TABLE AND ITS POSITION IS STILL BEHAVIOUR. It reads
 * `allowUncertifiedForSyntheticTest` and the caller's certified-field set —
 * neither knowable from `(field, mapping)` — so it stays inline in the resolver.
 * But a field that is both uncertified and unsupported returns
 * `field_or_mapping_not_certified` only because the certification check comes
 * first, so the resolver names its insertion point rather than leaving it to
 * whoever next edits the loop.
 */
export const OMIT_LADDER_CERTIFICATION_GUARD_FOLLOWS = 'semantic_mapping_type_mismatch';

/**
 * ⚠️ AND IT FAILS **CLOSED**, AT MODULE LOAD, BECAUSE THE ALTERNATIVE FAILS
 * OPEN ON A CLINICAL GATE.
 *
 * The resolver runs its certification check inside the table walk, gated on
 * `guard.guard === OMIT_LADDER_CERTIFICATION_GUARD_FOLLOWS`. If that string
 * ever stops naming a row — a guard renamed, the row deleted, this constant
 * edited — the `if` simply never matches and **the certification check is
 * skipped entirely**, with no error and no red. An uncertified mapping would
 * then fall through to the facts and resolve as though it had been confirmed.
 *
 * ⚠️ NO MATRIX ROW CAN CATCH IT, WHICH IS WHY THE CHECK IS HERE AND NOT THERE.
 * Every row of the biconditional passes `allowUncertifiedForSyntheticTest`, so
 * the guarded branch never executes in the arm that exists to compare the two
 * sides. A test-only assertion would also leave PRODUCTION unprotected; this
 * one is a pure function of two constants in this file, so it either always
 * throws or never does — it cannot surprise a doctor at runtime, and it stops
 * the build the moment the anchor stops resolving.
 */
if (!OMIT_LADDER_PRE_CONCEPT.some((g) => g.guard === OMIT_LADDER_CERTIFICATION_GUARD_FOLLOWS)) {
  throw new Error(
    `unmentioned-policy: OMIT_LADDER_CERTIFICATION_GUARD_FOLLOWS names ` +
      `'${OMIT_LADDER_CERTIFICATION_GUARD_FOLLOWS}', which is not a row of ` +
      `OMIT_LADDER_PRE_CONCEPT. The resolver's certification check hangs off ` +
      `that name and would be SKIPPED — an uncertified mapping would resolve ` +
      `as though it had been confirmed.`,
  );
}

/** Reached inside `missingResolution`, ahead of the policy. */
const PRACTICE_DEFAULT_GUARD = 'approved_practice_default';
/** `missingResolution`'s own short-circuit. */
const REQUIRES_INPUT_GUARD = 'required_fact_not_mentioned';
/** The `missingResolution` CALL SITES, in the order the resolver reaches them. */
export const OMIT_DEFERRAL_GUARDS = [
  'multi_concept_checkbox_deferred',
  'fixed_grid_cell_deferred',
] as const;
/** The offer's own narrowings — not shared with the resolver. */
export const OMIT_NARROWING_GUARDS = ['row_prototype_not_offerable'] as const;

/**
 * The exits reached only once some fact DOES carry this field's concept — the
 * `missingResolution` CALL SITES, as opposed to the guards above it.
 *
 * ⚠️ THIS IS WHERE THE SEVENTH AND EIGHTH DIVERGENCES BOTH LIVED, AND WHY THE
 * OLD MIRROR COULD NOT SEE EITHER: it was built by walking the guard LADDER, and
 * these are not guards in that ladder — they are different call sites of the
 * same function. `resolver/index.ts` says it plainly at the one site that earns
 * #191's kept default: *"The three other `missingResolution` sites are DEFERRALS
 * with facts in hand."* Three of the four cannot honour an omit, and the mirror
 * had walked past all of them.
 *
 * The resolver now calls THIS, so a fourth deferral cannot be added without the
 * offer learning about it in the same edit.
 *
 * ⚠️ EVERY EXIT HERE IS A CONSERVATIVE WITHHOLD, NAMED AS ONE. A visit where
 * NOTHING carrying this concept was dictated reaches the omit branch by the
 * other route and IS honoured — so withholding costs that narrow case. It is
 * withdrawn anyway, on the rule the fixed grid earned: a control whose promise
 * holds only on visits where the doctor dictated nothing about the field is not
 * one they can reason about, and the hint says flatly "this only stops it being
 * counted as an unanswered blank".
 */
export function omitDeferralGuard(
  field: OmitFieldView,
  mapping: OmitMappingView,
): string | null {
  // ⚠️ #179(5) — A CHECKBOX ANSWERS FOR EXACTLY ONE SYMPTOM. `resolver/index.ts`
  // refuses a multi-scope tick because "affirmed" is ambiguous between the
  // symptoms the scope covers, and routes to `missingResolution` WITHOUT
  // `conceptUnmatched`. THE EIGHTH DIVERGENCE: the old mirror had no clause for
  // it, so the control was offered on a box the resolver will not honour the
  // moment anything in scope is dictated.
  if (
    field.kind === 'checkbox' &&
    (mapping.conceptScope?.length ?? 0) > 1
  ) {
    return OMIT_DEFERRAL_GUARDS[0];
  }
  // A FIXED-GRID TABLE CELL IS ADDRESSED BY ITS ROW, AND THE RESOLVER CANNOT SEE
  // ROWS. In a 26-row vein grid every reflux cell shares one concept, so a single
  // dictated reflux time makes the candidate set non-empty for ALL 26 and sends
  // every one of them here.
  //
  // ⚠️ MEASURED ON THE LIVE PRODUCTION TEMPLATE, and the ordinary case is the bad
  // one: 20 ticked cells, **0 of 20 honoured**. Change only the fact's concept
  // and it is 20 of 20.
  //
  // ⚠️ `rowPrototype !== true` IS BACK, AND IT IS THE RESOLVER'S CLAUSE, NOT THE
  // OFFER'S. When this lived only in the offer it was deleted as dead — #234's
  // prototype narrowing returned first, so it could never be reached. But the
  // RESOLVER carries the same condition for an unrelated reason (a prototype
  // expands one row per fact, so it HAS a row to address and keeps resolving),
  // and this function is now the resolver's copy. Deleting it here would defer
  // every prototype at visit time. The narrowing is a separate function below.
  if (
    field.rendererBinding?.bindingType === 'table_cell' &&
    field.rowPrototype !== true
  ) {
    return OMIT_DEFERRAL_GUARDS[1];
  }
  return null;
}

/**
 * The one narrowing that is the OFFER'S OWN and is not shared with the resolver.
 *
 * ⚠️ SEPARATED FROM `omitDeferralGuard` DELIBERATELY, AND THE SEPARATION IS THE
 * WHOLE POINT OF RULING #258's SHAPE. Everything else this module decides, the
 * resolver decides too — that is why there is one copy. This clause the resolver
 * must NOT apply: it keeps resolving prototypes, and honours their omit. So it
 * lives alone, is called only by the offer, and carries its own behavioural
 * control — because a hand-written rule with no second reader is exactly the
 * thing the rest of this file just stopped being.
 */
export function omitProductNarrowing(field: OmitFieldView): string | null {
  // ⚠️ A REPEATING-SECTION PROTOTYPE IS NEVER OFFERED — RULING #234, WHICH IS
  // #192's RULE ARRIVING ONE SURFACE LATER.
  //
  // #192 says a prototype must not clone its text into every row. That bound the
  // KEEP; it binds the OFFER for the same reason. A prototype is not a field a
  // clinician answers — it is the TEMPLATE the rows are stamped from, so a
  // judgement recorded against it is a judgement recorded against every row that
  // will ever be generated from it, including rows that do not exist yet and
  // that the doctor has therefore never seen.
  //
  // ⚠️ IT IS THE ONE ROW THE RESOLVER DOES **NOT** SHARE, AND THAT IS DELIBERATE.
  // A prototype DOES reach the omit branch and the resolver DOES honour it. This
  // is a PRODUCT narrowing, not a mirror of resolver behaviour, so it is the one
  // clause here that must stay hand-written — and it carries its own behavioural
  // control for exactly that reason.
  //
  // ⚠️ THIS GUARD EXISTS BECAUSE ITS ABSENCE WAS DECLARED RATHER THAN MEASURED.
  // Ruling #227's allowlist carried `rowPrototype: 'prototypes never offer'` — a
  // claim nobody checked, and false: a prototype was offered under BOTH binding
  // types. The declaration bought a 37/37 green over a planted
  // offered-but-not-honoured lie. #234's cure is to VARY the dimension and
  // assert the property, never to re-word the claim.
  if (field.rowPrototype === true) {
    return OMIT_NARROWING_GUARDS[0];
  }
  return null;
}

/**
 * TRUE when an approved practice default answers this field before the policy is
 * ever read.
 *
 * ⚠️ ONE PROPERTY, ONE READER — `practiceDefaultResolution` calls this as its
 * own first statement. It is the FIRST statement of `missingResolution`, ahead
 * of the policy entirely, so a field carrying one cannot reach the omit branch
 * and must not be offered it. Ruling #194(a) is separately reducing the CLINICAL
 * half of this path (T11).
 *
 * The resolver additionally requires `status === 'certified'`, which is
 * unreachable-by-construction in production (an uncertified mapping exits at the
 * certification guard far above) and matters only on the synthetic-test path. It
 * is deliberately NOT in this predicate: at confirm time the mapping is being
 * certified, so gating on a status it does not have yet would offer a control
 * that stops working the moment the doctor certifies.
 */
export function practiceDefaultPreempts<T extends OmitMappingView>(
  mapping: T,
): mapping is T & { practiceDefault: string } {
  return mapping.practiceDefault !== null;
}

/**
 * The reason the RESOLVER would decline to honour an `omit` on this field — or
 * `null` when the omit branch is genuinely reachable.
 *
 * ⚠️ THIS FUNCTION NO LONGER DECIDES ANYTHING. It composes the table and the two
 * predicates above, all three of which the resolver itself walks, so there is no
 * longer a second opinion for it to hold. Ruling #258.
 *
 * ⚠️ AND THE ORIGINAL SHIPPED WITH ONLY ONE OF THESE. The first cut negated
 * `requiresClinicianInput` alone, which is evaluated INSIDE `missingResolution` —
 * five guards further down than the offer needed to look. The control was
 * therefore offered on `manual` fields (the surface labels them "filled by hand
 * each visit" one line above), on `verified_note_selection` fields, on fields
 * showing "· no concept yet", on unsupported fields, and on fields already
 * carrying an `approved_practice_default`. In every one of those the resolver
 * returns before the policy is read, so the doctor ticks "do not ask me about
 * this again", pays a forced re-certification because the mapping hash moves, and
 * is asked again on every visit forever.
 */
export function omitBranchUnreachable(
  field: OmitFieldView,
  mapping: OmitMappingView,
): string | null {
  for (const guard of OMIT_LADDER_PRE_CONCEPT) {
    if (guard.test(field, mapping)) return guard.guard;
  }
  if (practiceDefaultPreempts(mapping)) return PRACTICE_DEFAULT_GUARD;
  // ⚠️ ORDERED **AFTER** THE PRE-CONCEPT TABLE AND BEFORE THE DEFERRALS, AND THE
  // MATRIX CAUGHT THE MIS-ORDER. Placing it after produced
  // `fixed_grid_cell_deferred` for a grid cell that also requires input, while
  // the resolver returned `required_fact_not_mentioned` — the offer refusing for
  // the RIGHT field on the WRONG grounds, which the token arm exists to catch.
  // `requiresClinicianInput` is evaluated INSIDE `missingResolution`, so it wins
  // whichever call site arrived there.
  if (requiresClinicianInput(field, mapping)) return REQUIRES_INPUT_GUARD;
  return omitProductNarrowing(field) ?? omitDeferralGuard(field, mapping);
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
 * Every guard name `omitBranchUnreachable` can return, DERIVED from the table
 * and the constants the clauses actually return.
 *
 * ⚠️ IT IS DERIVED SO THE GATE CANNOT BE SATISFIED BY A LIST. The arm that used
 * to check this regexed `return '(\w+)'` out of this file's SOURCE — which
 * worked until ruling #258 turned the ladder into a table walk, at which point
 * it found nothing and would have gone quietly vacuous had the declaration
 * check not failed loudly first. A name here is the one the code returns,
 * because it IS the one the code returns.
 */
export const OMIT_GUARD_NAMES: readonly string[] = [
  ...OMIT_LADDER_PRE_CONCEPT.map((guard) => guard.guard),
  PRACTICE_DEFAULT_GUARD,
  REQUIRES_INPUT_GUARD,
  ...OMIT_NARROWING_GUARDS,
  ...OMIT_DEFERRAL_GUARDS,
];

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
  // ⚠️ THE EIGHTH GUARD. Same family as the fixed grid: the resolver routes a
  // multi-scope checkbox to `missingResolution` with facts in hand, so the token
  // is whatever that call returns — `required_fact_not_mentioned` when the field
  // requires input, `fact_not_mentioned` otherwise.
  multi_concept_checkbox_deferred: ['fact_not_mentioned', 'required_fact_not_mentioned'],
  // ⚠️ A CONSERVATIVE WITHHOLD, so the token is what the resolver WOULD have
  // emitted had the control been offered and ticked — measured, not assumed:
  // a prototype reaches the omit branch and is honoured.
  row_prototype_not_offerable: ['omitted_unsupported_default'],
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
