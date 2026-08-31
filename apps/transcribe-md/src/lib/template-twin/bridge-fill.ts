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

import { parseMarkdownRow } from '@/lib/markdown-row';
import { classifyHeaderCell } from '@/lib/table-header-shape';
import {
  FieldResolutionSchema,
  type FieldResolution,
  type FieldResolutionStatus,
  type TemplateDocIR,
  type TemplateField,
} from './ir';
import { bridgeChoiceSlotPicks } from './picks-bridge';
import { citationOf, matchMeasurementFact } from './bridge-evidence';
import { deriveFieldValueFromFact } from './field-value-derivation';
import type { EncounterFact, SemanticMapping } from './ir';

// ── numeric table-cell fill ─────────────────────────────────────────────────

/** A markdown pipe-table parsed out of the generated note. */
interface ParsedMarkdownRow {
  label: string;
  cells: string[];
}

interface ParsedMarkdownTable {
  /** Header cells, exactly as the note carries them.
   *
   *  ⚠️ THIS COMMENT USED TO READ "column 0 is the row-label column", AND THAT
   *  IS THE ONE THING THE HEADER DOES NOT GUARANTEE. It is the whole reason
   *  `labelColumnOffset` exists forty lines below: a note's header carries a
   *  label cell in one shape and not in the other, and which one you are
   *  holding is the question ruling #140 governs. A field comment asserting
   *  the answer is a `DEPLOYMENT_RUNBOOK §5.6` in miniature — an intended
   *  state written in the present tense, read as a description. */
  header: string[];
  rows: ParsedMarkdownRow[];
}

// A row may carry a trailing annotation AFTER its closing pipe. Two forms are
// produced in practice and both must be tolerated:
//   | GSV at the SFJ | 6.2 | 3.4 | [S1: "..."]      <- bracketed anchor
//   | GSV at the SFJ | 6.2 | 3.4 | "Right great ..." <- inline evidence quote
// Only the bracketed form was tolerated. A quoted row failed to match, and
// because it is typically the FIRST data row, table accumulation ended with
// ZERO rows — so all 52 measurement cells never reached the matcher and every
// dictated measurement was silently dropped. Measured on a real visit:
// parseMarkdownTables -> 2 tables, rows=0, filledCount=0.
// Anything after the closing pipe is an annotation, in ANY form. Three have
// been observed from L4 and enumerating them was a losing game:
//   | GSV at the SFJ | 6.2 | 3.4 | [S1: "..."]          bracketed anchor
//   | GSV at the SFJ | 6.2 | 3.4 | "Right great ..."    quoted evidence
//   | GSV at the SFJ | 7 | 2.4 | Great saphenous vein ...  bare prose
// Each unrecognised form silently killed the whole table: the row failed to
// match, and being the FIRST data row, accumulation ended with zero rows and
// every measurement was dropped. The cells are fixed by the pipes BEFORE the
// annotation, so the trailing text simply does not matter — capture to the last
// pipe and ignore the rest, rather than keep guessing at forms.
const TABLE_ROW_RE = /^\s*\|(.+)\|\s*.*$/;
const SEP_ROW_RE = /^[\s:|-]+$/; // the | --- | --- | separator

/** Split one "| a | b | c |" line into its cell strings (trimmed). Any trailing
 *  evidence-anchor "[...]" after the last pipe is dropped by TABLE_ROW_RE. */
/** ONE reader, five callers — `@/lib/markdown-row`. The primitive was BUILT
 *  from this function's tolerant semantics: greedy to the last pipe, trailing
 *  annotation ignored. The other four callers converged onto it; this one is
 *  unchanged in behaviour and now shares the definition rather than owning a
 *  private copy of it. */
function splitRow(line: string): string[] | null {
  return parseMarkdownRow(line)?.cells ?? null;
}

/** Extract every contiguous markdown pipe-table from the note. A table is a
 *  header row, a `---` separator row, then data rows. */
/** Diagnostic alias — same function, exported so a QA harness can show what the
 *  bridge actually parses out of a generated note. */
export function parseMarkdownTablesForDiagnosis(note: string): ParsedMarkdownTable[] {
  return parseMarkdownTables(note);
}

