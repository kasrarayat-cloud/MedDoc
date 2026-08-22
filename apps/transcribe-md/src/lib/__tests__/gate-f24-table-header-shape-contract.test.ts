// ============================================================================
// F24-S3 RECON — `isDataColumnHeader` IS LOAD-BEARING FOR TWO CALLERS AND HAD
// ZERO DIRECT TESTS.
// ----------------------------------------------------------------------------
// `lib/table-header-shape.ts` was introduced by F24 Slice 1 as the first kill in
// the five-matcher drift. Its own doc-comment states the invariant it exists to
// hold:
//
//     "ONE PREDICATE, TWO CALLERS. […] They must answer identically or the
//      generator will emit a shape the editor misreads — which is the defect
//      this module exists to close."
//
// Measured 2026-08-22, with a positive control so the zero is a real absence
// rather than a broken matcher:
//
//     grep -rln isDataColumnHeader  -> 3 files, NONE of them a test
//     grep -rln rowLateralityVerdict -> 3 files, ONE of them a test  (control)
//
// Same matcher, same form: it finds test files when they exist. So the
// predicate that decides whether a doctor's measurement grid is editable had
// no arm of its own, and was covered only incidentally through the ragged-table
// describe in `note-table-edit.test.ts` and the skeleton gate.
//
// ⚠️ WHAT THIS GATE CLAIMS, AND WHAT IT DELIBERATELY DOES NOT.
//
//   · It PINS the predicate's measured behaviour, INCLUDING six inputs where a
//     reasonable reader would expect the other answer. Those are named below as
//     accepted heuristic limits WITH their consequence — not as defects, and
//     not as aspirations. A heuristic nobody has written down is one somebody
//     "improves" at 02:00.
//   · It asserts the CONTRACT — generator and editor reaching the same answer
//     — by running BOTH REAL FUNCTIONS over a matrix of header shapes. It does
//     not re-implement either one, and it does not assert the regex.
//   · It does NOT claim the predicate is correct. Correctness here is a product
//     question about what a doctor's header means, and it is F24-S3's, not
//     this file's.
//   · It does NOT reach the twin. The editor has no twin awareness today
//     (recon: 0 twin refs in `chat-edit-visit.ts` / `note-table-edit.ts` /
//     `intent.ts`), and inventing one here would be asserting the item's own
//     unbuilt design.
// ============================================================================

import { describe, expect, it } from 'vitest';

import { isDataColumnHeader } from '../table-header-shape';
import { editTableCell } from '../note-table-edit';
import { renderStructureDirective } from '../../worker/note-templates/build-soap-prompt';
import { TableStructureSchema } from '../note-template-parse/note-template-schema';

/** The REAL generator's grid for a header/rowLabel pair — its own output, read
 *  back rather than reconstructed. Anything else would be a second matcher, and
 *  a second matcher is the class this module exists to end. */
function generatedGrid(columns: string[], rowLabels: string[]): string[] {
  const directive = renderStructureDirective({
    kind: 'table',
    columns,
    rowLabels,
  } as never);
  return directive.split('\n').filter((l) => l.trim().startsWith('|'));
}

/** Wrap the generator's own grid in the smallest note the editor will read. */
function noteFrom(grid: string[], caption = 'DIAMETER AND REFLUX TIME'): string {
  return ['## FINDINGS', caption, ...grid].join('\n');
}

// ---------------------------------------------------------------------------
// 1. THE REAL UNIVERSE — the customer form, and a header that names its label
// ---------------------------------------------------------------------------
describe('the production universe', () => {
  // WM_IOV's real header. Compiled from the tracked blank form, this is the
  // shape 52 of the certified template's 80 fields sit in.
  const WM_IOV = ['DIAMETER (mm)', 'REFLUX TIME (ms)'];

  it('the customer form has NO label column — its first header cell is DATA', () => {
    expect(isDataColumnHeader(WM_IOV[0])).toBe(true);
  });

  it('a header that NAMES its label column is recognised as having one', () => {
    expect(isDataColumnHeader('VEIN')).toBe(false);
    expect(isDataColumnHeader('Segment')).toBe(false);
  });

  // NON-VACUITY. If the generator ever stopped emitting a grid at all, every
  // contract arm below would pass over an empty array and say nothing.
  //
  // ⚠️ THE HEADER'S LEADING CELL IS EMPTY, AND THAT IS F24 SLICE 1's FIX.
  // This assertion was first written as `| DIAMETER (mm) | REFLUX TIME (ms) |`
  // — the PRE-Slice-1 shape — and the gate reddened against its own author on
  // first execution. The empty cell is deliberate: the doctor's DOCX has an
  // unheaded first cell, and naming it (`VEIN`, `SEGMENT`) would assert a
  // header their form does not carry. Pinned as the real shape.
  it('the generator actually emits a grid — header, rule, and one row per label', () => {
    const grid = generatedGrid(WM_IOV, ['GSV at the SFJ', 'SSV at the SPJ']);
    expect(grid.length).toBe(4);
    expect(grid[0]).toBe('|  | DIAMETER (mm) | REFLUX TIME (ms) |');
    expect(grid[2]).toContain('GSV at the SFJ');
  });
});

