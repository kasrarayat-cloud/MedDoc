// ============================================================================
// Template Twin — THE DENIAL CONTRACT.  Owner ruling #157(d), FINAL.
// ----------------------------------------------------------------------------
// ONE MODULE, EVERY READER. The resolver WRITES a denial, the validator
// RE-DERIVES it, the renderer decides whether the pair may be PRINTED, and the
// certification gate asks whether a withheld denial is fit to certify. Four
// call sites, one implementation — because a second copy of this logic drifts
// from the first the day either is fixed, and the thing that drifts is what
// reaches a signed clinical document.
//
// ⚠️ RULE (1), FINAL: A DENIED NARRATIVE FACT ALWAYS RENDERS BLANK, CARRYING
// ITS REASON TOKEN. NO TEXT HEURISTIC EVER DECIDES WHAT PRINTS ON A CLINICAL
// DOCUMENT.
//
// ⚠️ THE MACHINERY IS DELETED, NOT GATED — AND THAT IS THE RULING, NOT A
// TIDY-UP. A rule that still CONTAINS the predicate keeps the failure mode
// alive behind a narrower gate, and the next reader repairs the machinery
// rather than questioning it. There is therefore no self-negation predicate,
// no negation vocabulary, no clause-scoping, no heading strip, and no
// `dictatedDenialText` in this file to repair.
//
// ⚠️ THE ARC IS RECORDED BECAUSE THE CORRECTION IS THE POINT. One rule — what
// should a clinical document print for a DENIED fact — was formulated three
// times, and each formulation was falsified BY MEASUREMENT, not by review:
//
//   #157     print the fact VALUE verbatim.
//            FALSE: `projectEncounterFacts` puts the AFFIRMED ENTITY in
//            `fact.value`. "The patient has no history of diabetes." carries
//            value "Diabetes", and #157 would have printed that word into a
//            signed past-medical-history section with `valid: true`.
//
//   #157(b)  print the evidence QUOTE verbatim.
//            FALSE: L3 states polarity as a REQUIRED enum and a stated
//            polarity BYPASSES the denial vocabulary entirely
//            (`options.polarity ?? inferPolarity(…)`), so a fact can be
//            `denied` on a quote carrying no negation at all. A ROS finding
//            "Fever" denied on the quote "Fever, chills, and night sweats."
//            PRINTED THAT SENTENCE, valid=true, verified=true, zero issues.
//
//   #157(c)  print the quote when the quote SELF-NEGATES.
//            FALSE: a comma defeats the scoping. `past_medical_history`,
//            value "Hypertension", quote
//            "No history of diabetes, hypertension is well established."
//            renders THAT SENTENCE under a DENIED fact, valid=true, zero
//            issues — because the cue and the finding share one comma-joined
//            clause. And the predicate scoped the cue to ONE clause while the
//            printer printed EVERY clause, so
//            "Denies chest pain at rest. Chest pain on exertion, 8 out of 10."
//            SATISFIED BOTH GATE PROPERTIES AT ONCE — the printed text was a
//            subset of the doctor's quote AND contained a negation cue — and
//            reached the document whole.
//
// Each fix was correct. Each moved the failure one layer down. The gate was
// GREEN with the harm live every single time. A deterministic heuristic doing
// SEMANTICS always has a next counterexample, and the honest response is not a
// better predicate — it is to stop asking the question. The fail-closed answer
// IS the rule.
//
// ⚠️ THE CONCEDED COST IS DELIBERATE AND IT IS PINNED IN THE GATE. Fourteen
// realistic clinical denials that #157(b) would have printed now blank —
// "Patient is afebrile.", "Lungs are clear to auscultation bilaterally.",
// "NKDA.", "Family history non-contributory.", and the rest. They are recorded
// as a KNOWN AND ACCEPTED LOSS in the gate's conceded-loss arm rather than left
// for a future reader to rediscover as a regression. A blank is a VISIBLE
// ABSENCE; an inverted sentence is a SIGNED ASSERTION. The two errors are not
// symmetric, and after three falsifications the asymmetry is the whole design.
//
// ⚠️ WHAT A DENIAL MAY STILL DO, unchanged by this ruling:
//   · a CHECKBOX resolves `false` and renders unchecked. It is the one control
//     whose blank state IS the denial, and nothing here touches it.
//   · a MIXED-POLARITY narrative still renders: the AFFIRMED facts print by the
//     NORMAL path in DICTATION ORDER, and the denied facts contribute NOTHING
//     but the resolution's reason token (#157(c) Q3's document-killer fix,
//     which stands).
//
// ⚠️ EVERY OTHER OUTCOME IS A BLANK CARRYING A NAMED REASON — NEVER A REFUSED
// EXPORT. Rule (3): a denial must not be able to kill a document. Before this
// module, ONE denied sentence in an accumulating narrative section took the
// whole document down (`multiple_distinct_supported_values` -> FIELD_CONFLICT ->
// blocking -> VALIDATION_REQUIRED), and a `value_only` denial did the same
// through FIELD_AMBIGUOUS. Silence is illegal at the MANIFEST level; it is
// never bought at the document's expense.
// ============================================================================

