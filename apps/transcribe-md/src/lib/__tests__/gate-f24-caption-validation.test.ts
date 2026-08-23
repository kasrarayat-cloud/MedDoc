// ============================================================================
// GATE — F24-CAPTION-VALIDATION. What a caption IS, and that BOTH readers agree.
// ----------------------------------------------------------------------------
// The item: 20 of 28 bilateral production tables could not be edited at all,
// because `captionFor` read only the line DIRECTLY above a header and the
// canonical markdown shape puts a blank line in between.
//
// ⚠️ THE OBVIOUS FIX WAS BUILT, PROVEN AND WITHDRAWN ONCE ALREADY (Slice 1b):
// reaching one blank further, with no test of what was found, turned clinical
// narrative into a caption and wrote a RIGHT-leg correction into the LEFT leg,
// reporting `ok: true`. So this gate's job is not "does it reach further" — it
// is:
//
//   1. the NEW reach accepts only lines that earn it, and REFUSES on anything
//      else (fail-closed, which reproduces today's behaviour exactly);
//   2. the ADJACENT slot is UNCHANGED — no capability is removed;
//   3. the TWO readers accept exactly the same lines, driven through the real
//      exported functions rather than through a copy of the predicate.
//
// ⚠️ (3) IS THE ARM THAT COULD NOT EXIST BEFORE THIS ITEM. `note-table-edit.ts`
// narrows a clinical WRITE by the caption and `claim-prose.ts` labels a card
// with it; the moment they disagree about which line is the caption, a doctor
// is shown one table and edits another. That hazard sat in `note-table-edit`'s
// own comment for two days with nothing asserting it.
//
// ── THE UNTESTED CLAIM, WRITTEN DOWN BEFORE THE ADVERSARIAL PASS ────────────
//
// Canon asks the author to name it, so:
//
//   "I have NOT tested that a shape-valid line one blank above a header
//    belongs to the table BELOW it rather than to the table ABOVE it. Every
//    fixture here places the caption where a caption goes. A <=4-word,
//    unpunctuated, single-side TRAILING SUMMARY of the previous table would be
//    accepted as the next table's caption, and if the correct table happens to
//    carry no caption of its own, the narrowing would resolve to the WRONG
//    table and write silently."
//
// MEASURED, so the residual is sized rather than hand-waved (production,
// 2026-08-23, read-only):
//
//   | property                                              | count      |
//   |-------------------------------------------------------|------------|
//   | sections with MIXED caption availability (the shape)  | **0 of 31** |
//   | captioned bilateral sections naming one right + one left | **12 of 12** |
//   | candidates carrying BOTH laterality tokens            | 0 of 25    |
//   | candidates carrying sentence punctuation              | 0 of 25    |
//
// ⚠️ AND THE CLAIM ABOVE WAS TESTED, AND IT REPRODUCED — SO THE FENCE IS BUILT.
// Corrected 2026-08-23. The struck sentence read: *"the fence for it is a
// per-SECTION uniformity rule (accept a one-blank-up caption only when every
// table in the section has one), which needs cross-table state in both readers
// and is FILED, NOT BUILT here."* Both halves became false in the same session:
//
//   1. the fence IS built, on the shared module, and is exercised by the
//      `THE TRAILING-SUMMARY SHAPE` block below — not filed;
//   2. the rule named there — PRESENCE only — is the one that was tried and
//      REFUTED. It still wrote the wrong leg, because both tables carried a
//      caption and the substring narrowing then resolved to the one containing
//      `right`. `main` REFUSES that input, so shipping it would have been a
//      REGRESSION rather than a residual.
//
// The rule that shipped is stronger: every table in the section captioned,
// every caption naming exactly ONE side, and no two naming the SAME side.
//
// WHAT REMAINS OPEN, and it is a different slot: the ADJACENT line is NOT
// shape-checked and NOT fenced, exactly as on `main`. A line naming BOTH legs
// directly above a table still mis-narrows. Production holds 0 of 8 such lines.
// RE-ARMING CONDITION: one note whose narrative names both legs directly above
// a table — no code change anywhere. Pinned end-to-end below so the residual
// stays a measurement rather than a memory.
// ============================================================================

