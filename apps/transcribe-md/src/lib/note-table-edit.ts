// ============================================================================
// Changing ONE measurement, without letting a model rewrite the table.
// ----------------------------------------------------------------------------
// A doctor looking at a venous duplex says "the SFJ diameter should be 6.8".
// That is a single cell. The dangerous way to serve it is to hand the model the
// note and take back whatever markdown it returns — one hallucinated digit in a
// row nobody was talking about is a fabricated measurement in a medical record,
// and nothing downstream would ever flag it.
//
// So the model never writes markdown. It names a SECTION, a ROW, a COLUMN and a
// VALUE, and this module does the edit: it finds that one cell, replaces its
// contents, and leaves every other byte of the note exactly as it was. What it
// cannot locate unambiguously, it refuses.
//
// AMBIGUITY IS A REFUSAL, NEVER A GUESS. A bilateral study renders one table
// per leg with identical segment labels; picking whichever matched first would
// write the right number onto the wrong leg, silently, in a document the doctor
// is about to sign. The caller may disambiguate with the table's CAPTION —
// which is what carries the laterality — and only then does the write proceed.
//
// ONE SECTION MATCHER, AND IT IS NOT THIS FILE'S.
//
// The section is resolved with readNoteSection, the same function
// saveNoteSectionAction splices with. This module previously had its own
// normaliser, and the two disagreed: `spliceNoteSection` strips ALL punctuation
// ("FINDINGS (RIGHT)" -> "findings right") while the local one dropped a
// trailing parenthetical ("FINDINGS (RIGHT)" -> "findings"). A note carrying
// both a "FINDINGS" and a "FINDINGS (RIGHT)" heading would therefore have the
// RIGHT leg's table read out and written back over the OTHER section, deleting
// its rows. Sharing the matcher is what makes "read it, edit it, write it back"
// refer to the same section three times.
// ============================================================================

import { isDataColumnHeader } from './table-header-shape';
import { readNoteSection } from './splice-note-section';

/** `| --- | :--- |` — a table's alignment rule, never content. */
const RULE_RE = /^\s*\|[\s:|-]+\|\s*$/;
/** Any `| … | … |` line. */
const ROW_RE = /^\s*\|.*\|\s*$/;
/** `## HEADING` */
const HEADING_RE = /^\s*#{1,6}\s/;

export type TableEditFailure =
  | 'section_not_found'
  | 'no_table'
  | 'row_not_found'
  | 'row_ambiguous'
  | 'column_not_found'
  | 'column_ambiguous'
  | 'ragged_table'
  | 'illegal_value';

export interface TableEditResult {
  ok: boolean;
  /** The FULL section body with the one cell changed. Only on success. */
  body?: string;
  /** What the cell held before — so the reply can say what changed. */
  before?: string;
  /** The resolved header text of the column that was written. */
  column?: string;
  /** The resolved row label. */
  row?: string;
  /** The caption of the table that was written, when it has one. */
  caption?: string | null;
  /** On `row_ambiguous`: the captions the caller may choose between. */
  choices?: string[];
  reason?: TableEditFailure;
}

/** Loose match: case, surrounding whitespace and a trailing unit parenthetical
 *  are all noise. "DIAMETER (mm)" is the same column a doctor calls "diameter".
 *  Used ONLY for rows and columns — never for the section heading, which is
 *  readNoteSection's business. */
function norm(s: string): string {
  return s
    .trim()
    .toLowerCase()
    .replace(/\*\*/g, '')
    .replace(/\s*\([^)]*\)\s*$/, '')
    .replace(/\s+/g, ' ');
}

function cells(line: string): string[] | null {
  if (RULE_RE.test(line) || !ROW_RE.test(line)) return null;
  const inner = line.trim().replace(/^\|/, '').replace(/\|$/, '');
  return inner.split('|').map((c) => c.trim());
}

/** Rebuild a row, preserving cell count. */
function renderRow(parts: string[]): string {
  return `| ${parts.join(' | ')} |`;
}

/**
 * The caption above a table — the line before its header, when that line is
 * prose rather than another row or a heading. On a bilateral study it is what
 * carries the laterality, so it is the only honest disambiguator.
 */
function captionFor(lines: string[], headerIdx: number): string | null {
  for (let i = headerIdx - 1; i >= 0; i -= 1) {
    const line = lines[i];
    if (!line.trim()) return null;
    if (HEADING_RE.test(line) || cells(line)) return null;
    return line.trim();
  }
  return null;
}

/**
 * Replace ONE cell in ONE table row, inside ONE section.
 *
 * Every other character of the section — captions, blank lines, prose above and
 * below the table, the other cells in the same row — is returned untouched.
 */
