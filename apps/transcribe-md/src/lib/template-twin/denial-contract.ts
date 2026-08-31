// ============================================================================
// Template Twin — THE DENIAL CONTRACT.  Owner ruling #157(b), standing.
// ----------------------------------------------------------------------------
// ONE MODULE, EVERY READER. The resolver WRITES a denial, the validator
// RE-DERIVES it, the renderer decides whether the pair may be PRINTED, and the
// certification gate asks whether a withheld denial is fit to certify. Four
// call sites, one implementation — because a second copy of this logic drifts
// from the first the day either is fixed, and the thing that drifts is what
// reaches a signed clinical document.
//
// ⚠️ THE PREMISE THE ORIGINAL #157 WAS BUILT ON WAS FALSE, AND IT IS RECORDED
// HERE RATHER THAN QUIETLY CORRECTED.
//
// #157 said a narrative field "renders its denial's text verbatim". It does
// not — `projectEncounterFacts` puts the AFFIRMED ENTITY in `fact.value` and
// the doctor's sentence in `fact.evidenceQuote`. Measured, on the real
// projection:
//
//   "The patient has no history of diabetes."  -> value "Diabetes"
//   "No evidence of pulmonary embolism."       -> value "Pulmonary embolism"
//   "Plan: no further imaging is required."    -> value "Further imaging"
//   "Allergies: no known drug allergies"       -> value "No known drug allergies"
//
// Only the last carries prose. Implementing #157 as written would have printed
// **"Diabetes"** into the past-medical-history section of a document the doctor
// then signed, with `validateTemplateTwin` returning `valid: true`. Three of
// the four dictations above assert the OPPOSITE of what was said.
//
// So #157(b): the doctor's own sentence — `evidenceQuote` — is the ONLY text
// the house may print for a denial.
//
// ⚠️ ZERO COMPOSITION. NOT "MINIMAL", NOT "CAREFUL" — ZERO.
// Nothing here synthesizes, templates, prefixes, joins or rewrites a single
// word. "No <entity>" manufactures clinical phrasing that nobody dictated, and
// "no further imaging REQUIRED" is not "No further imaging". The one
// deterministic allowance is `stripLeadingDictationHeading`, and it removes a
// PREFIX — so the printed text is always a SUFFIX of the doctor's quote. That
// property is asserted in this module and again, end to end against a real
// rendered .docx, by the gate.
//
// ⚠️ AND FOUR PRODUCERS SYNTHESIZE AN `evidenceQuote` THAT IS NOT DICTATION —
// which is why `dictatedDenialText` gates on `sourceType` before anything else:
//
//   resolver/index.ts          "Physician-approved practice default for this …"
//   verified-note-selection.ts "Selected from the template's enumerated options…"
//   procedure-date.ts          "Procedure date derived from the visit (encounter) date."
//   clinician-override.ts      `Clinician set this control to "<option>".`
//
// Printing any of those as a clinical denial would put HOUSE PROSE in a signed
// note wearing the doctor's voice. `encounter_evidence` only.
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

import { EXPLICIT_DENIAL } from './encounter-facts';

/** The status a withheld denial carries. Blank, cited, and named. */
export const DENIAL_WITHHELD = 'denial_withheld' as const;

/**
 * A denial quote longer than this is withheld rather than printed.
 *
 * The renderer refuses above `MAX_RENDERED_FIELD_CHARACTERS` (32_767) with
 * FIELD_VALUE_TOO_LARGE — which is a REFUSED EXPORT, exactly what rule (3)
 * forbids. So the ceiling is enforced HERE, well below the renderer's, where
 * the outcome is a named blank instead of a lost document. A dictated sentence
 * is a sentence; 2_000 characters is already far outside that shape.
 */
export const MAX_DENIAL_QUOTE_CHARACTERS = 2_000;

