// ============================================================================
// Template Twin — unified LIVE-brain → IR fill bridge (picks + numeric cells).
// ----------------------------------------------------------------------------
// The deterministic evidence resolver (resolveTemplateFields) is the baseline
// producer of manifest.fields, but for a structured imaging template like WM_IOV
// it fills almost nothing: the CHOICE_SLOT {{one of}} picks and the dictated
// table MEASUREMENTS live only in the LIVE brain's generated note, not in the L3
// facts. This module bridges BOTH onto the IR's FieldResolutions the native
// renderer consumes, under the SAME constrained-fill invariants:
//   • single-selects  → bridgeChoiceSlotPicks  (exact option, blank when unsaid)
//   • table-cell numerics → bridgeNumericTableCells (bare value, laterality-
//     correct by forward-cursor vein-label alignment, never mis-placed/invented)
//   • merge = overlay onto the resolver baseline, replacing a field ONLY when the
//     resolver left it unfilled (real evidence always wins; overlays never fight).
//
// Pure + deterministic. No I/O, no AI. The generated note is the only new input.
// ============================================================================

import {
  FieldResolutionSchema,
  type FieldResolution,
  type FieldResolutionStatus,
  type TemplateDocIR,
  type TemplateField,
} from './ir';
import { bridgeChoiceSlotPicks } from './picks-bridge';

// ── numeric table-cell fill ─────────────────────────────────────────────────

/** A markdown pipe-table parsed out of the generated note. */
interface ParsedMarkdownTable {
  /** Header cells (column 0 is the row-label column). */
  header: string[];
  rows: { label: string; cells: string[] }[];
}

const TABLE_ROW_RE = /^\s*\|(.+)\|\s*(?:\[[^\]]*\].*)?$/; // trailing evidence anchor tolerated
const SEP_ROW_RE = /^[\s:|-]+$/; // the | --- | --- | separator

/** Split one "| a | b | c |" line into its cell strings (trimmed). Any trailing
 *  evidence-anchor "[...]" after the last pipe is dropped by TABLE_ROW_RE. */
function splitRow(line: string): string[] | null {
  const m = TABLE_ROW_RE.exec(line);
  if (!m) return null;
  return m[1].split('|').map((c) => c.trim());
}

/** Extract every contiguous markdown pipe-table from the note. A table is a
 *  header row, a `---` separator row, then data rows. */
function parseMarkdownTables(note: string): ParsedMarkdownTable[] {
  const lines = note.split('\n');
  const tables: ParsedMarkdownTable[] = [];
  for (let i = 0; i < lines.length; i++) {
    const header = splitRow(lines[i]);
    if (!header) continue;
    const sepCells = i + 1 < lines.length ? splitRow(lines[i + 1]) : null;
    if (!sepCells || !sepCells.every((c) => SEP_ROW_RE.test(c) && c.includes('-'))) continue;
    const rows: { label: string; cells: string[] }[] = [];
    let j = i + 2;
    for (; j < lines.length; j++) {
      const cells = splitRow(lines[j]);
      if (!cells) break;
      rows.push({ label: cells[0] ?? '', cells });
    }
    tables.push({ header, rows });
    i = j - 1;
  }
  return tables;
}

/** A cell holds a fillable measurement ONLY when it is a bare number. The
 *  landed cell conventions reserve "—" for stated-normal and "[not documented]"
 *  for not-assessed; both (and any prose) yield null → the cell stays blank. */
function numericCell(raw: string): string | null {
  const s = raw.trim();
  if (!/^-?\d+(?:\.\d+)?$/.test(s)) return null;
  return s;
}

/** Normalise a vein / row label for alignment: lowercase, drop laterality words,
 *  drop the "<<insert location>>" placeholder, strip punctuation, collapse space.
 *  Both the IR left_cell label and the generated row label pass through this so a
 *  leg-qualified generated label ("Right GSV at the SFJ") still core-matches the
 *  IR's "GSV at the SFJ". */
