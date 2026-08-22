// ============================================================================
// RULING #140 — THE LABEL COLUMN IS RESOLVED FROM EVIDENCE, NOT GUESSED FROM
// TEXT.
// ----------------------------------------------------------------------------
// The defect, in one line: a header cell that genuinely IS the row-label column
// and happens to satisfy a measurement-shaped text test was classified as DATA,
// the editor padded the header at the FRONT, every column resolved one place to
// the right, and a doctor's diameter landed in the REFLUX TIME cell — reported
// back as a successful diameter change.
//
// THREE CLAIMS ARE ASSERTED HERE, AND THEY ARE DIFFERENT CLAIMS:
//
//   1. THE GENERATOR IS UNTOUCHED. `isDataColumnHeader` answers exactly what it
//      answered before #140, for every input. The ruling authorises a change to
//      how the EDITOR resolves the label column; it does not authorise changing
//      what the generator emits into clinical notes.
//   2. THE CLASSIFIER PARTITIONS TOTALLY. Every header lands in exactly one of
//      data / label / cannot_tell, and the buckets reconcile against the corpus
//      size — so a classifier that quietly stopped classifying cannot pass.
//   3. THE EDITOR REFUSES WHAT THE TEXT CANNOT SETTLE — on ANY header cell,
//      not just the first — and still writes the shapes production holds.
//
// ⚠️ WHAT THIS FILE DOES **NOT** ASSERT, SO THE NAME IS NOT READ WIDER THAN THE
// WATCHED SET: ruling #140's TWIN half is not implemented and nothing here
// tests it. A first attempt was built and removed — it keyed on the twin's data
// COLUMN COUNT, which is invariant under which end a header is short at, and it
// widened grids the text route correctly refuses. See `table-header-shape.ts`.
//
// ⚠️ AND THE PRODUCTION CENSUS IS HERE AS A PINNED ROW, NOT AS A REASSURANCE.
// Measured 2026-08-22 against `transcribe_visits.soapFinal`: 45 table headers
// across 24 visits, SIX distinct first-cell values, and NOT ONE of them lands
// in `cannot_tell`. That is what makes #140 a tightening with no capability
// loss on the real corpus rather than a trade — and it is falsifiable: a value
// that started landing in `cannot_tell` would redden the row naming it.
// ============================================================================

import { describe, expect, it } from 'vitest';

import { editTableCell } from '../note-table-edit';
import { classifyHeaderCell, isDataColumnHeader, type HeaderCellVerdict } from '../table-header-shape';

