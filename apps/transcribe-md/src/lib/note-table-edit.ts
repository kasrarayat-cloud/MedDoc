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
// is about to sign. Same rule claim-prose already follows.
// ============================================================================

/** `| --- | :--- |` — a table's alignment rule, never content. */
const RULE_RE = /^\s*\|[\s:|-]+\|\s*$/;
/** Any `| … | … |` line. */
const ROW_RE = /^\s*\|.*\|\s*$/;
/** `## HEADING` */
const HEADING_RE = /^\s*#{1,6}\s+(.*)$/;

export type TableEditFailure =
  | 'section_not_found'
  | 'no_table'
  | 'row_not_found'
  | 'row_ambiguous'
  | 'column_not_found'
  | 'column_ambiguous';

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
  reason?: TableEditFailure;
}

/** Loose match: case, surrounding whitespace and a trailing unit parenthetical
 *  are all noise. "DIAMETER (mm)" is the same column a doctor calls "diameter". */
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
 * Make a value safe to sit inside one cell.
 *
 * A raw `|` in the value would close the cell early and hand the row an extra
 * column — the grid silently shifts, and every measurement to the right of it
 * ends up under the wrong heading. A newline would end the row entirely. The
 * model supplies this string, so neither can be assumed away.
 */
function sanitizeCell(value: string): string {
  return value
    .replace(/[\r\n]+/g, ' ')
    .replace(/\|/g, '\\|')
    .trim();
}

/**
 * Slice out one section's body from a note.
 *
 * Returns the body lines and the index range they occupy, so a caller can
 * splice the edited body back without touching the rest of the note.
 */
export function findSection(
  note: string,
  sectionLabel: string,
): { start: number; end: number; lines: string[] } | null {
  const lines = note.split('\n');
  const want = norm(sectionLabel);
  let start = -1;
  for (let i = 0; i < lines.length; i += 1) {
    const m = HEADING_RE.exec(lines[i]);
    if (m && norm(m[1]) === want) {
      start = i + 1;
      break;
    }
  }
  if (start === -1) return null;
  let end = lines.length;
  for (let i = start; i < lines.length; i += 1) {
    if (HEADING_RE.test(lines[i])) {
      end = i;
      break;
    }
  }
  return { start, end, lines: lines.slice(start, end) };
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
}): TableEditResult {
  const section = findSection(params.note, params.sectionLabel);
  if (!section) return { ok: false, reason: 'section_not_found' };

  const lines = [...section.lines];

  // A section can hold several tables (one per leg, typically). Collect every
  // header row so a column can be resolved against the table its row is in,
  // never against a neighbour's.
  const headerAt: number[] = [];
  for (let i = 0; i < lines.length; i += 1) {
    if (cells(lines[i]) && RULE_RE.test(lines[i + 1] ?? '')) headerAt.push(i);
  }
  if (headerAt.length === 0) return { ok: false, reason: 'no_table' };

  const wantRow = norm(params.rowLabel);
  const matches: { line: number; header: number }[] = [];
  for (let i = 0; i < lines.length; i += 1) {
    const c = cells(lines[i]);
    if (!c || headerAt.includes(i)) continue;
    if (norm(c[0]) !== wantRow) continue;
    // Which table does this row belong to? The nearest header ABOVE it.
    const header = [...headerAt].reverse().find((h) => h < i);
    if (header === undefined) continue;
    matches.push({ line: i, header });
  }

  if (matches.length === 0) return { ok: false, reason: 'row_not_found' };
  // TWO TABLES, ONE LABEL. On a bilateral study "GSV at the SFJ" exists under
  // both legs. Writing to either one is a coin flip on which leg gets the
  // measurement, so this is where we stop and ask.
  if (matches.length > 1) return { ok: false, reason: 'row_ambiguous' };

  const { line, header } = matches[0];
  const headerCells = cells(lines[header]);
  if (!headerCells) return { ok: false, reason: 'no_table' };

  const wantCol = norm(params.columnLabel);
  const colIdx = headerCells
    .map((h, i) => ({ h: norm(h), i }))
    // The first column is the row label itself, never a writable measurement.
    .filter((x) => x.i > 0 && x.h === wantCol)
    .map((x) => x.i);

  if (colIdx.length === 0) return { ok: false, reason: 'column_not_found' };
  if (colIdx.length > 1) return { ok: false, reason: 'column_ambiguous' };

  const rowCells = cells(lines[line]);
  if (!rowCells) return { ok: false, reason: 'no_table' };
  const idx = colIdx[0];
  // A row shorter than its header is malformed but survivable — pad rather
  // than write past the end and corrupt the grid.
  while (rowCells.length <= idx) rowCells.push('');

  const before = rowCells[idx];
  rowCells[idx] = sanitizeCell(params.value);
  lines[line] = renderRow(rowCells);

  return {
    ok: true,
    body: lines.join('\n'),
    before,
    column: headerCells[idx].trim(),
    row: rowCells[0].trim(),
  };
}

/** Doctor-facing, PHI-free explanation of a refusal. */
export const TABLE_EDIT_REASON: Record<TableEditFailure, string> = {
  section_not_found: "I couldn't find that section in the note.",
  no_table: "That section doesn't have a measurements table.",
  row_not_found: "I couldn't find that row in the table.",
  row_ambiguous:
    'That row appears in more than one table here — tell me which one (for example which leg) and I will change it.',
  column_not_found: "I couldn't find that column in the table.",
  column_ambiguous: 'That column name appears twice in the table, so I stopped rather than guess.',
};
