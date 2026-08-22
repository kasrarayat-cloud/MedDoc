// ============================================================================
// F24-S3 — THE CENSUS OF EDITOR-ADDRESSABLE REGIONS, BY REPLAY.
// ----------------------------------------------------------------------------
// RELAY's acceptance: "the census of editor-addressable regions reaches ZERO
// gaps on the certified template, proven by REPLAY — not by a source sweep."
//
// Every row of this census is produced by RUNNING the shipped editor
// (`editTableCell`) against a note built by the shipped generator
// (`renderStructureDirective`) over the real customer form compiled by the
// shipped compiler (`compileTemplateDocx`). Nothing here re-implements a
// predicate — Finding F of the substrate recon is explicit that re-implementing
// a shipped matcher inside a test is the F12-g failure.
//
// ⚠️ THE UNIVERSE IS PINNED BY CONTENT, NOT BY A VERSION FIELD — FINDING B.
// Two IR shapes exist in the wild at the IDENTICAL `compilerVersion` AND
// `irSchemaVersion`: 21 of 55 QA compiled versions carry no `rowLaterality`
// key at all, `ir.ts:72` defaults it to 'unknown', and `bridge-evidence.ts`
// then refuses EVERY sided fact against such a row. A census run on one of
// those measures a system where laterality routing can never succeed, and
// every arm would read as a finding about the editor. The predicate here is
// therefore CONTENT — rowLaterality present AND 52 sided cells — asserted as a
// non-vacuity floor before a single bucket is counted.
//
// ⚠️ AND THE FIRST DRAFT OF THIS FILE REPORTED `addressable: 0` FROM A BROKEN
// INSTRUMENT. It derived the note's columns from the IR's `table_header`
// labels and got ONE column, because the customer form's DIAMETER column is
// UNHEADED — its cell carries the vein name (`labelSource: 'left_cell'`), so
// no field anywhere in the IR is labelled `DIAMETER (mm)`. A one-column note
// makes every edit ambiguous, and the resulting zero looked exactly like a
// finding about the editor. The tell was in the instrument's own output: it
// printed one column for a two-column form. See NOTE_COLUMNS below.
// ============================================================================

import { readFileSync } from 'node:fs';
import path from 'node:path';

import { describe, expect, it } from 'vitest';

import { compileTemplateDocx } from '@/lib/note-template-docx';

import { editTableCell } from '../../note-table-edit';
import { renderStructureDirective } from '../../../worker/note-templates/build-soap-prompt';
import type { TemplateDocIR, TemplateField } from '../ir';

const WM_IOV_PATH = path.resolve(process.cwd(), '../../WM IOV Template.docx');
const ir: TemplateDocIR = compileTemplateDocx(new Uint8Array(readFileSync(WM_IOV_PATH)));

const isTableCell = (f: TemplateField) => f.rendererBinding.bindingType === 'table_cell';
const sided = (f: TemplateField) => f.rendererBinding.rowLaterality !== 'unknown';

/**
 * The note's column headers.
 *
 * ⚠️ ONLY THE SECOND ONE IS DERIVABLE FROM THE TWIN, AND THAT ASYMMETRY IS A
 * FINDING RATHER THAN AN INCONVENIENCE. `REFLUX TIME (ms)` is a real
 * `table_header` label in the IR and is asserted against it below, so this
 * constant cannot go stale silently. `DIAMETER (mm)` is NOT in the IR at all:
 * the doctor's DOCX leaves that column unheaded and the vein name sits in the
 * cell, which is why `build-soap-prompt.ts:283-291` exists. In production the
 * header text comes from `note_templates.sections`, produced by an AI-backed
 * parse (`parseNoteToTemplate`) that cannot be replayed deterministically —
 * so it is pinned here with its provenance instead of being faked as derived.
 * Same value `bridge-fill.test.ts:74` and `build-soap-prompt.ts:284` carry.
 */
const NOTE_COLUMNS = ['DIAMETER (mm)', 'REFLUX TIME (ms)'] as const;

const CAPTION: Record<string, string> = { right: 'Right Leg', left: 'Left Leg' };

/** The REAL generator's grid — its own output, read back rather than rebuilt. */
function generatedGrid(columns: readonly string[], rowLabels: string[]): string[] {
  const directive = renderStructureDirective({
    kind: 'table',
    columns: [...columns],
    rowLabels,
  } as never);
  return directive.split('\n').filter((l) => l.trim().startsWith('|'));
}

/** The IR's table rows, in document order, with the vein name and the side. */
function irRows(): { rowIndex: number; vein: string; laterality: string }[] {
  const byRow = new Map<number, TemplateField[]>();
  for (const f of ir.fields.filter(isTableCell)) {
    const r = f.rendererBinding.rowIndex ?? -1;
    (byRow.get(r) ?? byRow.set(r, []).get(r)!).push(f);
  }
  return [...byRow.keys()]
    .sort((a, b) => a - b)
    .map((rowIndex) => {
      const cellsOfRow = byRow.get(rowIndex)!;
      const labelCell = cellsOfRow.find((c) => c.labelSource === 'left_cell') ?? cellsOfRow[0];
      return {
        rowIndex,
        vein: labelCell.originalLabel,
        laterality: labelCell.rendererBinding.rowLaterality,
      };
    });
}