// ---------------------------------------------------------------------------
// THE CORPUS — every header this programme has a reason to hold an opinion on.
// ---------------------------------------------------------------------------
// Sources, so the list can be audited rather than trusted:
//   · PROD    — one of the six first-cell values measured on production
//   · RECON   — one of the eight divergences in the F24-S3 substrate recon
//   · #140    — a shape ruling #140 names by hand
//   · SHAPE   — a decoration/unit edge the recon calls out as its own class
const CORPUS: { header: string; source: string; verdict: HeaderCellVerdict }[] = [
  // ---- production's six, with their measured line counts -------------------
  { header: 'DIAMETER (mm)', source: 'PROD ×27 lines / 14 visits', verdict: 'data' },
  { header: 'Location', source: 'PROD ×8 lines / 4 visits', verdict: 'label' },
  { header: 'Segment', source: 'PROD ×6 lines / 3 visits', verdict: 'label' },
  { header: 'Site', source: 'PROD ×2 lines / 1 visit', verdict: 'label' },
  { header: 'DIAMETER', source: 'PROD ×1 line / 1 visit', verdict: 'data' },
  { header: 'Medication', source: 'PROD ×1 line / 1 visit', verdict: 'label' },

  // ---- the three #140 exists for ------------------------------------------
  { header: 'Vein Size', source: '#140 wrong-cell write', verdict: 'cannot_tell' },
  { header: 'Segment (right leg)', source: '#140 wrong-cell write', verdict: 'cannot_tell' },
  { header: 'Site (see key)', source: '#140 wrong-cell write', verdict: 'cannot_tell' },

  // ---- ⚠️ THE LATERALITY SHORTHAND — found by the adversarial pass ---------
  // `(L)` parsed as LITRES while `(R)` matched nothing, so the LEFT leg widened
  // and silently corrupted while the RIGHT leg refused, in one bilateral study.
  // The corpus had no single-letter parenthetical, so `cannot_tell` was a floor
  // over a set that did not contain the hazard.
  { header: 'Vein (L)', source: 'ADV laterality shorthand', verdict: 'cannot_tell' },
  { header: 'Vein (R)', source: 'ADV laterality shorthand', verdict: 'cannot_tell' },
  { header: 'Side (L)', source: 'ADV laterality shorthand', verdict: 'cannot_tell' },
  { header: 'Nerve (M)', source: 'ADV single-letter unit', verdict: 'cannot_tell' },
  { header: 'Muscle (G)', source: 'ADV single-letter unit', verdict: 'cannot_tell' },
  { header: 'Segment (S)', source: 'ADV single-letter unit', verdict: 'cannot_tell' },
  { header: 'Structure (in)', source: 'ADV English-word unit', verdict: 'cannot_tell' },
  { header: 'Category (deg)', source: 'ADV abbreviation unit', verdict: 'cannot_tell' },

  // ---- ⚠️ THE BARE MEASUREMENT NOUN USED AS A ROW LABEL --------------------
  // `Time` is the canonical row label of any timepoint table and is made
  // entirely of measurement nouns, so cell-0-only classification widened it.
  // It still reads `data` HERE — the editor's defence is that EVERY cell must
  // be data, and `HEART RATE` is not. Both rows are pinned so the pair stays
  // legible.
  { header: 'Time', source: 'ADV bare noun as row label', verdict: 'data' },
  { header: 'HEART RATE', source: 'ADV the cell that saves it', verdict: 'label' },

  // ---- the recon's fail-closed rows ---------------------------------------
  { header: 'CFV mm', source: 'RECON fails closed', verdict: 'label' },
  { header: 'Thickness', source: 'RECON fails closed', verdict: 'label' },
  { header: 'Grade', source: 'RECON fails closed', verdict: 'label' },
  { header: '**AREA (cm2)**', source: 'RECON decoration', verdict: 'label' },
  { header: 'AREA (cm2).', source: 'RECON decoration', verdict: 'label' },

  // ---- ⚠️ CLAIM-2 CLASS A: unambiguous units the first list MISSED --------
  // The adversarial pass measured 37 of 47 plausible clinical headers losing
  // their widen. Some of those were not ambiguity at all — they were a closed
  // unit list that was simply too short. Restored, because a unit is evidence.
  { header: 'Volume (cc)', source: 'ADV unit-list gap', verdict: 'data' },
  { header: 'Volume (cm3)', source: 'ADV unit-list gap', verdict: 'data' },
  { header: 'Flow (L/min)', source: 'ADV unit-list gap', verdict: 'data' },
  { header: 'Dose (mg)', source: 'ADV unit-list gap', verdict: 'data' },
  { header: 'Diameter mm', source: 'ADV bare unit token', verdict: 'data' },
  { header: 'Diameter [mm]', source: 'ADV non-round bracket', verdict: 'data' },
  { header: 'Reflux Duration', source: 'ADV measurement noun pair', verdict: 'data' },

  // ---- ⚠️ CLAIM-2 CLASS B: THE ACCEPTED LOSS, PINNED SO IT IS NOT SILENT ---
  // A measurement noun with a NON-measurement qualifier. These WIDENED on
  // `main` and now REFUSE. That is real capability loss and it is deliberate:
  // `| Max Diameter | REFLUX |` reads as {label, data} or {data, data} with
  // equal force, which is the very ambiguity #140 rules must be refused. Pinned
  // as `cannot_tell` so that anyone who later decides to admit them has to
  // change this table on purpose.
  { header: 'Max Diameter', source: 'ADV accepted loss', verdict: 'cannot_tell' },
  { header: 'Peak Velocity', source: 'ADV accepted loss', verdict: 'cannot_tell' },
  { header: 'Vein Diameter', source: 'ADV accepted loss', verdict: 'cannot_tell' },
  { header: 'Nodule Size', source: 'ADV accepted loss', verdict: 'cannot_tell' },
  { header: 'Total Length', source: 'ADV accepted loss', verdict: 'cannot_tell' },

  // ---- real data columns that must keep widening --------------------------
  { header: 'REFLUX TIME (ms)', source: 'WM IOV column', verdict: 'data' },
  { header: 'REFLUX TIME (seconds)', source: 'WM IOV column', verdict: 'data' },
  { header: 'AREA (cm2)', source: 'SHAPE unit', verdict: 'data' },
  { header: 'VELOCITY (cm/s)', source: 'SHAPE unit', verdict: 'data' },
  { header: 'REFLUX TIME', source: 'all-measurement words', verdict: 'data' },
  { header: 'VEIN', source: 'the canonical label column', verdict: 'label' },
];