function parseMarkdownTables(note: string): ParsedMarkdownTable[] {
  const lines = note.split('\n');
  const tables: ParsedMarkdownTable[] = [];
  for (let i = 0; i < lines.length; i++) {
    const header = splitRow(lines[i]);
    if (!header) continue;
    const sepCells = i + 1 < lines.length ? splitRow(lines[i + 1]) : null;
    if (!sepCells || !sepCells.every((c) => SEP_ROW_RE.test(c) && c.includes('-'))) continue;
    const rows: ParsedMarkdownRow[] = [];
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
  rowLaterality: 'right' | 'left' | 'unknown';
}

/** Group a table's cell fields into ordered data rows, tagging each row's
 *  diameter cell (the vein-name left_cell) and reflux cell (the header cell). */
/** IR rows split into leg groups, in document order, so each group can be
 *  walked against a candidate table with its own cursor. */
function groupByLeg(rows: readonly IrTableRow[]): IrTableRow[][] {
  const groups = new Map<string, IrTableRow[]>();
  for (const row of rows) {
    const key = row.rowLaterality;
    (groups.get(key) ?? groups.set(key, []).get(key)!).push(row);
  }
  return [...groups.values()];
}

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
    // The row's leg, stamped at compile time from the document's own headings.
    // The walk below is per-leg, so it has to travel with the row.
    const rowLaterality =
      (diameterField ?? refluxField ?? cells[0])?.rendererBinding.rowLaterality ?? 'unknown';
    rows.push({ rowIndex, vein, diameterField, refluxField, rowLaterality });
  }
  return rows;
}

/** The markdown table most likely to be this vein grid: it must carry a diameter
 *  or reflux column, and we prefer the one whose row labels best match the IR
 *  vein names (guards against picking an unrelated table in the note). */
/** ALL tables that plausibly belong to this IR grid, best first.
 *
 *  One grid in the document becomes TWO markdown tables in the note (Right Leg,
 *  Left Leg), so returning a single winner left half the cells never offered.
 *  Offering every candidate is safe now that addressing is fail-closed on row
 *  laterality: a right-leg value simply cannot fill a left-leg row, so the
 *  tables sort themselves out at the matcher instead of needing to be
 *  pre-assigned to legs here. */
function pickTables(tables: ParsedMarkdownTable[], irRows: IrTableRow[]): ParsedMarkdownTable[] {
  const veinCores = irRows.map((r) => normVein(r.vein)).filter(Boolean);
  const scored: Array<{ table: ParsedMarkdownTable; score: number }> = [];
  for (const t of tables) {
    if (!t.header.some((h) => classifyHeader(h) !== 'other')) continue;
    let score = 0;
    for (const row of t.rows) {
      const core = normVein(row.label);
      if (veinCores.some((v) => veinMatches(v, core))) score++;
    }
    if (score > 0) scored.push({ table: t, score });
  }
  return scored.sort((a, b) => b.score - a.score).map((x) => x.table);
}

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

/** A measurement is written ONLY when a real fact supports it, and it cites
 *  THAT fact. No match -> null, and the caller leaves the cell to the resolver
 *  baseline (blank) with the failure named in the log.
 *
 *  ⚠️ THE WRITTEN VALUE IS DERIVED FROM THE CITED FACT, NOT COPIED FROM THE
 *  NOTE. It used to be the model's raw markdown cell text, with the comment
 *  "narrative_text cells render the bare string; no unit, no reformat" — and
 *  the validator re-derives the same cell from the FACT and compares with
 *  strict `===`. The matcher proves the two agree NUMERICALLY (1e-9); it says
 *  nothing about their TEXT. `"3.1" === "3.10"` is false, so a dictated
 *  trailing zero produced ASSERTION_NOT_SUPPORTED, and because that issue is
 *  BLOCKING the cost was the ENTIRE native fill for the visit — silently: the
 *  document simply is not natively filled. Ruling #135; reproduced first by
 *  f5d-gsv-sfj-assertion-repro.test.ts. */