/**
 * The note as the system produces it for this form: ONE grid in the document
 * becomes TWO captioned markdown tables, one per leg. That is not a stylistic
 * choice — it is the shape `bridge-fill.ts:368` documents and the reason the
 * caption is the only disambiguator the editor has today.
 */
function buildNote(): string {
  const out: string[] = ['## FINDINGS'];
  for (const side of ['right', 'left'] as const) {
    const labels = irRows()
      .filter((r) => r.laterality === side)
      .map((r) => r.vein);
    out.push(CAPTION[side], ...generatedGrid(NOTE_COLUMNS, labels), '');
  }
  return out.join('\n');
}

// ---------------------------------------------------------------------------
// 0. THE UNIVERSE — pinned by CONTENT, before anything is counted
// ---------------------------------------------------------------------------
describe('F24-S3 census — the universe is pinned by content', () => {
  it('the compiled form is the 80-field shape this census is about', () => {
    expect(
      ir.fields.length,
      'not the 80-field form — every count below is about something else',
    ).toBe(80);
  });

  it('rowLaterality is PRESENT and knows a real side for 52 of 52 table cells', () => {
    const table = ir.fields.filter(isTableCell);
    expect(table.length, 'table-bound field count moved').toBe(52);
    expect(table.filter((f) => f.rendererBinding.rowLaterality === 'left').length).toBe(26);
    expect(table.filter((f) => f.rendererBinding.rowLaterality === 'right').length).toBe(26);
    expect(table.filter(sided).length, 'sided-cell floor — Finding B').toBe(52);
  });

  it('the 28 non-table fields are content controls, and none claims a side', () => {
    const nonTable = ir.fields.filter((f) => !isTableCell(f));
    expect(nonTable.length).toBe(28);
    expect(nonTable.every((f) => f.rendererBinding.bindingType === 'content_control')).toBe(true);
    expect(nonTable.filter(sided).length, 'a content control claimed a side').toBe(0);
  });

  it('the derivable column header IS derived — this constant cannot go stale silently', () => {
    const headers = new Set(
      ir.fields
        .filter((f) => isTableCell(f) && f.labelSource === 'table_header')
        .map((f) => f.originalLabel),
    );
    expect([...headers]).toEqual([NOTE_COLUMNS[1]]);
    // And the other one is genuinely absent — pinned so that the day the form
    // grows a real DIAMETER header, this arm says so instead of the constant
    // quietly becoming a lie.
    expect(
      ir.fields.some((f) => f.originalLabel.toLowerCase().includes('diameter')),
      'the IR now carries a diameter label — NOTE_COLUMNS[0] is no longer a pin',
    ).toBe(false);
  });

  it('the generator emits a two-column grid with an EMPTY leading label cell', () => {
    const grid = generatedGrid(NOTE_COLUMNS, ['GSV at the SFJ']);
    // Non-vacuity: if the generator stopped emitting a grid, every replay below
    // would refuse `no_table` and the census would read as a total failure of
    // the editor.
    expect(grid.length).toBe(3);
    expect(grid[0]).toBe('|  | DIAMETER (mm) | REFLUX TIME (ms) |');
  });
});

