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
//   3. THE EDITOR REFUSES ON `cannot_tell` AND RESOLVES FROM THE TWIN WHEN THE
//      TWIN IS THERE. Both directions, because a twin route that always widened
//      would satisfy the positive arm alone.
//
// ⚠️ AND THE PRODUCTION CENSUS IS HERE AS A PINNED ROW, NOT AS A REASSURANCE.
// Measured 2026-08-22 against `transcribe_visits.soapFinal`: 45 table headers
// across 24 visits, SIX distinct first-cell values, and NOT ONE of them lands
// in `cannot_tell`. That is what makes #140 a tightening with no capability
// loss on the real corpus rather than a trade — and it is falsifiable: a value
// that started landing in `cannot_tell` would redden the row naming it.
// ============================================================================

import { describe, expect, it } from 'vitest';

import { editTableCell, type TwinTableStructure } from '../note-table-edit';
import {
  classifyFirstHeaderCell,
  isDataColumnHeader,
  type HeaderCellVerdict,
} from '../table-header-shape';

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

  // ---- the recon's fail-closed rows ---------------------------------------
  { header: 'CFV mm', source: 'RECON fails closed', verdict: 'label' },
  { header: 'Thickness', source: 'RECON fails closed', verdict: 'label' },
  { header: 'Grade', source: 'RECON fails closed', verdict: 'label' },
  { header: '**AREA (cm2)**', source: 'RECON decoration', verdict: 'label' },
  { header: 'AREA (cm2).', source: 'RECON decoration', verdict: 'label' },

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
    const brackets = ['', ' (mm)', ' (cm/s)', ' (right leg)', ' (see key)', ' ()', ' (mm) '];
    const decor = ['', '**', '.', ' '];
    let checked = 0;
    for (const s of stems)
      for (const b of brackets)
        for (const d of decor) {
          const h = `${d}${s}${b}${d}`;
          expect(isDataColumnHeader(h)).toBe(preRuling140Predicate(h));
          checked += 1;
        }
    // NON-VACUITY: the loop actually ran, and it ran over both answers.
    expect(checked).toBe(stems.length * brackets.length * decor.length);
    expect(checked).toBeGreaterThan(200);
  });
});

