// ============================================================================
// WHAT A CAPTION *IS* — one definition, two readers.
// ----------------------------------------------------------------------------
// A bilateral study renders one table per leg with identical row labels. The
// only thing that says WHICH leg is the short line above the table, and two
// separate modules read it:
//
//   note-table-edit.ts   -> narrows an edit to one table   (a CLINICAL WRITE)
//   claim-prose.ts       -> labels a card with its leg     (a CLINICAL READ)
//
// They held two definitions between them, and `note-table-edit.ts`'s own
// comment had named that as "a wrong-table edit waiting to happen" for two days
// before anything shared the code. This module is the single definition.
//
// ⚠️ AND THE DIVERGENCE WAS REAL, NOT THEORETICAL — found by writing this file.
// The two `cells()` helpers disagree about a ONE-CELL pipe row: this module's
// editor treats any `| … |` line as a table row (never a caption), while
// `claim-prose`'s requires `>= 2` cells, so `| Right Leg |` was NOT a caption
// to the writer and WAS a caption to the reader. Unified on the stricter rule.
// Measured cost on production: zero — 0 of 45 headers carry a pipe row of any
// arity as their caption candidate.
//
// ── THE SHAPE OF THE FIX: THE BLANK LINE IS THE THING BEING PAID FOR ────────
//
// Two attempts to improve caption reach have been withdrawn, and both failed
// the same way — F24 Slice 1b reached ONE BLANK LINE FURTHER with no test of
// what it found, and reproduced this on the real function:
//
//     The right leg was normal; the left GSV is dilated.
//                                   <- one blank line
//     |  | DIAMETER (mm) | ... |    <- table 2, the LEFT leg
//     | GSV at the SFJ | 6.2 | 3.4 |
//
//   editTableCell(row 'GSV at the SFJ', tableCaption 'Right Leg', 6.8)
//     -> ok=true, before="6.2", the LEFT leg written, reported as success
//
// A WRONG-LEG MEASUREMENT IS WORSE THAN AN UNEDITABLE TABLE. So the question is
// not "how far up do we look" — it is "what is the EVIDENCE that this line
// belongs to this table", and the two slots have different answers:
//
//   ADJACENT (no blank between)  — the line is STRUCTURALLY BOUND to the table.
//                                  Nothing separates them; markdown renders
//                                  them as one block. Accepted on the legacy
//                                  rule, UNCHANGED.
//
//   ONE BLANK UP                 — the blank IS a paragraph break. It is
//                                  positive evidence that the line beyond it is
//                                  a SEPARATE block, so it must earn the label
//                                  by SHAPE. Previously always null.
//
// ⚠️ THE ASYMMETRY IS THE ARGUMENT, NOT A COMPROMISE. Validating the adjacent
// slot too was built first and WITHDRAWN THE SAME HOUR, because it removed a
// capability the product supports and tests: `DIAMETER AND REFLUX TIME — Right
// Leg` is SEVEN words, `claim-prose`'s tail-split exists specifically to
// display it, and a 4-word shape rule refused it — reddening four arms that had
// nothing to do with this item. **A production census over 49 notes measured
// zero titled captions and therefore could not see that the SUPPORTED shape
// space is wider than the OBSERVED one.** Restricting a working path on a
// population measurement is an accepted-capability loss, which is not this
// loop's to take.
//
// ── THE PREDICATE FOR THE NEW SLOT, AND EVERY CLAUSE IS MEASURED ────────────
//
// Measured on production 2026-08-23, read-only, counts only — 45 table headers
// across 49 notes. The partition reconciles:
//
//     16 heading-above  +  9 text-above  +  2 heading-beyond-blank
//   +  2 pipe-row-beyond-blank  +  16 TEXT-ONE-BLANK-UP            =  45
//
// and independently reproduces the recon's traversal control exactly
// (49 notes / 2,329 lines / 531 pipe rows / 45 alignment rules).
//
// Over the 25 text candidates (9 adjacent + 16 one-blank-up):
//
//   | clause                          | observed                       |
//   |---------------------------------|--------------------------------|
//   | <= 4 words                      | max 4.  25 of 25 pass          |
//   | <= 48 characters                | max 24. 25 of 25 pass          |
//   | no sentence punctuation . ; ! ? | 0 of 25 carry any              |
//   | not BOTH 'left' and 'right'     | 0 of 25 carry both             |
//
// A colon is FINE and deliberately permitted — 11 of 25 carry one, because the
// production shape is `Right Leg:`. A comma is not tested for: the 4-word cap
// already refuses every clause a comma appears in, and each extra clause is one
// more way to refuse a caption somebody legitimately writes.
//
// ⚠️ THE WITHDRAWN COUNTEREXAMPLE FAILS THREE OF THE FOUR — 9 words, both sides
// named, and sentence punctuation. It is not a near miss.
//
// ⚠️ THESE THRESHOLDS ARE A FACT ABOUT TODAY'S CORPUS, NOT A PROPERTY OF
// CAPTIONS, and the titled-caption miss above is the proof that the two differ.
// They bound the NEW slot only, where the alternative is not "a looser rule" but
// "no capability at all" — so a threshold that is too strict costs a refusal
// that already happens today, and cannot remove anything.
// RETIREMENT CONDITION, so this stays a lookup rather than a judgement:
// re-measure when a SECOND template shape certifies end-to-end (RELAY F5-i),
// because that is the event that changes what a caption looks like here.
//
// ── THE ERROR DIRECTIONS ARE NOT SYMMETRIC, AND THAT SETS EVERY THRESHOLD ───
//
// Canon, *ERR TOWARD THE EDGE — THE EDGE HAS A FENCE*:
//
//   too STRICT -> a real caption is refused -> `caption_not_found`, which is
//                 EXACTLY today's behaviour on this slot. The doctor retypes.
//   too LOOSE  -> narrative becomes a caption -> a measurement written into the
//                 other leg and reported as success. Silent, and wrong.
//
// ⚠️ AND IT IS EXACTLY ONE BLANK LINE. Two blanks, a heading beyond the blank,
// or a pipe row beyond the blank all return null — that is the remaining 4 of
// the 20 blocked headers, and no caption strategy can serve them. Widening to a
// RUN of blanks would buy 0 measured headers and re-open the distance question
// this file exists to close.
//
// ── WHAT THIS FILE DOES NOT CLAIM ───────────────────────────────────────────
//
// - It does NOT make the adjacent slot safer. A line naming BOTH legs directly
//   above a table still mis-narrows, exactly as it does on `main`. Measured
//   2026-08-23: production holds **0 of 8** such lines, so the path is real and
//   currently UNEXERCISED; ONE note whose narrative names both legs directly
//   above a table re-arms it with no code change anywhere. Closing it costs the
//   titled-caption capability above and is filed, not fixed.
// - It does NOT ask the twin. `rendererBinding.rowLaterality` knows a real side
//   for 52 of 52 table cells, and the recon measured its incremental reach over
//   a validated read at **0 headers today** — 2 of the 20 blocked are on the
//   certified template and both are in the one-blank-up bucket this serves.
// ============================================================================