import type {
  EncounterFact,
  FieldResolution,
  SemanticMapping,
  TemplateField,
} from './ir';

import {
  deriveFieldValueFromFact,
  isListValuedNarrative,
  NARRATIVE_LIST_SEPARATOR,
} from './field-value-derivation';

/** The status a withheld denial carries. Blank, cited, and named. */
export const DENIAL_WITHHELD = 'denial_withheld' as const;

/**
 * ⚠️ RULING #157(d) RULE (1) — THE REASON A NARRATIVE DENIAL IS BLANK.
 *
 * Unconditional, on every `polarityBehavior`, for every narrative shape. It
 * replaces the six tokens #157(b)/(c) needed to describe WHY a particular
 * quote could not be printed — provenance, empty-after-strip, unrenderable,
 * multiple distinct quotes, not-self-negating, no-cited-denial. None of those
 * questions is asked any more, so none of those tokens can be emitted.
 *
 * ⚠️ IT IS CERTIFICATION-EXEMPT BECAUSE IT IS RULED BEHAVIOUR, NOT A BROKEN
 * FILL. A template whose narrative section blanks on a denial is doing exactly
 * what #157(d) orders. Blocking on it would recreate the Q2 defect — a correct
 * blank that cannot certify — one ruling later, which is the specific mistake
 * this programme keeps making and this line refuses to repeat.
 */
export const DENIAL_WITHHELD_NARRATIVE_ALWAYS_BLANK =
  'denial_withheld_narrative_always_blank';

// ══ RULING #157(d) — THE Q1 HEURISTIC IS GONE. ═══════════════════════════════
//
// This is where `SELF_NEGATION_VOCABULARY`, `selfNegationCues`,
// `clauseBoundsAround`, `locateFinding`, `selfNegationScopingFinding`,
// `LEADING_DICTATION_HEADING`, `stripLeadingDictationHeading` and
// `DENIAL_QUOTE_NOT_SELF_NEGATING` used to live — a twenty-token negation
// vocabulary, a clause scoper and a heading stripper, all deciding whether a
// doctor's sentence could be printed under a DENIED fact.
//
// ⚠️ THE HEADING STRIP WAS MEASURED FOR A NON-DENIAL CALLER BEFORE IT WAS
// DELETED, BECAUSE THE RULING REQUIRED THAT CHECK RATHER THAN THAT ASSUMPTION.
// `grep -rn` across `apps/` and `packages/` found ONE call site —
// `dictatedDenialText`, inside this file — and `LEADING_DICTATION_HEADING` had
// exactly one declaration and one use, both here. There was no non-denial
// caller to keep it for. (`encounter-facts`'s `VALUE_LABEL_PREFIX` is a
// separate pattern with its own callers and is untouched.)
//
// Nothing replaces them. That is the ruling.

