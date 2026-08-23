import { describe, it, expect } from 'vitest';
import { renderStructureDirective } from '../build-soap-prompt';
import { editTableCell } from '@/lib/note-table-edit';
import { parseMarkdownTablesForDiagnosis } from '@/lib/template-twin/bridge-fill';
import { flattenTables } from '@/lib/ehr-formatters';

/**
 * F24 SLICE 1 — THE GENERATED SKELETON'S HEADER MATCHES THE ROWS IT DICTATES.
 *
 * `renderStructureDirective` emits a table skeleton and tells L4 to "reproduce
 * this markdown table skeleton exactly". Every row it emits leads with a label
 * cell. When the template's first column is itself a DATA column — WM_IOV's is
 * `DIAMETER (mm)` — the header had no cell for that label, so the skeleton
 * dictated a grid one cell narrower in its header than in its rows, and L4
 * obeyed.
 *
 * Measured on production 2026-08-21, over every data row under a detected
 * header: 339 rows at delta +1, 331 at delta 0, ZERO at any other delta.
 * `note-table-edit.ts:197` refuses every one of the 339 with `ragged_table` —
 * correctly, because column resolution indexes the header and writes the row at
 * the same index.
 *
 * ⚠️ THE FIX IS STOPPING THE GENERATOR FROM EMITTING A GRID THE GUARD IS RIGHT
 * TO REFUSE. This file must never be "fixed" by touching that guard.
 */
const wmIov = {
  kind: 'table',
  columns: ['DIAMETER (mm)', 'REFLUX TIME (ms)'],
  rowLabels: ['GSV at the SFJ', 'SSV at the SPJ'],
} as never;

const pipeLines = (s: string) => s.split('\n').filter((l) => l.trim().startsWith('|'));
const cellCount = (l: string) =>
  l.trim().replace(/^\|/, '').replace(/\|$/, '').split('|').length;

