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
// ⚠️ 28 OF THE 80 ROWS ARE NOT THIS FILE'S TO MEASURE, AND THE BUCKET USED TO
// SAY SOMETHING FALSE ABOUT THEM. It read `no_editor_intent`, and that was true
// until F24-S5 shipped `edit_form_control`: content controls now have an editor
// intent, an addressing (a server-issued ordinal) and a write path. They still
// never reach `editTableCell` — they render from the fill's
// `selectedOptionOrdinal`, not from the note markdown — so this file correctly
// declines to replay them, and it must not be read as saying they are
// unreachable.
//
// ⚠️ THE ACCEPTANCE WALK'S ARM 1 READ 52/80 AND WAS REPORTED AS A REFUSAL FOR
// EXACTLY THIS REASON: the number was true about a system that no longer
// exists. THE OTHER 28 ARE MEASURED, BY REPLAY, IN
// `gate-f24-s5-control-addressable-census.test.ts`. 52 + 28 = 80, and both
// files assert their own half of that partition so neither can drift into the
// other's territory.
//
// ⚠️ SO `bestAny` BELOW IS THE TABLE HALF ONLY. Read as a whole-form figure it
// is the "check whose TITLE is narrower than what it MEASURES" failure with the
// sign flipped — a number that is honest about 52 fields and silent about 28.
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
import { readNoteSection } from '../../splice-note-section';
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
 * ⚠️ WHICH SHAPE PRODUCTION HOLDS — MEASURED 2026-08-23, NO LONGER OPEN. This
 * comment used to say it was unestablished and name it as the next
 * measurement. It was taken against this template's real
 * `transcribe_visits.soapFinal` rows:
 *
 *   certified template `cmsxip5f9000901nadsggo2l1` — 3 production visits, all
 *   3 carrying tables. 6 table headers across them:
 *
 *     blank above 2 · heading 0 · pipe 0 · prose 4        (reconciles to 6)
 *
 *   and the split is per-VISIT, not per-leg: two visits are prose-above on
 *   BOTH legs, one is blank-above on both. So no visit is half-addressable,
 *   which is the arrangement that would have been worst.
 *
 *   The four prose lines are REAL CAPTIONS rather than narrative — 9 and 10
 *   characters, exactly one laterality token each, alternating right then left
 *   in both visits. That was checked because `captionFor` cannot tell a caption
 *   from a paragraph, and a narrative line accepted as a caption is the
 *   wrong-leg write of Slice 1b.
 *
 * So `captioned-adjacent` is the shape 2 of 3 production visits hold, and
 * `captioned-blank-line` is the third. The ordinal work below is worth 12 cells
 * on the first two and NOTHING on the third, which is F24-CAPTION-VALIDATION's
 * to close and not this item's.
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

  /**
   * THE TWIN'S ORDINAL — F24-S4. Among the rows the twin knows share a leg AND
   * a vein label, this row's 1-based position by `rowIndex` ascending.
   *
   * ⚠️ THIS IS THE CLAIM THE CENSUS NOW ASSERTS RATHER THAN ASSUMES: that the
   * twin's order (IR `rowIndex`) is the order the editor's candidates come out
   * in (note line order). If those two ever disagree, an ordinal writes a real
   * neighbouring measurement into the wrong row and reports success — so the
   * replay below verifies WHICH LINE MOVED, not merely that something did.
   */
  function twinRowOrdinal(f: TemplateField): number | undefined {
    const row = rowsOfIr.find((r) => r.rowIndex === f.rendererBinding.rowIndex);
    if (!row) return undefined;
    const siblings = rowsOfIr
      .filter((r) => r.laterality === row.laterality && r.vein === row.vein)
      .sort((a, b) => a.rowIndex - b.rowIndex);
    // Unambiguous rows are addressed without one, exactly as before — so an
    // ordinal appearing here can only ever be closing a duplicate-label gap.
    if (siblings.length < 2) return undefined;
    return siblings.findIndex((r) => r.rowIndex === row.rowIndex) + 1;
  }

  /**
   * WHICH LINE MOVED, and where it sits among its identical-label neighbours.
   *
   * ⚠️ THE CENSUS'S EXISTING `resolved_wrong_row` CHECK IS VACUOUS ON EXACTLY
   * THE ROWS F24-S4 MAKES WRITABLE. It compares `res.row` — the row's LABEL —
   * against the label that was requested, and all three tributary candidates
   * carry one identical label by design. It therefore holds no matter which of
   * the three was written, so an off-by-one would have been recorded as
   * `addressable`. Verification here is positional and content-based instead.
   */
  function changedRowOrdinal(
    before: string,
    after: string,
  ): { nth: number; table: number } | 'not_one_line' {
    const b = before.split('\n');
    const a = after.split('\n');
    if (b.length !== a.length) return 'not_one_line';
    const moved = b.map((_, i) => i).filter((i) => b[i] !== a[i]);
    if (moved.length !== 1) return 'not_one_line';
    const idx = moved[0];
    const label = (l: string) => l.split('|')[1]?.trim() ?? '';
    // The table this line belongs to: everything back to the nearest header.
    let start = 0;
    for (let i = idx; i >= 0; i -= 1) {
      if (!b[i].trim().startsWith('|')) {
        start = i + 1;
        break;
      }
    }
    let nth = 0;
    for (let i = start; i <= idx; i += 1) {
      if (b[i].trim().startsWith('|') && label(b[i]) === label(b[idx])) nth += 1;
    }
    // ⚠️ AND WHICH TABLE, NOT ONLY WHICH POSITION WITHIN IT. Position alone is
    // the same vacuity one level down: the 2nd tributary of the RIGHT leg and
    // the 2nd of the LEFT both answer `nth === 2`, so a cross-leg write would
    // have been recorded as `addressable`. `start` is the table's first line,
    // so it identifies the table.
    return { nth, table: start };
  }

  function replay(f: TemplateField, shape: NoteShape, useTwin: boolean): string {
    // ⚠️ OUT OF THIS FILE'S SCOPE, NOT UNREACHABLE — see the file header. A
    // content control never reaches `editTableCell`, because it renders from the
    // fill rather than from the note markdown. Since F24-S5 it IS addressable,
    // through `edit_form_control`, and that is measured by replay in
    // `gate-f24-s5-control-addressable-census.test.ts`.
    //
    // ⚠️ THE BUCKET IS NAMED AFTER THE FILE THAT OWNS IT, DELIBERATELY. The old
    // name (`no_editor_intent`) was a CLAIM about the product, and it went false
    // the minute S5 landed while this file went on printing it. A bucket named
    // after its owner cannot make a claim that decays.
    if (!isTableCell(f)) return 'content_control_measured_by_f24_s5_census';
    const row = rowsOfIr.find((r) => r.rowIndex === f.rendererBinding.rowIndex);
    if (!row) return 'no_ir_row';
    const columnLabel = f.labelSource === 'table_header' ? f.originalLabel : NOTE_COLUMNS[0];
    const rowLabel = useTwin ? shape.twinRowLabel(row.vein, row.laterality) : row.vein;
    const caption = useTwin ? shape.twinCaption(row.laterality) : undefined;
    // F24-S4: the twin supplies the ordinal, and ONLY where the label alone is
    // genuinely ambiguous. The bare-label reading never gets one — that column
    // is the floor this item is measured against.
    const ordinal = useTwin ? twinRowOrdinal(f) : undefined;
    const res = editTableCell({
      note: shape.note,
      sectionLabel: 'FINDINGS',
      rowLabel,
      columnLabel,
      value: '9.9',
      ...(caption ? { tableCaption: caption } : {}),
      ...(ordinal !== undefined ? { rowOrdinal: ordinal } : {}),
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
    // ⚠️ AND THE LABEL CHECK ABOVE CANNOT SEE AN OFF-BY-ONE AMONG IDENTICAL
    // LABELS — see `changedRowOrdinal`. Where the twin supplied an ordinal, the
    // line that actually moved must be the one it named. This is what turns
    // "the twin's order matches the note's order" from an assumption into an
    // assertion; if they ever diverge, these 12 land here and not in
    // `addressable`.
    if (ordinal !== undefined) {
      // ⚠️ AGAINST THE SECTION, NOT THE NOTE. `editTableCell` returns the
      // SECTION body — `readNoteSection`'s output with one line spliced — so
      // diffing it against the whole note compares two different universes and
      // every row reads as "more than one line moved". Driving the real reader
      // rather than slicing the note by hand, per canon's predicate-fidelity
      // rule.
      const section = readNoteSection(shape.note, 'FINDINGS') ?? '';
      const moved = changedRowOrdinal(section, res.body ?? '');
      if (moved === 'not_one_line') return 'wrote_more_than_one_line';
      if (moved.nth !== ordinal) return 'resolved_wrong_duplicate_row';
      // The row must sit in the table the twin's own laterality names.
      const wantLeg = row.laterality === 'right' ? 0 : 1;
      const tableStarts = [
        ...new Set(
          section
            .split('\n')
            .map((l, i) => (l.trim().startsWith('|') ? i : -1))
            .filter((i) => i >= 0)
            .filter((i, _j, all) => !all.includes(i - 1)),
        ),
      ];
      // One-table shapes carry both legs in one grid; there the leg lives in
      // the row LABEL and is already checked by `resolved_wrong_row` above.
      if (tableStarts.length > 1 && moved.table !== tableStarts[wantLeg]) {
        return 'resolved_wrong_leg';
      }
    }
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

      // ⚠️ A WRONG WRITE IS NEVER A CENSUS RESULT — IT IS A FAILURE, IN EVERY
      // CELL OF THE MATRIX. This assertion exists because the first version of
      // this file REPORTED `resolved_wrong_leg 6` and still passed: the ratchet
      // only reads the best shape, so a clinical defect on a worse shape was
      // printed and tolerated. A gate that names a wrong-leg write in its own
      // output and goes green is a decoration.
      //
      // These three buckets are the ones that mean "the editor wrote, and wrote
      // somewhere other than where it was told". Unlike a refusal, none of them
      // is ever an acceptable steady state.
      for (const bad of [
        'resolved_wrong_leg',
        'resolved_wrong_duplicate_row',
        'resolved_wrong_row',
        'resolved_wrong_column',
        'wrote_more_than_one_line',
      ]) {
        expect(twin.get(bad) ?? 0, `${shape.name}: ${bad}`).toBe(0);
        expect(bare.get(bad) ?? 0, `${shape.name} (bare): ${bad}`).toBe(0);
      }

      // The 28 are definitional in every cell of the matrix — this file's
      // denominator is 52, and the moment that stops being true one of the two
      // censuses has started measuring the other's fields.
      expect(bare.get('content_control_measured_by_f24_s5_census')).toBe(28);
      expect(twin.get('content_control_measured_by_f24_s5_census')).toBe(28);

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
    // ⚠️ RAISED 40 -> 52 BY F24-S4, WHICH IS THE POINT OF A RATCHET. The twin
    // now supplies an ordinal for the duplicate-label rows, so every one of the
    // 52 table-bound cells is addressable on both reachable shapes. Leaving the
    // floor at 40 would have let the whole closure regress unnoticed — a gate
    // that does not move when the fix lands is a decoration.
    const bestAny = Math.max(...best.values());
    expect(bestAny, 'best-case addressability REGRESSED').toBeGreaterThanOrEqual(52);

    // ⚠️ AND THE TABLE-BOUND HALF IS NOW COMPLETE, ASSERTED SEPARATELY FROM THE
    // TOTAL. `bestAny` alone cannot distinguish "all 52 table cells work" from
    // "40 table cells and 12 content controls somehow counted", so the thing
    // this item actually closed is pinned in its own right.
    expect(
      best.get('captioned-adjacent'),
      'the duplicate-label rows regressed on the shape production mostly holds',
    ).toBe(52);

    // ⚠️ AND THE RESIDUAL IS NOW ENTIRELY THE OTHER FILE'S HALF, WHICH IS A
    // DIFFERENT SENTENCE FROM THE ONE THIS ASSERTION USED TO MAKE.
    //
    // *Previous message, kept because the correction is the point:* "ZERO gaps
    // reached on some shape — F24-S3 acceptance may be met; update RELAY". That
    // read as a whole-form claim while `bestAny` only ever ranged over the 52
    // table-bound cells, so `80 - bestAny` could never reach 0 no matter how
    // complete the table editor became — a close condition that was
    // structurally unreachable, which is this repository's own "check whose
    // TITLE is narrower than what it MEASURES".
    //
    // What it asserts now is the honest thing: the 28 this file does not
    // measure are still 28, so the residual is exactly the other census's
    // denominator. If this ever drops below 28, `bestAny` has started counting
    // fields that are not table-bound and BOTH censuses are wrong.
    expect(
      80 - bestAny,
      'the table half is over-counting — bestAny has reached beyond the 52 table-bound cells',
    ).toBe(28);
  });
});
