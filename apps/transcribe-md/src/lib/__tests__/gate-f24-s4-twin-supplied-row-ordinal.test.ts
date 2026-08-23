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

import { readFileSync } from 'node:fs';
import path from 'node:path';
import { describe, it, expect } from 'vitest';
import { editTableCell, TABLE_EDIT_REASON } from '../note-table-edit';
import { EditTableCellIntentSchema } from '../chat-edit/intent';

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

  // ⚠️ THE ARM THAT CHANGED, AND IT CHANGED BECAUSE IT WAS WRONG. Its first
  // draft asserted `ok: true, before: '8.8'` — the ordinal counting across BOTH
  // legs in note order. That is a cross-leg write: the twin's ordinal counts
  // within ONE leg (1..3), so an unnarrowed 6-candidate set makes a LEFT-leg
  // field's ordinal 2 land on the RIGHT leg's second tributary, silently, and
  // report success. Found by the census arm added in the same change.
  //
  // An ordinal says WHICH ROW. It never says WHICH TABLE.
  it('with NO caption the ordinal REFUSES rather than crossing legs', () => {
    const res = editTableCell({ ...base, value: '4.4', rowOrdinal: 2 });
    expect(res.ok).toBe(false);
    expect(res.reason).toBe('row_ambiguous');
    expect(res.body).toBeUndefined();
    // And it asks for the thing that would actually resolve it.
    expect(res.choices).toEqual(['Right Leg', 'Left Leg']);
  });

  it('an ordinal cannot reach the far leg even when in range there', () => {
    // 6 candidates exist; without a caption none of ordinals 1-6 may write.
    for (const n of [1, 2, 3, 4, 5, 6]) {
      const res = editTableCell({ ...base, value: '4.4', rowOrdinal: n });
      expect(res.ok, `ordinal ${n} wrote without a table`).toBe(false);
    }
    // The note is untouched by all six attempts.
    expect(diameters(NOTE)).toEqual(['1.1', '2.2', '3.3', '7.7', '8.8', '9.9']);
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

  // ⚠️ THIS ARM USED TO ASSERT `rowChoices` HAD LENGTH 6, AND IT WAS PINNING A
  // DEFECT — CORRECTED BY THE INDEPENDENT ADVERSARIAL PASS ON THIS DIFF.
  //
  // Its name claimed the uncaptioned dead end was ANSWERABLE; its body checked
  // only that a list was PRESENT. It never fed one of those six ordinals back,
  // and every one of them was refused: the candidates span two tables, and an
  // ordinal cannot cross a table. So the doctor was shown six numbered rows,
  // spent a turn picking one, and got the same refusal with the list now gone.
  //
  // That is canon's *A CHECK WHOSE TITLE IS NARROWER THAN WHAT IT MEASURES*
  // with the title WIDER than the body — the arm was green throughout, because
  // presence was never the claim its name made.
  //
  // Two uncaptioned tables is now `caption_not_found` with NO list, which is
  // the honest answer: nothing the doctor can say resolves it, and the message
  // points at the fix — give the tables headings that differ.
  it('the uncaptioned TWO-TABLE case offers no list, because none would work', () => {
    const uncaptioned = NOTE.replace('Right Leg\n', '').replace('Left Leg\n', '');
    const res = editTableCell({
      ...base,
      note: uncaptioned,
      value: '4.4',
    });
    expect(res.ok).toBe(false);
    expect(res.reason).toBe('caption_not_found');
    expect(res.rowChoices).toBeUndefined();

    // The claim the old name made, now actually tested: whatever IS offered
    // must resolve. Vacuous here by construction, and that is the point —
    // `gate-f24-s4-ordinal-is-reachable-and-bounded.test.ts` carries the
    // non-vacuous half, where one uncaptioned table DOES get a usable list.
    for (const c of res.rowChoices ?? []) {
      expect(
        editTableCell({ ...base, note: uncaptioned, value: '4.4', rowOrdinal: c.ordinal }).ok,
      ).toBe(true);
    }
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

describe('F24-S4 — the capability HAS A CALLER, and the message is not a lie', () => {
  // ⚠️ F4's DEFECT, WHICH THIS BRANCH COMMITTED AND THIS ARM EXISTS TO STOP
  // RECURRING. The first draft added `rowOrdinal` to `editTableCell`, proved it
  // 28 ways, and never wired it: `chat-edit-visit.ts` called the function
  // without the field, so nothing in production could ever supply one. A
  // library capability with no caller passes every test it has.
  const CALLER = readFileSync(
    path.resolve(__dirname, '../../actions/chat-edit-visit.ts'),
    'utf8',
  );

  it('the model can name an ordinal — the intent schema carries it', () => {
    const parsed = EditTableCellIntentSchema.safeParse({
      kind: 'edit_table_cell',
      sectionLabel: 'FINDINGS',
      rowLabel: TRIB,
      columnLabel: 'DIAMETER (mm)',
      value: '4.4',
      rowOrdinal: 2,
    });
    expect(parsed.success).toBe(true);
  });

  it.each([0, -1, 1.5])('the schema refuses %s before it reaches the editor', (n) => {
    const parsed = EditTableCellIntentSchema.safeParse({
      kind: 'edit_table_cell',
      sectionLabel: 'FINDINGS',
      rowLabel: TRIB,
      columnLabel: 'DIAMETER (mm)',
      value: '4.4',
      rowOrdinal: n,
    });
    expect(parsed.success).toBe(false);
  });

  it('an intent WITHOUT an ordinal is still valid — this widens nothing', () => {
    const parsed = EditTableCellIntentSchema.safeParse({
      kind: 'edit_table_cell',
      sectionLabel: 'FINDINGS',
      rowLabel: TRIB,
      columnLabel: 'DIAMETER (mm)',
      value: '4.4',
    });
    expect(parsed.success).toBe(true);
  });

  // ⚠️ MATCHED ON TOKENS THAT EXIST ONLY IN CODE. Canon's substring trap: this
  // file's own comments say "rowOrdinal" and "rowChoices" in prose, and so do
  // the caller's, so a bare word would be satisfied by a COMMENT and assert
  // nothing. These two forms appear only where the work is actually done.
  it('the action passes the ordinal through to the editor', () => {
    expect(CALLER).toContain('rowOrdinal: intent.rowOrdinal');
  });

  // The message says "tell me which of the rows I listed you mean". If the
  // caller renders only `choices`, that sentence describes a list the doctor
  // was never shown — a refusal that states something false, which is worse
  // than the dead end it replaced.
  it('the refusal the message promises is actually rendered', () => {
    expect(CALLER).toContain('edit.rowChoices?.length');
    expect(TABLE_EDIT_REASON.row_ambiguous_same_table).toContain('which of the rows');
  });

  // Positive control on the reader itself: a zero from the two arms above would
  // be indistinguishable from a file that failed to load.
  it('the caller file was actually read', () => {
    expect(CALLER.length).toBeGreaterThan(1000);
    expect(CALLER).toContain('editTableCell');
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

  // ⚠️ THIS ARM'S NAME WAS RIGHT AND ITS ASSERTION WAS WRONG, WHICH IS THE
  // CHEAPEST POSSIBLE TELL AND I NEARLY SHIPPED PAST IT. It has always been
  // called "still refuses rather than ordinal-ing blind"; its first draft then
  // asserted `ok: true, before: '1.1'` — ordinal-ing blind. An unrecognised
  // caption narrows to zero, which is deliberately NOT a narrowing, so all six
  // candidates survive and the ordinal must refuse for the same reason as the
  // no-caption case.
  it('a caption that matches nothing still refuses rather than ordinal-ing blind', () => {
    const res = editTableCell({
      ...base,
      value: '4.4',
      tableCaption: 'Third Leg',
      rowOrdinal: 1,
    });
    expect(res.ok).toBe(false);
    expect(res.reason).toBe('row_ambiguous');
    expect(res.body).toBeUndefined();
  });
});
