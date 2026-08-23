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
// ⚠️ THAT COMMENT UNDERCOUNTS ITS OWN CLASS, AND THIS FILE'S FIRST DRAFT
// REPEATED THE UNDERCOUNT APPROVINGLY. There are THREE sites deciding "does
// header cell 0 name a data column?", using TWO vocabularies. The third is
// `template-twin/bridge-fill.ts:147-152` (`classifyHeader`), consumed at `:425`:
//
//     const labelColumnOffset = roleByCol[0] === 'other' || roleByCol.length === 0 ? 0 : 1;
//
// and its comment describes the identical decision — "if that column already
// classifies as DATA, the header has no label column and every data cell sits
// one to the right." Its vocabulary is `/reflux/` and
// `/diameter|(^|\W)mm(\W|$)/`, which agrees with `isDataColumnHeader` on the
// customer form and diverges elsewhere, in BOTH directions:
//
//     "CFV mm"           isDataColumnHeader false  ·  classifyHeader diameter
//     "VELOCITY (cm/s)"  isDataColumnHeader true   ·  classifyHeader other
//
// So the generator and the editor can agree while the TWIN FILL disagrees. They
// AGREE on the real customer form (`DIAMETER (mm)`, `REFLUX TIME (ms)`, `VEIN`),
// which is why nothing has broken in production.
//
// ⚠️ NOTHING IN THIS FILE ASSERTS THAT DIVERGENCE, AND THE OMISSION IS
// DELIBERATE. `classifyHeader` is not exported (`bridge-fill.ts:147`), and
// re-implementing a shipped predicate inside a test is the F12-g failure — an
// SQL re-implementation answered 19 where the shipped predicate answered 15,
// and the 19 reached a ledger row. So this is a FINDING, recorded in prose and
// in the recon report, and it is F24-S3's to reconcile with its own adversarial
// pass. Exporting the symbol to assert it would be a production change made for
// a test's convenience.
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
//   · It PINS the predicate's measured behaviour, INCLUDING **eight** inputs
//     where a reasonable reader would expect the other answer. A heuristic
//     nobody has written down is one somebody "improves" at 02:00.
//     ⚠️ THIS BULLET USED TO SAY "six … accepted heuristic limits, not
//     defects." Both halves were wrong: there are eight, and THREE OF THEM ARE
//     A DEFECT — they license a wrong-cell write on a legacy note. See the
//     DEFECT describe below, which reproduces the harm rather than asserting
//     it away.
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

  // ⚠️⚠️ THIS BLOCK USED TO CALL THESE "ACCEPTED LIMITS" AND ASSERT, ON THIS
  // PAGE, THAT THE COST IS "NEVER A WRITE INTO THE WRONG CELL". THAT SENTENCE
  // WAS FALSE, AND THE THREE FALSE-POSITIVE ROWS BELOW ARE PRECISELY THE INPUTS
  // THAT FALSIFY IT. The mandatory adversarial pass found it; see the
  // `THE FALSE POSITIVES ARE A WRONG-CELL WRITE` describe below, which now
  // reproduces the harm instead of asserting it away.
  //
  // The reasoning that was wrong is worth keeping, because it is seductive:
  // "one predicate answers for both callers, so a misclassification makes them
  // wrong in the SAME direction and the grid stays internally consistent."
  // ⚠️ THE TWO CALLERS ACT AT DIFFERENT TIMES. The generator wrote the note's
  // header months ago; the editor asks the predicate about it today. Internal
  // consistency is a property of ONE generation, never of a note already in the
  // database — and the widen exists only for notes from the other era.
  //
  // Every row is REAL, reproduced by running the predicate, and pinned at what
  // it ACTUALLY returns.
  const DIVERGES: [string, boolean, string][] = [
    // FALSE POSITIVE — a LABEL column read as DATA. ⚠️ THESE THREE LICENSE A
    // WRONG-CELL WRITE on a legacy note. Not an accepted limit: a defect.
    ['Segment (right leg)', true, 'a label column that ends in a parenthetical'],
    ['Vein Size', true, 'a label column containing a metric word'],
    ['Site (see key)', true, 'a label column with a parenthetical note'],
    // FALSE NEGATIVE — a DATA column read as the LABEL column. These fail
    // CLOSED: the column gets no cell and refuses with `column_not_found`.
    ['CFV mm', false, 'a data column whose unit is not parenthesised'],
    ['Thickness', false, 'a data column whose metric is not in the vocabulary'],
    ['Grade', false, 'a categorical data column'],
    // ⚠️ SEVENTH CLASS, and it is not about the WORDS at all — it is about
    // DECORATION. `/\([^)]*\)\s*$/` is anchored, so any non-space character
    // after the parenthetical kills that arm and the word arm knows only seven
    // metrics. `AREA (cm2)` is a data column; bold it and it stops being one.
    //
    // Reachable rather than hypothetical, and the proof is in this repository:
    // `note-table-edit.ts:79` STRIPS `**` from header cells before comparing,
    // so the editor already expects bold headers in exactly the strings this
    // predicate cannot parse.
    ['**AREA (cm2)**', false, 'DECORATION — bold kills the parenthetical anchor'],
    ['AREA (cm2).', false, 'DECORATION — a trailing full stop does the same'],
  ];

  it.each(DIVERGES)('%s -> %s  (%s)', (header, actual) => {
    expect(isDataColumnHeader(header)).toBe(actual);
  });

  it('the undecorated forms ARE data columns — so the seventh class is decoration, not vocabulary', () => {
    expect(isDataColumnHeader('AREA (cm2)')).toBe(true);
    // …and a TRAILING SPACE is fine, because the anchor allows `\s*$`. The
    // class is non-whitespace decoration specifically.
    expect(isDataColumnHeader('AREA (cm2) ')).toBe(true);
  });

  it('the divergence list is not silently empty', () => {
    expect(DIVERGES.length).toBe(8);
  });
});