describe('the generated table skeleton is not ragged', () => {
  it('emits a header with the same cell count as its rows', () => {
    const lines = pipeLines(renderStructureDirective(wmIov));
    // non-vacuity: a skeleton that emitted nothing would satisfy every
    // "no mismatch" assertion below while proving nothing.
    expect(lines.length).toBeGreaterThanOrEqual(4);
    const header = cellCount(lines[0]);
    const rows = lines.slice(2).map(cellCount);
    expect(new Set(rows).size).toBe(1);
    expect(header).toBe(rows[0]);
  });

  it('⚠️ the SEPARATOR is widened with the header, not left behind', () => {
    // Found by mutation: replacing the widened separator with the original
    // left this file GREEN at 6 of 6. A 3-cell header over a 2-cell separator
    // is malformed markdown — the header/row arms cannot see it because they
    // never look at line 2. The gate caught its own author here.
    const lines = pipeLines(renderStructureDirective(wmIov));
    expect(lines[1]).toMatch(/^\|[\s:|-]+\|$/); // it IS the separator
    expect(cellCount(lines[1])).toBe(cellCount(lines[0]));
    expect(cellCount(lines[1])).toBe(cellCount(lines[2]));
  });

  it('the label cell is EMPTY — it does not invent a column name', () => {
    // The doctor's DOCX has an unheaded first cell. Naming it would assert a
    // header their form does not carry.
    const lines = pipeLines(renderStructureDirective(wmIov));
    const first = lines[0].trim().replace(/^\|/, '').split('|')[0].trim();
    expect(first).toBe('');
    // and the real column names survive, in order
    expect(lines[0]).toContain('DIAMETER (mm)');
    expect(lines[0]).toContain('REFLUX TIME (ms)');
  });

  it('a note built from the skeleton is EDITABLE by the real editor', () => {
    const lines = pipeLines(renderStructureDirective(wmIov));
    const note = ['## VENOUS REFLUX STUDY', '', ...lines, ''].join('\n');
    const r = editTableCell({
      note,
      sectionLabel: 'VENOUS REFLUX STUDY',
      rowLabel: 'SSV at the SPJ',
      columnLabel: 'DIAMETER (mm)',
      value: '7.3',
    });
    expect(r.ok).toBe(true);
    if (r.ok) expect(r.column).toBe('DIAMETER (mm)');
  });

  it('⚠️ THE GUARD STILL REFUSES A GENUINELY RAGGED GRID', () => {
    // The control that stops this file being satisfied by a weakened guard.
    //
    // ⚠️ THIS FIXTURE WAS A +1 HEADER AND THAT WAS WRONG ONCE WIDEN-ON-PARSE
    // SHIPPED. A +1 is the UNAMBIGUOUS shape — 339 production rows, universe
    // closed at delta 0 and +1 with nothing else — and it is now normalised on
    // purpose, so this arm was asserting a refusal the slice deliberately
    // removed. It went red on the first full run after the two halves were put
    // together, which is the arm doing its job about the WRONG quantity.
    // A genuinely ragged grid is one nothing can be inferred about: here a
    // header TWO cells short, so no single missing label column explains it.
    const ragged = [
      '## X',
      '| DIAMETER (mm) |',
      '| --- |',
      '| SSV at the SPJ | 4.1 | 1.2 |',
    ].join('\n');
    const r = editTableCell({
      note: ragged,
      sectionLabel: 'X',
      rowLabel: 'SSV at the SPJ',
      columnLabel: 'DIAMETER (mm)',
      value: '7.3',
    });
    expect(r.ok).toBe(false);
    if (!r.ok) expect(r.reason).toBe('ragged_table');
  });

  it('the FILL path reads the corrected shape, and still reads the legacy one', () => {
    // The fill path's two-shape tolerance is deliberate. ⚠️ ITS MECHANISM
    // CHANGED UNDER RULING #140 and this comment used to name the old one
    // ("bridge-fill.ts:421 switches labelColumnOffset on whether header[0]
    // classifies as data"): the offset now comes from the header/row DELTA
    // plus the shared `classifyHeaderCell`, and the line reference was stale.
    // The tolerance itself, and everything this arm asserts, is unchanged —
    // the corrected shape is delta 0 and the legacy shape is delta 1.
    // This asserts the fix moves it between two branches that BOTH work,
    // rather than relying on tolerance that was never load-bearing.
    const rows = ['| GSV at the SFJ | 6.2 | 3.4 |', '| SSV at the SPJ | 4.1 | 1.2 |'];
    const corrected = ['|  | DIAMETER (mm) | REFLUX TIME (ms) |', '| --- | --- | --- |', ...rows].join('\n');
    const legacy = ['| DIAMETER (mm) | REFLUX TIME (ms) |', '| --- | --- |', ...rows].join('\n');
    const a = parseMarkdownTablesForDiagnosis(corrected);
    const b = parseMarkdownTablesForDiagnosis(legacy);
    expect(a[0].rows).toHaveLength(2);
    expect(b[0].rows).toHaveLength(2);
    expect(a[0].header).toHaveLength(3);
    expect(b[0].header).toHaveLength(2);
  });

  it('a template that ALREADY has a label column is left alone', () => {
    // Direction control: the fix must only add a cell where one is missing.
    const labelled = {
      kind: 'table',
      columns: ['VEIN', 'DIAMETER (mm)'],
      rowLabels: ['GSV at the SFJ'],
    } as never;
    const lines = pipeLines(renderStructureDirective(labelled));
    expect(lines[0].trim().replace(/^\|/, '').split('|')[0].trim()).toBe('VEIN');
    expect(cellCount(lines[0])).toBe(cellCount(lines[2]));
  });

  it('⚠️ the EHR paste carries no stray ": " for the unheaded column', () => {
    // Found by the adversarial pass in the EXPORT — the surface this change
    // was not aimed at. Zipping an empty header cell blindly produced
    //     : GSV at the SFJ · DIAMETER (mm): 6.2 · REFLUX TIME (ms): 3.4
    // in the text a doctor pastes into Epic or Cerner.
    const t = [
      '|  | DIAMETER (mm) | REFLUX TIME (ms) |',
      '| --- | --- | --- |',
      '| GSV at the SFJ | 6.2 | 3.4 |',
    ].join('\n');
    const out = flattenTables(t);
    expect(out.startsWith(':')).toBe(false);
    expect(out).toBe('GSV at the SFJ · DIAMETER (mm): 6.2 · REFLUX TIME (ms): 3.4');
    // DIRECTION CONTROL: a NAMED first column must still be labelled — the fix
    // must not strip names, only skip absent ones. THREE columns, because a
    // 2-column table takes flattenTables' documented `label: value` collapse
    // and never reaches the zip this fix touches. (My first version of this
    // control used two and asserted the zipped form — the arm caught my
    // expectation, not the code.)
    const named = [
      '| VEIN | DIAMETER (mm) | REFLUX TIME (ms) |',
      '| --- | --- | --- |',
      '| GSV at the SFJ | 6.2 | 3.4 |',
    ].join('\n');
    expect(flattenTables(named)).toBe(
      'VEIN: GSV at the SFJ · DIAMETER (mm): 6.2 · REFLUX TIME (ms): 3.4',
    );
  });
});