/**
 * Byte-identical in effect to `note-template-docx/renderer.ts`'s own
 * `INVALID_XML_CHARACTER_RE`. Duplicated deliberately and narrowly: importing
 * it would point a leaf module at the renderer, and the renderer's copy is the
 * one that must stay authoritative. Its only use here is to WITHHOLD early
 * rather than let the renderer refuse the package.
 */
const INVALID_XML_CHARACTER_RE =
  /[\u0000-\u0008\u000b\u000c\u000e-\u001f\ud800-\udfff]/u;

/**
 * THE ONE FORMATTING ALLOWANCE — a leading "<heading>:" token.
 *
 * L3 keeps a section label on some dictations: "Allergies: no known drug
 * allergies", "Plan: no further imaging is required." The label is the form's
 * own heading, not the doctor's clinical sentence, and printing it back into
 * the field beneath that same heading reads as a transcription error.
 *
 * ⚠️ DELIBERATELY STRICTER THAN `encounter-facts`'s `VALUE_LABEL_PREFIX`
 * (its pattern is `^\s`-star`[A-Za-z][^:\n]{0,39}:\s`-star, written without
 * its delimiters because the closing pair would end this comment block early),
 * AND THE REASON IS A COUNTEREXAMPLE, NOT
 * A PREFERENCE. That pattern is applied to short L3 VALUES; this one is applied
 * to a whole dictated SENTENCE, where `[^:\n]` happily eats a clock. Measured:
 *
 *   "At 10:30 the patient denied chest pain."
 *      VALUE_LABEL_PREFIX -> "30 the patient denied chest pain."   ← mangled
 *      this pattern       -> unchanged (the heading may not contain a digit)
 *
 * A heading here is letters, spaces, hyphens and slashes only, and something
 * non-blank must follow it — so the strip can never empty the quote and can
 * never cut into a sentence that merely contains a colon.
 */
export const LEADING_DICTATION_HEADING = /^\s*[A-Za-z][A-Za-z /-]{0,39}:[ \t]*(?=\S)/;

/**
 * The quote with at most one leading heading removed.
 *
 * ⚠️ THE RETURN IS ALWAYS A SUFFIX OF THE INPUT — asserted, not assumed. That
 * is what makes "zero composition" CHECKABLE rather than merely intended: a
 * caller (and the gate) can assert `quote.endsWith(printed)` and no
 * synthesized, templated or joined text can satisfy it.
 */
export function stripLeadingDictationHeading(quote: string): string {
  const heading = LEADING_DICTATION_HEADING.exec(quote);
  if (!heading) return quote;
  // ⚠️ A HEADING THAT CARRIES THE NEGATION IS NOT A HEADING — IT IS THE CLAIM.
  //
  // `LEADING_DICTATION_HEADING`'s class admits SPACES, and every token in
  // `DENIAL_VOCABULARY` is letters-and-spaces, so structured dictation puts the
  // negation exactly where this pattern looks for a label:
  //
  //   "Not taking: warfarin, aspirin, or clopidogrel."
  //    ^^^^^^^^^^^ matched as a heading -> stripped
  //   -> "warfarin, aspirin, or clopidogrel."  printed into a SIGNED note for a
  //      patient the encounter says is NOT taking them.
  //
  // ⚠️ AND THE ZERO-COMPOSITION PROPERTY CANNOT SEE THIS. The inverted output is
  // still a strict SUFFIX of the doctor's own quote, so `quote.endsWith(printed)`
  // is `true` for every one of these. A substring check proves nothing was
  // MANUFACTURED; it cannot prove nothing was DESTROYED. Both are needed.
  const removed = heading[0];
  if (EXPLICIT_DENIAL.test(removed)) return quote;
  const stripped = quote.slice(removed.length);
  return quote.endsWith(stripped) ? stripped : quote;
}

export type DenialText =
  | { readonly kind: 'text'; readonly text: string }
  | { readonly kind: 'withheld'; readonly reasonCode: string };

function withheld(reasonCode: string): DenialText {
  return { kind: 'withheld', reasonCode };
}