/** `## HEADING` — never a caption. */
const HEADING_RE = /^\s*#{1,6}\s/;

/**
 * Any line opening a pipe cell — a table row is never a caption.
 *
 * ⚠️ ARITY-BLIND ON PURPOSE. `claim-prose` used to require `>= 2` cells here
 * and this module's editor did not, so a one-cell `| Right Leg |` was a caption
 * to one reader and a table row to the other. The stricter rule wins: nothing
 * that opens with a pipe is prose.
 */
const PIPE_RE = /^\s*\|/;

/** Sentence punctuation. Prose has it; a caption does not. */
const SENTENCE_PUNCT_RE = /[.;!?]/;

/**
 * A laterality token on a word boundary.
 *
 * ⚠️ `\b` IS NOT USED, DELIBERATELY. `\bright\b` matches inside `right-sided` —
 * the hyphen is a non-word character — and this test decides whether a line
 * names one side or two. The explicit `[^a-z]` form treats a hyphenated
 * compound as one token, which is what a reader means by "names a side".
 */
const RIGHT_RE = /(^|[^a-z])right([^a-z]|$)/i;
const LEFT_RE = /(^|[^a-z])left([^a-z]|$)/i;

/** Observed max 4 across 25 of 25 production candidates. */
export const CAPTION_MAX_WORDS = 4;

/** Observed max 24 across 25 of 25 production candidates. */
export const CAPTION_MAX_CHARS = 48;

/**
 * Is this line structurally capable of being a caption at all?
 *
 * The legacy rule, shared so that both readers agree on it. Applies to BOTH
 * slots.
 */
function isCaptionEligible(raw: string): boolean {
  const line = raw.trim();
  if (!line) return false;
  if (HEADING_RE.test(line)) return false;
  if (PIPE_RE.test(line)) return false;
  return true;
}

/**
 * Does this line have the SHAPE of a table caption?
 *
 * Applied ONLY to the one-blank-up slot, where a paragraph break is positive
 * evidence that the line is a separate block. Fail-closed: anything
 * unrecognised is `false`, and `false` means "no caption", which is what that
 * slot already returned for every line.
 *
 * Exported so the guard drives the real predicate rather than a copy of it.
 */
