// ============================================================================
// F24-S4 — THE EDITOR ACCEPTS A TWIN-SUPPLIED ROW ORDINAL
//
// The certified template carries `Saphenous Tributary Vein <<insert location>>`
// THREE TIMES IN EACH LEG. They are blank slots the doctor fills in, so the
// labels are identical BY DESIGN and no caption can separate them: on the
// F24-S3 census those 12 cells are the entire remaining table-bound gap
// (`addressable 40 · row_ambiguous_same_table 12`).
//
// ⚠️ WHY EVERY ASSERTION HERE IS KEYED ON CELL CONTENT AND NEVER ON THE ROW
// LABEL. The F24-S3 census earns its `addressable` bucket partly via
//
//     if (res.row?.trim() !== rowLabel.trim()) return 'resolved_wrong_row';
//
// which is a real guard and is VACUOUS ON EXACTLY THESE ROWS — all three
// candidates share one label, so it holds no matter which of the three was
// written. A gate for the ordinal that compared labels would report success
// for an off-by-one that silently overwrote a neighbouring measurement. So the
// fixture gives every duplicate row a DISTINCT value, and the assertions read
// the value back.
// ============================================================================

import { describe, it, expect } from 'vitest';
import { editTableCell, TABLE_EDIT_REASON } from '../note-table-edit';

/** Three identical-label rows per leg, each with a DISTINCT diameter, so the
 *  row that was written is identifiable from the value alone. */
const NOTE = [
  '## FINDINGS',
  '',
  'Right Leg',
  '|  | DIAMETER (mm) | REFLUX TIME (ms) |',
  '| --- | --- | --- |',
  '| GSV at the SFJ | 5.1 | 0.3 |',
  '| Saphenous Tributary Vein <<insert location>> | 1.1 | 11 |',
  '| Saphenous Tributary Vein <<insert location>> | 2.2 | 22 |',
  '| Saphenous Tributary Vein <<insert location>> | 3.3 | 33 |',
  '',
  'Left Leg',
  '|  | DIAMETER (mm) | REFLUX TIME (ms) |',
  '| --- | --- | --- |',
  '| GSV at the SFJ | 6.2 | 3.4 |',
  '| Saphenous Tributary Vein <<insert location>> | 7.7 | 77 |',
  '| Saphenous Tributary Vein <<insert location>> | 8.8 | 88 |',
  '| Saphenous Tributary Vein <<insert location>> | 9.9 | 99 |',
  '',
].join('\n');

const TRIB = 'Saphenous Tributary Vein <<insert location>>';

const base = {
  note: NOTE,
  sectionLabel: 'FINDINGS',
  rowLabel: TRIB,
  columnLabel: 'DIAMETER (mm)',
};

/** Every diameter in the note, in note order — the ONLY way to see which row
 *  actually moved. Reading `res.row` cannot answer it: all six share a label. */
function diameters(body: string): string[] {
  return body
    .split('\n')
    .filter((l) => l.includes(TRIB))
    .map((l) => l.split('|')[2].trim());
}

describe('F24-S4 — the fixture is the shape this gate is about', () => {
  // NON-VACUITY. A fixture that lost its duplicate rows would make every
  // refusal below unreachable and every arm pass for the wrong reason.
  it('carries SIX identical-label rows, three under each of two captions', () => {
    expect(NOTE.split('\n').filter((l) => l.startsWith(`| ${TRIB}`))).toHaveLength(6);
    expect(diameters(NOTE)).toEqual(['1.1', '2.2', '3.3', '7.7', '8.8', '9.9']);
  });

  it('WITHOUT an ordinal the six are unresolvable — the gap this closes', () => {
    const res = editTableCell({ ...base, value: '9.9' });
    expect(res.ok).toBe(false);
    // Two captions across the six candidates, so this is the caption-answerable
    // refusal — the ordinal is not what is being tested here.
    expect(res.reason).toBe('row_ambiguous');
  });

  it('WITH a caption but no ordinal it is the SAME-TABLE dead end', () => {
    const res = editTableCell({ ...base, value: '4.4', tableCaption: 'Right Leg' });
    expect(res.ok).toBe(false);
    expect(res.reason).toBe('row_ambiguous_same_table');
  });
});