function supportedNumeric(
  field: TemplateField,
  value: string,
  segmentLabel: string,
  facts: readonly EncounterFact[],
  mapping?: SemanticMapping,
  rowLaterality?: 'right' | 'left' | 'unknown',
): FieldResolution | null {
  // ⚠️ THIS BRIDGE WRITES MEASUREMENTS AND ONLY MEASUREMENTS, AND THE GUARD IS
  // LOAD-BEARING RATHER THAN TIDY. Deriving from the fact means the derivation
  // now returns whatever the FIELD KIND says — including a BOOLEAN for a
  // checkbox, taken from the fact's polarity. So a numeric table cell compiled
  // as `checkbox` would have turned a dictated "3.1" into a TICKED BOX: the
  // validator would accept it (it re-derives the same boolean) and the renderer
  // would happily draw ☒. Before this change that combination was inert,
  // because writing the string "3.1" against a derived boolean always failed
  // assertion and blocked the render.
  //
  // Not reachable in production today — all 52 table_cell fields of the
  // customer's compiled template are `narrative_text` (measured 2026-08-20) —
  // and refused here anyway, because "not reachable today" is a fact about one
  // template rather than a property of this function. `single_select` is
  // refused for a second, independent reason: this function writes
  // `selectedOptionOrdinal: null`, and the renderer resolves a select through
  // its ordinal.
  const WRITABLE_KINDS: ReadonlySet<TemplateField['kind']> = new Set([
    'narrative_text',
    'number',
    'measurement',
  ]);
  if (!WRITABLE_KINDS.has(field.kind)) {
    console.info(
      `[template-twin:bridge] cell left blank field=${field.fieldId} reason=kind_not_writable_by_measurement_bridge kind=${field.kind}`,
    );
    return null;
  }
  // ⚠️ AND THE SECOND AXIS, WHICH THE KIND LIST ABOVE DOES NOT COVER — the
  // watched-set failure caught inside this very guard by the adversarial pass.
  // `assertionSupported` branches on `field.rowPrototype`, NOT on `field.kind`
  // (validation/index.ts:206), and that branch demands a ROW ARRAY. A table
  // cell inside a repeat region compiles to `rowPrototype: true` with kind
  // `narrative_text` — which the list above happily admits — and this function
  // only ever writes a SCALAR. That scalar then raises BOTH
  // ASSERTION_NOT_SUPPORTED and REPEATING_ROW_SHAPE_INVALID, killing the whole
  // native fill: the exact failure ruling #135 exists to remove.
  //
  // Not a regression (the pre-fix cell text was equally scalar) and not
  // reachable on the customer's form — measured 2026-08-20, WM IOV compiles 80
  // fields and ZERO rowPrototype. Refused anyway, for the same reason the kind
  // list is: reachability is a fact about one template, not about this
  // function. Filling repeat rows is a real feature and it is not this one.
  if (field.rowPrototype) {
    console.info(
      `[template-twin:bridge] cell left blank field=${field.fieldId} reason=row_prototype_needs_row_array`,
    );
    return null;
  }
  const matched = matchMeasurementFact({ value, segmentLabel, facts, mapping, rowLaterality });
  if (!matched.ok) {
    console.info(
      `[template-twin:bridge] cell left blank field=${field.fieldId} reason=${matched.reason}`,
    );
    return null;
  }
  const derived = deriveFieldValueFromFact(field, mapping, matched.match.fact);
  // A refusal from the derivation is honoured as a refusal. Writing `value`
  // here as a fallback would restore the exact defect this call replaced.
  if (derived === null) {
    console.info(
      `[template-twin:bridge] cell left blank field=${field.fieldId} reason=value_not_derivable_from_fact`,
    );
    return null;
  }
  return FieldResolutionSchema.parse({
    fieldId: field.fieldId,
    status: 'supported',
    // Written through UNCHANGED, never stringified: the renderer type-checks by
    // field kind (renderer.ts:778-824) and refuses a string where it wants a
    // number with FIELD_VALUE_INVALID, which fails the whole render.
    value: derived,
    ...citationOf(matched.match),
    selectedOptionOrdinal: null,
    reasonCode: 'table_cell_measurement',
    clinicianReviewed: false,
  });
}