export function isCaptionShaped(raw: string): boolean {
  if (!isCaptionEligible(raw)) return false;
  const line = raw.trim();

  if (line.length > CAPTION_MAX_CHARS) return false;
  if (SENTENCE_PUNCT_RE.test(line)) return false;

  const words = line.split(/\s+/).filter(Boolean);
  if (words.length > CAPTION_MAX_WORDS) return false;

  // ⚠️ BOTH SIDES NAMED IS THE MIS-NARROWING SHAPE, AND IT IS THE ONE CLAUSE
  // THAT IS ABOUT MEANING RATHER THAN SHAPE. The narrowing in
  // `note-table-edit.ts` is a SUBSTRING match, so a line carrying both tokens
  // matches a caller asking for EITHER one — which is precisely how a RIGHT-leg
  // correction reaches a LEFT-leg table. A line that cannot discriminate must
  // never be used to discriminate.
  if (RIGHT_RE.test(line) && LEFT_RE.test(line)) return false;

  return true;
}

/** `| --- | :--- |` — a table's alignment rule. A header is the row above one. */
const RULE_RE = /^\s*\|[\s:|-]+\|\s*$/;

/** The caption a slot yields, and WHICH slot yielded it. */
type Slot = 'adjacent' | 'one-blank-up';

function rawCandidate(lines: string[], headerIdx: number): { text: string; slot: Slot } | null {
  const adjacent = headerIdx - 1;
  if (adjacent < 0) return null;

  const a1 = lines[adjacent];
  if (a1 === undefined) return null;

  // SLOT 1 — structurally bound to the table. Legacy rule, unchanged.
  if (a1.trim()) {
    return isCaptionEligible(a1) ? { text: a1.trim(), slot: 'adjacent' } : null;
  }

  // SLOT 2 — across exactly one blank line. Must earn it by shape.
  const beyond = headerIdx - 2;
  if (beyond < 0) return null;
  const a2 = lines[beyond];
  if (a2 === undefined) return null;
  // A SECOND blank is not a paragraph break, it is distance. Nothing there
  // belongs to this table, whatever it says.
  if (!a2.trim()) return null;

  return isCaptionShaped(a2) ? { text: a2.trim(), slot: 'one-blank-up' } : null;
}

/**
 * Every table header in the same section as `headerIdx`.
 *
 * The section is bounded by the nearest heading above and the nearest heading
 * below, or by the ends of the array. That works for BOTH callers:
 * `note-table-edit` passes a section body that usually has no heading in it,
 * and `claim-prose` passes the whole note.
 */
function siblingHeaders(lines: string[], headerIdx: number): number[] {
  let from = 0;
  for (let i = headerIdx - 1; i >= 0; i -= 1) {
    if (HEADING_RE.test(lines[i] ?? '')) {
      from = i + 1;
      break;
    }
  }
  let to = lines.length - 1;
  for (let i = headerIdx + 1; i < lines.length; i += 1) {
    if (HEADING_RE.test(lines[i] ?? '')) {
      to = i - 1;
      break;
    }
  }
  const out: number[] = [];
  for (let i = from; i <= to; i += 1) {
    const line = lines[i];
    if (line === undefined) continue;
    if (!PIPE_RE.test(line)) continue;
    if (RULE_RE.test(line)) continue;
    if (RULE_RE.test(lines[i + 1] ?? '')) out.push(i);
  }
  return out;
}

/**
 * The caption for the table whose header is at `headerIdx`, or null.
 *
 * @param lines  the lines the caller is scanning. `note-table-edit` passes a
 *               SECTION BODY and `claim-prose` passes the whole note; neither
 *               can read across a heading, because a heading in either slot
 *               returns null.
 */