// ══ OWNER RULING #157(c) Q2 — THE CERTIFICATION BLOCKER EXEMPTS AN ENUMERATED
// ALLOWLIST, NEVER A BLANKET. ══════════════════════════════════════════════
//
// `denialWithheldMaterialFieldIds` blocked on STATUS and MATERIALITY and never
// read `reasonCode`, so every withheld denial blocked certification — including
// the ones rule (4) APPROVES. A template whose `value_only` mapping correctly
// blanks a denial was unable to certify for behaving exactly as ruled.
//
// ⚠️ AN ENUMERATED SET, AND THE GATE ASSERTS SET EQUALITY IN BOTH DIRECTIONS.
// A blanket "any reason code exempts" would let a FUTURE token join the
// exemption silently — and the tokens this set does NOT carry are the ones that
// mean the fill is broken.
//
// ⚠️ #157(d) SHRANK BOTH SIDES, AND THE REASON IS THE POINT. Six of the seven
// blocking tokens named here — `denial_withheld_quote_not_dictated`,
// `…_quote_empty_after_heading_strip`, `…_quote_unrenderable`,
// `…_multiple_distinct_quotes`, `…_no_cited_denial` and `…_fact_not_denied` —
// existed to explain why a particular QUOTE could not be printed. No quote is
// printed any more, so not one of them can be emitted, and a set that still
// named them would be an allowlist reconciling against tokens that do not
// exist. What remains blocking is `denial_withheld_kind_cannot_carry_denial`
// and `denial_withheld_repeating_rows_assert_presence`.
//
// ⚠️ `denial_withheld_repeating_rows_assert_presence` IS DELIBERATELY ABSENT,
// AND IT IS AN OPEN QUESTION RATHER THAN A DECISION. It is rule-(2)-shaped by
// the same "a row asserts presence" logic as the selection token, but #157(c)
// says "*the* selection-shaped withholding", singular, and neither it nor
// #157(d) settles whether the repeating-row token joins it. Anything the ruling
// does not name is a decision being MADE, not one that was GIVEN — and the safe
// direction for a certificate is to keep blocking, because blocking costs a
// certificate and exempting can attest a hole. Still flagged upward, still not
// resolved here.
export const CERTIFICATION_EXEMPT_DENIAL_REASONS: ReadonlySet<string> = new Set([
  'denial_withheld_value_only',
  'denial_withheld_affirmative_only',
  'denial_withheld_selection_asserts_presence',
  DENIAL_WITHHELD_NARRATIVE_ALWAYS_BLANK,
]);

// ⚠️ RULING #157(d) — `DenialText`, `withheld()`, `dictatedDenialText` and
// `narrativeDenialText` ARE DELETED. Between them they were the only functions
// in this repository whose job was to decide whether a denial may print, and
// rule (1) removes the question. Nothing here converts a denied fact into text.