import { describe, it, expect } from 'vitest';
import {
  captionCandidate,
  isCaptionShaped,
  CAPTION_MAX_WORDS,
  CAPTION_MAX_CHARS,
} from '../table-caption';
import { editTableCell } from '../note-table-edit';
import { claimProse } from '../claim-prose';

/** The withdrawn Slice-1b counterexample, verbatim. */
const NARRATIVE = 'The right leg was normal; the left GSV is dilated.';

/** A caption the product SUPPORTS and `claim-prose`'s tail-split exists for. */
const TITLED = 'DIAMETER AND REFLUX TIME — Right Leg';

const TABLE = [
  '|  | DIAMETER (mm) | REFLUX TIME (ms) |',
  '| --- | --- | --- |',
  '| GSV at the SFJ | 5.1 | 0.3 |',
];

describe('F24-CAPTION-VALIDATION — the thresholds are the ones the comment claims', () => {
  // ⚠️ NON-VACUITY. Every shape arm below is stated in terms of these two
  // numbers; if a later edit loosens them, the arms would keep passing while
  // meaning something weaker. Pinned so the loosening is the failure.
  it('the measured bounds are 4 words and 48 characters', () => {
    expect(CAPTION_MAX_WORDS).toBe(4);
    expect(CAPTION_MAX_CHARS).toBe(48);
  });
});

describe('F24-CAPTION-VALIDATION — isCaptionShaped, the NEW slot only', () => {
  // Every shape class production actually holds, from the kind census.
  it.each([
    ['Right Leg:', 'the production shape — 2 words, a colon'],
    ['Left Leg:', 'its sibling'],
    ['Right Leg', 'no colon'],
    ['SSV Right Leg', '3 words'],
    ['Great Saphenous Right Leg', '4 words — the observed maximum'],
    ['Arterial', 'no laterality at all is fine — a caption need not name a side'],
  ])('ACCEPTS %j — %s', (line) => {
    expect(isCaptionShaped(line)).toBe(true);
  });

  it.each([
    [NARRATIVE, 'the withdrawn counterexample — 9 words, both sides, punctuation'],
    ['The right leg was normal today', '5 words — one over the bound'],
    ['Right and Left Legs', 'BOTH sides named: cannot discriminate, must not discriminate'],
    ['Right leg, left leg', 'both sides again, comma form'],
    ['Normal study.', 'sentence punctuation — a full stop'],
    ['Right Leg;', 'sentence punctuation — a semicolon'],
    ['Normal?', 'sentence punctuation — a question mark'],
    ['Normal!', 'sentence punctuation — an exclamation'],
    ['## FINDINGS', 'a heading is never a caption'],
    ['| GSV at the SFJ | 5.1 |', 'a table row is never a caption'],
    ['| Right Leg |', 'a ONE-CELL pipe row — the arity the two readers disagreed about'],
    ['', 'empty'],
    ['   ', 'whitespace only'],
  ])('REFUSES %j — %s', (line) => {
    expect(isCaptionShaped(line)).toBe(false);
  });

  it('REFUSES a 4-word line that is over the character bound', () => {
    // Guards the two continuous clauses independently: a line can satisfy the
    // word cap and still be nothing like a caption.
    const long = `Supercalifragilistic${'x'.repeat(40)} A B`;
    expect(long.split(/\s+/)).toHaveLength(3);
    expect(long.length).toBeGreaterThan(CAPTION_MAX_CHARS);
    expect(isCaptionShaped(long)).toBe(false);
  });

  it('⚠️ a HYPHENATED compound counts as naming that side — `\\b` would not', () => {
    // `\bright\b` matches inside `right-sided`, because a hyphen is a non-word
    // character. That would let a both-sides line through the one clause whose
    // whole job is to catch it.
    expect(isCaptionShaped('right-sided and left-sided')).toBe(false);
    // …and the single-sided compound is still a legitimate caption.
    expect(isCaptionShaped('right-sided reflux')).toBe(true);
  });
});