export interface BridgeNumericTableCellsInput {
  /** The L3 EncounterFacts for this encounter. Every bridged value must cite
   *  one of these — see bridge-evidence.ts. */
  facts: readonly EncounterFact[];
  /** Approved mappings, so a citation also satisfies the validator's
   *  concept/temporality rule rather than merely existing. */
  mappings?: readonly SemanticMapping[];
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
  const { ir, filledNote, facts } = input;
  const mappingById = new Map((input.mappings ?? []).map((m) => [m.fieldId, m]));
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
    const candidates = pickTables(tables, irRows);
    if (candidates.length === 0) continue;
    for (const md of candidates) {

    // Which markdown data column is diameter, which is reflux (by header).
    // ⚠️ The two INDICES are resolved below, AFTER the label column is known —
    // see "A ROW-LABEL COLUMN IS NEVER A DATA ROLE".
    const roleByCol = md.header.map(classifyHeader);

    // HEADER/CELL ALIGNMENT. A data row is always [label, ...values], but the
    // header does NOT always carry a column for the label:
    //
    //   | Segment | DIAMETER (mm) | REFLUX TIME (s) |   header 3, cells 3  -> offset 0
    //   | DIAMETER (mm) | REFLUX TIME (s) |             header 2, cells 3  -> offset 1
    //
    // Both shapes come out of L4. Indexing cells by header position assumed the
    // first form, so under the second the DIAMETER column read the row LABEL
    // (dropped as non-numeric) and the REFLUX column read the DIAMETER value.
    // Measured on the pinned note: filledCount=0, and a 7 mm diameter was
    // offered to a reflux cell — refused only because the evidence matcher
    // checks the fact's concept against the field's mapping. Alignment is a
    // shape problem and belongs here, not behind the matcher.
    //
    // Detect it from the header's own first column: if that column already
    // classifies as DATA, the header has no label column and every data cell
    // sits one to the right.
    //
    // ⚠️ RULING #140 — THIS WAS THE **THIRD** SITE DECIDING THAT QUESTION, WITH
    // ITS OWN VOCABULARY, AND THE DRIFT HAD WIDENED FROM TWO ANSWERS TO THREE.
    // `classifyHeader` below is a COLUMN-ROLE classifier (diameter / reflux /
    // other) and it is exactly right for that job — which is why it keeps it.
    // It was ALSO being asked "does this header carry a label column?", a
    // different question, and it answered with `!== 'other'`. On `Vein Size`
    // the three sites said:
    //
    //     isDataColumnHeader   -> true         "no label column"   (generator)
    //     classifyHeaderCell   -> cannot_tell  "REFUSE"            (editor)
    //     classifyHeader       -> other        "has a label column" (HERE)
    //
    // Three answers to one question, and the fill path held the outlier. It
    // diverged in BOTH directions and neither is benign, because this offset
    // decides WHICH NOTE CELL a measurement is read out of:
    //
    //     | VELOCITY (cm/s) | DIAMETER (mm) |   role 'other' -> offset 0
    //     | GSV at the SFJ | 12 | 6.2 |         diameterCol 1 -> reads "12"
    //       -> the VELOCITY is written into the DIAMETER field of the
    //          doctor's own form. The evidence matcher refuses most of these
    //          on concept — but "refused by the layer behind it" is a second
    //          line of defence, never the reason a shape is safe.
    //
    // ⚠️ THE ROW LABEL IS PROVEN, NOT GUESSED. `place` is only ever reached for
    // a row whose cell 0 already matched an IR vein name (`veinMatches`,
    // below). So cell 0 IS the label. The open question is whether the HEADER
    // carries a cell for it.
    //
    // ⚠️⚠️ AN EARLIER VERSION OF THIS BLOCK ANSWERED THAT FROM THE PREDICATE
    // ALONE AND SAID "DELTA IS DELIBERATELY NOT CONSULTED", CITING CANON'S
    // DOUBLE TAP. THAT CITATION OVER-REACHED AND THE ADVERSARIAL PASS PROVED IT
    // WITH TWO WRONG-CELL WRITES. The double tap forbids inferring WHICH END is
    // short from a +1 delta. It says nothing about delta ZERO — and delta 0
    // PLUS a proven label at cell 0 is a PROOF, not an inference:
    //
    //   | Location (cm) | DIAMETER (mm) | REFLUX TIME (seconds) |   header 3
    //   | Right GSV at the SFJ | 6.2 | 3.4 |                        cells  3
    //
    // `classifyHeaderCell('Location (cm)')` is `data` — the trailing `(cm)` is
    // a unit — so the predicate alone said offset 1, and the DIAMETER column
    // read the REFLUX value while the reflux column ran off the end. The old
    // vocabulary got this RIGHT (`other` -> 0), so the predicate-only form was
    // a REGRESSION of exactly #140's class. Four of production's six observed
    // first cells flip this way the moment a unit is appended.
    //
    // THE STRUCTURE IS THE EVIDENCE AND THE TEXT IS THE GUESS — which is
    // ruling #140's own instruction, "EVIDENCE OVER TEXT-GUESSING":
    //
    //   delta 0 -> every header cell has a row cell, and cell 0 is the label,
    //              so header[0] IS the label column. OFFSET 0, whatever the
    //              text says. (offset 1 here would leave the LAST header
    //              column with no cell — incoherent, not merely unlikely.)
    //   delta 1 -> the header is short by one. NOW the text decides WHICH END,
    //              and this is the only place the predicate is consulted:
    //                'data'        -> short at the FRONT      -> OFFSET 1
    //                'label'       -> claims to name the label column AND the
    //                                 row has a spare cell -> INCOHERENT
    //                                 -> REFUSE
    //                'cannot_tell' -> #140's refusal bucket  -> REFUSE
    //   otherwise -> REFUSE.
    //
    // ⚠️ AND THE DELTA IS PER ROW, NOT PER TABLE. A ragged table refuses only
    // the rows that are ragged; `cellIndex >= cells.length` catches a read that
    // runs off the END and never a read of the NEIGHBOUR, which is precisely
    // how the wrong-cell write above survived it.
    const headerShape = md.header.length === 0 ? 'cannot_tell' : classifyHeaderCell(md.header[0]);
    let refusalLogged = false;

    /** null = REFUSE this row. Otherwise the row-cell offset for a header index. */
    const offsetFor = (mdRow: ParsedMarkdownRow): 0 | 1 | null => {
      const delta = mdRow.cells.length - md.header.length;
      if (delta === 0) return 0;
      if (delta === 1 && headerShape === 'data') return 1;
      if (!refusalLogged) {
        refusalLogged = true;
        // Logged DISTINCTLY: a bucket that absorbs a refusal and an absence
        // cannot answer "did my change break this?", which is the one question
        // it will be asked.
        // ⚠️ THE VERDICT AND A LENGTH, NEVER THE CELL TEXT. An earlier draft
        // logged `md.header[0]` raw. It is very probably a template column name
        // and this repo has twice adjudicated that class as a PHI-safe
        // projection — but `parseMarkdownTables` matches ANY pipe line in
        // `soapFinal`, including a table the model invented, so there is no
        // template binding at this site and the string is unbounded. It would
        // also have been the first note-derived text this file ever logged;
        // every other console.info here prints a fieldId and a reason code.
        // The diagnostic value being argued for is carried entirely by the
        // verdict, so the text buys nothing and costs a new class.
        console.info('[twin-fill] row REFUSED — label_column_unresolved', {
          headerShape,
          headerCells: md.header.length,
          rowCells: mdRow.cells.length,
          headerCell0Length: (md.header[0] ?? '').length,
        });
      }
      return null;
    };

    // ⚠️ A ROW-LABEL COLUMN IS NEVER A DATA ROLE — AND THE TWO CLASSIFIERS CAN
    // DISAGREE ABOUT THE SAME CELL, WHICH IS WHAT THIS LINE EXISTS FOR.
    // Found by the adversarial pass's own fixture, not by design: for a header
    // cell like `CFV mm`, `classifyHeaderCell` says LABEL (no trailing unit
    // parenthetical, no measurement noun) while `classifyHeader`'s
    // /(^|\W)mm(\W|$)/ branch says DIAMETER. `findIndex` then bound the
    // diameter role to column 0 — the row-label column — and the offset bound
    // it to the label TEXT.
    //
    // It failed CLOSED (`numericCell` refuses a vein name, and a numeric row
    // label could never have matched `veinMatches` in the first place), so no
    // wrong value was ever written. What it cost was a FILL: on
    // `| CFV mm | DIAMETER (mm) | REFLUX TIME (seconds) |` the diameter was
    // silently dropped while the reflux landed correctly.
    //
    // Once the header is known to name its label column, that column is index 0
    // BY DEFINITION, so a data role there is a contradiction rather than a
    // preference. Searching from index 1 resolves it and is a no-op wherever
    // the two classifiers already agree — which is every shape production
    // holds.
    // ⚠️ THE ROLE SEARCH IS DERIVED FROM THE OFFSET, SO IT MOVES WITH IT — and
    // it is resolved per row for the same reason the offset is.
    const roleColFor = (role: ColumnRole, offset: 0 | 1) =>
      // offset 0 => header[0] IS the label column, so a data role there is a
      // contradiction rather than a preference. `CFV mm` is the shape that
      // proves it: `classifyHeaderCell` says LABEL while `classifyHeader`'s
      // /(^|\W)mm(\W|$)/ branch says DIAMETER, and `indexOf` bound the diameter
      // role to the row-label column.
      roleByCol.indexOf(role, offset === 0 ? 1 : 0);

    // ROW PAIRING. WM_IOV is a single 26-row grid; L4 renders it as two 13-row
    // tables (Right Leg, Left Leg) — but it can also render one combined table,
    // and the row labels are IDENTICAL between the legs. A single monotonic
    // cursor over all 26 IR rows handled the combined shape and failed the split
    // one: the right-leg rows consumed the LEFT table's rows before the
    // left-leg rows were reached. The matcher correctly refused every one of
    // those pairings on laterality — but the note row was already spent, so no
    // left-leg cell could ever fill. Six right cells filled and thirteen left
    // cells did not, from an encounter that dictated both legs equally.
    //
    // So pairing is decided by EVIDENCE, not by position: for each IR row, try
    // every note row whose vein label matches, and keep the first one that
    // actually produces a supported value. A note row is consumed only when it
    // fills something, so a refused pairing costs nothing. Rows already
    // consumed are not offered again, which preserves the one-note-row-per-IR-row
    // property the cursor was there to guarantee.
    //
    // This is ADDRESSING only. Which fact may support a cell, and what it must
    // cite, are unchanged.
    //
    // ⚠️ ONE HONEST QUALIFICATION, ADDED BY F5-d(b) AND FOUND BY ITS ADVERSARIAL
    // PASS: since `supportedNumeric` can now refuse because a value is NOT
    // DERIVABLE from the matched fact, DERIVABILITY IS AN INPUT TO ADDRESSING.
    // A refused pairing still costs nothing (the note row is not consumed), but
    // the loop moves on and a LATER note row may fill the cell instead — so the
    // note row a cell ends up bound to can differ from the pre-fix choice.
    //
    // LATERALITY IS UNAFFECTED — `rowLateralityVerdict` (bridge-evidence.ts:207)
    // is fail-closed on side and untouched, so no leg can cross. What changes is
    // WHICH NOTE ROW, not WHICH LEG. Unreachable on production's route today
    // (a narrative_text cell with a string-valued fact always derives), and
    // stated here so nobody reads "addressing is unchanged" as wider than it is.
    const consumed = new Set<number>();
    for (const irRow of irRows) {
      const core = normVein(irRow.vein);

      const place = (field: TemplateField | null, role: ColumnRole, mdRow: ParsedMarkdownRow) => {
        if (!field) return false;
        const offset = offsetFor(mdRow);
        if (offset === null) return false;
        const col = roleColFor(role, offset);
        if (col < 0) return false;
        const cellIndex = col + offset;
        if (cellIndex >= mdRow.cells.length) return false;
        const num = numericCell(mdRow.cells[cellIndex]);
        if (num == null) return false; // —/[not documented]/prose → blank
        // Laterality comes from the MATCHED FACT, never from row position.
        const resolved = supportedNumeric(
          field,
          num,
          irRow.vein,
          facts,
          mappingById.get(field.fieldId),
          field.rendererBinding.rowLaterality,
        );
        if (!resolved) return false;
        out.push(resolved);
        return true;
      };

      for (let i = 0; i < md.rows.length; i++) {
        if (consumed.has(i)) continue;
        if (!veinMatches(core, normVein(md.rows[i].label))) continue;
        const mdRow = md.rows[i];
        const filledDiameter = place(irRow.diameterField, 'diameter', mdRow);
        const filledReflux = place(irRow.refluxField, 'reflux', mdRow);
        if (filledDiameter || filledReflux) {
          consumed.add(i);
          break;
        }
      }
    }
    } // end candidate table
  }
  // A field may be offered by BOTH note tables; fail-closed laterality means at
  // most one can produce a resolution, but keep the first defensively so a
  // future addressing change cannot introduce duplicates silently.
  const seen = new Set<string>();
  return out.filter((r) => (seen.has(r.fieldId) ? false : (seen.add(r.fieldId), true)));
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
      // ⚠️ A WITHHELD DENIAL IS NULL BY CONSTRUCTION, AND IT IS NOT UNFILLED.
      // Rule (2) is decided in the resolver and was undone here one function
      // later: `denial_withheld` carries `value === null` by schema refine, so
      // an overlay pick overwrote it and the dropdown rendered the very finding
      // the encounter DENIED — with validation green and every count blank.
      // Withholding is a DECISION; absence is not.
      const currentUnfilled =
        current.status !== 'denial_withheld' &&
        (current.value === null || UNFILLED.has(current.status));
      if (currentUnfilled && r.value !== null) byId.set(r.fieldId, r);
    }
  }
  // Preserve ir.fields order for a stable, renderer-friendly array.
  return ir.fields.map((f) => byId.get(f.fieldId)!);
}

