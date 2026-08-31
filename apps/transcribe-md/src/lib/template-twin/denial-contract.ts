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

import {
  deriveFieldValueFromFact,
  isListValuedNarrative,
  NARRATIVE_LIST_SEPARATOR,
} from './field-value-derivation';

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

// ══ OWNER RULING #157(c) Q1 — THE DISCRIMINATOR IS SELF-NEGATION, CHECKED AND
// NEVER ASSUMED. ═══════════════════════════════════════════════════════════
//
// ⚠️ #157(b)'s RULE (1) WAS FALSIFIED, AND THIS IS THE AMENDMENT. "A denied
// narrative fact prints its evidence quote VERBATIM" is sound ONLY when the
// quote ITSELF carries the denial. Measured on this tree, it frequently does
// not:
//
//   · L3 states polarity as a REQUIRED enum
//     (worker/layers/03-extract-entities.ts:193)
//   · and is INSTRUCTED that "absence of the word 'no' is not absence of a
//     denial" (:446)
//   · and a stated polarity BYPASSES the denial vocabulary entirely
//     (encounter-facts/index.ts:507 — `options.polarity ?? inferPolarity(…)`)
//
// So a fact can be `denied` on a quote carrying no negation at all, and rule
// (1) as written prints its OPPOSITE. Driven end to end through the real
// projection -> compiler -> resolver -> validator -> awaited renderer:
//
//   ros finding "Fever", polarity denied,
//   quote "Fever, chills, and night sweats."
//     -> the document PRINTS THAT SENTENCE. valid=true, verified=true, zero
//        issues at every layer. No heading is involved, so no strip-side guard
//        reaches it.
//
// ⚠️ AND IT CLOSES A SECOND PATH THE FIRST FIX ONLY THOUGHT IT HAD CLOSED.
// #157(b) refused the heading strip when the removed prefix matched
// `EXPLICIT_DENIAL` — six spellings, built from `DENIAL_VOCABULARY`. Measured
// against fourteen negating headings, TWELVE were still stripped and printed
// their inverse:
//
//   Absent:  Ruled out:  Free of:  None:  Nil:  Unremarkable:
//   Within normal limits:  Negative:  Excluded:  Not present:
//   Clear of:  Resolved:            ← all stripped, all inverted
//   Denied:  No longer taking:      ← the only two in vocabulary
//
// Both paths are closed by ONE predicate applied in TWO places, and the two
// placements are NOT redundant — each is mutation-proved separately:
//
//   · `stripLeadingDictationHeading` PRESERVES a print that would otherwise be
//     destroyed. A prefix that carries a negation is the CLAIM, not a heading.
//   · `dictatedDenialText` REFUSES a print that carries no negation at all.
//     This is the wall R1 walks into, and it also catches anything the strip
//     destroys for a reason nobody anticipated — the printed text is what is
//     tested, so a negation removed by any means fails here.
//
// ⚠️ COMPOSITION STAYS FORBIDDEN FOREVER. Nothing here synthesizes, templates,
// prefixes or rewrites a word. The discriminator only ever answers YES or NO
// about text the doctor already said; a NO is a BLANK, never a repair.
//
// ⚠️ HONEST LIMIT, RECORDED RATHER THAN IMPLIED. This is a heuristic about
// TEXT. There is no clinical NER in this repository (`redactPhi` is a log
// scrubber, not an entity recogniser), so it can be wrong in both directions
// and it is built to FAIL TOWARD BLANK:
//
//   no negation token anywhere in the printed text        -> BLANK   (the R1 harm)
//   a locatable finding, negation only in ANOTHER clause  -> BLANK
//   an unlocatable finding, and more than one clause      -> BLANK
//   a negation in the finding's own clause                -> PRINT
//   an unlocatable finding in a single clause, negated    -> PRINT
//
// A blank is a VISIBLE ABSENCE. An inverted sentence is a SIGNED ASSERTION.
// The two errors are not symmetric, and the asymmetry is deliberate.
//
// ⚠️ IT IS NOT `EXPLICIT_DENIAL` AND IT IS NOT `denialGovernsValue`, AND THAT
// IS MEASURED, NOT STYLISTIC:
//   · `EXPLICIT_DENIAL` is SIX tokens. Seventeen out-of-vocabulary negation
//     families are invisible to it — that is the twelve-of-fourteen row above.
//   · `denialGovernsValue`'s positional scan (arm (b), encounter-facts:341)
//     deliberately refuses a cue that sits AFTER the value, so
//     "Chest pain was denied by the patient." reads AFFIRMED there. Reusing it
//     would blank a legitimate print, and post-positive negation
//     ("Melena negative.", "PE excluded.", "Hepatomegaly is not present.") is
//     ordinary clinical dictation. Same-CLAUSE, not before-the-value, is the
//     line this predicate draws.

