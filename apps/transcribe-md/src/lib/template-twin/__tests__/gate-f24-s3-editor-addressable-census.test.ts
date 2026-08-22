// ============================================================================
// F24-S3 — THE CENSUS OF EDITOR-ADDRESSABLE REGIONS, BY REPLAY.
// ----------------------------------------------------------------------------
// RELAY's acceptance: "the census of editor-addressable regions reaches ZERO
// gaps on the certified template, proven by REPLAY — not by a source sweep."
//
// The table-bound rows here are produced by RUNNING the shipped editor
// (`editTableCell`) against notes built by the shipped generator
// (`renderStructureDirective`) over the real customer form compiled by the
// shipped compiler. Nothing re-implements a predicate — Finding F of the
// substrate recon is explicit that re-implementing a shipped matcher inside a
// test is the F12-g failure.
//
// ⚠️ 28 OF THE 80 ROWS ARE A CLASSIFICATION, NOT A REPLAY, AND THE HEADER SAYS
// SO BECAUSE AN EARLIER DRAFT DID NOT. Content controls have no editor intent
// at all, so they never reach `editTableCell`. "Every row is produced by
// running the shipped editor" was false for 35% of this census.
//
// ⚠️ THE UNIVERSE IS PINNED BY CONTENT, NOT BY A VERSION FIELD — FINDING B.
// Two IR shapes exist in the wild at the IDENTICAL `compilerVersion` AND
// `irSchemaVersion`: 21 of 55 QA compiled versions carry no `rowLaterality`
// key at all, `ir.ts:72` defaults it to 'unknown', and `bridge-evidence.ts`
// then refuses EVERY sided fact against such a row. A census run on one of
// those measures a system where laterality routing can never succeed. The
// predicate here is therefore CONTENT — rowLaterality present AND 52 sided
// cells — asserted as a non-vacuity floor before a single bucket is counted.
//
// ⚠️ AND TWO EARLIER DRAFTS OF THIS FILE WERE WRONG IN WAYS WORTH KEEPING:
//
//   1. It derived the note's columns from the IR's `table_header` labels and
//      got ONE column, because the customer form's DIAMETER column is
//      UNHEADED — its cell carries the vein name (`labelSource: 'left_cell'`),
//      so no field anywhere in the IR is labelled `DIAMETER (mm)`. A one-column
//      note makes every edit ambiguous, and the resulting `addressable: 0`
//      looked exactly like a finding about the editor. The tell was in the
//      instrument's own output: one column printed for a two-column form.
//
//   2. It measured ONE note arrangement and reported the answer as "the"
//      census. See the SHAPES block below — that one is the more dangerous of
//      the two, because its number was plausible.
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
 * ⚠️ ONLY THE SECOND ONE IS DERIVABLE FROM THE TWIN, AND THE FIRST IS AN
 * ASSUMPTION THIS CENSUS CANNOT CHECK. `REFLUX TIME (ms)` is a real
 * `table_header` label in the IR and is asserted against it below, so it cannot
 * go stale silently. `DIAMETER (mm)` is NOT in the IR at all: the doctor's DOCX
 * leaves that column unheaded and the vein name sits in the cell, which is why
 * `build-soap-prompt.ts:283-291` exists. In production the header text comes
 * from `note_templates.sections`, produced by an AI-backed parse
 * (`parseNoteToTemplate`) that cannot be replayed deterministically.
 *
 * ⚠️ SO THIS CONSTANT BOTH BUILDS THE NOTE AND QUERIES IT, AND A WRONG VALUE
 * WOULD BE INVISIBLE HERE WHILE BREAKING EVERY REAL EDIT. If production's
 * header is anything other than `DIAMETER (mm)`, real edits return
 * `column_not_found` and this census still reads the same number. That is a
 * limit of the harness, stated rather than papered over; closing it means
 * reading the header off this template's real `note_templates.sections` row.
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
 * ⚠️ THE NOTE SHAPE IS A ROUTE, NOT A DETAIL — AND AN EARLIER DRAFT OF THIS
 * FILE MEASURED EXACTLY ONE OF THEM AND REPORTED THE ANSWER AS "THE" CENSUS.
 *
 * That draft built ONE arrangement — a bare caption on the line immediately
 * above each leg's header — and reported `addressable: 40`. The mandatory
 * adversarial pass refuted it: the captions and the leg split are written by
 * THIS FILE, not by the generator (`renderStructureDirective` emits a single
 * grid and no caption at all), and the arrangement chosen happens to be the one
 * in which caption disambiguation can work at all. Run over the shapes this
 * repository itself documents, the same census gives 0.
 *
 * That is canon's "A WELL-CHOSEN FIXTURE DISGUISES A WRONG UNIVERSE", landing
 * in the harness rather than in the product: a number that is a property of the
 * fixture, presented as a property of the system.
 *
 * So the census runs the MATRIX. Each shape is a real candidate for how this
 * template's notes are written, each carries its provenance, and each is
 * measured with the best route the TWIN can offer for that shape — because
 * measuring a caption route against a note that has no captions would OVER-state
 * the gap exactly as the single-shape draft UNDER-stated it.
 *
 * ⚠️ WHICH SHAPE PRODUCTION ACTUALLY HOLDS IS NOT ESTABLISHED HERE. That needs
 * a query against this template's real `transcribe_visits.soapFinal` rows, and
 * it is named in the ledger as the next measurement rather than guessed at.
 */