// ══ OWNER RULING #157(c) Q3 — MIXED POLARITY RESOLVES PER FACT. ════════════
//
// ⚠️ `polarity_conflict` IS A DOCUMENT-KILLER STRICTLY MORE COMMON THAN THE ONE
// #157(b) ALREADY FIXED, AND IT CANNOT SURVIVE A SLICE WHOSE PROMISE IS THAT
// DENIALS STOP KILLING DOCUMENTS. Measured on this tree before the fix:
//
//   facts = [assessment "Pneumonia" affirmed,
//            assessment "Pulmonary embolism" denied]
//     -> status=conflict, reason=polarity_conflict, valid=false,
//        blocking=[FIELD_CONFLICT] -> renderTemplateDocx REJECTED:
//        "The document field resolutions are incomplete or invalid."
//
// ONE affirmed fact plus ONE denied fact in ONE narrative field and the doctor
// loses the WHOLE DOCUMENT. `past_medical_history`, `family_history`,
// `allergy` and `medication` are all accumulating list-valued narratives in
// production (17 of the 32 `explicit_denial_allowed` narrative mappings carry
// one of those concepts), and "history of diabetes, no history of hypertension"
// is exactly this shape. ⚠️ AND THE OWNER'S OWN ROS IS MIXED-POLARITY — this is
// his critical path, not an edge case.
//
// ⚠️ PER FACT, IN DICTATION ORDER, AND NEVER PER FIELD. Each fact contributes
// its own segment and the segments keep the order the facts arrived in:
//
//   affirmed -> its DERIVED VALUE (`deriveFieldValueFromFact`, the same
//               function the validator re-derives with and the same one
//               `joinListValuedNarrative` uses, so all three agree by
//               construction)
//   denied   -> NOTHING. Rule (1), #157(d): the reason token rides on the
//               resolution's own `reasonCode` and the validator names the
//               field on the issue channel.
//
// ⚠️ #157(d) DELETED THE SECOND REGISTER. #157(c) had the affirmed side print
// a VALUE and the denied side print a QUOTE, so a mixed field read
// "Pneumonia; No evidence of pulmonary embolism." — two registers in one
// section, recorded at the time as a deliberate product decision. It rested on
// the same falsified premise as rule (1) and dies with it: the denied side now
// prints nothing at all, and the field reads "Pneumonia".
//
// ⚠️ AND THE ZERO-COMPOSITION PROPERTY IS NOW STRONGER, NOT WEAKER. Every
// segment is an affirmed fact's derived value, so the whole string is
// byte-identical to `joinListValuedNarrative(field, mapping, affirmed)` — the
// AFFIRMED PATH'S OWN OUTPUT, reachable with no denial in the picture at all.
// The gate asserts that equality rather than asserting a per-segment property
// about text this function can no longer produce.
//
// ⚠️ THE INVARIANT THAT KEEPS THIS FROM WIDENING ANYTHING: THE MIXED PATH NEVER
// DOES BETTER FOR THE AFFIRMED SET THAN THE AFFIRMED-ONLY PATH WOULD. If two
// distinct affirmed values would have conflicted on this field (a narrative
// that is not an accumulating SECTION), the mixed case REFUSES and falls back
// to the conflict it already was. Removing a denial from the picture can never
// turn a rejected fill into an accepted one.
// ⚠️ #157(d) C3/C4 — THE REASON TOKEN IS THE ENUMERATED BASE, AND THE TYPE
// ENFORCES IT. `reasonCode` is typed `typeof MIXED_POLARITY_REASON`, so a
// composed string does not compile. The previous shape emitted
// `mixed_polarity_per_fact:<token>` by concatenation, which appears as a
// literal NOWHERE — so the reconciliation arm's source scan was structurally
// blind to it and a Q2 BLOCKING token
// (`mixed_polarity_per_fact:denial_withheld_quote_not_dictated`, measured live)
// rode a `supported` resolution straight past certification. Context about the
// withheld denials belongs on the ISSUE channel, which the validator fills from
// the cited facts; it never belongs in an identifier.
export type MixedPolarityOutcome =
  | {
      readonly kind: 'text';
      readonly text: string;
      readonly reasonCode: typeof MIXED_POLARITY_REASON;
    }
  | { readonly kind: 'refused' };

/** The reason token a per-fact mixed resolution carries. The ONLY one. */
export const MIXED_POLARITY_REASON = 'mixed_polarity_per_fact';

function mixedRefused(): MixedPolarityOutcome {
  return { kind: 'refused' };
}

/**
 * The value a narrative field carrying BOTH affirmed and denied facts renders,
 * or a refusal that leaves the caller exactly where it was.
 *
 * Written by the resolver, RE-DERIVED by the validator from the same inputs and
 * the same cited set — one implementation for the write side and the verify
 * side, exactly as `denialOutcome` is.
 */
