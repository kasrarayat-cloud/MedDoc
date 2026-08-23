// ============================================================================
// F24-S4 — THE ADVERSARIAL PASS'S GATE: THE ORDINAL IS REACHABLE, AND BOUNDED
//
// Written by the INDEPENDENT adversarial pass on PR #809 (loop run
// 20260823-071023-b1, session 03), against a branch its author had already
// proved 29 ways and cited 4 of 4. Every arm below was RED on `e8544cba`
// before the fix that accompanies it.
//
// ⚠️ THE DEFECT WAS ONE LAYER ABOVE EVERY EXISTING PROOF. The author's gate
// checks the editor (`editTableCell` accepts `rowOrdinal`), the schema
// (`EditTableCellIntentSchema` parses it) and the caller (`chat-edit-visit.ts`
// passes it through). All three are correct. The one actor that has to
// PRODUCE an ordinal is the MODEL, and the model is instructed by exactly one
// artifact — `CHAT_EDIT_SYSTEM` in `lib/chat-edit/prompt.ts` — which this
// branch never touched and which never mentions the field.
//
// So the capability was wired end-to-end and unreachable, and the refusal that
// invites it — "tell me which of the rows I listed you mean and I will change
// it" — was a promise the system had no path to keeping.
//
// This is canon's *A CHECK WHOSE TITLE IS NARROWER THAN WHAT IT MEASURES*,
// arriving with the title WIDER than the measurement: the author's arm named
// "the model can name an ordinal" asserts only that ZOD accepts the field. It
// is a claim about the model discharged by an assertion about a parser, and it
// is green whether or not `prompt.ts` mentions `rowOrdinal` at all.
// ============================================================================

import { readFileSync } from 'node:fs';
import path from 'node:path';
import { describe, it, expect } from 'vitest';
import { editTableCell, TABLE_EDIT_REASON } from '../note-table-edit';
import { CHAT_EDIT_SYSTEM } from '../chat-edit/prompt';

/** Already joined at its export site — kept as its own binding so every arm
 *  below reads the exact string the model is sent, never a re-derivation. */
const PROMPT = CHAT_EDIT_SYSTEM;

const TRIB = 'Saphenous Tributary Vein <<insert location>>';

/** Two tables, three identical-label rows each, every diameter distinct so the
 *  row that actually moved is identifiable from the VALUE — never from the
 *  label, which all six share. */
const CAPTIONED = [
  '## FINDINGS',
  '',
  'Right Leg',
  '|  | DIAMETER (mm) | REFLUX TIME (ms) |',
  '| --- | --- | --- |',
  `| ${TRIB} | 1.1 | 11 |`,
  `| ${TRIB} | 2.2 | 22 |`,
  `| ${TRIB} | 3.3 | 33 |`,
  '',
  'Left Leg',
  '|  | DIAMETER (mm) | REFLUX TIME (ms) |',
  '| --- | --- | --- |',
  `| ${TRIB} | 7.7 | 77 |`,
  `| ${TRIB} | 8.8 | 88 |`,
  `| ${TRIB} | 9.9 | 99 |`,
  '',
].join('\n');

/** The same note with both caption lines removed — the shape that produces
 *  `caption_not_found`, i.e. "two tables and NEITHER can be named". */
const UNCAPTIONED = CAPTIONED.replace('Right Leg\n', '').replace('Left Leg\n', '');

const base = {
  sectionLabel: 'FINDINGS',
  rowLabel: TRIB,
  columnLabel: 'DIAMETER (mm)',
};

describe('F24-S4 pass — the fixture is the shape these arms are about', () => {
  // Non-vacuity. Every arm below is worthless if the note does not actually
  // carry the ambiguity, and a fixture that silently stopped doing so would
  // make the whole file pass by describing nothing.
  it('carries six identical-label rows across two tables', () => {
    expect(CAPTIONED.split('\n').filter((l) => l.startsWith(`| ${TRIB}`))).toHaveLength(6);
    expect(UNCAPTIONED.split('\n').filter((l) => l.startsWith(`| ${TRIB}`))).toHaveLength(6);
  });

  it('the uncaptioned variant really has lost its captions', () => {
    expect(CAPTIONED).toContain('Right Leg');
    expect(UNCAPTIONED).not.toContain('Right Leg');
    expect(UNCAPTIONED).not.toContain('Left Leg');
  });
});