// ---------------------------------------------------------------------------
// 2b. ⚠️ THE FALSE POSITIVES WERE A WRONG-CELL WRITE — CLOSED BY RULING #140.
// ---------------------------------------------------------------------------
// ⚠️ THIS BLOCK USED TO PIN THE DEFECT AND NOW PINS THE REFUSAL, AND THE
// PREVIOUS TEXT IS KEPT BELOW BECAUSE IT IS THE EVIDENCE. Its own comment said:
// "If somebody fixes the predicate, these arms go RED and they must update them
// DELIBERATELY — which is the point." They went red on the first run of #140's
// fix, against their author's successor, and this is that deliberate update.
//
// RULING #140 — the label column is resolved from EVIDENCE, not guessed from
// text. `Vein Size`, `Segment (right leg)` and `Site (see key)` are the three
// shapes the text vocabulary cannot settle, and they are now the fallback's
// PERMANENT REFUSAL ARMS. The `Vein Size` fixture is pinned VERBATIM as the
// wrong-cell regression guard, exactly as the ruling requires.
//
// The original finding, unedited, because it is what the arms below protect:
//
// A legacy note whose header NAMES its label column is supposed to be refused:
// that is what the `ragged_table` guard is for, and with `VEIN` it works. But
// when the label column's text happens to satisfy `isDataColumnHeader`, the
// widen fires, the header is padded at the FRONT, and every column resolves one
// place to the right of where it belongs.
//
//     | Vein Size | DIAMETER (mm) |
//     | --- | --- |
//     | GSV at the SFJ | 6.2 | 3.4 |
//
//     edit DIAMETER (mm) := 7.7
//       ->  ok: true,  column: "DIAMETER (mm)",  before: "3.4"
//           | GSV at the SFJ | 6.2 | 7.7 |
//
// The diameter is UNTOUCHED. 7.7 landed in the REFLUX TIME cell, destroying a
// measurement, and the doctor was told the diameter had changed. This is the
// exact defect `note-table-edit.ts:295-317` records the guard as having closed
// — arriving through the guard's own predicate.
//
// ⚠️ LATENT, NOT LIVE — and the number is what makes it a filing rather than an
// incident. Measured on production 2026-08-22 over `note_templates.sections`:
// **3 table structures, and all 3 have `DIAMETER (mm)` as their first column**,
// which the predicate classifies correctly. No production template triggers
// this today.
//
// HONEST LIMIT: that measures TEMPLATE structures, not the headers sitting in
// already-written NOTES. A note generated under a template whose columns have
// since changed is not covered by it, and establishing that would mean reading
// note bodies.
//
// THE TRIGGER, so it is a lookup and not a judgement: a doctor's table whose
// FIRST column is a row-label column whose text ends in a parenthetical or
// contains one of diameter|reflux|velocity|length|depth|time|size.
describe('RULING #140 — a label column the text cannot settle is REFUSED', () => {
  // ⚠️ PINNED VERBATIM. Ruling #140 names this fixture as the wrong-cell
  // regression guard, so the header, the row and the values are the ones the
  // ruling quotes. Changing them silently retires the guard.
  const legacy = (header0: string) =>
    [
      '## FINDINGS',
      'DIAMETER AND REFLUX TIME',
      `| ${header0} | DIAMETER (mm) |`,
      '| --- | --- |',
      '| GSV at the SFJ | 6.2 | 3.4 |',
    ].join('\n');

  const askForDiameter = (header0: string) =>
    editTableCell({
      note: legacy(header0),
      sectionLabel: 'FINDINGS',
      rowLabel: 'GSV at the SFJ',
      columnLabel: 'DIAMETER (mm)',
      value: '7.7',
    });

  // THE CONTROL FIRST. A label column the predicate reads correctly is refused,
  // so what follows is a property of the PREDICATE and not of the fixture.
  it.each(['VEIN', 'Segment'])('control: %s is correctly REFUSED', (h) => {
    const r = askForDiameter(h);
    expect(r.ok).toBe(false);
    expect(r.reason).toBe('ragged_table');
  });

  // ⚠️ THE THREE SHAPES, NOW REFUSED — AND THE REFUSAL IS ITS OWN REASON.
  // `ragged_table` would have been true and less useful: this grid DOES line
  // up, under exactly one of two readings, and the evidence does not pick
  // between them. Keeping the two apart is what lets a count answer "did my
  // change break this?" — the bucket-collapse canon names.
  it.each(['Vein Size', 'Segment (right leg)', 'Site (see key)'])(
    '#140: %s is REFUSED as label_column_unresolved',
    (h) => {
      const r = askForDiameter(h);
      expect(r.ok).toBe(false);
      expect(r.reason).toBe('label_column_unresolved');
    },
  );

  // ⚠️ AND THE NOTE IS NOT TOUCHED — the half a reason code cannot assert.
  // A refusal that had already written the cell would satisfy the arm above.
  it.each(['Vein Size', 'Segment (right leg)', 'Site (see key)'])(
    '#140: %s leaves the note completely unchanged',
    (h) => {
      const r = askForDiameter(h);
      expect(r.body).toBeUndefined();
      expect(r.before).toBeUndefined();
    },
  );

  // ⚠️ MUTATE TOWARD SUCCESS, NOT ONLY TOWARD FAILURE. A fix that refused
  // EVERYTHING would satisfy every arm above and would be strictly worse than
  // the defect — it would make all 27 production `DIAMETER (mm)` headers
  // uneditable. This is the legacy shape that MUST still widen and write.
  //
  // ⚠️ AND MY FIRST VERSION OF THIS CONTROL WAS AIMED WHERE THE ANSWER WAS
  // PREDETERMINED, WHICH RUNNING IT IS WHAT FOUND. It reused `legacy(h)` with
  // `columnLabel: 'DIAMETER (mm)'`, so for h = `DIAMETER (mm)` the widened
  // header was ['', 'DIAMETER (mm)', 'DIAMETER (mm)'] and the edit died on
  // `column_ambiguous` — a refusal from a DIFFERENT mechanism, which no state
  // of the widen could have changed. The canon's "a control aimed where the
  // answer is predetermined is not a control", caught on its own author.
  //
  // The real customer-form shape, and BOTH columns are asserted: a widen that
  // lands one place out would put 7.7 in the other cell, so checking one column
  // alone cannot distinguish a correct widen from an off-by-one.
  describe('positive control — the real customer-form header still writes', () => {
    const customerForm = [
      '## FINDINGS',
      'DIAMETER AND REFLUX TIME',
      '| DIAMETER (mm) | REFLUX TIME (ms) |',
      '| --- | --- |',
      '| GSV at the SFJ | 6.2 | 3.4 |',
    ].join('\n');

    const edit = (columnLabel: string) =>
      editTableCell({
        note: customerForm,
        sectionLabel: 'FINDINGS',
        rowLabel: 'GSV at the SFJ',
        columnLabel,
        value: '7.7',
      });

    it('DIAMETER (mm) resolves to the diameter cell', () => {
      const r = edit('DIAMETER (mm)');
      expect(r.ok).toBe(true);
      expect(r.before).toBe('6.2');
      expect(r.body).toContain('| GSV at the SFJ | 7.7 | 3.4 |');
    });

    it('REFLUX TIME (ms) resolves to the reflux cell', () => {
      const r = edit('REFLUX TIME (ms)');
      expect(r.ok).toBe(true);
      expect(r.before).toBe('3.4');
      expect(r.body).toContain('| GSV at the SFJ | 6.2 | 7.7 |');
    });
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
    // ⚠️ ASSERTED AS `ok`, NOT AS "not ragged". The first draft said
    // `r.ok === true || r.reason !== 'ragged_table'` — true of a matrix in
    // which every shape refused for some OTHER reason, i.e. vacuous in exactly
    // the direction that would hide a broken contract. Measured: all five
    // shapes return `ok: true` and write. So the knowable value is asserted.
    expect(r.ok).toBe(true);
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
// The widen is LEGACY-ONLY code. Its population is the 237 of 441 production
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

  // ⚠️ THE ARM ABOVE REDDENS UNDER THE DELTA-ONLY MUTATION AND CANNOT
  // DEMONSTRATE ANY HARM. THIS ONE CAN, AND THAT DIFFERENCE IS THE LESSON.
  //
  // Found by re-reading my own fixture AFTER its mutation proof had already
  // gone green -> red. Measured with the widen mutated to fire on DELTA alone:
  //
  //   the arm above   ask REFLUX  -> | GSV at the SFJ | seg | 6.2 | 9.9 |
  //                                   the CORRECT cell. Refusing it is
  //                                   conservative, not protective.
  //   this arm        ask DIAMETER -> | GSV at the SFJ | 6.2 | 9.9 |
  //                                   the diameter is UNTOUCHED and 9.9 landed
  //                                   in the REFLUX position.
  //
  // The second is the defect quoted verbatim at note-table-edit.ts:304-312:
  // the doctor asks to correct a diameter, is told the diameter changed, and
  // the reflux time is destroyed. A mutation aimed at the wrong FORM produces a
  // red as empty as a green that never ran.
  it('the REFERENCE shape — a header short a TRAILING data column — is refused', () => {
    const reference = [
      '## FINDINGS',
      'DIAMETER AND REFLUX TIME',
      // Names its label column AND is short one trailing data column. Delta is
      // +1 here exactly as it is above — which is why delta can never say
      // WHICH END is short.
      '| VEIN | DIAMETER (mm) |',
      '| --- | --- |',
      '| GSV at the SFJ | 6.2 | 3.4 |',
    ].join('\n');

    const r = editTableCell({
      note: reference,
      sectionLabel: 'FINDINGS',
      rowLabel: 'GSV at the SFJ',
      columnLabel: 'DIAMETER (mm)',
      value: '9.9',
    });

    expect(r.ok).toBe(false);
    expect(r.reason).toBe('ragged_table');
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