export function mixedPolarityNarrative(
  field: TemplateField,
  mapping: SemanticMapping | undefined,
  facts: ReadonlyArray<EncounterFact>,
): MixedPolarityOutcome {
  // Only prose accumulates. A `single_select` bound to two polarities still has
  // one slot and one answer, and a repeating section expands ROWS — rule (2)
  // says a row asserts presence, so a denial can never populate one.
  if (field.kind !== 'narrative_text' || field.rowPrototype) return mixedRefused();

  const affirmed = facts.filter((fact) => fact.polarity === 'affirmed');
  const denied = facts.filter((fact) => fact.polarity === 'denied');
  // Anything that is neither is `uncertain` or `conditional`, which the
  // resolver answers with `ambiguous` well before this point. Refusing here
  // keeps the validator's re-derivation identical to the write side even if a
  // future caller reaches it from somewhere else.
  if (affirmed.length + denied.length !== facts.length) return mixedRefused();
  if (affirmed.length === 0 || denied.length === 0) return mixedRefused();

  // ⚠️ NON-DIRECT EVIDENCE REFUSES, BECAUSE A `supported` STATUS THAT BLOCKS IS
  // AN INCOHERENT STATE AND A NEW ROUTE TO A BLOCKING ISSUE.
  //
  // MEASURED while writing this: a `conflicting`-quality fact
  // (`encounter-facts/index.ts:645` — `superseded` or `conflict_note`) reaches
  // here and composes a value, the resolution becomes `supported`, and the
  // validator's `SUPPORTED_STATUS_CONFLICTS_WITH_QUALITY` then blocks it. The
  // doctor's outcome is identical to the `conflict` this replaces — both block
  // — but the field would carry a VALUE while blocked, and the blocking would
  // arrive through a code that has nothing to do with polarity. Refusing keeps
  // the case exactly where #157(c) found it.
  //
  // `unclear`/`review` never reach this line: the resolver answers those with
  // `ambiguous` well above. `conflicting` is the live shape, and it is the one
  // this guard was written for.
  if (facts.some((fact) => fact.quality.evidence !== 'direct')) return mixedRefused();

  // ⚠️ LATERALITY ACROSS THE **AFFIRMED** FACTS ONLY — AND THE CORRECTION IS THE
  // WHOLE POINT OF #157(d).
  //
  // This guard used to read every cited fact, and its stated reason was that
  // "a left-leg affirmation and a right-leg denial would be merged into one
  // unattributed section". Under #157(c) that was true: the denied fact printed
  // its quote. **#157(d) deleted that.** A denied fact now contributes ZERO
  // characters to this value — measured, and asserted by the C4 arm — so there
  // is nothing of the denial left to merge, and no unattributed section can
  // form. The hazard is gone.
  //
  // ⚠️ THE AMENDMENT REMOVED THE REASON AND LEFT THE VETO, WHICH COST THE WHOLE
  // DOCUMENT. Measured on the modal vascular impression:
  //   "Findings consistent with right leg deep vein thrombosis.
  //    No evidence of left leg deep vein thrombosis."
  //   -> affirmed/right + denied/left -> lateralities.size === 2 -> refused
  //   -> polarity_conflict -> FIELD_CONFLICT -> the export is LOST.
  // The affirmed fact ALONE renders. So the denial's laterality, and nothing
  // else, destroyed the document — on the owner's own specialty, and on a
  // branch whose headline promise is that denials stop killing documents.
  //
  // Reading only the affirmed side restores the module's own "never better than
  // affirmed alone" invariant EXACTLY: the value is byte-identical to what the
  // affirmed facts produce by themselves.
  const lateralities = new Set(
    affirmed
      .map((fact) => fact.laterality)
      .filter((side) => side !== 'not_applicable' && side !== 'unknown'),
  );
  if (lateralities.size > 1) return mixedRefused();

  // ⚠️ #157(d) C4 — THE DENIED BRANCH IS GONE, SO NO COMPOSITION OF DENIAL
  // TEXT CAN EXIST HERE. The affirmed facts derive by the NORMAL path in
  // DICTATION ORDER (`facts.filter` preserves order, and nothing between the
  // resolver's candidate filters and here sorts), and the denied facts
  // contribute nothing but the resolution's reason token. What this loop
  // produces is byte-identical to `joinListValuedNarrative(field, mapping,
  // affirmed)` — the affirmed path's own function — which is asserted as a
  // PROPERTY by the gate rather than described as an intention here.
  const segments: string[] = [];
  for (const fact of affirmed) {
    const derived = deriveFieldValueFromFact(field, mapping, fact);
    // A cited fact that does not derive would be DROPPED from a section the
    // note presents as complete, and the validator — which re-derives with
    // this same function — would accept the loss. Refuse the whole thing.
    if (derived === null) return mixedRefused();
    const text = String(derived).trim();
    if (!text) continue;
    if (!segments.includes(text)) segments.push(text);
  }

  // ⚠️ THE NEVER-BETTER-THAN-AFFIRMED-ALONE INVARIANT. Two distinct affirmed
  // values on a narrative that is not an accumulating SECTION are a genuine
  // conflict — `multiple_distinct_supported_values` — and they stay one.
  if (segments.length > 1 && !isListValuedNarrative(field, mapping)) {
    return mixedRefused();
  }
  if (segments.length === 0) return mixedRefused();

  // ⚠️ NO CEILING AND NO XML CLASS, DELIBERATELY, BECAUSE THE AFFIRMED PATH HAS
  // NEITHER. `joinListValuedNarrative` imposes no length limit, so a ceiling
  // here would refuse a mixed field that the SAME affirmed facts alone would
  // render — falling back to `polarity_conflict`, FIELD_CONFLICT, and the dead
  // document Q3 exists to prevent. The value this returns is now an affirmed
  // value like any other, and it is bounded exactly as every other affirmed
  // value is: by the renderer, at `MAX_RENDERED_FIELD_CHARACTERS`.
  return {
    kind: 'text',
    text: segments.join(NARRATIVE_LIST_SEPARATOR),
    reasonCode: MIXED_POLARITY_REASON,
  };
}