/**
 * The negation tokens that make a sentence read as a denial of something in it.
 *
 * ⚠️ DELIBERATELY WIDER THAN `DENIAL_VOCABULARY` AND DELIBERATELY NARROWER THAN
 * "ANYTHING NEGATIVE-SOUNDING". Wider, because that list is tuned for INFERRING
 * a polarity nobody stated and its six tokens miss most structured dictation.
 * Narrower, because a false positive here LICENSES A PRINT — the one direction
 * this must not fail in.
 *
 * ⚠️ BARE `not` IS NOT A TOKEN, AND THE COUNTEREXAMPLE IS PINNED IN THE GATE:
 * "It is not severe, but it is there." is an AFFIRMATION. `not` earns its place
 * only in collocation with a word that carries the negation's object.
 *
 * ⚠️ AND FOUR CANDIDATES ARE REFUSED ON PURPOSE, WITH THEIR REASON, so the next
 * reader does not "complete" the list:
 *   `doubt`     — a hedge. "Doubt pulmonary embolism." is a probability, not a
 *                 denial, and #157(c)'s honest limit says fail toward BLANK.
 *   `cannot`    — ambiguous object. "Cannot identify a lesion." negates;
 *                 "Cannot tolerate aspirin." AFFIRMS an intolerance.
 *   `unlikely`  — a hedge, as `doubt`.
 *   `normal`    — "Normal:" as a heading is not a claim about the finding, and
 *                 admitting it would keep every "Normal:" prefix unstripped.
 */
export const SELF_NEGATION_VOCABULARY = [
  // ⚠️ ORDER IS LOAD-BEARING FOR THE REPORTED MATCH, NOT FOR THE ANSWER.
  // Longer alternatives first so a shared prefix reports the longer token.
  { name: 'within normal limits', token: 'within\\s+normal\\s+limits' },
  { name: 'not <negated object>', token: 'not\\s+(?:currently\\s+|presently\\s+|actively\\s+|routinely\\s+|clinically\\s+)?(?:taking|on|present|appreciated|identified|seen|noted|observed|detected|demonstrated|visuali[sz]ed|elicited|palpable|reported|endorsed|found|evident|apparent|indicated|performed)' },
  { name: 'ruled out', token: 'rule[sd]?\\s+out' },
  { name: 'absence of / absent', token: 'absen(?:ce|t)' },
  { name: 'unremarkable', token: 'unremarkable' },
  { name: 'excluded', token: 'exclude[sd]' },
  { name: 'negative', token: 'negative' },
  { name: 'resolved', token: 'resolved' },
  { name: 'denies', token: 'den(?:y|ies|ied|ying)' },
  { name: 'without', token: 'without' },
  { name: 'clear of', token: 'clear\\s+of' },
  { name: 'free of', token: 'free\\s+of' },
  { name: 'neither', token: 'neither' },
  { name: 'never', token: 'never' },
  { name: 'none', token: 'none' },
  { name: 'wnl', token: 'wnl' },
  { name: 'nor', token: 'nor' },
  { name: 'nil', token: 'nil' },
  { name: 'no', token: 'no' },
  { name: '-ve', token: '-ve' },
] as const;

/**
 * ⚠️ THE LEADING CLASS IS A BOUNDARY, NOT PART OF THE TOKEN — and the match
 * this module reports is the TOKEN, so a caller (and the gate) can assert the
 * rendered text CONTAINS it. `(?:\b|$)` closes it, exactly as `EXPLICIT_DENIAL`
 * does, so "Nose:" does not match `no` and "not severe" does not match `not`.
 */
const SELF_NEGATION_CUE = new RegExp(
  `(?:^|[\\s,;:(\\["'])(${SELF_NEGATION_VOCABULARY.map((e) => e.token).join('|')})(?:\\b|$)`,
  'gi',
);

/** One negation cue: the token as it appears, its vocabulary name, its offset. */
export interface SelfNegationCue {
  readonly name: string;
  readonly match: string;
  readonly index: number;
}

const CLAUSE_BREAK_CHARACTERS = '.;\n';

