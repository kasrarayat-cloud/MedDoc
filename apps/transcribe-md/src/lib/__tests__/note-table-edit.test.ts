// ============================================================================
// One cell moves. Nothing else does.
// ----------------------------------------------------------------------------
// The whole reason this module exists instead of asking a model for markdown is
// that a table round-tripped through an LLM can come back with a different digit
// in a row nobody mentioned — a fabricated measurement, in a record about to be
// signed, that nothing downstream would flag. So the tests that matter most are
// the ones asserting what did NOT change.
// ============================================================================

import { describe, expect, it } from 'vitest';

import { editTableCell, TABLE_EDIT_REASON } from '../note-table-edit';
import { readNoteSection } from '../splice-note-section';

const NOTE = [
  '## TECHNIQUE',
  'Standard venous duplex protocol was followed.',
  '',
  '## FINDINGS',
  'DIAMETER AND REFLUX TIME — Right Leg',
  '| Segment | DIAMETER (mm) | REFLUX TIME (seconds) |',
  '| --- | --- | --- |',
  '| GSV at the SFJ | 6.2 | 3.4 |',
  '| GSV at the Knee | 3.4 | 1.8 |',
  '',
  '## IMPRESSION',
  'Right great saphenous vein is reflux positive.',
].join('\n');

/** The same note with a second leg — identical row labels under both tables. */
const BILATERAL = [
  '## FINDINGS',
  'DIAMETER AND REFLUX TIME — Right Leg',
  '| Segment | DIAMETER (mm) |',
  '| --- | --- |',
  '| GSV at the SFJ | 6.2 |',
  '',
  'DIAMETER AND REFLUX TIME — Left Leg',
  '| Segment | DIAMETER (mm) |',
  '| --- | --- |',
  '| GSV at the SFJ | 5.1 |',
].join('\n');

const base = { note: NOTE, sectionLabel: 'FINDINGS' };