interface NoteShape {
  name: string;
  provenance: string;
  note: string;
  /** How the twin would address a row on this shape. */
  twinRowLabel: (vein: string, laterality: string) => string;
  twinCaption: (laterality: string) => string | undefined;
}

function legTables(
  caption: (side: string) => string[],
  labelFor: (vein: string, side: string) => string,
): string {
  const out: string[] = ['## FINDINGS'];
  for (const side of ['right', 'left'] as const) {
    const labels = irRows()
      .filter((r) => r.laterality === side)
      .map((r) => labelFor(r.vein, side));
    out.push(...caption(side), ...generatedGrid(NOTE_COLUMNS, labels), '');
  }
  return out.join('\n');
}

const SHAPES: NoteShape[] = [
  {
    name: 'captioned-adjacent',
    provenance: 'caption directly above the header — the only arrangement captionFor can read',
    note: legTables((s) => [CAPTION[s]], (v) => v),
    twinRowLabel: (v) => v,
    twinCaption: (lat) => CAPTION[lat],
  },
  {
    name: 'captioned-blank-line',
    provenance:
      'caption, BLANK LINE, then the table — bridge-fill.test.ts SPLIT_NOTE; canon records 20 of 45 production headers with a blank line above',
    note: legTables((s) => [CAPTION[s], ''], (v) => v),
    twinRowLabel: (v) => v,
    twinCaption: (lat) => CAPTION[lat],
  },
  {
    name: 'combined-leg-in-label',
    provenance:
      'ONE table, the leg carried in the row label — bridge-fill.test.ts primary NOTE fixture, and the single-skeleton shape bridge-fill.ts:366-372 describes',
    note: [
      '## FINDINGS',
      ...generatedGrid(
        NOTE_COLUMNS,
        irRows().map((r) => `${r.laterality === 'right' ? 'Right' : 'Left'} ${r.vein}`),
      ),
    ].join('\n'),
    // No caption exists on this shape, so the twin's route is the LABEL: it
    // knows the side and can name the row the way the note names it.
    twinRowLabel: (v, lat) => `${lat === 'right' ? 'Right' : 'Left'} ${v}`,
    twinCaption: () => undefined,
  },
];

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

  it('the derivable column header IS derived — that constant cannot go stale silently', () => {
    const headers = new Set(
      ir.fields
        .filter((f) => isTableCell(f) && f.labelSource === 'table_header')
        .map((f) => f.originalLabel),
    );
    expect([...headers]).toEqual([NOTE_COLUMNS[1]]);
    // And the other is genuinely absent — pinned so that the day the form grows
    // a real DIAMETER header, this says so instead of the constant becoming a
    // lie. ⚠️ It does NOT verify that production's header IS `DIAMETER (mm)`;
    // see the note on NOTE_COLUMNS.
    expect(
      ir.fields.some((f) => f.originalLabel.toLowerCase().includes('diameter')),
      'the IR now carries a diameter label — NOTE_COLUMNS[0] is no longer a pin',
    ).toBe(false);
  });

  it('the generator emits a two-column grid with an EMPTY leading label cell', () => {
    const grid = generatedGrid(NOTE_COLUMNS, ['GSV at the SFJ']);
    // Non-vacuity: if the generator stopped emitting a grid, every replay would
    // refuse `no_table` and the census would read as a failure of the editor.
    expect(grid.length).toBe(3);
    expect(grid[0]).toBe('|  | DIAMETER (mm) | REFLUX TIME (ms) |');
  });

  it('⚠️ the generator supplies NO caption — the captions below are the harness’s', () => {
    // The arm that would have caught the single-shape draft. If this ever goes
    // red because the generator started emitting a caption, the SHAPES matrix
    // is measuring something other than what ships.
    const directive = renderStructureDirective({
      kind: 'table',
      columns: [...NOTE_COLUMNS],
      rowLabels: ['GSV at the SFJ'],
    } as never);
    expect(directive.includes('Right Leg')).toBe(false);
    expect(directive.includes('Left Leg')).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// 1. THE CENSUS — replayed over EVERY candidate note shape
// ---------------------------------------------------------------------------
describe('F24-S3 census — replay, over every candidate note shape', () => {
  const rowsOfIr = irRows();

  function replay(f: TemplateField, shape: NoteShape, useTwin: boolean): string {
    // ⚠️ A CLASSIFICATION, NOT A REPLAY — see the file header. A content
    // control never reaches the editor because no intent addresses one.
    if (!isTableCell(f)) return 'no_editor_intent';
    const row = rowsOfIr.find((r) => r.rowIndex === f.rendererBinding.rowIndex);
    if (!row) return 'no_ir_row';
    const columnLabel = f.labelSource === 'table_header' ? f.originalLabel : NOTE_COLUMNS[0];
    const rowLabel = useTwin ? shape.twinRowLabel(row.vein, row.laterality) : row.vein;
    const caption = useTwin ? shape.twinCaption(row.laterality) : undefined;
    const res = editTableCell({
      note: shape.note,
      sectionLabel: 'FINDINGS',
      rowLabel,
      columnLabel,
      value: '9.9',
      ...(caption ? { tableCaption: caption } : {}),
    });
    if (!res.ok) return res.reason ?? 'unknown';

    // ⚠️ `ok: true` IS NOT ADDRESSABILITY. An edit CAN succeed against the wrong
    // cell and report success — Finding E of the substrate recon, live on
    // shipped code — so a bucket earned on `ok` alone would make this census the
    // "title wider than what it measures" failure its own header cites.
    // Compared by exact string: `res.column` is `headerCells[idx].trim()` and
    // `res.row` is `rowCells[0].trim()`, both read out of the note we asked
    // about, so no normaliser is needed — and re-implementing the editor's
    // `norm` here would be the F12-g failure.
    if (res.column?.trim() !== columnLabel.trim()) return 'resolved_wrong_column';
    if (res.row?.trim() !== rowLabel.trim()) return 'resolved_wrong_row';
    return 'addressable';
  }

  const tally = (shape: NoteShape, useTwin: boolean) => {
    const t = new Map<string, number>();
    for (const f of ir.fields) {
      const b = replay(f, shape, useTwin);
      t.set(b, (t.get(b) ?? 0) + 1);
    }
    return t;
  };

  it('CENSUS: the matrix, and every field lands in exactly one named bucket', () => {
    const lines: string[] = [
      '',
      'F24-S3 CENSUS — editor-addressable regions on the certified template',
      `  fields ${ir.fields.length} · table-bound ${ir.fields.filter(isTableCell).length} · content controls ${ir.fields.filter((f) => !isTableCell(f)).length}`,
      `  distinct vein labels per leg: ${new Set(rowsOfIr.filter((r) => r.laterality === 'right').map((r) => r.vein)).size} of ${rowsOfIr.filter((r) => r.laterality === 'right').length}`,
      '',
    ];

    const best = new Map<string, number>();

    for (const shape of SHAPES) {
      // Non-vacuity, PER SHAPE: a shape whose note lost its tables would bucket
      // everything as `no_table` and read as a finding about the editor.
      expect(
        shape.note.split('\n').filter((l) => l.startsWith('|')).length,
        `shape ${shape.name} produced no table rows`,
      ).toBeGreaterThan(20);

      const bare = tally(shape, false);
      const twin = tally(shape, true);
      const fmt = (t: Map<string, number>) =>
        [...t.entries()]
          .sort((a, b) => b[1] - a[1])
          .map(([b, n]) => `${b} ${n}`)
          .join(' · ');

      lines.push(
        `  ${shape.name}`,
        `      (${shape.provenance})`,
        `      row label alone : ${fmt(bare)}`,
        `      twin-addressed  : ${fmt(twin)}`,
        '',
      );

      // The partition reconciles for EVERY shape and BOTH readings.
      expect([...bare.values()].reduce((a, b) => a + b, 0)).toBe(80);
      expect([...twin.values()].reduce((a, b) => a + b, 0)).toBe(80);

      // The 28 are definitional in every cell of the matrix.
      expect(bare.get('no_editor_intent')).toBe(28);
      expect(twin.get('no_editor_intent')).toBe(28);

      best.set(shape.name, twin.get('addressable') ?? 0);
    }

    lines.push(
      `  BEST twin-addressed, by shape: ${[...best.entries()].map(([k, v]) => `${k}=${v}`).join(' · ')}`,
      '',
    );
    // eslint-disable-next-line no-console
    console.info(lines.join('\n'));

    // ── WHAT THE MATRIX ESTABLISHES, AND WHAT IT DOES NOT ───────────────────
    //
    // ⚠️ ADDRESSABILITY IS SHAPE-DEPENDENT, AND THE SPREAD IS THE FINDING. A
    // single-shape census reported 40 and read as a property of the system; it
    // was a property of the arrangement. The ledger carries the matrix, never
    // the flattering cell.
    //
    // A RATCHET, not a pin: the BEST shape may not regress. A gate that goes red
    // when the thing it guards starts working is a gate nobody keeps.
    const bestAny = Math.max(...best.values());
    expect(bestAny, 'best-case addressability REGRESSED').toBeGreaterThanOrEqual(40);

    // ⚠️ AND THE ACCEPTANCE IS NOT MET ON ANY SHAPE. RELAY asks for ZERO gaps.
    // Asserted rather than commented, so the day it is met this line fails and
    // forces the ledger row to be rewritten by somebody who has looked.
    expect(
      80 - bestAny,
      'ZERO gaps reached on some shape — F24-S3 acceptance may be met; update RELAY',
    ).toBeGreaterThan(0);
  });
});
