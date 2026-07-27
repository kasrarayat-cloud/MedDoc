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

import { editTableCell, findSection, TABLE_EDIT_REASON } from '../note-table-edit';

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
    const before = findSection(NOTE, 'FINDINGS')!.lines;
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

  it('a value containing a pipe cannot break out of its cell', () => {
    // Unescaped, "6.8 | 9.9" closes the cell early: the row gains a fourth
    // column and every measurement to the right of it lands under the wrong
    // heading. Caught by this test on the first run.
    const r = editTableCell({ ...base, rowLabel: 'GSV at the SFJ', columnLabel: 'diameter', value: '6.8 | 9.9' });
    expect(r.ok).toBe(true);
    const row = r.body!.split('\n').find((l) => l.includes('GSV at the SFJ'))!;
    // Three cells, exactly as before: 4 structural pipes + 1 escaped.
    expect((row.match(/(?<!\\)\|/g) || []).length).toBe(4);
    expect(row).toContain('6.8 \\| 9.9');
    // And the reflux value is still in the reflux column.
    expect(row.trim().endsWith('| 3.4 |')).toBe(true);
  });

  it('a newline in a value cannot end the row', () => {
    const r = editTableCell({ ...base, rowLabel: 'GSV at the SFJ', columnLabel: 'diameter', value: '6.8\n9.9' });
    expect(r.ok).toBe(true);
    expect(r.body!.split('\n').filter((l) => l.includes('GSV at the SFJ'))).toHaveLength(1);
  });

  it('leaves the sections around it alone', () => {
    const r = editTableCell({ ...base, rowLabel: 'GSV at the SFJ', columnLabel: 'diameter', value: '6.8' });
    // The body returned is FINDINGS only — the caller splices it back — so the
    // other headings must not appear in it.
    expect(r.body).not.toContain('IMPRESSION');
    expect(r.body).not.toContain('TECHNIQUE');
  });
});