describe('F24-CAPTION-VALIDATION — captionCandidate, slot by slot', () => {
  const withCaption = (caption: string, gaps: number) =>
    ['## FINDINGS', '', caption, ...Array(gaps).fill(''), ...TABLE];
  // header index inside the array above: 3 + gaps
  const headerIdx = (gaps: number) => 3 + gaps;

  it('ADJACENT is UNCHANGED — it accepts a 7-word TITLED caption', () => {
    // ⚠️ THE CAPABILITY-LOSS REGRESSION GUARD, AND IT CAUGHT ITS OWN AUTHOR.
    // The first version of this change applied the 4-word shape rule to the
    // adjacent slot too. `DIAMETER AND REFLUX TIME — Right Leg` is SEVEN words,
    // so four `claim-prose` arms went red — a capability the product supports
    // and tests, removed on the strength of a production census that measured
    // zero titled captions and therefore could not see them.
    expect(TITLED.split(/\s+/).length).toBeGreaterThan(CAPTION_MAX_WORDS);
    expect(isCaptionShaped(TITLED)).toBe(false);
    expect(captionCandidate(withCaption(TITLED, 0), headerIdx(0))).toBe(TITLED);
  });

  it('ADJACENT is UNCHANGED — it accepts the narrative too, exactly as `main` does', () => {
    // ⚠️ STATED AS A MEASUREMENT, NOT AS AN ENDORSEMENT. This item does NOT
    // make the adjacent slot safer; a line naming both legs directly above a
    // table still mis-narrows, on `main` and here. Production holds 0 of 8 such
    // lines. Pinned so that nobody later reads this gate as proof of a safety
    // property it does not establish.
    expect(captionCandidate(withCaption(NARRATIVE, 0), headerIdx(0))).toBe(NARRATIVE);
  });

  it('ONE BLANK UP is NEW — a shaped line is accepted', () => {
    expect(captionCandidate(withCaption('Right Leg:', 1), headerIdx(1))).toBe('Right Leg:');
  });

  it('⚠️ ONE BLANK UP REFUSES the narrative — the withdrawn defect, pinned', () => {
    expect(captionCandidate(withCaption(NARRATIVE, 1), headerIdx(1))).toBeNull();
  });

  it('⚠️ ONE BLANK UP refuses the TITLED caption too, and that is deliberate', () => {
    // The asymmetry is the design: across a paragraph break a line must earn
    // the label by shape, and a 7-word title does not. This costs nothing
    // measured (0 of 25 production candidates are titled) and it is the strict
    // direction — the alternative on this slot is no capability at all.
    expect(captionCandidate(withCaption(TITLED, 1), headerIdx(1))).toBeNull();
  });

  it('TWO blanks is distance, not a paragraph break — null', () => {
    expect(captionCandidate(withCaption('Right Leg:', 2), headerIdx(2))).toBeNull();
    expect(captionCandidate(withCaption('Right Leg:', 3), headerIdx(3))).toBeNull();
  });

  it('a HEADING beyond the blank is null — 2 of the 4 unreachable production headers', () => {
    expect(captionCandidate(['## FINDINGS', '', ...TABLE], 2)).toBeNull();
  });

  it('a PIPE ROW beyond the blank is null — the other 2', () => {
    expect(captionCandidate(['| a | b |', '', ...TABLE], 2)).toBeNull();
  });

  it('a header at index 0 or 1 cannot run off the front', () => {
    expect(captionCandidate(TABLE, 0)).toBeNull();
    expect(captionCandidate(['', ...TABLE], 1)).toBeNull();
  });
});