function normVein(s: string): string {
  return s
    .toLowerCase()
    .replace(/&lt;|&gt;|[<>]/g, ' ')
    .replace(/\binsert location\b/g, ' ')
    .replace(/\b(right|left|rt|lt|bilateral|r|l)\b/g, ' ')
    .replace(/[^a-z0-9 ]+/g, ' ')
    .replace(/\bat the\b/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
}

/** Token-set alignment (NOT substring): "gsv sfj" must NOT match "aagsv sfj".
 *  Matches when the two token sets are equal or one is a subset of the other
 *  (a leg-qualified or more-specific generated label still core-matches). */
function veinMatches(irCore: string, mdCore: string): boolean {
  if (!irCore || !mdCore) return false;
  const a = new Set(irCore.split(' ').filter(Boolean));
  const b = new Set(mdCore.split(' ').filter(Boolean));
  if (a.size === 0 || b.size === 0) return false;
  const subset = (x: Set<string>, y: Set<string>) => [...x].every((t) => y.has(t));
  return subset(a, b) || subset(b, a);
}

type ColumnRole = 'diameter' | 'reflux' | 'other';
function classifyHeader(h: string): ColumnRole {
  const t = h.toLowerCase();
  if (/reflux/.test(t)) return 'reflux';
  if (/diameter|(^|\W)mm(\W|$)/.test(t)) return 'diameter';
  return 'other';
}

interface IrTableRow {
  rowIndex: number;
  vein: string;
  diameterField: TemplateField | null;
  refluxField: TemplateField | null;
}

/** Group a table's cell fields into ordered data rows, tagging each row's
 *  diameter cell (the vein-name left_cell) and reflux cell (the header cell). */
function irTableRows(fields: TemplateField[]): IrTableRow[] {
  const byRow = new Map<number, TemplateField[]>();
  for (const f of fields) {
    const r = f.rendererBinding.rowIndex ?? -1;
    (byRow.get(r) ?? byRow.set(r, []).get(r)!).push(f);
  }
  const rows: IrTableRow[] = [];
  for (const rowIndex of [...byRow.keys()].sort((a, b) => a - b)) {
    const cells = byRow.get(rowIndex)!.sort(
      (a, b) => (a.rendererBinding.cellIndex ?? 0) - (b.rendererBinding.cellIndex ?? 0),
    );
    const refluxField = cells.find((c) => /reflux/i.test(c.originalLabel)) ?? null;
    // The diameter cell carries the vein name (labelSource 'left_cell'); if the
    // template ever labels differently, fall back to the non-reflux data cell.
    const diameterField =
      cells.find((c) => c.labelSource === 'left_cell') ??
      cells.find((c) => c !== refluxField) ??
      null;
    const vein = diameterField ? diameterField.originalLabel : cells[0]?.originalLabel ?? '';
    rows.push({ rowIndex, vein, diameterField, refluxField });
  }
  return rows;
}

/** The markdown table most likely to be this vein grid: it must carry a diameter
 *  or reflux column, and we prefer the one whose row labels best match the IR
 *  vein names (guards against picking an unrelated table in the note). */
function pickTable(tables: ParsedMarkdownTable[], irRows: IrTableRow[]): ParsedMarkdownTable | null {
  const veinCores = irRows.map((r) => normVein(r.vein)).filter(Boolean);
  let best: ParsedMarkdownTable | null = null;
  let bestScore = 0;
  for (const t of tables) {
    if (!t.header.some((h) => classifyHeader(h) !== 'other')) continue;
    let score = 0;
    for (const row of t.rows) {
      const core = normVein(row.label);
      if (veinCores.some((v) => veinMatches(v, core))) score++;
    }
    if (score > bestScore) { bestScore = score; best = t; }
  }
  return bestScore > 0 ? best : null;
}

function supportedNumeric(field: TemplateField, value: string): FieldResolution {
  return FieldResolutionSchema.parse({
    fieldId: field.fieldId,
    status: 'supported',
    value, // narrative_text cells render the bare string; no unit, no reformat
    sourceFactIds: [`ttfact_${'0'.repeat(24)}`],
    evidenceAnchorIds: ['table-cell-measurement'],
    selectedOptionOrdinal: null,
    reasonCode: 'table_cell_measurement',
    clinicianReviewed: false,
  });
}

export interface BridgeNumericTableCellsInput {
  ir: TemplateDocIR;
  /** The LIVE brain's generated note (its markdown table holds the measurements). */
  filledNote: string;
}

/**
 * Map dictated table measurements in the generated note onto the IR's table-cell
 * fields. Returns a PARTIAL list — only the cells it can fill — under strict
 * constrained-fill invariants: values are copied bare (never converted), rows are
 * aligned laterality-correct by forward-cursor vein match (Right block then Left,
 * in document order), and a cell is filled ONLY when its column holds a bare
 * number; "—"/"[not documented]"/prose/absent all stay blank (not_mentioned).
 *
 * LATERALITY / ORDER ASSUMPTION (patient-safety critical): the forward cursor is
 * safe because the generated markdown table is a FULL SKELETON REPRODUCTION —
 * renderStructureDirective seeds every rowLabel (both legs, in document order)
 * with "[not documented]", and the note-generation prompt (CELL_DISCIPLINE)
 * forbids the model from adding, removing, or reordering rows; it may only replace
 * a "[not documented]" cell. So both leg blocks are ALWAYS present in the same
 * order as the IR rows, even for a one-leg dictation (the undictated leg's rows
 * are present but "[not documented]"). The Nth markdown data row is therefore the
 * Nth IR data row, and an undictated leg's cells stay blank — a left value can
 * never land in a right cell. `normVein` strips the leg word deliberately (the IR
 * vein labels carry no leg), so laterality rides entirely on this full-skeleton
 * ordering, NOT on the leg word. A one-leg-only regression in bridge-fill.test.ts
 * locks this: a full skeleton with only the left block filled must leave every
 * right cell blank.
 */
export function bridgeNumericTableCells(input: BridgeNumericTableCellsInput): FieldResolution[] {
  const { ir, filledNote } = input;
  const cellFields = ir.fields.filter((f) => f.rendererBinding.bindingType === 'table_cell');
  if (cellFields.length === 0) return [];

  const tables = parseMarkdownTables(filledNote);
  if (tables.length === 0) return [];

  const out: FieldResolution[] = [];
  const byTableId = new Map<string | null, TemplateField[]>();
  for (const f of cellFields) {
    const key = f.tableId;
    (byTableId.get(key) ?? byTableId.set(key, []).get(key)!).push(f);
  }

  for (const fields of byTableId.values()) {
    const irRows = irTableRows(fields);
    const md = pickTable(tables, irRows);
    if (!md) continue;

    // Which markdown data column is diameter, which is reflux (by header).
    const roleByCol = md.header.map(classifyHeader);
    const diameterCol = roleByCol.findIndex((r) => r === 'diameter');
    const refluxCol = roleByCol.findIndex((r) => r === 'reflux');

    let cursor = 0;
    for (const irRow of irRows) {
      const core = normVein(irRow.vein);
      let matchedAt = -1;
      for (let i = cursor; i < md.rows.length; i++) {
        if (veinMatches(core, normVein(md.rows[i].label))) { matchedAt = i; break; }
      }
      if (matchedAt < 0) continue; // no row match → leave to the resolver baseline (blank)
      cursor = matchedAt + 1;
      const mdRow = md.rows[matchedAt];

      const place = (field: TemplateField | null, col: number) => {
        if (!field || col < 0 || col >= mdRow.cells.length) return;
        const num = numericCell(mdRow.cells[col]);
        if (num == null) return; // —/[not documented]/prose → blank
        out.push(supportedNumeric(field, num));
      };
      place(irRow.diameterField, diameterCol);
      place(irRow.refluxField, refluxCol);
    }
  }
  return out;
}

// ── merge ───────────────────────────────────────────────────────────────────

const UNFILLED: ReadonlySet<FieldResolutionStatus> = new Set<FieldResolutionStatus>([
  'not_mentioned',
  'needs_clinician_input',
  'ambiguous',
]);

/**
 * Overlay partial bridge resolutions onto the resolver baseline, keyed by
 * fieldId, returning EXACTLY one resolution per ir.field (the renderer rejects
 * any other cardinality). An overlay replaces the baseline for a field ONLY when
 * the baseline left it unfilled (status unfilled or value null) — so a value the
 * evidence resolver genuinely supported/denied/conflicted always wins, and the
 * overlays (disjoint field sets in practice) never overwrite each other.
 */
export function mergeFieldResolutions(
  ir: TemplateDocIR,
  baseline: readonly FieldResolution[],
  ...overlays: readonly FieldResolution[][]
): FieldResolution[] {
  const byId = new Map<string, FieldResolution>();
  for (const r of baseline) byId.set(r.fieldId, r);
  // Ensure every field has a baseline entry (defensive; resolver already covers all).
  for (const field of ir.fields) {
    if (!byId.has(field.fieldId)) {
      byId.set(field.fieldId, {
        fieldId: field.fieldId,
        status: 'not_mentioned',
        value: null,
        sourceFactIds: [],
        evidenceAnchorIds: [],
        selectedOptionOrdinal: null,
        reasonCode: 'blank_when_unsaid',
        clinicianReviewed: false,
      });
    }
  }
  for (const overlay of overlays) {
    for (const r of overlay) {
      const current = byId.get(r.fieldId);
      if (!current) continue; // field not in this IR — ignore
      const currentUnfilled = current.value === null || UNFILLED.has(current.status);
      if (currentUnfilled && r.value !== null) byId.set(r.fieldId, r);
    }
  }
  // Preserve ir.fields order for a stable, renderer-friendly array.
  return ir.fields.map((f) => byId.get(f.fieldId)!);
}

// ── unified entry ─────────────────────────────────────────────────────────────

export interface BridgeTemplateFillInput {
  ir: TemplateDocIR;
  /** The compiled {{one of}} marker text (drives the single-select picks). */
  markerText: string;
  /** The LIVE brain's generated note (picks + table measurements). */
  filledNote: string;
  /** The evidence resolver's full baseline resolution set (one per ir.field). */
  baseline: readonly FieldResolution[];
}

/**
 * Produce the final FieldResolution[] for the renderer: the resolver baseline,
 * overlaid with the CHOICE_SLOT single-select picks and the numeric table-cell
 * fills recovered from the generated note. Exactly one resolution per ir.field.
 */
export function bridgeTemplateFill(input: BridgeTemplateFillInput): FieldResolution[] {
  const picks = bridgeChoiceSlotPicks({
    ir: input.ir,
    markerText: input.markerText,
    filledNote: input.filledNote,
  }).filter((r) => r.status === 'supported');
  const numerics = bridgeNumericTableCells({ ir: input.ir, filledNote: input.filledNote });
  return mergeFieldResolutions(input.ir, input.baseline, picks, numerics);
}
