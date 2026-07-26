// ============================================================================
// Bridge evidence matcher — real citations, or nothing.
// ----------------------------------------------------------------------------
// Both bridges used to MINT provenance: a bridged value was written
// `status: 'supported'` citing a placeholder fact id
// (`ttfact_000000000000000000000000`) and a placeholder anchor
// ('choice-slot-pick' / 'table-cell-measurement'). Neither existed in the fact
// set, so validateTemplateTwin rejected every bridged value —
// SOURCE_FACT_MISSING, EVIDENCE_ANCHOR_UNTRACEABLE, ASSERTION_NOT_SUPPORTED.
// Because prepareTemplateTwinFill is shared, that rejection happened on the
// VISIT path too, which is why bridged measurements have never actually
// reached a rendered document.
//
// The bridge is now a MATCHER, not a stamper. The generated note and the
// EncounterFacts come from the SAME transcript, so anything the doctor really
// dictated appears in both: a genuinely dictated value HAS a fact to cite. If
// no fact supports a candidate, the honest answer is a blank cell with a named
// reason — not a fabricated citation.
//
// That is also why this cannot be solved by relaxing the validator: the check
// is what stops an unevidenced number reaching a signed document.
// ============================================================================

import type { EncounterFact, SemanticMapping } from './ir';

/** Same normalisation validation/index.ts uses — a citation this module makes
 *  must satisfy the check the validator will later apply, or the bridge is just
 *  producing a different flavour of unsupported assertion. */
function normalizeConcept(value: string): string {
  // Byte-for-byte the validator's normalisation. If these ever diverge the
  // bridge starts citing facts the validator rejects.
  return value.normalize('NFKC').trim().toLocaleLowerCase('en-US');
}

/**
 * The validator's own rule (factMatchesMapping): the fact's concept must BE the
 * mapping's concept or an approved synonym, and temporality must agree. The
 * bridge applies it up front so it can only ever cite a fact the validator will
 * accept — otherwise a "real" citation still fails as
 * SOURCE_FACT_CONCEPT_MISMATCH, which is exactly what the first matcher run hit.
 */
function factSatisfiesMapping(fact: EncounterFact, mapping: SemanticMapping): boolean {
  if (!mapping.clinicalConcept) return false;
  const concepts = new Set(
    [mapping.clinicalConcept, ...mapping.approvedSynonyms].map(normalizeConcept),
  );
  if (!concepts.has(normalizeConcept(fact.concept))) return false;
  if (
    mapping.temporality !== null &&
    mapping.temporality !== 'any' &&
    fact.temporality !== mapping.temporality
  ) {
    return false;
  }
  return true;
}

/** Why a candidate produced no citation. Named, never silent. */
export type BridgeMatchFailure =
  | 'no_supporting_fact'
  | 'ambiguous_laterality'
  | 'laterality_mismatch'
  | 'row_laterality_unknown'
  | 'ambiguous_candidates';

export interface BridgeMatch {
  fact: EncounterFact;
  /** Laterality taken FROM the matched fact — never inferred from position. */
  laterality: EncounterFact['laterality'];
}

export type BridgeMatchResult =
  | { ok: true; match: BridgeMatch }
  | { ok: false; reason: BridgeMatchFailure };

const norm = (s: string) =>
  foldAnatomy(s)
    .replace(/[^a-z0-9]+/g, ' ')
    .trim();

/**
 * ABBREVIATION <-> SPOKEN-FORM FOLD (addressing only).
 *
 * The template's row label says "GSV at the SFJ". The dictation — and therefore
 * the fact — says "great saphenous vein at the saphenofemoral junction". Both
 * name the same anatomy, and without a fold every measurement fact misses its
 * row while looking, from the logs, exactly like missing evidence.
 *
 * Found by the Stage-1 eval, which scored 0/8 on segments for precisely this
 * reason before the scorer learned the same fold.
 *
 * This is ADDRESSING: it decides which row a fact is offered to. It does not
 * decide whether the value is written — that still requires the fact to satisfy
 * factSatisfiesMapping and to match numerically, both untouched.
 *
 * Code-defined and enumerated on purpose: a fuzzy matcher here would quietly
 * align "SSV" with "GSV" one day.
 */
const ANATOMY_FOLD: ReadonlyArray<readonly [RegExp, string]> = [
  [/anterior accessory great saphenous vein/g, 'aagsv'],
  [/posterior accessory great saphenous vein/g, 'pagsv'],
  [/great saphenous vein/g, 'gsv'],
  [/small saphenous vein/g, 'ssv'],
  [/saphenofemoral junction/g, 'sfj'],
  [/saphenopopliteal junction/g, 'spj'],
  [/perforator vein/g, 'perforator'],
];

/** Fold spoken anatomy to the abbreviations templates use. Idempotent: applying
 *  it to already-abbreviated text is a no-op. */
export function foldAnatomy(text: string): string {
  return ANATOMY_FOLD.reduce(
    (acc, [pattern, abbrev]) => acc.replace(pattern, abbrev),
    text.toLocaleLowerCase('en-US'),
  );
}

/** Vein/segment tokens worth aligning on; generic words would match anything. */
const STOP = new Set([
  'the', 'at', 'of', 'and', 'vein', 'veins', 'leg', 'reflux', 'time', 'diameter',
  'sec', 'secs', 'seconds', 'mm', 'cm', 'level', 'junction',
]);

function tokens(label: string): string[] {
  return norm(label)
    .split(' ')
    .filter((t) => t.length > 1 && !STOP.has(t));
}