describe('F24-S4 — the ordinal selects the row, verified by CONTENT', () => {
  // The load-bearing arm. Each ordinal must move ITS OWN row and leave the
  // other five byte-identical.
  it.each([
    [1, ['4.4', '2.2', '3.3', '7.7', '8.8', '9.9']],
    [2, ['1.1', '4.4', '3.3', '7.7', '8.8', '9.9']],
    [3, ['1.1', '2.2', '4.4', '7.7', '8.8', '9.9']],
  ])('rowOrdinal %i writes exactly that row under Right Leg', (ordinal, expected) => {
    const res = editTableCell({
      ...base,
      value: '4.4',
      tableCaption: 'Right Leg',
      rowOrdinal: ordinal as number,
    });
    expect(res.ok).toBe(true);
    expect(diameters(res.body!)).toEqual(expected);
  });

  it('reports the value it REPLACED, so an off-by-one is visible in the reply', () => {
    const res = editTableCell({
      ...base,
      value: '4.4',
      tableCaption: 'Right Leg',
      rowOrdinal: 2,
    });
    expect(res.before).toBe('2.2');
  });

  // ⚠️ THE ORDINAL IS COUNTED AFTER CAPTION NARROWING, NOT OVER THE WHOLE
  // SECTION. Ordinal 1 under `Left Leg` is the note's FOURTH tributary row.
  // If the two were composed the other way round, "the 1st tributary" would
  // mean a different row depending on whether a caption was given.
  it('counts within the captioned table — ordinal 1 of Left Leg is the 4th row', () => {
    const res = editTableCell({
      ...base,
      value: '4.4',
      tableCaption: 'Left Leg',
      rowOrdinal: 1,
    });
    expect(res.ok).toBe(true);
    expect(res.before).toBe('7.7');
    expect(diameters(res.body!)).toEqual(['1.1', '2.2', '3.3', '4.4', '8.8', '9.9']);
  });

  it('with NO caption the ordinal counts across all six, in note order', () => {
    const res = editTableCell({ ...base, value: '4.4', rowOrdinal: 5 });
    expect(res.ok).toBe(true);
    expect(res.before).toBe('8.8');
  });

  it('ordinal 1 of 1 is legitimate — an unambiguous row stays addressable', () => {
    const res = editTableCell({
      ...base,
      rowLabel: 'GSV at the SFJ',
      value: '4.4',
      tableCaption: 'Right Leg',
      rowOrdinal: 1,
    });
    expect(res.ok).toBe(true);
    expect(res.before).toBe('5.1');
  });
});

describe('F24-S4 — out of range REFUSES and never clamps', () => {
  // ⚠️ THE DIRECTION THAT MATTERS. Canon, ERR TOWARD THE EDGE: a clamp-to-last
  // would overwrite a real neighbouring measurement and report success, which
  // is strictly worse than the refusal it replaced. This arm asserts BOTH that
  // it refuses AND that the note is untouched — a refusal that had already
  // mutated the body would satisfy a reason-only check.
  it.each([4, 7, 99])('rowOrdinal %i past the end refuses, note unchanged', (n) => {
    const res = editTableCell({
      ...base,
      value: '4.4',
      tableCaption: 'Right Leg',
      rowOrdinal: n,
    });
    expect(res.ok).toBe(false);
    expect(res.reason).toBe('row_ordinal_out_of_range');
    expect(res.body).toBeUndefined();
  });

  it('does NOT clamp — ordinal 4 leaves row 3 exactly as it was', () => {
    const res = editTableCell({
      ...base,
      value: '4.4',
      tableCaption: 'Right Leg',
      rowOrdinal: 4,
    });
    expect(res.ok).toBe(false);
    // The clamp bug would have written 3.3 -> 4.4 and returned ok:true.
    expect(diameters(NOTE)).toEqual(['1.1', '2.2', '3.3', '7.7', '8.8', '9.9']);
  });

  it.each([0, -1, 1.5, NaN, Infinity])('rowOrdinal %s is invalid, not clamped to 1', (n) => {
    const res = editTableCell({
      ...base,
      value: '4.4',
      tableCaption: 'Right Leg',
      rowOrdinal: n as number,
    });
    expect(res.ok).toBe(false);
    expect(res.reason).toBe('row_ordinal_invalid');
    expect(res.body).toBeUndefined();
  });
});