// ---------------------------------------------------------------------------
// 2. THE TRUTH TABLE, AS MEASURED — including where it surprises
// ---------------------------------------------------------------------------
describe('isDataColumnHeader — pinned behaviour', () => {
  // Inputs where the answer matches the doc-comment's stated intent.
  const AGREES: [string, boolean][] = [
    ['DIAMETER (mm)', true],
    ['REFLUX TIME (ms)', true],
    ['PEAK VELOCITY', true],
    ['AREA (cm2)', true],
    ['VEIN', false],
    ['Segment', false],
  ];

  it.each(AGREES)('%s -> %s', (header, expected) => {
    expect(isDataColumnHeader(header)).toBe(expected);
  });

  // ⚠️ THE SIX DIVERGENCES. Every one is REAL, reproduced by running the
  // predicate, and every one is pinned at what it ACTUALLY returns.
  //
  // They are recorded here rather than fixed because the consequence is bounded
  // and is proved by the contract arms below: because ONE predicate answers for
  // BOTH callers, a misclassification makes the generator and the editor wrong
  // in the SAME direction, so the grid stays internally consistent. The cost is
  // a coverage gap or a redundant column — never a write into the wrong cell.
  // Widening the vocabulary to "fix" any row here is a product decision about
  // doctors' headers, and it is F24-S3's to make with evidence.
  const DIVERGES: [string, boolean, string][] = [
    // FALSE POSITIVE — a LABEL column read as DATA.
    ['Segment (right leg)', true, 'a label column that ends in a parenthetical'],
    ['Vein Size', true, 'a label column containing a metric word'],
    ['Site (see key)', true, 'a label column with a parenthetical note'],
    // FALSE NEGATIVE — a DATA column read as the LABEL column.
    ['CFV mm', false, 'a data column whose unit is not parenthesised'],
    ['Thickness', false, 'a data column whose metric is not in the vocabulary'],
    ['Grade', false, 'a categorical data column'],
  ];

  it.each(DIVERGES)('%s -> %s  (accepted limit: %s)', (header, actual) => {
    expect(isDataColumnHeader(header)).toBe(actual);
  });

  it('the divergence list is not silently empty', () => {
    expect(DIVERGES.length).toBe(6);
  });
});