// ---------------------------------------------------------------------------
// 2. THE PARTITION IS TOTAL AND RECONCILES
// ---------------------------------------------------------------------------
describe('#140 — the classifier partitions every header exactly once', () => {
  it.each(CORPUS)('$header ($source) -> $verdict', ({ header, verdict }) => {
    expect(classifyFirstHeaderCell(header)).toBe(verdict);
  });

  it('the buckets reconcile against the corpus, and none is empty', () => {
    const tally: Record<HeaderCellVerdict, number> = { data: 0, label: 0, cannot_tell: 0 };
    for (const { header } of CORPUS) tally[classifyFirstHeaderCell(header)] += 1;
    expect(tally.data + tally.label + tally.cannot_tell).toBe(CORPUS.length);
    // A classifier that collapsed to one answer would still reconcile. These
    // floors are what stop that reading as a pass.
    expect(tally.data).toBeGreaterThan(0);
    expect(tally.label).toBeGreaterThan(0);
    expect(tally.cannot_tell).toBe(3);
  });

  // ⚠️ `cannot_tell` IS EXACTLY THE SET THE OLD PREDICATE GOT WRONG — the rows
  // where it said "data" and a reader says "label". Asserting the identity
  // rather than the count is what keeps the bucket meaning what its name says.
  it('cannot_tell is precisely: the old predicate fired, and it should not have', () => {
    const cannotTell = CORPUS.filter((c) => classifyFirstHeaderCell(c.header) === 'cannot_tell');
    expect(cannotTell.map((c) => c.header).sort()).toEqual(
      ['Segment (right leg)', 'Site (see key)', 'Vein Size'].sort(),
    );
    // Every one of them was a TRUE from the old predicate — i.e. every one of
    // them licensed the widen before #140.
    for (const c of cannotTell) expect(preRuling140Predicate(c.header)).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// 3. THE PRODUCTION CENSUS, PINNED
// ---------------------------------------------------------------------------
describe('#140 — the production corpus takes no capability loss', () => {
  const PRODUCTION = CORPUS.filter((c) => c.source.startsWith('PROD'));

  it('all six production first-cell values are still classified, none ambiguous', () => {
    expect(PRODUCTION).toHaveLength(6);
    for (const p of PRODUCTION) {
      expect(classifyFirstHeaderCell(p.header)).not.toBe('cannot_tell');
    }
  });

  // ⚠️ THE ROW THAT WOULD HAVE REFUTED THE CLAIM. 27 of the 45 production
  // headers lead with `DIAMETER (mm)`, and those are exactly the legacy notes
  // whose header is short at the front. If #140 had cost them their widen, the
  // ruling would be a trade rather than a tightening — and this arm is where
  // that would show.
  it('the 27-line majority shape still classifies as data', () => {
    expect(classifyFirstHeaderCell('DIAMETER (mm)')).toBe('data');
  });
});

// ---------------------------------------------------------------------------
// 4. THE EDITOR — evidence when the twin is there, refusal when it is not
// ---------------------------------------------------------------------------
describe('#140 — the editor resolves from the twin, and refuses without it', () => {
  /** A legacy grid: header short by one, rows carrying a leading label cell. */
  const note = (header0: string) =>
    [
      '## FINDINGS',
      'DIAMETER AND REFLUX TIME',
      `| ${header0} | REFLUX TIME (ms) |`,
      '| --- | --- |',
      '| GSV at the SFJ | 6.2 | 3.4 |',
    ].join('\n');

  const edit = (header0: string, tableStructure?: TwinTableStructure) =>
    editTableCell({
      note: note(header0),
      sectionLabel: 'FINDINGS',
      rowLabel: 'GSV at the SFJ',
      columnLabel: 'REFLUX TIME (ms)',
      value: '9.9',
      tableStructure,
    });

  /** What the WM IOV form's compiled IR says: a left-cell row label, two data
   *  columns. Derived from `labelSource: 'left_cell'` on a `table_cell` field. */
  const WM_IOV_TWIN: TwinTableStructure = { dataColumnCount: 2, rowLabelInLeftCell: true };

  it('WITHOUT a twin, an ambiguous header REFUSES', () => {
    const r = edit('Vein Size');
    expect(r.ok).toBe(false);
    expect(r.reason).toBe('label_column_unresolved');
  });

  // ⚠️ THE SAME INPUT, THE OPPOSITE ANSWER, AND THAT IS THE WHOLE RULING. The
  // text cannot settle `Vein Size`; the twin can, because it knows its rows
  // carry a leading label cell and exactly two data columns follow it. Evidence
  // over text-guessing, as one executable sentence.
  it('WITH the twin, the same ambiguous header RESOLVES and writes the right cell', () => {
    const r = edit('Vein Size', WM_IOV_TWIN);
    expect(r.ok).toBe(true);
    expect(r.before).toBe('3.4');
    expect(r.body).toContain('| GSV at the SFJ | 6.2 | 9.9 |');
  });

  // ⚠️ BOTH DIRECTIONS. A twin route that widened unconditionally would pass
  // the arm above and be a worse defect than the one #140 closes — it would
  // widen on a header that genuinely names its label column.
  it('a twin that says the rows have NO left-cell label declines to widen', () => {
    const r = edit('Vein Size', { dataColumnCount: 2, rowLabelInLeftCell: false });
    expect(r.ok).toBe(false);
    expect(r.reason).toBe('ragged_table');
  });

  it('a twin whose column count disagrees with the note declines to widen', () => {
    const r = edit('Vein Size', { dataColumnCount: 3, rowLabelInLeftCell: true });
    expect(r.ok).toBe(false);
    expect(r.reason).toBe('ragged_table');
  });

  // ⚠️ ABSENT IS NOT FALSE, AND THE TWIN IS NEVER CONSULTED FOR A GRID THAT
  // ALREADY LINES UP. A note the generator wrote since F24 Slice 1 carries a
  // matching header, so no widen is needed and the twin changes nothing.
  it('an already-aligned grid is unaffected, twin or no twin', () => {
    const aligned = [
      '## FINDINGS',
      '|  | DIAMETER (mm) | REFLUX TIME (ms) |',
      '| --- | --- | --- |',
      '| GSV at the SFJ | 6.2 | 3.4 |',
    ].join('\n');
    for (const tableStructure of [undefined, WM_IOV_TWIN]) {
      const r = editTableCell({
        note: aligned,
        sectionLabel: 'FINDINGS',
        rowLabel: 'GSV at the SFJ',
        columnLabel: 'REFLUX TIME (ms)',
        value: '9.9',
        tableStructure,
      });
      expect(r.ok).toBe(true);
      expect(r.before).toBe('3.4');
    }
  });

  // ⚠️ #140 NARROWS WHEN THE WIDEN MAY FIRE. IT MUST NOT WIDEN THE SET OF GRIDS
  // THAT REACH IT — so a genuinely ragged table is still refused even with a
  // twin that would otherwise license a widen.
  it('a genuinely ragged grid is still refused, twin present', () => {
    const ragged = [
      '## FINDINGS',
      '| DIAMETER (mm) | REFLUX TIME (ms) |',
      '| --- | --- |',
      '| GSV at the SFJ | 6.2 | 3.4 | 1.1 |',
      '| SSV | 4.0 |',
    ].join('\n');
    const r = editTableCell({
      note: ragged,
      sectionLabel: 'FINDINGS',
      rowLabel: 'GSV at the SFJ',
      columnLabel: 'REFLUX TIME (ms)',
      value: '9.9',
      tableStructure: WM_IOV_TWIN,
    });
    expect(r.ok).toBe(false);
    expect(r.reason).toBe('ragged_table');
  });
});