// ---------------------------------------------------------------------------
// 1. THE GENERATOR IS UNTOUCHED — the pre-#140 predicate, quoted verbatim.
// ---------------------------------------------------------------------------
// ⚠️ THIS RE-IMPLEMENTATION IS DELIBERATE AND IS THE ONLY ONE IN THIS FILE.
// The claim under test is "the new code agrees with the OLD code", and the old
// code no longer exists to call, so the old expression IS the oracle. It is
// copied byte-for-byte from `table-header-shape.ts` as it stood before #140:
//
//     return /\([^)]*\)\s*$/.test(h) || /diameter|reflux|.../i.test(h);
//
// Everywhere else in this programme, re-implementing a shipped matcher inside a
// test is the F12-g failure. Here the alternative is asserting nothing.
function preRuling140Predicate(h: string): boolean {
  return /\([^)]*\)\s*$/.test(h) || /diameter|reflux|velocity|length|depth|time|size/i.test(h);
}

describe('#140 — the GENERATOR’s view is unchanged', () => {
  it.each(CORPUS)('$header ($source)', ({ header }) => {
    expect(isDataColumnHeader(header)).toBe(preRuling140Predicate(header));
  });

  // ⚠️ THE CORPUS ABOVE IS HAND-PICKED, SO IT PROVES AGREEMENT ON THE CASES ITS
  // AUTHOR THOUGHT OF. This sweeps a generated space instead — every
  // combination of a stem, a decoration and a bracket — so agreement is a
  // property of the two functions rather than of my imagination.
  it('agrees on a generated space, not only on the hand-picked corpus', () => {
    const stems = ['VEIN', 'Segment', 'Vein Size', 'DIAMETER', 'REFLUX TIME', 'Grade', 'Site', ''];
    const brackets = ['', ' (mm)', ' (cm/s)', ' (right leg)', ' (see key)', ' (L)', ' ()', ' (mm) '];
    const decor = ['', '**', '.', ' '];
    const answers: boolean[] = [];
    const verdicts: HeaderCellVerdict[] = [];
    for (const s of stems)
      for (const b of brackets)
        for (const d of decor) {
          const h = `${d}${s}${b}${d}`;
          expect(isDataColumnHeader(h)).toBe(preRuling140Predicate(h));
          answers.push(preRuling140Predicate(h));
          verdicts.push(classifyHeaderCell(h));
        }

    // ⚠️ THE FLOOR MEASURES THE *ANSWERS*, NOT THE TRIP COUNT — AND THE FIRST
    // VERSION OF IT MEASURED THE TRIP COUNT, WHICH THE ADVERSARIAL PASS PROVED
    // WAS DECORATION. It read `expect(checked).toBe(stems*brackets*decor)`,
    // comparing a counter incremented once per iteration against the loop's own
    // size — structurally incapable of failing — plus `toBeGreaterThan(200)`,
    // which counts COMBINATIONS and not answers. Demonstrated: a generated
    // space in which all 224 combinations answer `false`, with zero `data` and
    // zero `cannot_tell`, passed 51 of 51.
    //
    // An agreement test over a space where the oracle always says the same
    // thing proves only that both functions are constant. These floors are what
    // make the space discriminate.
    expect(answers.length).toBeGreaterThan(200);
    expect(answers.filter(Boolean).length).toBeGreaterThan(20);
    expect(answers.filter((a) => !a).length).toBeGreaterThan(20);
    for (const v of ['data', 'label', 'cannot_tell'] as const) {
      expect(verdicts.filter((x) => x === v).length).toBeGreaterThan(20);
    }
  });
});