/**
 * The text ONE denied fact licenses the house to print, or a named refusal.
 *
 * Gates, in order, on: dictated provenance, denied polarity, a non-blank
 * remainder after the heading strip, and renderability.
 */
export function dictatedDenialText(fact: EncounterFact): DenialText {
  if (fact.sourceType !== 'encounter_evidence') {
    return withheld('denial_withheld_quote_not_dictated');
  }
  if (fact.polarity !== 'denied') {
    return withheld('denial_withheld_fact_not_denied');
  }
  const text = stripLeadingDictationHeading(fact.evidenceQuote);
  if (text.trim().length === 0) {
    return withheld('denial_withheld_quote_empty_after_heading_strip');
  }
  if (
    text.length > MAX_DENIAL_QUOTE_CHARACTERS ||
    INVALID_XML_CHARACTER_RE.test(text)
  ) {
    return withheld('denial_withheld_quote_unrenderable');
  }
  return { kind: 'text', text };
}

/**
 * The text a NARRATIVE denial licenses, across every fact the resolution cites.
 *
 * ⚠️ MORE THAN ONE DISTINCT QUOTE IS WITHHELD, NOT JOINED — and this is the
 * decision that keeps rule (1) absolute.
 *
 * An accumulating section ("no diabetes and no hypertension") normally yields
 * SEVERAL facts carrying ONE quote, and that collapses to the single sentence
 * the doctor actually said. Two GENUINELY different denied sentences have no
 * verbatim rendering: `"A."` + `"B."` is a composition, however small the
 * separator, and the affirmed path's `"; "` join is exactly the manufacturing
 * rule (1) forbids. So the honest outcome is a named blank.
 *
 * The alternative was measured and rejected before this was written: today the
 * multi-fact denial falls through to `multiple_distinct_supported_values` ->
 * FIELD_CONFLICT -> blocking, and the doctor loses the WHOLE DOCUMENT. Blank
 * with a reason is strictly better than that and strictly safer than a join.
 */
export function narrativeDenialText(
  field: TemplateField,
  mapping: SemanticMapping | undefined,
  facts: ReadonlyArray<EncounterFact>,
): DenialText {
  if (field.kind !== 'narrative_text' || field.rowPrototype) {
    return withheld('denial_withheld_kind_cannot_carry_denial');
  }
  if (mapping?.polarityBehavior !== 'explicit_denial_allowed') {
    return withheld(
      mapping?.polarityBehavior === 'affirmative_only'
        ? 'denial_withheld_affirmative_only'
        : 'denial_withheld_value_only',
    );
  }
  if (facts.length === 0) return withheld('denial_withheld_no_cited_denial');
  const distinct: string[] = [];
  for (const fact of facts) {
    const one = dictatedDenialText(fact);
    if (one.kind === 'withheld') return one;
    if (!distinct.includes(one.text)) distinct.push(one.text);
  }
  const only = distinct[0];
  if (distinct.length !== 1 || only === undefined) {
    return withheld('denial_withheld_multiple_distinct_quotes');
  }
  return { kind: 'text', text: only };
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
 *   explicit_denial_allowed -> the doctor's quote on a narrative field;
 *                              `false` on a checkbox; BLANK on everything else.
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
  facts: ReadonlyArray<EncounterFact>,
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
  const text = narrativeDenialText(field, mapping, facts);
  if (text.kind === 'withheld') return withheldOutcome(text.reasonCode);
  return {
    status: 'explicitly_denied',
    value: text.text,
    reasonCode: 'explicit_denial_dictated_quote',
  };
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
  if (field.rowPrototype) return false;
  if (field.kind === 'checkbox') return value === false;
  if (field.kind === 'narrative_text') {
    return typeof value === 'string' && value.length > 0;
  }
  return false;
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
 * So the export renders and CERTIFICATION BLOCKS, by name. Same shape as the
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
        material.get(resolution.fieldId) === true,
    )
    .map((resolution) => resolution.fieldId);
}