/** Every negation cue in `text`, in order of appearance. */
export function selfNegationCues(text: string): SelfNegationCue[] {
  const cues: SelfNegationCue[] = [];
  SELF_NEGATION_CUE.lastIndex = 0;
  let match: RegExpExecArray | null;
  while ((match = SELF_NEGATION_CUE.exec(text)) !== null) {
    const token = match[1];
    if (token === undefined || match[0].length === 0) {
      SELF_NEGATION_CUE.lastIndex += 1;
      continue;
    }
    // The token always sits at the END of the whole match — the leading class
    // is one character or nothing, and the trailing assertion is zero-width.
    // Computing the offset by subtraction rather than by `indexOf` cannot pick
    // up a coincidental earlier occurrence of the token inside its own boundary.
    const index = match.index + match[0].length - token.length;
    const name =
      SELF_NEGATION_VOCABULARY.find((entry) =>
        new RegExp(`^(?:${entry.token})$`, 'i').test(token),
      )?.name ?? 'unnamed';
    cues.push({ name, match: token, index });
  }
  return cues;
}

/** The clause containing `at`, delimited by `.`, `;` or a newline. */
function clauseBoundsAround(text: string, at: number): [number, number] {
  let begin = 0;
  for (let i = Math.min(at, text.length) - 1; i >= 0; i -= 1) {
    if (CLAUSE_BREAK_CHARACTERS.includes(text.charAt(i))) {
      begin = i + 1;
      break;
    }
  }
  let end = text.length;
  for (let i = Math.max(at, 0); i < text.length; i += 1) {
    if (CLAUSE_BREAK_CHARACTERS.includes(text.charAt(i))) {
      end = i;
      break;
    }
  }
  return [begin, end];
}

const SELF_NEGATION_METACHARACTERS = /[.*+?^${}()|[\]\\]/g;

/** Case-insensitive offset of `finding` inside `text`, or -1. Mirrors
 *  `encounter-facts`'s `locateValueInQuote`: L3 CAPITALISES the finding while
 *  the quote keeps the sentence's own casing, so a case-sensitive search
 *  returns -1 for essentially every real fact. */
function locateFinding(text: string, finding: string): number {
  if (!finding.trim()) return -1;
  const match = new RegExp(
    finding.replace(SELF_NEGATION_METACHARACTERS, '\\$&'),
    'i',
  ).exec(text);
  return match ? match.index : -1;
}

/**
 * THE Q1 PREDICATE: does `text` — the text that would actually be PRINTED —
 * carry a negation scoping `finding`?
 *
 * Returns the cue, so a caller can assert containment rather than take the
 * boolean on trust. `null` means BLANK.
 */
export function selfNegationScopingFinding(
  text: string,
  finding: unknown,
): SelfNegationCue | null {
  const cues = selfNegationCues(text);
  if (cues.length === 0) return null;

  const stated = typeof finding === 'string' ? finding.trim() : '';
  const start = locateFinding(text, stated);

  if (start < 0) {
    // Nothing positional can be said about a finding that is not in its own
    // printed text — L3 normalises "Never a smoker." to the entity "Smoking".
    // A SINGLE clause carrying a negation is that clause's own claim, so it
    // prints; more than one clause and the cue may belong to a different
    // sentence entirely, so it BLANKS.
    // ⚠️ "SINGLE CLAUSE" IS "NOTHING FOLLOWS THE FIRST BREAK", NOT "THE BREAK IS
    // AT THE END". A sentence-final full stop IS a clause break, so comparing
    // the break's offset against the trimmed length called EVERY ordinary
    // sentence multi-clause and blanked four legitimate prints — measured:
    // "Never a smoker.", "Troponin -ve.", "Cardiovascular exam unremarkable.",
    // "Respiratory exam within normal limits.". What matters is whether there
    // is a SECOND clause for the cue to have belonged to.
    const [, firstClauseEnd] = clauseBoundsAround(text, 0);
    const rest = text.slice(firstClauseEnd + 1).trim();
    return rest.length === 0 ? (cues[0] ?? null) : null;
  }

  const [begin, end] = clauseBoundsAround(text, start);
  return cues.find((cue) => cue.index >= begin && cue.index < end) ?? null;
}

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
  // ⚠️ #157(c) Q1 — THE PREDICATE IS `selfNegationScopingFinding`, NOT
  // `EXPLICIT_DENIAL`, AND THE WIDENING IS MEASURED. `EXPLICIT_DENIAL` is built
  // from `DENIAL_VOCABULARY`'s SIX spellings; against fourteen negating headings
  // it kept two and STRIPPED TWELVE, each of which then printed its own inverse
  // into a signed note. `Absent:`, `Ruled out:`, `Free of:`, `None:`, `Nil:`,
  // `Unremarkable:`, `Within normal limits:`, `Negative:`, `Excluded:`,
  // `Not present:`, `Clear of:` and `Resolved:` are all claims, not labels.
  //
  // The finding is not known here — this function sees only the quote — so the
  // prefix is asked the UNSCOPED question: does this text carry a negation at
  // all? A prefix is a handful of words and there is no second clause for a cue
  // to belong to, so scoping has nothing to add.
  if (selfNegationCues(removed).length > 0) return quote;
  const stripped = quote.slice(removed.length);
  return quote.endsWith(stripped) ? stripped : quote;
}