export function editTableCell(params: {
  note: string;
  sectionLabel: string;
  rowLabel: string;
  columnLabel: string;
  value: string;
  /** Optional: which table, when the row label appears under more than one.
   *  Matched loosely against the caption line above each table. */
  tableCaption?: string | null;
}): TableEditResult {
  // A PIPE ENDS A CELL, AND NOTHING DOWNSTREAM UNDERSTANDS AN ESCAPE.
  //
  // This used to write `\|`, which is correct markdown and useless here: the
  // note is consumed by claim-prose, the screen-reader block, the DOCX table
  // builder and the export reconciler, none of which unescape it. The escape
  // just moved the corruption from the note into every renderer, and made the
  // next edit of that row read a cell that no longer matched. A measurement
  // never legitimately contains a pipe, so this is a refusal.
  if (/[|]/.test(params.value)) return { ok: false, reason: 'illegal_value' };
  if (/[\r\n]/.test(params.value)) return { ok: false, reason: 'illegal_value' };

  const sectionBody = readNoteSection(params.note, params.sectionLabel);
  if (sectionBody === null) return { ok: false, reason: 'section_not_found' };

  const lines = sectionBody.split('\n');

  // A section can hold several tables (one per leg, typically). Collect every
  // header row so a column can be resolved against the table its row is in,
  // never against a neighbour's.
  const headerAt: number[] = [];
  for (let i = 0; i < lines.length; i += 1) {
    if (cells(lines[i]) && RULE_RE.test(lines[i + 1] ?? '')) headerAt.push(i);
  }
  if (headerAt.length === 0) return { ok: false, reason: 'no_table' };

  const wantRow = norm(params.rowLabel);
  let matches: { line: number; header: number; caption: string | null }[] = [];
  for (let i = 0; i < lines.length; i += 1) {
    const c = cells(lines[i]);
    if (!c || headerAt.includes(i)) continue;
    if (norm(c[0]) !== wantRow) continue;
    const header = [...headerAt].reverse().find((h) => h < i);
    if (header === undefined) continue;
    matches.push({ line: i, header, caption: captionFor(lines, header) });
  }

  if (matches.length === 0) return { ok: false, reason: 'row_not_found' };

  // TWO TABLES, ONE LABEL. On a bilateral study "GSV at the SFJ" exists under
  // both legs. The caller may say WHICH — by the caption, which is what carries
  // the laterality — and that narrowing is applied here rather than left to
  // whichever row happened to come first.
  if (matches.length > 1 && params.tableCaption) {
    const want = norm(params.tableCaption);
    const narrowed = matches.filter(
      (m) => m.caption && (norm(m.caption) === want || norm(m.caption).includes(want)),
    );
    if (narrowed.length === 1) matches = narrowed;
  }
  if (matches.length > 1) {
    return {
      ok: false,
      reason: 'row_ambiguous',
      // Say what the caller may pick BETWEEN. Asking "which one?" while
      // offering no way to answer is how the bilateral case — the main
      // ultrasound case — became simply uneditable.
      choices: matches.map((m) => m.caption).filter((c): c is string => Boolean(c)),
    };
  }

  const { line, header, caption } = matches[0];
  const rawHeaderCells = cells(lines[header]);
  const rowCells = cells(lines[line]);
  if (!rawHeaderCells || !rowCells) return { ok: false, reason: 'no_table' };

  // ⚠️ LEGACY WIDEN-ON-PARSE — F24 SLICE 1. THE NOTE IS NOT TOUCHED.
  //
  // Notes generated before the skeleton fix carry a header one cell narrower
  // than their rows, because `renderStructureDirective` emitted
  // `| DIAMETER (mm) | REFLUX TIME (ms) |` over rows that always lead with a
  // label cell. Measured on production 2026-08-21, over every data row under a
  // detected header:
  //
  //     delta = +1 : 339 rows      delta = 0 : 331 rows      delta OTHER : 0
  //
  // THE UNIVERSE IS CLOSED. There is no delta of +2, and none of -1. So the
  // only ragged shape that exists is the one whose missing cell is the label
  // column, and recognising it is a measurement rather than a guess.
  //
  // ⚠️ AND THE MISSING CELL IS PROVABLY *LEADING*, NOT TRAILING — which is the
  // whole risk, because inferring the wrong end reintroduces exactly the
  // off-by-one write the guard exists to prevent. The proof is upstream, at the
  // match loop: a row becomes a candidate ONLY when `norm(c[0]) === wantRow`.
  // So for the row we are about to write, cell 0 IS the row label, by the same
  // predicate that selected it. The extra cell is at the front.
  //
  // ⚠️ THIS IS NOT A WEAKENING OF THE GUARD, AND THE GUARD'S LINE BELOW IS
  // UNCHANGED. What changes is the header VALUE handed to it: a header that
  // says nothing about its label column is read as having an unnamed one. Every
  // other mismatch still reaches the refusal — a delta of 2, a table whose rows
  // disagree with each other, a header WIDER than its rows. The synthesised
  // cell is empty and index 0 is filtered out of column resolution below, so it
  // can never be written to and can never be selected as a target.
  const dataRowCounts: number[] = [];
  for (let i = header + 2; i < lines.length; i += 1) {
    if (headerAt.includes(i)) break;
    const c = cells(lines[i]);
    if (!c) {
      if (lines[i].trim().startsWith('|')) break;
      if (lines[i].trim() === '') continue;
      break;
    }
    dataRowCounts.push(c.length);
  }
  const everyDataRowAgrees =
    dataRowCounts.length > 0 && new Set(dataRowCounts).size === 1;
  // ⚠️ THE DELTA SAYS *THAT* A CELL IS MISSING. IT NEVER SAYS *WHICH END*.
  //
  // The first version of this widened on delta alone, reasoning that a row is
  // only a candidate when `norm(c[0]) === wantRow`, so cell 0 is the label.
  // THAT IS A NON-SEQUITUR AND THE ADVERSARIAL PASS BROKE IT: it proves cell 0
  // of the ROW is the label and says nothing about the HEADER. A header that
  // NAMES its label column and is short a TRAILING data column is delta +1 too.
  //
  // Reproduced on the real function before this guard was added:
  //     | VEIN | DIAMETER (mm) |          <- names its label column, short one
  //     | GSV at the SFJ | 6.2 | 3.4 |
  //   edit DIAMETER := 7.7  ->  ok=true, reports column "DIAMETER (mm)",
  //                             writes `| GSV at the SFJ | 6.2 | 7.7 |`
  // The diameter was left uncorrected, the REFLUX time was destroyed, and the
  // doctor was told the diameter had changed. Before the slice that input was
  // refused. A WRONG measurement under a correct-looking confirmation is worse
  // than the refusal it replaced — which is precisely what the original
  // `ragged_table` test feared, arriving through the fix for it.
  //
  // ⚠️ AND THE PRODUCTION CENSUS COULD NOT HAVE CAUGHT IT: it measured DELTA
  // (+1 -> 339, 0 -> 331, other -> 0), and delta is invariant under which end
  // is short. An observation that cannot come out the other way is not
  // evidence for the thing it was cited for.
  //
  // SO THE WIDEN NOW TURNS ON EVIDENCE ABOUT THE HEADER: it fires only when the
  // header's FIRST cell is itself a DATA column, i.e. the header demonstrably
  // has no label column — the same question, through the same predicate, that
  // the generator asks when deciding whether to emit one.
  const headerLacksLabelColumn =
    rawHeaderCells.length > 0 && isDataColumnHeader(rawHeaderCells[0]);
  const headerCells =
    headerLacksLabelColumn &&
    rawHeaderCells.length === rowCells.length - 1 &&
    everyDataRowAgrees &&
    dataRowCounts[0] === rowCells.length
      ? ['', ...rawHeaderCells]
      : rawHeaderCells;

  // A RAGGED TABLE IS NOT WRITABLE.
  //
  // Column resolution indexes the header and writes the row at the SAME index.
  // If a header omits the row-label column — `| DIAMETER | REFLUX |` over
  // `| GSV at the SFJ | 6.2 | 3.4 |` — every index is off by one, and the write
  // lands one column left of the one it then reports back. Refusing is the only
  // safe reading of a grid that does not line up.
  if (headerCells.length !== rowCells.length) return { ok: false, reason: 'ragged_table' };

  const wantCol = norm(params.columnLabel);
  const colIdx = headerCells
    .map((h, i) => ({ h: norm(h), i }))
    // The first column is the row label itself, never a writable measurement.
    .filter((x) => x.i > 0 && x.h === wantCol)
    .map((x) => x.i);

  if (colIdx.length === 0) return { ok: false, reason: 'column_not_found' };
  if (colIdx.length > 1) return { ok: false, reason: 'column_ambiguous' };

  const idx = colIdx[0];
  const before = rowCells[idx];
  rowCells[idx] = params.value.trim();
  lines[line] = renderRow(rowCells);

  return {
    ok: true,
    body: lines.join('\n'),
    before,
    column: headerCells[idx].trim(),
    row: rowCells[0].trim(),
    caption,
  };
}

/** Doctor-facing, PHI-free explanation of a refusal. */
export const TABLE_EDIT_REASON: Record<TableEditFailure, string> = {
  section_not_found: "I couldn't find that section in the note.",
  no_table: "That section doesn't have a measurements table.",
  row_not_found: "I couldn't find that row in the table.",
  row_ambiguous:
    'That row appears in more than one table here — tell me which one and I will change it.',
  column_not_found: "I couldn't find that column in the table.",
  column_ambiguous: 'That column name appears twice in the table, so I stopped rather than guess.',
  ragged_table:
    "That table's header and its rows don't line up, so I can't tell which column is which.",
  illegal_value: "A measurement can't contain a line break or a “|”.",
};