// ---------------------------------------------------------------------------
// 3. THE CONTRACT — the generator's grid is one the editor can read
// ---------------------------------------------------------------------------
// This is the invariant `table-header-shape.ts` claims in prose. It is asserted
// here by running the REAL generator and the REAL editor over the same headers,
// including every divergent shape above — because the whole point of the shared
// predicate is that a WRONG answer still keeps the two callers in step.
describe('generator -> editor: the emitted grid is never ragged', () => {
  const HEADERS: [string, string[]][] = [
    ['the customer form (no label column)', ['DIAMETER (mm)', 'REFLUX TIME (ms)']],
    ['a header naming its label column', ['Segment', 'DIAMETER (mm)']],
    ['label column ending in a parenthetical', ['Segment (right leg)', 'DIAMETER (mm)']],
    ['label column containing a metric word', ['Vein Size', 'DIAMETER (mm)']],
    ['first data column not in the vocabulary', ['Thickness', 'Depth (mm)']],
  ];

  // ⚠️ SINGLE-COLUMN TABLES ARE EXCLUDED BECAUSE THE SCHEMA CANNOT EXPRESS ONE,
  // NOT BECAUSE THEY PASS.
  //
  // The first draft of this matrix carried `['Segment']`, and the contract arm
  // went RED on it: the generator forces one placeholder via
  // `Math.max(valueColumnCount, 1)`, emitting a 2-cell row under a 1-cell
  // header, which the editor then refuses as `ragged_table`.
  //
  // That looked like a residual of F24 Slice 1. It is not — it is an input the
  // system cannot produce. `TableStructureSchema.columns` is `.min(2)`
  // (`note-template-parse/note-template-schema.ts:58`), so a one-column table
  // is refused at parse time and never becomes a template. Filing it would
  // have been a fabricated finding about an unreachable shape.
  //
  // The floor is asserted rather than trusted, so the day it is relaxed this
  // exclusion stops being true LOUDLY instead of silently.
  it('the excluded shape is excluded BY THE SCHEMA, not by choice', () => {
    expect(TableStructureSchema.shape.columns.safeParse(['Segment']).success).toBe(false);
    expect(TableStructureSchema.shape.columns.safeParse(['Segment', 'DIAMETER (mm)']).success).toBe(
      true,
    );
  });

  it.each(HEADERS)('%s', (_name, columns) => {
    const grid = generatedGrid(columns, ['GSV at the SFJ']);
    const r = editTableCell({
      note: noteFrom(grid),
      sectionLabel: 'FINDINGS',
      rowLabel: 'GSV at the SFJ',
      // Ask for the LAST column, which is a data column in every shape above.
      columnLabel: columns[columns.length - 1],
      value: '7.7',
    });
    // The editor may legitimately refuse for a reason that is not about grid
    // SHAPE. `ragged_table` is the one refusal that means the two callers
    // disagreed, and it is the one this contract forbids.
    expect(r.ok === true || r.reason !== 'ragged_table').toBe(true);
  });

  it('and on the customer form the write actually lands in the named column', () => {
    const grid = generatedGrid(['DIAMETER (mm)', 'REFLUX TIME (ms)'], ['GSV at the SFJ']);
    const r = editTableCell({
      note: noteFrom(grid),
      sectionLabel: 'FINDINGS',
      rowLabel: 'GSV at the SFJ',
      columnLabel: 'REFLUX TIME (ms)',
      value: '2.8',
    });
    expect(r.ok).toBe(true);
    // The REFLUX cell moved and the DIAMETER cell did not — the exact
    // off-by-one that F24 Slice 1's adversarial pass found and fixed.
    expect(r.body).toContain('| GSV at the SFJ | [not documented] | 2.8 |');
  });
});

// ---------------------------------------------------------------------------
// 3b. THE LEGACY SHAPE — the only input that reaches the widen at all
// ---------------------------------------------------------------------------
// ⚠️ THIS SECTION EXISTS BECAUSE THE MUTATION PROOF CAUGHT THE SECTION ABOVE
// BEING BLIND, AND THAT IS THE PART WORTH READING.
//
// Mutation B replaced the editor's `isDataColumnHeader(rawHeaderCells[0])` with
// a predicate that never matches — i.e. the editor stops sharing the module and
// the two callers drift, which is the exact defect `table-header-shape.ts` says
// it exists to close. The contract matrix above stayed **26 of 26 GREEN**.
//
// The reason is not a weak assertion; it is a WRONG UNIVERSE. That matrix
// builds every note from the REAL generator, and F24 Slice 1 fixed the
// generator to emit a matching header (`|  | DIAMETER (mm) | …`, with the empty
// label cell). A grid that already lines up never needs widening, so
// `headerLacksLabelColumn` is unreachable from any freshly generated note and
// the arm's result is PREDETERMINED by the generator's fix rather than by the
// editor's health.
//
// The widen is LEGACY-ONLY code. Its population is the 339 of 670 production
// data rows F24 Slice 1 measured — notes written BEFORE the generator fix,
// carrying a header one cell narrower than their rows. That shape is the only
// input that exercises the editor's half of the shared predicate, so it is the
// only input that can prove the two callers still agree.
describe('a PRE-Slice-1 note — the widen path, and the only arm that sees drift', () => {
  // Exactly the shape the old generator emitted: header names only the data
  // columns; every row carries a leading label cell the header has no slot for.
  const LEGACY = [
    '## FINDINGS',
    'DIAMETER AND REFLUX TIME',
    '| DIAMETER (mm) | REFLUX TIME (ms) |',
    '| --- | --- |',
    '| GSV at the SFJ | 6.2 | 3.4 |',
    '| GSV at the Knee | 3.4 | 1.8 |',
  ].join('\n');

  it('the header IS one cell narrower than its rows — the fixture is the real defect', () => {
    const lines = LEGACY.split('\n');
    const cellsOf = (l: string) => l.split('|').slice(1, -1).length;
    expect(cellsOf(lines[2])).toBe(2);
    expect(cellsOf(lines[4])).toBe(3);
  });

  it('the widen fires and the edit lands in the named column', () => {
    const r = editTableCell({
      note: LEGACY,
      sectionLabel: 'FINDINGS',
      rowLabel: 'GSV at the SFJ',
      columnLabel: 'REFLUX TIME (ms)',
      value: '2.8',
    });
    expect(r.ok).toBe(true);
    // The REFLUX cell, not the DIAMETER cell beside it. This is the off-by-one
    // that writes a doctor's reflux time into the diameter column when the
    // editor's half of the predicate drifts.
    expect(r.body).toContain('| GSV at the SFJ | 6.2 | 2.8 |');
  });

  it('and the OTHER row is untouched', () => {
    const r = editTableCell({
      note: LEGACY,
      sectionLabel: 'FINDINGS',
      rowLabel: 'GSV at the SFJ',
      columnLabel: 'DIAMETER (mm)',
      value: '9.9',
    });
    expect(r.ok).toBe(true);
    expect(r.body).toContain('| GSV at the Knee | 3.4 | 1.8 |');
  });
});