/**
 * ⚠️ #157(c) Q1's REASON TOKEN, SPELLED EXACTLY AS THE RULING SPELLS IT.
 *
 * It does NOT carry the `denial_withheld_` prefix the sibling tokens use. That
 * is the ruling's own wording, twice, and a token is an identifier a ruling
 * names — not a naming convention to be tidied into line. Recorded here so the
 * divergence reads as deliberate rather than as a slip somebody should "fix".
 */
export const DENIAL_QUOTE_NOT_SELF_NEGATING = 'denial_quote_not_self_negating';

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
// mean the fill is broken (`denial_withheld_quote_not_dictated`,
// `…_quote_empty_after_heading_strip`, `…_quote_unrenderable`,
// `…_multiple_distinct_quotes`, `…_no_cited_denial`,
// `…_kind_cannot_carry_denial`, `…_fact_not_denied`). Those must keep blocking.
//
// ⚠️ `denial_withheld_repeating_rows_assert_presence` IS DELIBERATELY ABSENT,
// AND IT IS AN OPEN QUESTION RATHER THAN A DECISION. It is rule-(2)-shaped by
// the same "a row asserts presence" logic as the selection token, but #157(c)
// says "*the* selection-shaped withholding", singular, and the text does not
// settle whether the repeating-row token joins it. Anything the ruling does not
// name is a decision being MADE, not one that was GIVEN — and the safe
// direction for a certificate is to keep blocking, because blocking costs a
// certificate and exempting can attest a hole. Flagged upward, not resolved
// here.
export const CERTIFICATION_EXEMPT_DENIAL_REASONS: ReadonlySet<string> = new Set([
  'denial_withheld_value_only',
  'denial_withheld_affirmative_only',
  'denial_withheld_selection_asserts_presence',
  DENIAL_QUOTE_NOT_SELF_NEGATING,
]);

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
  // ⚠️ #157(c) Q1 — THE WALL R1 WALKS INTO. A denied fact whose PRINTED text
  // carries no negation scoping the finding renders BLANK. This is the second
  // and independent placement of the discriminator: the strip guard above
  // PRESERVES a print, this one REFUSES one, and neither substitutes for the
  // other. It is tested against `text` — what would actually reach the
  // document — so a negation destroyed by ANY means, anticipated or not, fails
  // here rather than reaching a signature.
  if (selfNegationScopingFinding(text, fact.value) === null) {
    return withheld(DENIAL_QUOTE_NOT_SELF_NEGATING);
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
//   affirmed                  -> its DERIVED VALUE (`deriveFieldValueFromFact`,
//                                the same function the validator re-derives
//                                with, so the two cannot disagree)
//   denied, self-negating     -> its QUOTE, per Q1
//   denied, not self-negating -> NOTHING, and its reason token rides on the
//                                resolution's own `reasonCode`
//
// ⚠️ TWO REGISTERS IN ONE SECTION, AND IT IS DELIBERATE RATHER THAN OVERLOOKED.
// The affirmed side prints a VALUE and the denied side prints a QUOTE, so a
// mixed field reads "Pneumonia; No evidence of pulmonary embolism." That is
// honest — every character came from the encounter — and it is an OWNER-VISIBLE
// product decision, recorded here and surfaced in the slice report rather than
// buried. The alternative (printing the affirmed quotes too) would restate a
// whole sentence for every entity and is a bigger change than this ruling asks.
//
// ⚠️ AND THE ZERO-COMPOSITION ASSERTION CANNOT BE APPLIED TO THE WHOLE FIELD —
// the joined output is a substring of no single quote. The property is asserted
// PER SEGMENT by the gate: each denied segment is a suffix of its own fact's
// quote, each affirmed segment is exactly its own fact's derived value, and the
// only house-authored characters in the whole string are the separator the
// affirmed path has always used.
//
// ⚠️ THE INVARIANT THAT KEEPS THIS FROM WIDENING ANYTHING: THE MIXED PATH NEVER
// DOES BETTER FOR THE AFFIRMED SET THAN THE AFFIRMED-ONLY PATH WOULD. If two
// distinct affirmed values would have conflicted on this field (a narrative
// that is not an accumulating SECTION), the mixed case REFUSES and falls back
// to the conflict it already was. Removing a denial from the picture can never
// turn a rejected fill into an accepted one.
export type MixedPolarityOutcome =
  | {
      readonly kind: 'text';
      readonly text: string;
      readonly reasonCode: string;
      /** Distinct reason tokens of the denials that contributed nothing. */
      readonly withheldReasonCodes: readonly string[];
    }
  | { readonly kind: 'refused' };

/** The reason token a per-fact mixed resolution carries. */
export const MIXED_POLARITY_REASON = 'mixed_polarity_per_fact';

const MAX_REASON_CODE_CHARACTERS = 120;

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

  // ⚠️ LATERALITY ACROSS *ALL* CITED FACTS, WHICH IS STRICTER THAN
  // `joinListValuedNarrative`'s OWN GUARD, AND ON PURPOSE. That function only
  // sees the facts it joins; here a left-leg affirmation and a right-leg denial
  // would be merged into one unattributed section with nothing else watching —
  // `mapping.laterality` is `optional` or null on narrative mappings, so the
  // resolver's laterality arm never fires.
  const lateralities = new Set(
    facts
      .map((fact) => fact.laterality)
      .filter((side) => side !== 'not_applicable' && side !== 'unknown'),
  );
  if (lateralities.size > 1) return mixedRefused();

  const segments: string[] = [];
  const withheldReasonCodes: string[] = [];
  const affirmedSegments: string[] = [];

  for (const fact of facts) {
    if (fact.polarity === 'affirmed') {
      const derived = deriveFieldValueFromFact(field, mapping, fact);
      // A cited fact that does not derive would be DROPPED from a section the
      // note presents as complete, and the validator — which re-derives with
      // this same function — would accept the loss. Refuse the whole thing.
      if (derived === null) return mixedRefused();
      const text = String(derived).trim();
      if (!text) continue;
      if (!affirmedSegments.includes(text)) affirmedSegments.push(text);
      if (!segments.includes(text)) segments.push(text);
      continue;
    }
    // The denied side is decided by the SAME rule (4) split the all-denied path
    // uses, so a `value_only` or `affirmative_only` mapping withholds here for
    // the identical reason it withholds there.
    const one =
      mapping?.polarityBehavior === 'explicit_denial_allowed'
        ? dictatedDenialText(fact)
        : withheld(
            mapping?.polarityBehavior === 'affirmative_only'
              ? 'denial_withheld_affirmative_only'
              : 'denial_withheld_value_only',
          );
    if (one.kind === 'withheld') {
      if (!withheldReasonCodes.includes(one.reasonCode)) {
        withheldReasonCodes.push(one.reasonCode);
      }
      continue;
    }
    if (!segments.includes(one.text)) segments.push(one.text);
  }

  // ⚠️ THE NEVER-BETTER-THAN-AFFIRMED-ALONE INVARIANT. Two distinct affirmed
  // values on a narrative that is not an accumulating SECTION are a genuine
  // conflict — `multiple_distinct_supported_values` — and they stay one.
  if (affirmedSegments.length > 1 && !isListValuedNarrative(field, mapping)) {
    return mixedRefused();
  }
  if (segments.length === 0) return mixedRefused();

  const text = segments.join(NARRATIVE_LIST_SEPARATOR);
  if (
    text.length > MAX_DENIAL_QUOTE_CHARACTERS ||
    INVALID_XML_CHARACTER_RE.test(text)
  ) {
    // Same ceiling as a single denial quote, for the same reason: the renderer
    // refuses above its own limit and rule (3) forbids a denial refusing an
    // export. Falling back to the conflict is not ideal, but it is the state
    // this field was already in.
    return mixedRefused();
  }

  const composed =
    withheldReasonCodes.length === 0
      ? MIXED_POLARITY_REASON
      : `${MIXED_POLARITY_REASON}:${withheldReasonCodes.join(',')}`;
  // A TRUNCATED TOKEN IS A LIE. If the composed reason cannot fit the schema's
  // ceiling, name the SHAPE instead of half-naming the reasons.
  const reasonCode =
    composed.length <= MAX_REASON_CODE_CHARACTERS
      ? composed
      : `${MIXED_POLARITY_REASON}:denials_withheld`;

  return { kind: 'text', text, reasonCode, withheldReasonCodes };
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
        material.get(resolution.fieldId) === true &&
        // ⚠️ #157(c) Q2 — THE SEAM. This predicate never read `reasonCode`, so a
        // blank the ruling APPROVES blocked certification exactly as hard as a
        // blank that means the fill is broken.
        !CERTIFICATION_EXEMPT_DENIAL_REASONS.has(resolution.reasonCode),
    )
    .map((resolution) => resolution.fieldId);
}