// ── unified entry ─────────────────────────────────────────────────────────────

export interface BridgeTemplateFillInput {
  /** L3 EncounterFacts — the evidence every bridged value must match. */
  facts: readonly EncounterFact[];
  /** Approved mappings — a citation must satisfy the validator's rule. */
  mappings?: readonly SemanticMapping[];
  ir: TemplateDocIR;
  /** The compiled {{one of}} marker text (drives the single-select picks). */
  markerText: string;
  /** The LIVE brain's generated note (picks + table measurements). */
  filledNote: string;
  /** The evidence resolver's full baseline resolution set (one per ir.field). */
  baseline: readonly FieldResolution[];
}

export interface BridgeTemplateFillResult {
  resolutions: FieldResolution[];
  /** Provenance facts minted by the picks overlay, to be merged into the fact
   *  set the manifest records and the validator checks against. */
  facts: EncounterFact[];
}

/**
 * Produce the final FieldResolution[] for the renderer: the resolver baseline,
 * overlaid with the CHOICE_SLOT single-select picks and the numeric table-cell
 * fills recovered from the generated note. Exactly one resolution per ir.field.
 */
export function bridgeTemplateFill(input: BridgeTemplateFillInput): BridgeTemplateFillResult {
  const picks = bridgeChoiceSlotPicks({
    ir: input.ir,
    markerText: input.markerText,
    filledNote: input.filledNote,
    facts: input.facts,
    mappings: input.mappings,
  });
  const numerics = bridgeNumericTableCells({
    ir: input.ir,
    filledNote: input.filledNote,
    facts: input.facts,
    mappings: input.mappings,
  });
  return {
    resolutions: mergeFieldResolutions(
      input.ir,
      input.baseline,
      picks.resolutions.filter((r) => r.status === 'supported'),
      numerics,
    ),
    // The picks' provenance facts must travel WITH the resolutions: a citation
    // to a fact that is not in the manifest's fact set is untraceable, and the
    // validator says so.
    facts: picks.facts,
  };
}