describe('F24-CAPTION-VALIDATION — end to end through editTableCell', () => {
  const bilateral = (gaps: number) => {
    const g = Array(gaps).fill('');
    return [
      '## FINDINGS',
      '',
      'Right Leg:',
      ...g,
      '|  | DIAMETER (mm) | REFLUX TIME (ms) |',
      '| --- | --- | --- |',
      '| GSV at the SFJ | 5.1 | 0.3 |',
      '',
      'Left Leg:',
      ...g,
      '|  | DIAMETER (mm) | REFLUX TIME (ms) |',
      '| --- | --- | --- |',
      '| GSV at the SFJ | 6.2 | 3.4 |',
      '',
    ].join('\n');
  };

  const edit = (gaps: number, tableCaption?: string) =>
    editTableCell({
      note: bilateral(gaps),
      sectionLabel: 'FINDINGS',
      rowLabel: 'GSV at the SFJ',
      columnLabel: 'DIAMETER (mm)',
      value: '6.8',
      ...(tableCaption ? { tableCaption } : {}),
    });

  it('⚠️ THE ITEM: the blocked shape now edits, into the leg that was NAMED', () => {
    const r = edit(1, 'Right Leg');
    expect(r.ok).toBe(true);
    if (r.ok) {
      // ASSERT THE CELL. A wrong-leg write returns ok:true as well — that is
      // the entire defect class this item sits in, and `before` is what
      // discriminates: the right leg reads 5.1, the left reads 6.2.
      expect(r.before).toBe('5.1');
      const body = r.body ?? '';
      const [right, left] = body.split('Left Leg:');
      expect(right).toContain('| GSV at the SFJ | 6.8 | 0.3 |');
      expect(left).toContain('| GSV at the SFJ | 6.2 | 3.4 |');
    }
  });

  it('⚠️ …and the OTHER leg, by the same route — a fixture that only works one way proves nothing', () => {
    const r = edit(1, 'Left Leg');
    expect(r.ok).toBe(true);
    if (r.ok) {
      expect(r.before).toBe('6.2');
      const body = r.body ?? '';
      const [right, left] = body.split('Left Leg:');
      expect(right).toContain('| GSV at the SFJ | 5.1 | 0.3 |');
      expect(left).toContain('| GSV at the SFJ | 6.8 | 3.4 |');
    }
  });

  it('unnamed, the blocked shape now REFUSES WITH OPTIONS instead of a dead end', () => {
    const r = edit(1);
    expect(r.ok).toBe(false);
    if (!r.ok) {
      expect(r.reason).toBe('row_ambiguous');
      expect(r.choices).toEqual(['Right Leg:', 'Left Leg:']);
    }
  });

  it('TWO blanks still refuses honestly — an empty list, and it says why', () => {
    const r = edit(2, 'Right Leg');
    expect(r.ok).toBe(false);
    if (!r.ok) {
      expect(r.reason).toBe('caption_not_found');
      expect(r.choices ?? []).toHaveLength(0);
      expect(r.rowChoices ?? []).toHaveLength(0);
    }
  });

  it('⚠️ REGRESSION: narrative one blank above a table is STILL not its caption', () => {
    // The withdrawn widen made this exact note write the LEFT leg when asked
    // for the RIGHT and report ok=true. The PERMANENT FLOOR — never relaxed to
    // let a fix through.
    const note = [
      '## FINDINGS',
      '',
      '|  | DIAMETER (mm) | REFLUX TIME (ms) |',
      '| --- | --- | --- |',
      '| GSV at the SFJ | 5.1 | 0.3 |',
      '',
      NARRATIVE,
      '',
      '|  | DIAMETER (mm) | REFLUX TIME (ms) |',
      '| --- | --- | --- |',
      '| GSV at the SFJ | 6.2 | 3.4 |',
      '',
    ].join('\n');
    const r = editTableCell({
      note,
      sectionLabel: 'FINDINGS',
      rowLabel: 'GSV at the SFJ',
      columnLabel: 'DIAMETER (mm)',
      value: '6.8',
      tableCaption: 'Right Leg',
    });
    expect(r.ok).toBe(false);
    // and nothing was written
    if (!r.ok) expect((r as { body?: string }).body).toBeUndefined();
  });
});

