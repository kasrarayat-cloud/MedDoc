// ============================================================================
// Deterministic lane-capture + conservation matching (gate instrument fix,
// 2026-06-12 — see docs/eval-runs/gate-instrument-validity-note-20260612*.md).
// ----------------------------------------------------------------------------
// Run-3 forensics: the single-pass Gate-2 completeness judge listed facts as
// "material omissions" that were LITERALLY in the suggestions lane it was
// shown ("Patient lives with his wife" flagged while lane item 4 was
// "- Lives with his wife."). The pre-registered addendum defines a material
// omission as absent from the new body AND not in the lane — this module
// enforces the lane clause (and a baseline-conservation diagnostic)
// DETERMINISTICALLY instead of trusting an LLM to apply it. The rubric and
// the pre-registered bars are unchanged; this fixes the instrument.
// ============================================================================

const STOPWORDS = new Set([
  'the', 'and', 'for', 'with', 'was', 'were', 'has', 'have', 'had', 'this',
  'that', 'are', 'is', 'not', 'his', 'her', 'their', 'they', 'she', 'him',
  'its', 'per', 'into', 'onto', 'from', 'been', 'being', 'will', 'would',
  'should', 'could', 'than', 'then', 'when', 'where', 'which', 'who',
  'patient', 'patients', 'reports', 'reported', 'states', 'stated', 'denies',
  'denied', 'notes', 'noted', 'documented',
]);

/** Content tokens: digits + words len ≥3, normalized, stopwords removed.
 *  Clinical register words ("patient", "reports") are stopworded so a fact
 *  matches its lane phrasing ("Patient lives with his wife" ↔ "- Lives with
 *  his wife."). */
export function contentTokens(s: string): string[] {
  const toks =
    s
      .toLowerCase()
      .replace(/[^a-z0-9\s]/g, ' ')
      .match(/[a-z0-9]+/g) ?? [];
  return toks.filter(
    (t) => (/\d/.test(t) || t.length >= 3) && !STOPWORDS.has(t)
  );
}

/** Token equivalence: exact, or shared 5-char prefix for ≥5-char words —
 *  the same stemming-lite rule the verifier's negation override uses
 *  ("allergy" ↔ "allergies", "blocked" ↔ "blockage"). */
function tokenMatches(a: string, b: string): boolean {
  if (a === b) return true;
  if (/\d/.test(a) || /\d/.test(b)) return false; // digits match exactly only
  return a.length >= 5 && b.length >= 5 && a.slice(0, 5) === b.slice(0, 5);
}

/** Fraction of `factTokens` present in `bag` (prefix-5 equivalence). */
export function tokenCoverage(factTokens: string[], bag: string[]): number {
  if (factTokens.length === 0) return 0;
  let hit = 0;
  for (const f of factTokens) {
    if (bag.some((b) => tokenMatches(f, b))) hit++;
  }
  return hit / factTokens.length;
}

export const CAPTURE_THRESHOLD = 0.5;

/** HARD DIGIT VETO: if the fact carries digit tokens, EVERY one must appear
 *  exactly in the candidate bag — token overlap can never "capture" a fact
 *  whose numbers differ ("Aspirin 300 mg" vs the 75 mg lane item). */
function digitVeto(factTokens: string[], bag: string[]): boolean {
  return factTokens
    .filter((t) => /\d/.test(t))
    .every((d) => bag.includes(d));
}

export interface LaneItem {
  text: string;
  section?: string;
}

/** Is `fact` represented by ANY lane item (text + its section label)?
 *  The section matters: the lane shows "- Penicillin (reaction not
 *  stated)." under section "Drug Allergies" — without it, "Allergy to
 *  penicillin" has only the drug token in common. */
export function laneCaptured(fact: string, lane: LaneItem[]): boolean {
  const factTokens = contentTokens(fact);
  if (factTokens.length === 0) return false;
  return lane.some((item) => {
    const bag = contentTokens(`${item.text} ${item.section ?? ''}`);
    return (
      digitVeto(factTokens, bag) &&
      tokenCoverage(factTokens, bag) >= CAPTURE_THRESHOLD
    );
  });
}

/** Is `fact` represented in the body? Matched against each line and each
 *  pair of consecutive lines (facts often wrap), never the whole-note bag
 *  (token scatter would false-conserve). */
export function bodyCaptured(fact: string, body: string): boolean {
  const factTokens = contentTokens(fact);
  if (factTokens.length === 0) return false;
  const lines = body.split('\n').map((l) => l.trim()).filter(Boolean);
  for (let i = 0; i < lines.length; i++) {
    const single = contentTokens(lines[i]);
    if (
      digitVeto(factTokens, single) &&
      tokenCoverage(factTokens, single) >= CAPTURE_THRESHOLD
    )
      return true;
    if (i + 1 < lines.length) {
      const pair = contentTokens(`${lines[i]} ${lines[i + 1]}`);
      if (
        digitVeto(factTokens, pair) &&
        tokenCoverage(factTokens, pair) >= CAPTURE_THRESHOLD
      )
        return true;
    }
  }
  return false;
}

export interface ConservationResult {
  /** Baseline content lines checked. */
  total: number;
  /** Lines found in new body ∪ lane. */
  conserved: number;
  /** Baseline lines in NEITHER body nor lane — the silent-loss list. */
  violations: string[];
}

/** Deterministic conservation check: every content line of the flag-off
 *  BASELINE note must appear in the new body OR the suggestions lane.
 *  Headers, blanks, and "[not documented]" placeholders are skipped; so are
 *  lines with <3 content tokens (single-word fragments can't be matched
 *  meaningfully). Diagnostic — Gate-2's judge decides transcript support;
 *  this catches silent loss judge-free. */
export function conservationCheck(
  baselineNote: string,
  newBody: string,
  lane: LaneItem[]
): ConservationResult {
  const violations: string[] = [];
  let total = 0;
  for (const raw of baselineNote.split('\n')) {
    const line = raw.trim();
    if (!line) continue;
    if (/^#{1,6}\s/.test(line)) continue;
    if (/^\*\*[^*]+\*\*:?\s*$/.test(line)) continue;
    if (/\[not documented\]/i.test(line)) continue;
    const toks = contentTokens(line);
    // ≥2 content tokens: "- Penicillin allergy." is checkable; bare
    // single-word fragments ("Stable.") are not.
    if (toks.length < 2) continue;
    total++;
    if (!bodyCaptured(line, newBody) && !laneCaptured(line, lane)) {
      violations.push(line);
    }
  }
  return { total, conserved: total - violations.length, violations };
}