// ---------------------------------------------------------------------------
// 2. THE PARTITION IS TOTAL AND RECONCILES
// ---------------------------------------------------------------------------
describe('#140 — the classifier partitions every header exactly once', () => {
  it.each(CORPUS)('$header ($source) -> $verdict', ({ header, verdict }) => {
    expect(classifyHeaderCell(header)).toBe(verdict);
  });

  it('the buckets reconcile against the corpus, and none is empty', () => {
    const tally: Record<HeaderCellVerdict, number> = { data: 0, label: 0, cannot_tell: 0 };
    for (const { header } of CORPUS) tally[classifyHeaderCell(header)] += 1;
    expect(tally.data + tally.label + tally.cannot_tell).toBe(CORPUS.length);
    // A classifier that collapsed to one answer would still reconcile. These
    // floors are what stop that reading as a pass.
    //
    // ⚠️ THIS USED TO READ `expect(tally.cannot_tell).toBe(3)` AND THE NUMBER
    // WENT STALE THE MOMENT THE ADVERSARIAL PASS ADDED THE LATERALITY FAMILY —
    // which is the point the pass made about it: a count pinned to a
    // HAND-MAINTAINED corpus measures the corpus, not the classifier. The
    // meaning lives in the per-row arms above and in the subset invariant
    // below; this one only has to prove no bucket is empty.
    expect(tally.data).toBeGreaterThan(0);
    expect(tally.label).toBeGreaterThan(0);
    expect(tally.cannot_tell).toBeGreaterThan(0);
  });

  // ⚠️ `cannot_tell` IS A SUBSET OF WHAT THE OLD PREDICATE ACCEPTED — that is
  // the invariant that keeps the bucket meaning what its name says, and it is
  // what makes #140 a TIGHTENING: every row that lands here used to license the
  // widen, and none of them is a row the old predicate already refused.
  it('every cannot_tell row is one the OLD predicate accepted — a strict tightening', () => {
    const cannotTell = CORPUS.filter((c) => classifyHeaderCell(c.header) === 'cannot_tell');
    expect(cannotTell.length).toBeGreaterThan(0);
    for (const c of cannotTell) expect(preRuling140Predicate(c.header)).toBe(true);
  });

  // The named families, asserted by NAME rather than by count, so adding a
  // corpus row never silently retires one of them.
  it('the #140 shapes and the laterality family are all cannot_tell', () => {
    for (const h of [
      'Vein Size',
      'Segment (right leg)',
      'Site (see key)',
      'Vein (L)',
      'Vein (R)',
      'Structure (in)',
    ]) {
      expect(classifyHeaderCell(h)).toBe('cannot_tell');
    }
  });
});

// ---------------------------------------------------------------------------
// 3. THE PRODUCTION CENSUS, PINNED
// ---------------------------------------------------------------------------
describe('#140 — the production corpus takes no capability loss', () => {
  const PRODUCTION = CORPUS.filter((c) => c.source.startsWith('PROD'));

  // ⚠️ FOUR OF THE SIX COULD NOT HAVE FAILED, AND SAYING SO IS THE POINT.
  // The classifier is only ever reached for a header that is SHORT BY EXACTLY
  // ONE. Measured on production (header cells -> first data-row cells):
  //
  //     DIAMETER (mm)  2->3   26 lines   REACHES the classifier
  //     DIAMETER       2->3    1 line    REACHES the classifier
  //     DIAMETER (mm)  2->2    1 line    aligned — never reaches it
  //     Location 3->3 (8) · Segment 3->3 (6) · Site 3->3 (2) · Medication 3->3 (1)
  //                                       aligned — never reach it
  //
  // 27 of 45 reach it; 18 never do. And for Location/Segment/Site/Medication
  // `cannot_tell` is unreachable BY INSPECTION OF THE STRING — no trailing
  // parenthetical, no vocabulary word — so asserting "not ambiguous" about
  // them is a control aimed where the answer is predetermined. The arm below
  // still runs over all six, because a future edit could make one of them
  // ambiguous, but the LOAD-BEARING content is the two that widen.
  it('the six production values are classified, and none is ambiguous', () => {
    expect(PRODUCTION).toHaveLength(6);
    for (const p of PRODUCTION) {
      expect(classifyHeaderCell(p.header)).not.toBe('cannot_tell');
    }
  });

  // ⚠️ THE ROWS THAT WOULD HAVE REFUTED THE CLAIM — the ones that actually
  // widen. An earlier draft of this arm said "27 of the 45 lead with
  // `DIAMETER (mm)` and those are exactly the short-at-front notes", which is
  // FALSE and the adversarial pass measured it: 27 lead with `DIAMETER (mm)`
  // but only 26 are short at the front — one is already aligned — and the 27th
  // short-at-front header is `DIAMETER`, a different corpus row the old arm
  // did not cover at all.
  //
  // Production's widening headers are a CLOSED SET OF THREE header lines, and
  // #140 must leave every cell of all three classified as `data` or it has
  // taken a capability away:
  //
  //     | DIAMETER (mm) | REFLUX TIME (ms) |        13 lines / 7 visits
  //     | DIAMETER (mm) | REFLUX TIME (seconds) |   13 lines / 7 visits
  //     | DIAMETER | REFLUX TIME |                   1 line  / 1 visit
  it.each([
    ['DIAMETER (mm)', 'REFLUX TIME (ms)'],
    ['DIAMETER (mm)', 'REFLUX TIME (seconds)'],
    ['DIAMETER', 'REFLUX TIME'],
  ])('every cell of production header [%s | %s] stays data', (a, b) => {
    expect(classifyHeaderCell(a)).toBe('data');
    expect(classifyHeaderCell(b)).toBe('data');
  });

  // And end to end: the real header lines still widen and still write the
  // correct cell. Classification is a proxy; this is the behaviour.
  it.each([
    ['DIAMETER (mm)', 'REFLUX TIME (ms)'],
    ['DIAMETER (mm)', 'REFLUX TIME (seconds)'],
    ['DIAMETER', 'REFLUX TIME'],
  ])('production header [%s | %s] still edits both columns correctly', (a, b) => {
    const note = ['## FINDINGS', `| ${a} | ${b} |`, '| --- | --- |', '| GSV | 6.2 | 3.4 |'].join(
      '\n',
    );
    const first = editTableCell({
      note,
      sectionLabel: 'FINDINGS',
      rowLabel: 'GSV',
      columnLabel: a,
      value: '7.7',
    });
    expect(first.ok).toBe(true);
    expect(first.before).toBe('6.2');
    const second = editTableCell({
      note,
      sectionLabel: 'FINDINGS',
      rowLabel: 'GSV',
      columnLabel: b,
      value: '9.9',
    });
    expect(second.ok).toBe(true);
    expect(second.before).toBe('3.4');
  });
});