describe('F24-CAPTION-VALIDATION — ⚠️ THE TRAILING-SUMMARY SHAPE, the untested claim', () => {
  // The claim written down before the pass: a shape-valid line one blank above
  // a header might belong to the table ABOVE it. Here it is, built to be as
  // hostile as the shape allows — a 3-word, unpunctuated, single-side SUMMARY
  // of table 1, sitting one blank above table 2, in a section where table 1
  // itself carries no caption (a heading is directly above it).
  const TRAILING_SUMMARY = [
    '## FINDINGS',
    '|  | DIAMETER (mm) | REFLUX TIME (ms) |', // table 1 = RIGHT leg, uncaptioned
    '| --- | --- | --- |',
    '| GSV at the SFJ | 5.1 | 0.3 |',
    '',
    'Right leg normal', // a summary OF TABLE 1 — 3 words, no punctuation, one side
    '',
    '|  | DIAMETER (mm) | REFLUX TIME (ms) |', // table 2 = LEFT leg
    '| --- | --- | --- |',
    '| GSV at the SFJ | 6.2 | 3.4 |',
    '',
  ].join('\n');

  it('⚠️ a RIGHT-leg request must not be written into the LEFT leg', () => {
    // ⚠️ THIS ARM WENT RED AGAINST ITS OWN AUTHOR, WHICH IS WHY THE FENCE
    // EXISTS. Before the section-uniformity rule this returned
    // `ok:true, before:"6.2"` — the LEFT leg, for a RIGHT-leg request,
    // reported as success. The shape rule alone could not see it: `Right leg
    // normal` is perfectly caption-shaped; what is wrong is that it belongs to
    // the table ABOVE.
    const r = editTableCell({
      note: TRAILING_SUMMARY,
      sectionLabel: 'FINDINGS',
      rowLabel: 'GSV at the SFJ',
      columnLabel: 'DIAMETER (mm)',
      value: '6.8',
      tableCaption: 'Right Leg',
    });
    if (r.ok) expect(r.before).not.toBe('6.2');
    expect(r.ok).toBe(false);
    if (!r.ok) expect(r.reason).toBe('caption_not_found');
  });

  // ⚠️ THE SIBLING-CAPTIONED VARIANT — THE SECOND WRONG-LEG WRITE THIS ITEM
  // PRODUCED, AND THE FIRST FENCE DID NOT CLOSE IT.
  //
  // Presence is not discrimination. With table 1 captioned `Arterial` — a
  // caption that names no side — a presence-only fence is satisfied, and the
  // substring narrowing then resolves `Right Leg` to the ONE table whose
  // caption contains it: the wrong one.
  //
  //   measured before the fix:  ok:true, before:"6.2"   <- the LEFT leg
  //
  // ⚠️ AND `main` REFUSES THIS INPUT, so it was a REGRESSION introduced by this
  // change rather than a pre-existing residual. Found by probing the author's
  // own written-down untested claim one level deeper, while the citation ran.
  const SIBLING_CAPTIONED = [
    '## FINDINGS',
    'Arterial', // table 1's caption — adjacent, and names NO side
    '|  | DIAMETER (mm) | REFLUX TIME (ms) |',
    '| --- | --- | --- |',
    '| GSV at the SFJ | 5.1 | 0.3 |', // the RIGHT leg
    '',
    'Right leg normal', // a summary OF TABLE 1
    '',
    '|  | DIAMETER (mm) | REFLUX TIME (ms) |',
    '| --- | --- | --- |',
    '| GSV at the SFJ | 6.2 | 3.4 |', // the LEFT leg
    '',
  ].join('\n');

  it('⚠️ a caption that names NO side cannot satisfy the fence for its sibling', () => {
    const r = editTableCell({
      note: SIBLING_CAPTIONED,
      sectionLabel: 'FINDINGS',
      rowLabel: 'GSV at the SFJ',
      columnLabel: 'DIAMETER (mm)',
      value: '6.8',
      tableCaption: 'Right Leg',
    });
    if (r.ok) expect(r.before).not.toBe('6.2');
    expect(r.ok).toBe(false);
  });

  it('⚠️ two captions naming the SAME side: the ONE-BLANK-UP one is dropped, the ADJACENT one still resolves', () => {
    // ⚠️ THIS ARM'S FIRST VERSION ASSERTED `ok === false` AND THE GATE REDDENED
    // AGAINST ITS AUTHOR — correctly. The refusal I expected would have been a
    // capability LOSS: table 1's caption is ADJACENT, so it is never subject to
    // the fence, and `Right Leg:` over the right leg is exactly the write the
    // doctor asked for. `main` behaves identically here.
    //
    // What the fence must do is narrower and it is what is asserted: table 2's
    // one-blank-up `Right leg normal` is DROPPED (it names the same side as its
    // sibling, so it cannot discriminate), leaving the adjacent caption to
    // resolve on its own — into the RIGHT leg, which is `before: '5.1'`.
    const note = SIBLING_CAPTIONED.replace('Arterial', 'Right Leg:');
    const r = editTableCell({
      note,
      sectionLabel: 'FINDINGS',
      rowLabel: 'GSV at the SFJ',
      columnLabel: 'DIAMETER (mm)',
      value: '6.8',
      tableCaption: 'Right Leg',
    });
    expect(r.ok).toBe(true);
    if (r.ok) {
      // ASSERT THE CELL. `6.2` here would be the wrong-leg write.
      expect(r.before).toBe('5.1');
      const body = r.body ?? '';
      expect(body).toContain('| GSV at the SFJ | 6.8 | 0.3 |');
      expect(body).toContain('| GSV at the SFJ | 6.2 | 3.4 |');
    }
    // …and the dropped caption is not offered as a choice anywhere.
    const unnamed = editTableCell({
      note,
      sectionLabel: 'FINDINGS',
      rowLabel: 'GSV at the SFJ',
      columnLabel: 'DIAMETER (mm)',
      value: '6.8',
    });
    expect(unnamed.ok).toBe(false);
    if (!unnamed.ok) expect(unnamed.choices ?? []).not.toContain('Right leg normal');
  });

  it('the READ side is fenced by the same rule, not only the write side', () => {
    // `claim-prose` labels a suggestion card with the leg. A card that names
    // the wrong leg in the doctor's own vocabulary "reads as authoritative" —
    // its own comment says so — so the fence has to cover it too. It does,
    // because the rule lives on the shared module rather than on the callers.
    const out = claimProse('| GSV at the SFJ | 6.2 | 3.4 |', TRAILING_SUMMARY);
    expect(out).not.toContain('Right leg normal');
    expect(out).not.toContain(' — ');
  });

  it('⚠️ the fence does NOT reach the ADJACENT slot — no capability is removed', () => {
    // The fence is a condition on the NEW slot only. An adjacent caption in a
    // section whose sibling table has none still works exactly as on `main`;
    // making the fence universal would be an accepted-capability loss wearing
    // a safety fix's clothes.
    const note = [
      '## FINDINGS',
      '|  | DIAMETER (mm) | REFLUX TIME (ms) |', // table 1, uncaptioned
      '| --- | --- | --- |',
      '| GSV at the SFJ | 5.1 | 0.3 |',
      '',
      'Left Leg:', // ADJACENT to table 2 — no blank between
      '|  | DIAMETER (mm) | REFLUX TIME (ms) |',
      '| --- | --- | --- |',
      '| GSV at the SFJ | 6.2 | 3.4 |',
      '',
    ].join('\n');
    const r = editTableCell({
      note,
      sectionLabel: 'FINDINGS',
      rowLabel: 'GSV at the SFJ',
      columnLabel: 'DIAMETER (mm)',
      value: '6.8',
      tableCaption: 'Left Leg',
    });
    expect(r.ok).toBe(true);
    if (r.ok) expect(r.before).toBe('6.2');
  });

  it('a UNIFORMLY one-blank-up captioned section is untouched by the fence', () => {
    // Mutate-toward-SUCCESS: a fence that refused everything would pass every
    // refusal arm above and be strictly worse than no change at all.
    const lines = [
      '## FINDINGS',
      '',
      'Right Leg:',
      '',
      '|  | DIAMETER (mm) |',
      '| --- | --- |',
      '| GSV at the SFJ | 5.1 |',
      '',
      'Left Leg:',
      '',
      '|  | DIAMETER (mm) |',
      '| --- | --- |',
      '| GSV at the SFJ | 6.2 |',
      '',
    ];
    expect(captionCandidate(lines, 4)).toBe('Right Leg:');
    expect(captionCandidate(lines, 10)).toBe('Left Leg:');
  });

  it('the fence is scoped to the SECTION — a bare table in the NEXT section does not veto it', () => {
    // `siblingHeaders` bounds on headings in both directions. Without that
    // bound an unrelated uncaptioned table further down the note would suppress
    // a perfectly good caption, which is the over-refusal direction.
    const lines = [
      '## FINDINGS',
      '',
      'Right Leg:',
      '',
      '|  | DIAMETER (mm) |',
      '| --- | --- |',
      '| GSV at the SFJ | 5.1 |',
      '',
      '## IMPRESSION',
      '|  | X |',
      '| --- | --- |',
      '| a | 1 |',
    ];
    expect(captionCandidate(lines, 4)).toBe('Right Leg:');
  });
});