export type DenialOutcome =
  | {
      readonly status: 'explicitly_denied';
      readonly value: string | false;
      readonly reasonCode: string;
    }
  | {
      readonly status: typeof DENIAL_WITHHELD;
      readonly value: null;
      readonly reasonCode: string;
    };

function withheldOutcome(reasonCode: string): DenialOutcome {
  return { status: DENIAL_WITHHELD, value: null, reasonCode };
}

/**
 * THE outcome for a field every one of whose cited facts is a DENIAL.
 *
 * Written by the resolver, RE-DERIVED by the validator from the same inputs.
 * Exactly three things can be printed for a denial, and everything else is a
 * named blank:
 *
 *   value_only              -> BLANK. 88 of production's 150 mappings keep
 *                              their refusal right. "Withholds" means BLANK,
 *                              not "blocks the export".
 *   affirmative_only        -> BLANK. A real meaning again, rather than the
 *                              second route to a refusal it had been.
 *   explicit_denial_allowed -> `false` on a checkbox; BLANK on EVERYTHING
 *                              else, narrative_text included — rule (1).
 *
 * ⚠️ SELECTION-SHAPED FIELDS NEVER SELECT ON A DENIAL — rule (2). A
 * single_select, a multi_select and a rowPrototype expansion all ASSERT
 * PRESENCE by rendering, so the ruling's own test ("never print what would
 * assert falsely") reaches every one of them and not merely the checkbox the
 * first enumeration named. Production has 28 single_selects; the day one of
 * them is mapped to `extraction` under a denial-approving behaviour, this is
 * the only thing standing between a denied finding and a ticked dropdown.
 *
 * ⚠️ A CHECKBOX WITH `value === false` RENDERS UNCHECKED: UNCHANGED. It is the
 * one control whose blank state IS the denial, and nothing here touches it.
 *
 * ⚠️ date / number / measurement CANNOT CARRY A DENIAL AND ARE BLANKED. A
 * denied procedure date has no date to print; printing one asserts a procedure
 * happened. Today they keep their value, reach the renderer as
 * `explicitly_denied` on a non-checkbox, and REFUSE THE PACKAGE — so this is
 * strictly better than what it replaces, in the direction of the document
 * surviving.
 */