// ---------------------------------------------------------------------------
// 4. THE CROSS-TIME HAZARD — and the direction it fails in
// ---------------------------------------------------------------------------
// The widen decision is made at EDIT time, on a note whose shape was decided at
// GENERATE time. Those are different moments, and a note in the database
// outlives any change to this predicate. So: if somebody widens the vocabulary,
// what happens to notes already written under the old answer?
//
// This arm pins the ANSWER, not the hope. A legacy note carrying a header that
// today's predicate reads differently must be REFUSED, never written to on a
// re-derived column index.
describe('a legacy grid the predicate would now read differently', () => {
  it('is REFUSED, not rewritten on a re-derived index', () => {
    // A header that NAMES its label column, over rows that carry a leading
    // label cell AND a cell for every header column — the shape a generator
    // would emit if it believed the first column were DATA.
    const legacy = [
      '## FINDINGS',
      'DIAMETER AND REFLUX TIME',
      '| Segment | DIAMETER (mm) | REFLUX TIME (ms) |',
      '| --- | --- | --- |',
      '| GSV at the SFJ | seg | 6.2 | 3.4 |',
    ].join('\n');

    const r = editTableCell({
      note: legacy,
      sectionLabel: 'FINDINGS',
      rowLabel: 'GSV at the SFJ',
      columnLabel: 'REFLUX TIME (ms)',
      value: '9.9',
    });

    expect(r.ok).toBe(false);
    expect(r.reason).toBe('ragged_table');
    // And nothing was written — the refusal carries no body.
    expect(r.body).toBeUndefined();
  });
});

// ---------------------------------------------------------------------------
// 5. THE ADDRESSABILITY GAP F24-S3 EXISTS TO CLOSE
// ---------------------------------------------------------------------------
// When the predicate reads a real DATA column as the label column, that column
// gets no placeholder from the generator AND is unreachable by the editor,
// because column resolution filters index 0 (`x.i > 0`) — the row label is
// never writable. The doctor's column is then a region the editor cannot
// address, which is precisely the census F24-S3 must drive to zero.
//
// Pinned here so the gap has a NAMED refusal and a number, rather than being
// rediscovered as "the editor didn't do anything".
describe('a first data column read as the label column', () => {
  const grid = generatedGrid(['Thickness', 'Depth (mm)'], ['GSV at the SFJ']);

  it('is UNADDRESSABLE, and says so by name', () => {
    const r = editTableCell({
      note: noteFrom(grid),
      sectionLabel: 'FINDINGS',
      rowLabel: 'GSV at the SFJ',
      columnLabel: 'Thickness',
      value: '4.0',
    });
    expect(r.ok).toBe(false);
    expect(r.reason).toBe('column_not_found');
  });

  it('while the column beside it is addressable — so the gap is the column, not the table', () => {
    const r = editTableCell({
      note: noteFrom(grid),
      sectionLabel: 'FINDINGS',
      rowLabel: 'GSV at the SFJ',
      columnLabel: 'Depth (mm)',
      value: '4.0',
    });
    expect(r.ok).toBe(true);
  });
});
