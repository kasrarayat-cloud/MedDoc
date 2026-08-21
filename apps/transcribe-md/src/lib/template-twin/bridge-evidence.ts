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
  //
  // ⚠️ F5-e: `fact.segment` IS THE AUTHORITATIVE TERM HERE, AND IT IS READ
  // FIRST BECAUSE THE QUOTE IS ONLY A PROXY FOR IT.
  //
  // L3 extracts the segment per measurement as REQUIRED data and emits one
  // entry per number, so both halves of "Right GSV at the SFJ: diameter 3.10
  // millimeters, reflux time 0.110 seconds" name the vessel. Only the DIAMETER
  // half says so in its quote. Reading prose alone therefore answered this
  // question correctly for one column and blindly for the other — 0 of 20
  // reflux quotes carried anatomy on production's own manifest, so every reflux
  // cell refused and the doctor's table rendered blank down that column.
  //
  // ⚠️ THIS WIDENS THE HAYSTACK, so it can only ever produce MORE matches. That
  // is the direction that fills a WRONG row, and it is defensible only because
  // the added term is the structured answer to the exact question being asked,
  // not a looser reading of the same prose. The vessel-identity arms in
  // `gate-f5e-*` pin BOTH directions (a GSV row must not bind an AAGSV fact,
  // and vice versa) precisely so this widening cannot rot into a wrong-vessel
  // citation on a signed document.
  const hay = `${norm(fact.segment ?? '')} ${norm(fact.concept)} ${norm(String(fact.value ?? ''))} ${norm(fact.evidenceQuote ?? '')}`;
  // ⚠️ WHOLE TOKENS, NEVER `hay.includes(t)` — THE ABBREVIATIONS NEST.
  //
  // `'aagsv'.includes('gsv')` is true, so a substring test made a **GSV Below
  // Knee** row congruent with an **AAGSV at the Proximal Thigh** fact: a
  // different vessel at a different level, sharing nothing but a suffix. Only
  // numeric equality and laterality stood between that and a wrong-vessel value
  // in a signed document, and neither is a vessel check.
  //
  // Pre-existing, and F5-e is why it is fixed HERE: adding `segment` widens this
  // haystack, and widening a predicate with a known substring hole extends the
  // hole to the reflux column rather than leaving it where it was. This is the
  // STRICTER direction — it can only remove matches, never add them.
  //
  // ⚠️ AND THE STEM IS WHY THIS IS NOT A BARE EQUALITY. Whole-token matching
  // alone is stricter in a way that BREAKS a real case: a row labelled
  // "Perforator" stops matching a fact whose segment says "perforators", which
  // the substring test used to catch. The imaging vocabulary this product steers
  // the model toward uses the PLURAL — `specialty-guidance.ts:119` ("GSV / SSV /
  // perforators") and `ultrasound-report-template.ts:150` ("Perforators:
  // location …") — so that is the expected dictation, not an edge case.
  //
  // Not reachable on production's only certified template today (measured: 0 of
  // its 80 field labels mention a perforator), and fixed anyway, because the
  // next form is not this form and a silent blank column is exactly the failure
  // F5-e already cost. Stemming a trailing plural keeps the nesting fix intact —
  // `gsv` and `aagsv` are still different tokens.
  const stem = (t: string) => (t.length > 3 && t.endsWith('s') ? t.slice(0, -1) : t);
  const hayTokens = new Set(hay.split(' ').map(stem));
  return want.some((t) => hayTokens.has(stem(t)));
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

  if (input.rowLaterality !== undefined) {
    const verdict = rowLateralityVerdict(fact, input.rowLaterality);
    if (verdict !== 'ok') return { ok: false, reason: verdict };
  }

  return { ok: true, match: { fact, laterality: fact.laterality } };
}

/**
 * FAIL-CLOSED ROW CONGRUENCE. A right-leg measurement in a left-leg row is the
 * error this whole chain exists to prevent, and it would pass silently: the
 * value is real, the citation is real, only the ROW is wrong.
 *
 * Exported because the resolver needs the SAME rule. It did not have it, and
 * that is how three right-leg reflux cells were filled from left-leg facts and
 * only caught downstream as ASSERTION_NOT_SUPPORTED — the bridge refused them,
 * the resolver baseline underneath did not. One rule, both callers.
 */
export function rowLateralityVerdict(
  fact: Pick<EncounterFact, 'laterality'>,
  rowLaterality: 'right' | 'left' | 'unknown',
): 'ok' | 'laterality_mismatch' | 'row_laterality_unknown' {
  const sidedFact = fact.laterality === 'left' || fact.laterality === 'right';
  if (rowLaterality === 'unknown') {
    // An unmarked row cannot accept a sided value. The document gave no leg
    // signal, so filling here would be a guess wearing a citation.
    return sidedFact ? 'row_laterality_unknown' : 'ok';
  }
  // Includes a bilateral/not_applicable fact offered to a sided row.
  return sidedFact && fact.laterality === rowLaterality ? 'ok' : 'laterality_mismatch';
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