describe('editTableCell', () => {
  it('changes the target cell', () => {
    const r = editTableCell({ ...base, rowLabel: 'GSV at the SFJ', columnLabel: 'DIAMETER (mm)', value: '6.8' });
    expect(r.ok).toBe(true);
    expect(r.before).toBe('6.2');
    expect(r.body).toContain('| GSV at the SFJ | 6.8 | 3.4 |');
  });

  it('leaves EVERY other line byte-identical', () => {
    const r = editTableCell({ ...base, rowLabel: 'GSV at the SFJ', columnLabel: 'diameter', value: '6.8' });
    // The SAME reader the splice uses — the section this module edits and the
    // section saveNoteSectionAction writes back must be one section.
    const before = readNoteSection(NOTE, 'FINDINGS')!.split('\n');
    const after = r.body!.split('\n');
    expect(after).toHaveLength(before.length);
    after.forEach((line, i) => {
      if (line.includes('GSV at the SFJ')) return;
      expect(line, `line ${i} moved`).toBe(before[i]);
    });
  });

  it('does not touch the OTHER row in the same table', () => {
    const r = editTableCell({ ...base, rowLabel: 'GSV at the SFJ', columnLabel: 'diameter', value: '9.9' });
    expect(r.body).toContain('| GSV at the Knee | 3.4 | 1.8 |');
  });

  it('does not touch the other cell in the SAME row', () => {
    const r = editTableCell({ ...base, rowLabel: 'GSV at the SFJ', columnLabel: 'diameter', value: '9.9' });
    expect(r.body).toContain('| GSV at the SFJ | 9.9 | 3.4 |');
  });

  it('matches a column loosely — the unit parenthetical is noise', () => {
    for (const col of ['DIAMETER (mm)', 'diameter', 'Diameter', '  DIAMETER  ']) {
      expect(editTableCell({ ...base, rowLabel: 'GSV at the SFJ', columnLabel: col, value: '7' }).ok).toBe(true);
    }
  });

  it('writes the reflux column, not the diameter one', () => {
    const r = editTableCell({ ...base, rowLabel: 'GSV at the SFJ', columnLabel: 'REFLUX TIME', value: '2.0' });
    expect(r.body).toContain('| GSV at the SFJ | 6.2 | 2.0 |');
  });

  it('REFUSES a row that exists under two tables, rather than pick a leg', () => {
    const r = editTableCell({
      note: BILATERAL,
      sectionLabel: 'FINDINGS',
      rowLabel: 'GSV at the SFJ',
      columnLabel: 'diameter',
      value: '7.0',
    });
    expect(r.ok).toBe(false);
    expect(r.reason).toBe('row_ambiguous');
    expect(TABLE_EDIT_REASON[r.reason!]).toContain('which one');
  });

  it('never writes the row-label column itself', () => {
    const r = editTableCell({ ...base, rowLabel: 'GSV at the SFJ', columnLabel: 'Segment', value: 'HACKED' });
    expect(r.ok).toBe(false);
    expect(r.reason).toBe('column_not_found');
  });

  it('names a missing section, row and column separately', () => {
    expect(editTableCell({ ...base, sectionLabel: 'NOPE', rowLabel: 'x', columnLabel: 'y', value: '1' }).reason)
      .toBe('section_not_found');
    expect(editTableCell({ ...base, rowLabel: 'Nonexistent', columnLabel: 'diameter', value: '1' }).reason)
      .toBe('row_not_found');
    expect(editTableCell({ ...base, rowLabel: 'GSV at the SFJ', columnLabel: 'Nonexistent', value: '1' }).reason)
      .toBe('column_not_found');
  });

  it('a section with no table is named as such, not as a missing row', () => {
    expect(
      editTableCell({ note: NOTE, sectionLabel: 'TECHNIQUE', rowLabel: 'x', columnLabel: 'y', value: '1' }).reason,
    ).toBe('no_table');
  });

  it('reports the cell it wrote, so the reply can be specific', () => {
    const r = editTableCell({ ...base, rowLabel: 'gsv at the sfj', columnLabel: 'diameter', value: '6.8' });
    expect(r.row).toBe('GSV at the SFJ');
    expect(r.column).toBe('DIAMETER (mm)');
    expect(r.before).toBe('6.2');
  });

  it('REFUSES a value containing a pipe rather than escaping it', () => {
    // Escaping produced valid markdown that nothing else here understands:
    // claim-prose, the screen-reader block, the DOCX table builder and the
    // export reconciler all read the raw note, so `\\|` moved the corruption
    // out of the note and into every renderer. A measurement never contains a
    // pipe, so refusing is both safe and honest.
    const r = editTableCell({ ...base, rowLabel: 'GSV at the SFJ', columnLabel: 'diameter', value: '6.8 | 9.9' });
    expect(r.ok).toBe(false);
    expect(r.reason).toBe('illegal_value');
  });

  it('REFUSES a newline in a value', () => {
    const r = editTableCell({ ...base, rowLabel: 'GSV at the SFJ', columnLabel: 'diameter', value: '6.8\n9.9' });
    expect(r.ok).toBe(false);
    expect(r.reason).toBe('illegal_value');
  });

  it('leaves the sections around it alone', () => {
    const r = editTableCell({ ...base, rowLabel: 'GSV at the SFJ', columnLabel: 'diameter', value: '6.8' });
    // The body returned is FINDINGS only — the caller splices it back — so the
    // other headings must not appear in it.
    expect(r.body).not.toContain('IMPRESSION');
    expect(r.body).not.toContain('TECHNIQUE');
  });

  // ── WHAT THE AUDIT CAUGHT ───────────────────────────────────────────────
  it('resolves the section with the SAME matcher the save splices with', () => {
    // THE BLOCKER. This module used to normalise a heading by dropping a
    // trailing parenthetical ("FINDINGS (RIGHT)" -> "findings") while
    // spliceNoteSection strips all punctuation ("findings right"). Given both
    // headings, the RIGHT leg's table was read out and written back over the
    // plain FINDINGS section, deleting its rows.
    const twoHeadings = [
      '## FINDINGS',
      '| Segment | DIAMETER (mm) |',
      '| --- | --- |',
      '| GSV at the Knee | 3.4 |',
      '',
      '## FINDINGS (RIGHT)',
      '| Segment | DIAMETER (mm) |',
      '| --- | --- |',
      '| GSV at the SFJ | 6.2 |',
    ].join('\n');

    const r = editTableCell({
      note: twoHeadings,
      sectionLabel: 'FINDINGS',
      rowLabel: 'GSV at the SFJ',
      columnLabel: 'diameter',
      value: '9.9',
    });
    // "GSV at the SFJ" is NOT in the section called FINDINGS, and the row must
    // not be found there. Silently editing the other section is the bug.
    expect(r.ok).toBe(false);
    expect(r.reason).toBe('row_not_found');

    // And the body this module returns is always the body of the section the
    // splice will write to — assert on the shared reader, not on our own.
    const ok = editTableCell({
      note: twoHeadings,
      sectionLabel: 'FINDINGS (RIGHT)',
      rowLabel: 'GSV at the SFJ',
      columnLabel: 'diameter',
      value: '9.9',
    });
    expect(ok.ok).toBe(true);
    expect(readNoteSection(twoHeadings, 'FINDINGS (RIGHT)')).toContain('GSV at the SFJ');
    expect(ok.body).not.toContain('GSV at the Knee');
  });

  // ⚠️ RE-PINNED 2026-08-21 (F24 SLICE 1). THIS TEST USED TO ASSERT THAT THE
  // SHAPE BELOW IS REFUSED. Its reason, verbatim, as history:
  //
  //   "A header that omits the row-label column puts every index off by one,
  //    so the write lands in a different column from the one it reports back."
  //
  // THAT WAS TRUE WHEN WRITTEN AND THE NORMALISATION MADE IT FALSE. The header
  // is widened on parse, so the indices line up and the write lands where it
  // says it does. The sentence is not deleted — it is replaced by the arm that
  // proves it STAYS false, because the fear it expressed is exactly what would
  // return if anyone widened the guard instead of the header.
  //
  // WHAT WAS PROTECTED WAS THE REFUSAL OF GENUINE AMBIGUITY, NOT THIS FIXTURE.
  // Measured on production 2026-08-21 over every data row under a detected
  // header: delta +1 -> 339 rows, delta 0 -> 331, delta ANYTHING ELSE -> 0.
  // The universe is closed, so a +1 header is missing its LABEL column and
  // nothing else; and the missing cell is provably LEADING because a row is
  // selected only when `norm(c[0]) === wantRow`.
  describe('a ragged table: normalised when unambiguous, refused otherwise', () => {
    const note = (header: string, sep: string, rows: string[]) =>
      ['## FINDINGS', header, sep, ...rows].join('\n');
    const edit = (n: string, columnLabel = 'DIAMETER (mm)') =>
      editTableCell({
        note: n,
        sectionLabel: 'FINDINGS',
        rowLabel: 'GSV at the SFJ',
        columnLabel,
        value: '9.9',
      });

    // (a) THE UNAMBIGUOUS +1 — the owner's 339 production rows.
    it('normalises the +1 shape AND writes the CORRECT cell, both columns', () => {
      // ⚠️ ASSERT THE CELL, NOT MERELY SUCCESS. The old test's fear was a write
      // landing one column left; `ok === true` cannot see that, and a fix that
      // succeeded into the wrong column would satisfy it. 6.2 and 3.4 are
      // deliberately distinct so an off-by-one is VISIBLE.
      const legacy = note(
        '| DIAMETER (mm) | REFLUX TIME (seconds) |',
        '| --- | --- |',
        ['| GSV at the SFJ | 6.2 | 3.4 |'],
      );

      const d = edit(legacy, 'DIAMETER (mm)');
      expect(d.ok).toBe(true);
      if (d.ok) {
        expect(d.column).toBe('DIAMETER (mm)');
        expect(d.before).toBe('6.2');
        expect(d.body).toContain('| GSV at the SFJ | 9.9 | 3.4 |');
      }

      const x = edit(legacy, 'REFLUX TIME (seconds)');
      expect(x.ok).toBe(true);
      if (x.ok) {
        expect(x.column).toBe('REFLUX TIME (seconds)');
        expect(x.before).toBe('3.4');
        expect(x.body).toContain('| GSV at the SFJ | 6.2 | 9.9 |');
      }
    });

    // (b) EVERY OTHER RAGGED SHAPE — still refused, verbatim reason.
    it('still REFUSES a header two or more cells narrower', () => {
      const r = edit(note('| DIAMETER (mm) |', '| --- |', ['| GSV at the SFJ | 6.2 | 3.4 |']));
      expect(r.ok).toBe(false);
      if (!r.ok) expect(r.reason).toBe('ragged_table');
    });

    it('still REFUSES a header WIDER than its rows', () => {
      const r = edit(
        note(
          '| A | DIAMETER (mm) | REFLUX TIME (seconds) | Z |',
          '| --- | --- | --- | --- |',
          ['| GSV at the SFJ | 6.2 | 3.4 |'],
        ),
      );
      expect(r.ok).toBe(false);
      if (!r.ok) expect(r.reason).toBe('ragged_table');
    });

    it('still REFUSES when the data rows disagree with EACH OTHER', () => {
      // Nothing can be inferred about a table that is not internally consistent.
      const r = edit(
        note('| DIAMETER (mm) | REFLUX TIME (seconds) |', '| --- | --- |', [
          '| GSV at the SFJ | 6.2 | 3.4 | 9.9 |',
          '| SSV at the SPJ | 4.1 | 1.2 |',
        ]),
      );
      expect(r.ok).toBe(false);
      if (!r.ok) expect(r.reason).toBe('ragged_table');
    });

    it('leaves a well-formed table completely alone', () => {
      const r = edit(
        note('| VEIN | DIAMETER (mm) | REFLUX TIME (seconds) |', '| --- | --- | --- |', [
          '| GSV at the SFJ | 6.2 | 3.4 |',
        ]),
      );
      expect(r.ok).toBe(true);
      if (r.ok) {
        expect(r.column).toBe('DIAMETER (mm)');
        expect(r.before).toBe('6.2');
      }
    });
  });

  it('a bilateral study IS editable once the table is named', () => {
    // The refusal used to ask which leg while offering no way to answer, so the
    // commonest ultrasound on this surface could never have a cell changed.
    const ambiguous = editTableCell({
      note: BILATERAL,
      sectionLabel: 'FINDINGS',
      rowLabel: 'GSV at the SFJ',
      columnLabel: 'diameter',
      value: '7.0',
    });
    expect(ambiguous.ok).toBe(false);
    expect(ambiguous.choices).toEqual([
      'DIAMETER AND REFLUX TIME — Right Leg',
      'DIAMETER AND REFLUX TIME — Left Leg',
    ]);

    const named = editTableCell({
      note: BILATERAL,
      sectionLabel: 'FINDINGS',
      rowLabel: 'GSV at the SFJ',
      columnLabel: 'diameter',
      value: '7.0',
      tableCaption: 'Left Leg',
    });
    expect(named.ok).toBe(true);
    // The LEFT leg moved (5.1 -> 7.0) and the right one did not.
    expect(named.before).toBe('5.1');
    expect(named.body).toContain('| GSV at the SFJ | 6.2 |');
    expect(named.body).toContain('| GSV at the SFJ | 7.0 |');
  });
});