export function denialOutcome(
  field: TemplateField,
  mapping: SemanticMapping | undefined,
): DenialOutcome {
  const behavior = mapping?.polarityBehavior;
  if (behavior !== 'explicit_denial_allowed') {
    return withheldOutcome(
      behavior === 'affirmative_only'
        ? 'denial_withheld_affirmative_only'
        : 'denial_withheld_value_only',
    );
  }
  if (field.rowPrototype) {
    return withheldOutcome('denial_withheld_repeating_rows_assert_presence');
  }
  if (field.kind === 'single_select' || field.kind === 'multi_select') {
    return withheldOutcome('denial_withheld_selection_asserts_presence');
  }
  if (field.kind === 'checkbox') {
    return {
      status: 'explicitly_denied',
      value: false,
      reasonCode: 'explicit_denial_supported',
    };
  }
  if (field.kind !== 'narrative_text') {
    return withheldOutcome('denial_withheld_kind_cannot_carry_denial');
  }
  // ⚠️ RULING #157(d) RULE (1), AND IT IS THE LAST LINE OF THIS FUNCTION ON
  // PURPOSE: there is nothing after it to consult. A denied narrative fact is
  // BLANK, unconditionally, whatever the quote says and however many facts are
  // cited.
  return withheldOutcome(DENIAL_WITHHELD_NARRATIVE_ALWAYS_BLANK);
}

/**
 * May this (field, value) pair be PRINTED under `explicitly_denied`?
 *
 * The renderer's wall, and the last thing standing if the resolver ever
 * regresses. It refuses rather than blanks BECAUSE reaching it means a
 * resolution that no legal path can produce — a bug, not a denial — and rule
 * (3) is about denials, not about laundering an invalid resolution into a
 * quiet blank.
 */
export function isPrintableDenial(
  field: TemplateField,
  value: FieldResolution['value'],
): boolean {
  // ⚠️ #157(d) — THE `narrative_text` ARM IS DELETED AND THE WALL IS BACK TO
  // ONE SHAPE. A narrative denial is `denial_withheld` with a null value long
  // before the renderer sees it, so an `explicitly_denied` narrative is a
  // resolution no legal path can mint — a BUG — and this refuses it rather than
  // laundering it into a quiet blank.
  if (field.rowPrototype) return false;
  return field.kind === 'checkbox' && value === false;
}

/**
 * The clinically material fields this fill left BLANK because of a denial.
 *
 * ⚠️ THIS IS THE CERTIFICATION GATE'S HALF OF RULE (3), AND THE SEPARATION IS
 * THE WHOLE POINT. Rule (3) forbids a denial from refusing an EXPORT — so
 * `FIELD_DENIAL_WITHHELD` is a warning and the document always renders. It says
 * nothing about whether a TEMPLATE is fit to be certified, and a certificate
 * that attested a template whose clinically material section silently blanks
 * would be exactly the "green with a hole in it" that
 * `allowUncertifiedForSyntheticTest` already produces for
 * `needs_clinician_input`.
 *
 * So the export renders and the blank is NAMED in two durable places — the
 * reason token and the counts. ⚠️ IT DOES NOT BLOCK CERTIFICATION for a
 * narrative denial: #157(d) Q2 exempts that token by name, and a comment here
 * claimed the opposite until the pass measured
 * `denialWithheldMaterialFieldIds = 0` against five denied material concepts.
 * Blocking still holds for the NON-exempt tokens. Same shape as the
 * fill-coverage and blank-verification invariants beside it: an invariant that
 * gates the certificate without gating the visit.
 */
export function denialWithheldMaterialFieldIds(
  fields: ReadonlyArray<TemplateField>,
  resolutions: ReadonlyArray<FieldResolution | null | undefined>,
): string[] {
  const material = new Map(
    fields.map((field) => [
      field.fieldId,
      field.clinicallyMaterial || field.criticality !== 'routine',
    ]),
  );
  return resolutions
    .filter(
      (resolution): resolution is FieldResolution =>
        resolution != null &&
        resolution.status === DENIAL_WITHHELD &&
        material.get(resolution.fieldId) === true &&
        // ⚠️ #157(c) Q2 — THE SEAM. This predicate never read `reasonCode`, so a
        // blank the ruling APPROVES blocked certification exactly as hard as a
        // blank that means the fill is broken.
        !CERTIFICATION_EXEMPT_DENIAL_REASONS.has(resolution.reasonCode),
    )
    .map((resolution) => resolution.fieldId);
}