// ---------------------------------------------------------------------------
// FINDING 1 — THE MODEL IS NEVER TOLD THE FIELD EXISTS
// ---------------------------------------------------------------------------
describe('F24-S4 pass — the ordinal is REACHABLE by the only actor that can send one', () => {
  // ⚠️ POSITIVE CONTROL FIRST, BECAUSE THIS WHOLE BLOCK RESTS ON A GREP OF ONE
  // FILE. `tableCaption` is the sibling field that WAS documented when it
  // shipped, so it proves the matcher and the file resolve. Without it, a
  // prompt that failed to load and a prompt missing the field are the same
  // zero — canon's two-zeroes-with-opposite-meanings.
  it('the prompt was actually read, and it documents the sibling field', () => {
    expect(PROMPT.length).toBeGreaterThan(1000);
    expect(PROMPT).toContain('edit_table_cell');
    expect(PROMPT).toContain('tableCaption');
  });

  // THE ARM THAT WAS RED. The model's ONLY instructions are this prompt: the
  // zod schema reaches it as a tool input_schema (`useToolUse` in
  // chat-edit-visit.ts) but `intent.ts` carries no `.describe()` anywhere, so
  // the JSDoc that says "THIS FIELD IS AN ECHO AND NOT A COUNT THE MODEL TAKES
  // OFF THE NOTE" reaches nobody. The model sees a bare unexplained integer.
  it('the prompt names `rowOrdinal`, or no model can ever answer the refusal', () => {
    expect(PROMPT).toContain('rowOrdinal');
  });

  // ⚠️ AND NAMING IT IS NOT ENOUGH — THE SAFETY RULE IS THE POINT.
  // `tableCaption` shipped with "If the doctor did not say which side, ASK —
  // do not pick one." The ordinal's equivalent hazard is strictly worse: an
  // index counted off a note is unverifiable by the person reading the reply,
  // where a caption at least names something they can recognise. The field's
  // own JSDoc forbids exactly this and forbids it where nothing can read it.
  it('the prompt forbids INVENTING one — an ordinal is echoed, never counted', () => {
    const seg = PROMPT.slice(PROMPT.indexOf('rowOrdinal'));
    // Matched on the instruction's meaning, not on one phrasing: the prompt
    // must tell the model the number comes from the application's own list.
    expect(seg).toMatch(/only[\s\S]{0,400}(listed|offered|numbered)|(listed|offered|numbered)[\s\S]{0,400}back/i);
    expect(seg).toMatch(/never|do not|don't/i);
  });
});

// ---------------------------------------------------------------------------
// FINDING 2 — THE REFUSAL'S PROMISE MUST BE KEEPABLE, END TO END
// ---------------------------------------------------------------------------
describe('F24-S4 pass — the promise the refusal makes can actually be kept', () => {
  // The captioned case is the one the ordinal was built for, and it works.
  // Asserted here so the file cannot be read as "the ordinal is broken".
  it('a caption plus an issued ordinal resolves, and writes the row it names', () => {
    const first = editTableCell({ ...base, note: CAPTIONED, value: '4.4', tableCaption: 'Left Leg' });
    expect(first.ok).toBe(false);
    expect(first.reason).toBe('row_ambiguous_same_table');
    expect(first.rowChoices).toHaveLength(3);

    const chosen = first.rowChoices![1];
    const second = editTableCell({
      ...base,
      note: CAPTIONED,
      value: '4.4',
      tableCaption: 'Left Leg',
      rowOrdinal: chosen.ordinal,
    });
    expect(second.ok).toBe(true);
    // Keyed on CONTENT. `res.row` is the shared label and cannot discriminate.
    expect(second.before).toBe('8.8');
  });

  // ⚠️ THE ARM THAT WAS RED, AND IT IS THE DISHONEST-AFFORDANCE ONE.
  //
  // On the uncaptioned note `editTableCell` returns `caption_not_found`
  // CARRYING six numbered `rowChoices`, and `chat-edit-visit.ts` renders
  // `rowChoices` in PREFERENCE to `choices` — so the doctor is shown a numbered
  // list of six rows spanning both legs. Every ordinal in that list is then
  // guaranteed to be refused, because the ordinal path requires the candidates
  // to have been narrowed to ONE table first.
  //
  // A list you are shown and cannot use is the dead end this slice set out to
  // remove, wearing the costume of the fix. The author's own arm for this case
  // is named "the uncaptioned dead end is answerable too" and asserts only
  // that `rowChoices` is PRESENT — it never checks that any ordinal resolves,
  // which is the entire claim the name makes.
  // ⚠️ THE CAPABILITY ARM, AND IT IS WHY THE ONE BELOW CANNOT BE SATISFIED BY
  // SUPPRESSION ALONE. A single UNCAPTIONED table with the label repeated is a
  // real shape, an ordinal genuinely resolves it, and a fix that simply stopped
  // offering lists everywhere would redden here. Canon: prove the guard MOVES
  // toward success, not only that it can go red.
  it('one uncaptioned table with a repeated label IS answerable by ordinal', () => {
    const single = [
      '## FINDINGS',
      '',
      '|  | DIAMETER (mm) | REFLUX TIME (ms) |',
      '| --- | --- | --- |',
      `| ${TRIB} | 1.1 | 11 |`,
      `| ${TRIB} | 2.2 | 22 |`,
      `| ${TRIB} | 3.3 | 33 |`,
      '',
    ].join('\n');

    const first = editTableCell({ ...base, note: single, value: '4.4' });
    // ONE table, so the honest reason is "the row repeats in this table" —
    // never "I cannot tell two tables apart", which is what it used to say.
    expect(first.reason).toBe('row_ambiguous_same_table');
    expect(first.rowChoices).toHaveLength(3);

    const third = editTableCell({ ...base, note: single, value: '4.4', rowOrdinal: 3 });
    expect(third.ok).toBe(true);
    expect(third.before).toBe('3.3');
  });

  it('every ordinal offered on an uncaptioned refusal is actually usable', () => {
    const first = editTableCell({ ...base, note: UNCAPTIONED, value: '4.4' });
    expect(first.reason).toBe('caption_not_found');

    // Whatever the refusal OFFERS, it must be answerable. Either it offers
    // nothing here (correct — the doctor's next move is to caption the
    // tables), or every number it offers resolves.
    for (const c of first.rowChoices ?? []) {
      const next = editTableCell({
        ...base,
        note: UNCAPTIONED,
        value: '4.4',
        rowOrdinal: c.ordinal,
      });
      expect(
        next.ok,
        `ordinal ${c.ordinal} was offered by the refusal and then refused as ${next.reason}`,
      ).toBe(true);
    }
  });

  // ⚠️ AND THE SAME REASON CODE MUST NOT CHANGE ITS SHAPE BETWEEN TURNS.
  // Turn 1 (`caption_not_found`) carried `rowChoices`; turn 2, reached by
  // echoing one of them, returns `caption_not_found` with NO `rowChoices`, so
  // the list the message refers to vanishes from under the doctor.
  it('a refusal does not drop the list it showed a turn earlier', () => {
    const first = editTableCell({ ...base, note: UNCAPTIONED, value: '4.4' });
    const second = editTableCell({ ...base, note: UNCAPTIONED, value: '4.4', rowOrdinal: 1 });
    if (second.reason === first.reason) {
      expect(
        (second.rowChoices?.length ?? 0) === (first.rowChoices?.length ?? 0),
        `${first.reason} carried ${first.rowChoices?.length ?? 0} choices, then ${second.rowChoices?.length ?? 0}`,
      ).toBe(true);
    }
  });

  // The doctor-facing prose must match what the refusal can actually accept.
  // `caption_not_found` means "neither table has a heading I can tell them
  // apart by" — so telling the doctor to name the table is the correct advice,
  // and it must not be paired with a numbered row list that implies otherwise.
  it('caption_not_found asks for the thing that can actually resolve it', () => {
    expect(TABLE_EDIT_REASON.caption_not_found).toMatch(/name each table|heading/i);
  });
});

// ---------------------------------------------------------------------------
// FINDING 3 — THE UNSAFE DIRECTION STAYS CLOSED
// ---------------------------------------------------------------------------
describe('F24-S4 pass — an ordinal never crosses a table, and never clamps', () => {
  // These two hold on `e8544cba` and are asserted here so a fix for the arms
  // above cannot buy reachability by weakening the guard that makes the
  // feature safe. Canon, *ERR TOWARD THE EDGE*: an over-shoot fails closed and
  // is visibly missing; an under-shoot writes a real neighbouring measurement.
  it('an ordinal alone cannot select across two tables', () => {
    const res = editTableCell({ ...base, note: CAPTIONED, value: '4.4', rowOrdinal: 4 });
    expect(res.ok).toBe(false);
    expect(res.reason).toBe('row_ambiguous');
  });

  it('out of range refuses and leaves every row byte-identical', () => {
    const res = editTableCell({
      ...base,
      note: CAPTIONED,
      value: '4.4',
      tableCaption: 'Right Leg',
      rowOrdinal: 4,
    });
    expect(res.ok).toBe(false);
    expect(res.reason).toBe('row_ordinal_out_of_range');
    expect(res.body).toBeUndefined();
  });
});