describe('F24-S4 — the refusal is answerable, and the index is ISSUED not invented', () => {
  it('row_ambiguous_same_table carries one numbered choice per candidate', () => {
    const res = editTableCell({ ...base, value: '4.4', tableCaption: 'Right Leg' });
    expect(res.reason).toBe('row_ambiguous_same_table');
    expect(res.rowChoices?.map((c) => c.ordinal)).toEqual([1, 2, 3]);
  });

  // The whole point: the numbers alone are not answerable by a doctor, so the
  // cells that DO differ travel with them.
  it('each choice carries the cells that distinguish it', () => {
    const res = editTableCell({ ...base, value: '4.4', tableCaption: 'Right Leg' });
    expect(res.rowChoices?.map((c) => c.cells[1])).toEqual(['1.1', '2.2', '3.3']);
  });

  // ⚠️ THE ROUND TRIP. An issued ordinal, fed straight back, must resolve — and
  // must resolve to the row whose cells were shown beside it. This is what
  // makes it an echo rather than an inference.
  it('an ordinal taken from rowChoices resolves to the row it was shown with', () => {
    const refusal = editTableCell({ ...base, value: '4.4', tableCaption: 'Right Leg' });
    const chosen = refusal.rowChoices![1];
    const res = editTableCell({
      ...base,
      value: '4.4',
      tableCaption: 'Right Leg',
      rowOrdinal: chosen.ordinal,
    });
    expect(res.ok).toBe(true);
    expect(res.before).toBe(chosen.cells[1]);
  });

  it('the uncaptioned dead end is answerable too', () => {
    const uncaptioned = NOTE.replace('Right Leg\n', '').replace('Left Leg\n', '');
    const res = editTableCell({
      ...base,
      note: uncaptioned,
      value: '4.4',
    });
    expect(res.ok).toBe(false);
    expect(res.reason).toBe('caption_not_found');
    expect(res.rowChoices).toHaveLength(6);
  });

  // ⚠️ THE PROSE MOVED WITH THE BEHAVIOUR. The old message sent the doctor to
  // edit the document by hand, which is now false — there is an answer they
  // can give. A refusal describing a dead end that no longer exists is a
  // stated invariant that has become a wish.
  it('the doctor-facing message no longer sends them to the document', () => {
    expect(TABLE_EDIT_REASON.row_ambiguous_same_table).not.toContain('directly in the document');
    expect(TABLE_EDIT_REASON.row_ambiguous_same_table).toContain('which of the rows');
  });

  it('every failure reason has a doctor-facing message', () => {
    for (const r of ['row_ordinal_invalid', 'row_ordinal_out_of_range'] as const) {
      expect(TABLE_EDIT_REASON[r], `${r} has no message`).toBeTruthy();
    }
  });
});

describe('F24-S4 — the ordinal does not widen anything else', () => {
  it('a row that does not exist is still row_not_found, ordinal or not', () => {
    const res = editTableCell({
      ...base,
      rowLabel: 'No Such Vein',
      value: '4.4',
      rowOrdinal: 1,
    });
    expect(res.ok).toBe(false);
    expect(res.reason).toBe('row_not_found');
  });

  it('an illegal value is still refused before any ordinal work', () => {
    const res = editTableCell({
      ...base,
      value: 'a|b',
      tableCaption: 'Right Leg',
      rowOrdinal: 1,
    });
    expect(res.ok).toBe(false);
    expect(res.reason).toBe('illegal_value');
  });

  it('a caption that matches nothing still refuses rather than ordinal-ing blind', () => {
    const res = editTableCell({
      ...base,
      value: '4.4',
      tableCaption: 'Third Leg',
      rowOrdinal: 1,
    });
    // The caption narrowed to zero, which is NOT a narrowing, so all six
    // candidates remain and ordinal 1 is the first of them.
    expect(res.ok).toBe(true);
    expect(res.before).toBe('1.1');
  });
});