describe('F24-CAPTION-VALIDATION — ⚠️ THE TWO READERS ACCEPT THE SAME LINES', () => {
  // Driven through the real exported functions on both sides. A copy of the
  // predicate compared against itself would agree perfectly and prove nothing.
  //
  // The WRITE side is observed through `editTableCell`'s disambiguation: a
  // caption it accepts appears in `choices`. The READ side is observed through
  // `claimProse`: a caption it accepts is prefixed onto the card.
  const CANDIDATES: [string, string][] = [
    ['Right Leg:', 'the production shape'],
    ['Right Leg', 'no colon'],
    ['SSV Right Leg', '3 words'],
    [NARRATIVE, 'the withdrawn counterexample'],
    ['Normal study.', 'sentence punctuation'],
    ['| Right Leg |', '⚠️ a ONE-CELL pipe row — the arity the two used to disagree on'],
    ['## Right Leg', 'a heading'],
  ];

  const writeSideAccepts = (caption: string, gaps: number): boolean => {
    const g = Array(gaps).fill('');
    const note = [
      '## FINDINGS',
      '',
      caption,
      ...g,
      '|  | DIAMETER (mm) | REFLUX TIME (ms) |',
      '| --- | --- | --- |',
      '| GSV at the SFJ | 5.1 | 0.3 |',
      '',
      'Left Leg:',
      '|  | DIAMETER (mm) | REFLUX TIME (ms) |',
      '| --- | --- | --- |',
      '| GSV at the SFJ | 6.2 | 3.4 |',
      '',
    ].join('\n');
    const r = editTableCell({
      note,
      sectionLabel: 'FINDINGS',
      rowLabel: 'GSV at the SFJ',
      columnLabel: 'DIAMETER (mm)',
      value: '9.9',
    });
    // Ambiguous either way; the question is whether THIS table's caption was
    // recognised, which shows up as a second distinct choice.
    return !r.ok && (r.choices ?? []).length === 2;
  };

  const readSideAccepts = (caption: string, gaps: number): boolean => {
    const g = Array(gaps).fill('');
    const note = [
      '## FINDINGS',
      '',
      caption,
      ...g,
      '|  | DIAMETER (mm) |',
      '| --- | --- |',
      '| GSV at the SFJ | 5.1 |',
      '',
    ].join('\n');
    const out = claimProse('| GSV at the SFJ | 5.1 |', note);
    return out.includes(' — ');
  };

  it.each([0, 1, 2])('the two readers agree on every candidate, at %i blank line(s)', (gaps) => {
    // ⚠️ NON-VACUITY: the comparison is worthless unless the candidates
    // actually split into both outcomes at this distance. Asserted, not hoped.
    const results = CANDIDATES.map(([line, why]) => ({
      line,
      why,
      write: writeSideAccepts(line, gaps),
      read: readSideAccepts(line, gaps),
    }));

    for (const r of results) {
      expect(
        r.write,
        `disagreement at ${gaps} blank(s) on ${JSON.stringify(r.line)} (${r.why}): ` +
          `write=${r.write} read=${r.read}`,
      ).toBe(r.read);
    }

    if (gaps === 0) {
      // At zero blanks the legacy rule applies: prose in, heading and pipe out.
      const accepted = results.filter((r) => r.write).map((r) => r.line);
      expect(accepted).toEqual(['Right Leg:', 'Right Leg', 'SSV Right Leg', NARRATIVE, 'Normal study.']);
    }
    if (gaps === 1) {
      // At one blank the shape rule applies: only the caption-shaped survive.
      const accepted = results.filter((r) => r.write).map((r) => r.line);
      expect(accepted).toEqual(['Right Leg:', 'Right Leg', 'SSV Right Leg']);
    }
    if (gaps === 2) {
      expect(results.filter((r) => r.write)).toHaveLength(0);
      expect(results.filter((r) => r.read)).toHaveLength(0);
    }
  });
});