export function captionCandidate(lines: string[], headerIdx: number): string | null {
  const mine = rawCandidate(lines, headerIdx);
  if (!mine) return null;
  if (mine.slot === 'adjacent') return mine.text;

  // ⚠️ THE ONE-BLANK-UP SLOT ALSO REQUIRES THE SECTION TO BE UNIFORMLY
  // CAPTIONED, AND THIS FENCE EXISTS BECAUSE THE FIX WITHOUT IT WAS A
  // WRONG-LEG WRITE. Reproduced on the real function before it was added —
  // `gate-f24-caption-validation.test.ts`, "THE TRAILING-SUMMARY SHAPE":
  //
  //     ## FINDINGS
  //     |  | DIAMETER (mm) | ... |     <- table 1, the RIGHT leg, UNCAPTIONED
  //     | GSV at the SFJ | 5.1 | 0.3 | <- (a heading sits directly above it)
  //                                    <- blank
  //     Right leg normal               <- a SUMMARY OF TABLE 1. 3 words, one
  //                                    <- blank      side, no punctuation:
  //     |  | DIAMETER (mm) | ... |     <- table 2, the LEFT leg — and it reads
  //     | GSV at the SFJ | 6.2 | 3.4 |    that summary as ITS caption
  //
  //   editTableCell(row 'GSV at the SFJ', tableCaption 'Right Leg', 6.8)
  //     -> ok=true, before="6.2"   <- the LEFT leg. Reported as success.
  //
  // The shape rule cannot see this: `Right leg normal` is a perfectly
  // caption-shaped line. What is wrong is not the LINE, it is that it belongs
  // to the table ABOVE — and the only available evidence for that is that its
  // SIBLING has no caption at all. A section where one table is captioned and
  // another is not is not following a captioning convention; it is prose that
  // happens to sit in the right place.
  //
  // ⚠️ AND THE FENCE IS SOUND RATHER THAN FIXTURE-SHAPED. With it, a wrong
  // narrowing needs the CORRECT table's caption to miss while the WRONG one's
  // matches — but if both tables are captioned and the caller names a side,
  // the correct table's caption names that side too, so the narrowing resolves
  // to two candidates and refuses. Measured on production 2026-08-23:
  // **0 of 31 sections carry mixed caption availability**, and all 12 captioned
  // bilateral sections name exactly one `right` and one `left`. So this costs
  // nothing that exists today and closes a defect that would have shipped.
  //
  // It lives HERE, not in the two callers, because a per-caller list is kept
  // complete by hand and hand-kept lists are wrong eventually.
  // ⚠️ AND "EVERY TABLE HAS *A* CAPTION" WAS NOT ENOUGH — THE FIRST VERSION OF
  // THIS FENCE STILL WROTE THE WRONG LEG, AND THE PROBE THAT FOUND IT IS THE
  // ONE BELOW. A caption only helps if it DISCRIMINATES, and presence is not
  // discrimination:
  //
  //     ## FINDINGS
  //     Arterial                       <- table 1's caption. Names NO side.
  //     |  | DIAMETER (mm) | ... |     <- table 1, the RIGHT leg, 5.1
  //     | GSV at the SFJ | 5.1 | 0.3 |
  //                                    <- blank
  //     Right leg normal               <- a summary OF TABLE 1, read as table
  //                                    <- blank      2's caption
  //     |  | DIAMETER (mm) | ... |     <- table 2, the LEFT leg, 6.2
  //     | GSV at the SFJ | 6.2 | 3.4 |
  //
  //   editTableCell(..., tableCaption 'Right Leg', 6.8)
  //     -> ok:true, before:"6.2"       <- THE LEFT LEG. Measured, not argued.
  //
  // Both tables carry a caption, so a presence-only fence passes. The narrowing
  // is a SUBSTRING match on the laterality, so it resolves to the one table
  // whose caption happens to contain `right` — the wrong one. ⚠️ `main` REFUSES
  // this input (table 2 has no caption at all there), so a presence-only fence
  // would have shipped a REGRESSION, not merely left a residual.
  //
  // THE RULE THAT IS SOUND, and it is the convention production already
  // follows: in a section with more than one table, a one-blank-up caption is
  // used only when EVERY table in the section carries a caption, EVERY one of
  // those captions names exactly ONE laterality side, and NO TWO name the same
  // side. Then a caller naming a side matches exactly one table, and it is the
  // one the section's own captions say it is.
  //
  // Measured on production 2026-08-23: **all 12 captioned bilateral sections
  // name exactly one `right` and one `left`**, and 0 of 31 sections carry mixed
  // caption availability. So this refuses nothing that exists today.
  //
  // Anything else REFUSES — `caption_not_found`, which is exactly what `main`
  // does. A section captioned `Arterial` / `Venous` is therefore not served,
  // deliberately: it is a shape no production note holds, and inventing a
  // discriminator for it is how this seam produced two wrong-leg writes already.
  const siblings = siblingHeaders(lines, headerIdx).filter((h) => h !== headerIdx);
  if (siblings.length === 0) return mine.text;

  const seen = new Set<string>();
  for (const h of [headerIdx, ...siblings]) {
    const cap = h === headerIdx ? mine : rawCandidate(lines, h);
    if (cap === null) return null;
    const right = RIGHT_RE.test(cap.text);
    const left = LEFT_RE.test(cap.text);
    // Exactly one side, or it cannot discriminate.
    if (right === left) return null;
    const side = right ? 'right' : 'left';
    if (seen.has(side)) return null;
    seen.add(side);
  }
  return mine.text;
}