// ---------------------------------------------------------------------------
// 1. THE CENSUS — every field replayed through the shipped editor
// ---------------------------------------------------------------------------
describe('F24-S3 census — replay', () => {
  it('CENSUS: every one of the 80 fields lands in exactly one named bucket', () => {
    const note = buildNote();
    const rowsOfIr = irRows();

    // Non-vacuity on the note itself.
    expect(note.split('\n').filter((l) => l.startsWith('|')).length).toBeGreaterThan(20);

    /** Replay one field. `useTwin` decides whether the twin's `rowLaterality`
     *  is allowed to supply the caption — which is the whole of this item. */
    function replay(f: TemplateField, useTwin: boolean): string {
      if (!isTableCell(f)) return 'no_editor_intent';
      const row = rowsOfIr.find((r) => r.rowIndex === f.rendererBinding.rowIndex);
      if (!row) return 'no_ir_row';
      const columnLabel =
        f.labelSource === 'table_header' ? f.originalLabel : NOTE_COLUMNS[0];
      const res = editTableCell({
        note,
        sectionLabel: 'FINDINGS',
        rowLabel: row.vein,
        columnLabel,
        value: '9.9',
        ...(useTwin ? { tableCaption: CAPTION[row.laterality] } : {}),
      });
      if (!res.ok) return res.reason ?? 'unknown';

      // ⚠️ `ok: true` IS NOT ADDRESSABILITY, AND COUNTING IT AS SUCH WOULD MAKE
      // THIS CENSUS THE EXACT FAILURE ITS OWN HEADER WARNS ABOUT — a check whose
      // TITLE ("addressable") is wider than what it MEASURES ("an edit
      // returned ok"). The whole reason this item exists is that an edit can
      // succeed against the WRONG CELL and report success: that is Finding E of
      // the substrate recon, verbatim, and it is live on shipped code.
      //
      // So the bucket is earned only if the editor resolved to THIS field's own
      // row and column. Compared by exact string: `res.column` is
      // `headerCells[idx].trim()` and `res.row` is `rowCells[0].trim()`, both
      // taken from the note we asked about, so no normaliser is needed — and
      // re-implementing the editor's `norm` here would be the F12-g failure.
      if (res.column?.trim() !== columnLabel.trim()) return 'resolved_wrong_column';
      if (res.row?.trim() !== row.vein.trim()) return 'resolved_wrong_row';
      return 'addressable';
    }

    const tally = (useTwin: boolean) => {
      const t = new Map<string, number>();
      for (const f of ir.fields) {
        const b = replay(f, useTwin);
        t.set(b, (t.get(b) ?? 0) + 1);
      }
      return t;
    };

    const today = tally(false);
    const withTwin = tally(true);

    const fmt = (t: Map<string, number>) =>
      [...t.entries()]
        .sort((a, b) => b[1] - a[1])
        .map(([b, n]) => `    ${b.padEnd(24)} ${n}`)
        .join('\n');

    // eslint-disable-next-line no-console
    console.info(
      [
        '',
        'F24-S3 CENSUS — editor-addressable regions on the certified template',
        `  fields: ${ir.fields.length} · table-bound ${ir.fields.filter(isTableCell).length} · content controls ${ir.fields.filter((f) => !isTableCell(f)).length}`,
        `  distinct vein labels per leg: ${new Set(rowsOfIr.filter((r) => r.laterality === 'right').map((r) => r.vein)).size} of ${rowsOfIr.filter((r) => r.laterality === 'right').length}`,
        '',
        '  TODAY — rowLabel only (the editor has no twin awareness):',
        fmt(today),
        '',
        '  WITH THE TWIN — rowLaterality supplies the caption:',
        fmt(withTwin),
        '',
      ].join('\n'),
    );

    // ── the partition reconciles in both readings ───────────────────────────
    expect([...today.values()].reduce((a, b) => a + b, 0)).toBe(80);
    expect([...withTwin.values()].reduce((a, b) => a + b, 0)).toBe(80);

    // ── TODAY: the editor has no twin awareness, so NOTHING is addressable ──
    // ⚠️ THIS ZERO IS A MEASUREMENT, NOT A BLIND INSTRUMENT, AND THE PROOF IS
    // THE LINE BELOW IT: the SAME replay function, over the SAME note, reports
    // 40 addressable once the twin supplies the caption. An instrument that can
    // produce a non-zero is one whose zero means something.
    expect(today.get('addressable') ?? 0).toBe(0);
    expect(today.get('row_ambiguous')).toBe(52);
    expect(today.get('no_editor_intent')).toBe(28);

    // ── WITH THE TWIN: a RATCHET, not a pin ─────────────────────────────────
    // Deliberately `>=` / `<=`. A gate that goes RED when the thing it guards
    // starts working is a gate nobody keeps — and closing these gaps is exactly
    // what F24-S3 exists to do. This reddens on a REGRESSION and stays green as
    // the count improves; the exact figures of the day are printed above.
    const addressable = withTwin.get('addressable') ?? 0;
    const gaps = 80 - addressable;
    expect(addressable, 'addressability REGRESSED — the twin used to reach 40').toBeGreaterThanOrEqual(40);
    expect(gaps, 'gap set grew').toBeLessThanOrEqual(40);

    // ── THE GAP SET, NAMED. This is the item's remaining work. ──────────────
    // 28 · content controls — no editor intent addresses them at all. F24-S3
    //      PART 2: structured edits routed to their own writers.
    // 12 · `Saphenous Tributary Vein <<insert location>>`, three identical
    //      blank slots per leg × 2 cells × 2 legs. The twin knows the rowIndex;
    //      the editor addresses by LABEL, and the label is duplicated by design.
    //      Refused honestly since this branch — see `row_ambiguous_same_table`.
    expect(withTwin.get('no_editor_intent')).toBe(28);
    expect(
      withTwin.get('row_ambiguous_same_table') ?? 0,
      'the duplicate-label gap changed shape — re-read the census before trusting it',
    ).toBe(12);

    // ⚠️ AND THE ACCEPTANCE IS NOT MET. RELAY asks for ZERO gaps. It is 40.
    // Stated as an assertion rather than a comment so that the day it reaches
    // zero, this line fails and forces the ledger row to be rewritten by
    // somebody who has looked.
    expect(gaps, 'ZERO gaps reached — F24-S3 acceptance is now met; update RELAY').toBeGreaterThan(0);
  });
});