// ============================================================================
// ⚠️ THE OPEN RESIDUAL, PINNED — the ADJACENT slot, which this item does NOT fix.
// ----------------------------------------------------------------------------
// Added by the independent adversarial pass, 2026-08-23, after the same pass
// found `note-table-edit.ts` asserting in a comment that the adjacent line was
// shape-checked. It is not, and the difference is a wrong-leg write.
//
// ⚠️ THESE TWO ARMS ASSERT A DEFECT, DELIBERATELY. They are green because the
// product is wrong here, and they are the tripwire for its re-arming
// condition: production holds 0 of 8 both-leg lines today, and ONE note whose
// narrative names both legs directly above a table exercises it with no code
// change anywhere. **When somebody closes this hole these arms go RED — that
// is the signal, not a failure.** Delete them in the same commit that closes
// it, and correct `table-caption.ts`'s disclosure and `note-table-edit.ts`'s
// `captionFor` comment at the same time; all three describe one fact.
//
// Behaviour is IDENTICAL on `main`. Nothing here is a regression introduced by
// F24-CAPTION-VALIDATION — the fence it adds guards the ONE-BLANK-UP slot only.
// ============================================================================
describe('F24-CAPTION-VALIDATION — ⚠️ THE ADJACENT SLOT IS STILL UNVALIDATED', () => {
  it('⚠️ returns a 9-word, punctuated, BOTH-SIDES line that the shape rule refuses', () => {
    // The two predicates disagree ON PURPOSE, and this is the asymmetry stated
    // as a measurement rather than as a paragraph.
    expect(isCaptionShaped(NARRATIVE)).toBe(false);
    expect(captionCandidate([NARRATIVE, ...TABLE], 1)).toBe(NARRATIVE);
  });

  it('⚠️ a BOTH-LEGS adjacent line writes a RIGHT-leg correction into the LEFT leg', () => {
    // The RIGHT table is uncaptioned (a heading sits directly above it), so it
    // cannot match. The LEFT table carries a line naming BOTH sides, so a
    // substring match on `right` hits it — and it is the only survivor.
    const note = [
      '## FINDINGS',
      '|  | DIAMETER (mm) | REFLUX TIME (ms) |',
      '| --- | --- | --- |',
      '| GSV at the SFJ | 5.1 | 0.3 |', // the RIGHT leg
      '',
      'Right and left legs',
      '|  | DIAMETER (mm) | REFLUX TIME (ms) |',
      '| --- | --- | --- |',
      '| GSV at the SFJ | 6.2 | 3.4 |', // the LEFT leg
      '',
    ].join('\n');
    const r = editTableCell({
      note,
      sectionLabel: 'FINDINGS',
      rowLabel: 'GSV at the SFJ',
      columnLabel: 'DIAMETER (mm)',
      value: '6.8',
      tableCaption: 'right',
    });
    expect(r.ok).toBe(true);
    if (!r.ok) return;
    // ⚠️ ASSERT THE CELL, NOT THE FLAG. A wrong-leg write returns ok:true too —
    // that is the entire reason this class is dangerous.
    expect(r.before).toBe('6.2'); // 6.2 is the LEFT leg. The right leg holds 5.1.
    expect(r.caption).toBe('Right and left legs');
    expect(r.body).toContain('| GSV at the SFJ | 5.1 | 0.3 |'); // right leg UNTOUCHED
    expect(r.body).toContain('| GSV at the SFJ | 6.8 | 3.4 |'); // left leg overwritten
  });
});