/** Congruent when the fact's concept/value mentions the row's vein/segment. */
function segmentCongruent(label: string, fact: EncounterFact): boolean {
  const want = tokens(label);
  if (want.length === 0) return false;
  // The EVIDENCE QUOTE is part of the haystack because anatomy is deliberately
  // NOT baked into the concept string — a measurement fact's concept is its
  // KIND ("measurement.diameter") and the segment travels as data, with its
  // spoken form in the quote. Reading the quote here is addressing, not
  // evidence: it decides which row the fact is offered to, never whether the
  // value is written.
  const hay = `${norm(fact.concept)} ${norm(String(fact.value ?? ''))} ${norm(fact.evidenceQuote ?? '')}`;
  return want.some((t) => hay.includes(t));
}

function numbersEqual(a: number, b: number): boolean {
  // Exact to the precision either side carries — a bridged measurement must be
  // the SAME number the transcript produced, not a rounding of it.
  return Math.abs(a - b) < 1e-9;
}

/**
 * Match a measurement candidate to a real fact.
 *
 * Requires numeric identity AND vein/segment congruence. Laterality is read
 * off the matched fact; when two facts match the same number and segment with
 * DIFFERENT sides, the cell is refused rather than guessed — putting a right-leg
 * measurement in a left-leg row is precisely the error that must never ship.
 */
export function matchMeasurementFact(input: {
  value: string;
  segmentLabel: string;
  facts: readonly EncounterFact[];
  /** The field's approved mapping — the citation must satisfy it. */
  mapping?: SemanticMapping;
  /** The ROW's laterality, stamped at compile time from the document's own leg
   *  headings. Addressing is FAIL-CLOSED on it: a sided fact may only fill a
   *  same-sided row, and an unmarked row may never silently accept a sided
   *  value. Omitted (legacy callers) means no row-side constraint. */
  rowLaterality?: 'right' | 'left' | 'unknown';
}): BridgeMatchResult {
  const n = Number(input.value);
  if (!Number.isFinite(n)) return { ok: false, reason: 'no_supporting_fact' };

  const candidates = input.facts.filter(
    (f) =>
      f.polarity === 'affirmed' &&
      typeof f.number === 'number' &&
      numbersEqual(f.number, n) &&
      segmentCongruent(input.segmentLabel, f) &&
      (!input.mapping || factSatisfiesMapping(f, input.mapping)),
  );
  if (candidates.length === 0) return { ok: false, reason: 'no_supporting_fact' };

  const sides = new Set(candidates.map((f) => f.laterality));
  if (sides.size > 1) return { ok: false, reason: 'ambiguous_laterality' };

  const fact = candidates[0]!;
  if (fact.laterality === 'unknown') return { ok: false, reason: 'ambiguous_laterality' };

  // FAIL-CLOSED ROW CONGRUENCE. A right-leg measurement in a left-leg row is
  // the error this whole chain exists to prevent, and it would pass silently:
  // the value is real, the citation is real, only the ROW is wrong.
  if (input.rowLaterality !== undefined) {
    const sidedFact = fact.laterality === 'left' || fact.laterality === 'right';
    if (input.rowLaterality === 'unknown') {
      // An unmarked row cannot accept a sided value. The document gave no leg
      // signal, so filling here would be a guess wearing a citation.
      if (sidedFact) return { ok: false, reason: 'row_laterality_unknown' };
    } else if (!sidedFact || fact.laterality !== input.rowLaterality) {
      // Includes a bilateral/not_applicable fact offered to a sided row.
      return { ok: false, reason: 'laterality_mismatch' };
    }
  }

  return { ok: true, match: { fact, laterality: fact.laterality } };
}

/**
 * Match a CHOICE_SLOT pick to a real fact.
 *
 * The selected option must be ENTAILED by a fact: the note and the facts come
 * from one transcript, so a genuinely dictated pick is expressed in both. A
 * pick the model chose without dictated support has nothing to cite and is
 * refused — the constrained-fill invariants (template options only, blank when
 * unsaid, nothing invented) are unchanged; this only adds the citation.
 */
export function matchPickFact(input: {
  optionText: string;
  facts: readonly EncounterFact[];
  /** The field's approved mapping — the citation must satisfy it. */
  mapping?: SemanticMapping;
}): BridgeMatchResult {
  const want = norm(input.optionText);
  if (!want) return { ok: false, reason: 'no_supporting_fact' };
  const wantTokens = tokens(input.optionText);

  const candidates = input.facts.filter((f) => {
    if (f.polarity !== 'affirmed') return false;
    if (input.mapping && !factSatisfiesMapping(f, input.mapping)) return false;
    const hay = `${norm(String(f.value ?? ''))} ${norm(f.concept)}`;
    // Forward containment only: the FACT must carry the option, never the
    // reverse. Accepting `want.includes(factValue)` would let a vaguer fact
    // ("lower extremities") satisfy a far more specific option ("chronic
    // venous hypertension with other complications of bilateral lower
    // extremities") — silently upgrading a loose finding into a diagnosis.
    // Caught by the partial-overlap canary below.
    if (hay.includes(want)) return true;
    // Otherwise require EVERY distinctive token of the option to be present.
    return wantTokens.length > 0 && wantTokens.every((t) => hay.includes(t));
  });
  if (candidates.length === 0) return { ok: false, reason: 'no_supporting_fact' };

  return { ok: true, match: { fact: candidates[0]!, laterality: candidates[0]!.laterality } };
}

/** The citation a matched fact licenses. Real ids only — this is the whole point. */
export function citationOf(match: BridgeMatch): {
  sourceFactIds: string[];
  evidenceAnchorIds: string[];
} {
  return {
    sourceFactIds: [match.fact.factId],
    evidenceAnchorIds: [...match.fact.evidenceAnchorIds],
  };
}