// ---------------------------------------------------------------------------
// 4. THE EDITOR — evidence when the twin is there, refusal when it is not
// ---------------------------------------------------------------------------
describe('#140 — the editor refuses what the text cannot settle', () => {
  /** A legacy grid: header short by one, rows carrying a leading label cell. */
  const note = (header0: string) =>
    [
      '## FINDINGS',
      'DIAMETER AND REFLUX TIME',
      `| ${header0} | REFLUX TIME (ms) |`,
      '| --- | --- |',
      '| GSV at the SFJ | 6.2 | 3.4 |',
    ].join('\n');

  const edit = (header0: string) =>
    editTableCell({
      note: note(header0),
      sectionLabel: 'FINDINGS',
      rowLabel: 'GSV at the SFJ',
      columnLabel: 'REFLUX TIME (ms)',
      value: '9.9',
    });

  it('an ambiguous first cell REFUSES', () => {
    const r = edit('Vein Size');
    expect(r.ok).toBe(false);
    expect(r.reason).toBe('label_column_unresolved');
  });

  // ⚠️ THE LATERALITY SHORTHAND, AND IT IS THE MOST DANGEROUS SHAPE IN THIS
  // FILE. The unit list once carried single letters, so `(L)` parsed as LITRES
  // and `Vein (L)` widened while `Vein (R)` refused — **the left leg silently
  // corrupted and the right leg refused, in the same bilateral study.** Found
  // by the adversarial pass; these arms exist so it cannot come back.
  it.each(['Vein (L)', 'Vein (R)', 'Side (L)', 'Nerve (M)', 'Segment (S)', 'Structure (in)'])(
    'the laterality/abbreviation shorthand %s REFUSES',
    (h) => {
      const r = edit(h);
      expect(r.ok).toBe(false);
      expect(r.reason).toBe('label_column_unresolved');
    },
  );

  it('(L) and (R) are treated IDENTICALLY — neither leg is privileged', () => {
    expect(classifyHeaderCell('Vein (L)')).toBe(classifyHeaderCell('Vein (R)'));
    expect(edit('Vein (L)').reason).toBe(edit('Vein (R)').reason);
  });

  // ⚠️ EVERY CELL, NOT ONLY THE FIRST. `Time` is made entirely of measurement
  // nouns and is the canonical row label of any timepoint table; `HEART RATE`
  // is not measurement vocabulary at all. Asking only about cell 0 widened this
  // grid and destroyed the blood pressure.
  it('a vitals table whose row label is `Time` is REFUSED, not widened', () => {
    const r = editTableCell({
      note: ['## FINDINGS', '| Time | HEART RATE |', '| --- | --- |', '| 08:00 | 72 | 120/80 |'].join(
        '\n',
      ),
      sectionLabel: 'FINDINGS',
      rowLabel: '08:00',
      columnLabel: 'HEART RATE',
      value: '88',
    });
    expect(r.ok).toBe(false);
    expect(r.body).toBeUndefined();
  });

  it('an already-aligned grid is unaffected', () => {
    const r = editTableCell({
      note: [
        '## FINDINGS',
        '|  | DIAMETER (mm) | REFLUX TIME (ms) |',
        '| --- | --- | --- |',
        '| GSV at the SFJ | 6.2 | 3.4 |',
      ].join('\n'),
      sectionLabel: 'FINDINGS',
      rowLabel: 'GSV at the SFJ',
      columnLabel: 'REFLUX TIME (ms)',
      value: '9.9',
    });
    expect(r.ok).toBe(true);
    expect(r.before).toBe('3.4');
  });

  // ⚠️ THIS ARM REPLACES ONE THAT WAS AIMED WHERE THE ANSWER WAS PREDETERMINED.
  // The previous "genuinely ragged grid" fixture had a 2-cell header over a
  // 4-cell matched row, so `shortByExactlyOne` (2 !== 3) refused it before
  // `gridIsRegular` was ever evaluated — and the adversarial pass proved it:
  // DELETING the `gridIsRegular` precondition entirely left all 94 arms GREEN.
  //
  // This fixture is short-by-one AND irregular, so `gridIsRegular` is the only
  // thing standing between it and a write into a grid whose rows provably
  // disagree about their own width.
  it('a grid that is short-by-one AND irregular is refused', () => {
    const r = editTableCell({
      note: [
        '## FINDINGS',
        '| DIAMETER (mm) | REFLUX TIME (ms) |',
        '| --- | --- |',
        '| GSV at the SFJ | 6.2 | 3.4 |',
        '| SSV | 4.0 | 1.1 | 9.9 |',
      ].join('\n'),
      sectionLabel: 'FINDINGS',
      rowLabel: 'GSV at the SFJ',
      columnLabel: 'REFLUX TIME (ms)',
      value: '7.7',
    });
    expect(r.ok).toBe(false);
    expect(r.reason).toBe('ragged_table');
    expect(r.body).toBeUndefined();
  });

  // ⚠️ AN UNNAMED COLUMN IS NEVER A TARGET. `norm` strips a trailing
  // parenthetical, so a model-authored `columnLabel` of `(mm)` normalises to
  // the EMPTY STRING and used to select any blank header cell — writing into an
  // unnamed column and confirming it to the doctor with an empty column name.
  //
  // ⚠️ THE FIXTURE IS AN **ALIGNED** GRID, DELIBERATELY. My first version used a
  // short-by-one grid, and the "every cell must be data" rule now refuses that
  // one at `ragged_table` before column resolution is ever reached — so the arm
  // passed for a reason that had nothing to do with the guard it names. An
  // aligned grid reaches column resolution, which is the only place this can be
  // demonstrated.
  it('an empty header cell cannot be targeted by an empty column label', () => {
    const r = editTableCell({
      note: [
        '## FINDINGS',
        '|  | DIAMETER (mm) |  |',
        '| --- | --- | --- |',
        '| GSV at the SFJ | 6.2 | 1.1 |',
      ].join('\n'),
      sectionLabel: 'FINDINGS',
      rowLabel: 'GSV at the SFJ',
      columnLabel: '(mm)',
      value: '7.7',
    });
    expect(r.ok).toBe(false);
    expect(r.reason).toBe('column_not_found');
    expect(r.body).toBeUndefined();
  });

  // The positive control for the same grid: a NAMED column in it still writes,
  // so the arm above is a statement about empty names and not about the fixture
  // being unusable.
  it('…but a named column in that same grid still writes', () => {
    const r = editTableCell({
      note: [
        '## FINDINGS',
        '|  | DIAMETER (mm) |  |',
        '| --- | --- | --- |',
        '| GSV at the SFJ | 6.2 | 1.1 |',
      ].join('\n'),
      sectionLabel: 'FINDINGS',
      rowLabel: 'GSV at the SFJ',
      columnLabel: 'DIAMETER (mm)',
      value: '7.7',
    });
    expect(r.ok).toBe(true);
    expect(r.before).toBe('6.2');
  });
});
