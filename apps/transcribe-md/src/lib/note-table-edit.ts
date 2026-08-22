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

import { parseMarkdownRow, MARKDOWN_RULE_ROW_RE } from './markdown-row';
import { isDataColumnHeader } from './table-header-shape';
import { readNoteSection } from './splice-note-section';

/** `| --- | :--- |` — a table's alignment rule, never content. */
/** Any `| … | … |` line. */
/** `## HEADING` */
const HEADING_RE = /^\s*#{1,6}\s/;

/** Sentinel bucket for "this candidate has no caption at all", kept distinct
 *  from any real caption text so the two unanswerable cases stay separable. */
const NO_CAPTION = ' no-caption';

export type TableEditFailure =
  /** Two tables carry this row and NEITHER has a caption to name it by.
   *  Distinct from `row_ambiguous`, which the caller CAN answer. */
  | 'caption_not_found'
  /** The row appears more than once under the SAME caption — the certified
   *  template's three blank tributary slots per leg. Naming the table cannot
   *  separate them, so this is distinct from `row_ambiguous`, which the caller
   *  CAN answer. */
  | 'row_ambiguous_same_table'
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

/** ONE reader, five callers — `lib/markdown-row.ts`.
 *
 *  ⚠️ THIS CALLER NOW SEES ROWS IT USED TO SKIP. Under the strict matcher a row
 *  carrying a trailing annotation after its last pipe returned null here, was
 *  skipped by the match loop, and the doctor was told `row_not_found` about a
 *  row printed in their document — while the fill path read it correctly the
 *  whole time. The suffix is deliberately dropped at THIS caller: an edit
 *  rewrites the row from its cells, and carrying an evidence quote for a value
 *  that has just been replaced would put two records on one line. */
function cells(line: string): string[] | null {
  // A separator is not content HERE — the header scan and the match loop both
  // rely on it. The shared primitive parses it, because `bridge-fill` needs
  // that; the judgement lives with the caller that holds it.
  if (MARKDOWN_RULE_ROW_RE.test(line)) return null;
  return parseMarkdownRow(line)?.cells ?? null;
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
  // ⚠️ THE ADJACENT LINE ONLY. A ONE-BLANK SKIP WAS BUILT, PROVEN, AND
  // WITHDRAWN — F24 SLICE 1b, 2026-08-21.
  //
  // The motivation was real and still stands: 20 of 45 production headers have
  // a blank line above them, so a bilateral study in the canonical markdown
  // shape (caption, blank line, table) could not be disambiguated at all.
  //
  // ⚠️ BUT `captionFor` NEVER DISTINGUISHED A CAPTION FROM ARBITRARY PROSE —
  // it returns whatever line sits above, and always has. Widening its reach
  // therefore did not teach it to find captions; it multiplied the amount of
  // ORDINARY CLINICAL NARRATIVE it could mistake for one. Reproduced on the
  // real function before the revert:
  //
  //     ## FINDINGS
  //     |  | DIAMETER (mm) | ... |        <- table 1, the RIGHT leg, 5.1
  //     | GSV at the SFJ | 5.1 | 0.3 |
  //
  //     The right leg was normal; the left GSV is dilated.
  //                                        <- one blank line
  //     |  | DIAMETER (mm) | ... |        <- table 2, the LEFT leg, 6.2
  //     | GSV at the SFJ | 6.2 | 3.4 |
  //
  //   editTableCell(rowLabel 'GSV at the SFJ', tableCaption 'Right Leg', 6.8)
  //     -> ok=true, before="6.2", LEFT leg written, RIGHT leg untouched
  //
  // That narrative became table 2's caption, the substring narrowing matched
  // "right" inside it, and the doctor's RIGHT-leg correction was persisted
  // into the LEFT leg and reported as success. `.caption` has no consumer, so
  // nothing downstream shows which table was chosen.
  //
  // A WRONG-LEG MEASUREMENT IS WORSE THAN AN UNEDITABLE TABLE. The refusal it
  // replaced cost the doctor a retype; this costs them a wrong record.
  //
  // THE REAL DEFECT IS CAPTION *VALIDATION*, NOT CAPTION *DISTANCE*, and a
  // correct fix has to decide what a caption IS — which is a product question,
  // not a loop bound. Reaching further without answering it is strictly worse
  // than reaching one line. (Note that `claim-prose.ts:71` reads the adjacent
  // line too; whatever answers this must move both, or the two readers in this
  // codebase will disagree about what a caption is.)
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
    if (cells(lines[i]) && MARKDOWN_RULE_ROW_RE.test(lines[i + 1] ?? '')) headerAt.push(i);
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
    // ⚠️ AN EMPTY `want` IS THE ABSENCE OF A SIGNAL, NOT A MATCH-ALL — AND THIS
    // WAS A LIVE WRONG-LEG WRITE ON `main`, FOUND BY THE ADVERSARIAL PASS.
    //
    // `norm` deletes a TRAILING PARENTHETICAL, so a caption that is ENTIRELY a
    // parenthetical — `(right leg)`, `(Right)` — normalises to `''`. Every
    // captioned candidate then satisfied `norm(m.caption).includes('')`, so the
    // filter kept whichever tables happened to carry a caption and, when that
    // left exactly one, WROTE TO IT. Reproduced against a note whose RIGHT-leg
    // table is uncaptioned and whose LEFT-leg table is captioned `Left Leg`:
    //
    //   tableCaption '(right leg)' -> ok:true, caption "Left Leg", before "6.2"
    //
    // The doctor's RIGHT-leg correction landed in the LEFT leg and was reported
    // as success, and nothing on screen says otherwise — `chat-edit-visit.ts`
    // surfaces the row and the column, never the caption. `(Right)` is an
    // entirely plausible thing for the model to emit, given the note's own
    // `FINDINGS (RIGHT)` heading convention.
    const narrowed = matches.filter(
      (m) =>
        want !== '' && m.caption && (norm(m.caption) === want || norm(m.caption).includes(want)),
    );
    // ⚠️ NARROW WHENEVER THE CAPTION DISCRIMINATES, NOT ONLY WHEN IT RESOLVES —
    // F24-S3. This read `if (narrowed.length === 1)`, so a caption that cut six
    // candidates down to three was DISCARDED ENTIRELY and the refusal below
    // then offered the doctor both legs again — including the leg they had
    // just named. Measured by replay on the certified template: asking for the
    // right-leg tributary returned
    //   choices: ["Right Leg","Right Leg","Right Leg","Left Leg","Left Leg","Left Leg"]
    // A narrowing that only counts when it fully resolves throws away the half
    // of the answer the doctor did give.
    //
    // Narrowing to ZERO is NOT a narrowing: a caption that matches nothing is
    // a caption we failed to recognise, and dropping every candidate on it
    // would turn "I don't know that table" into `row_not_found`.
    if (narrowed.length > 0) matches = narrowed;
  }
  if (matches.length > 1) {
    // ⚠️ AN UNANSWERABLE QUESTION IS NOT A REFUSAL, IT IS A DEAD END — SLICE 1b.
    //
    // `row_ambiguous` means "tell me which one and I will change it". Emitting
    // it with an EMPTY choices list asks the doctor to pick from nothing, and
    // no answer they can give will ever narrow it. That shape is now
    // unreachable BY CONSTRUCTION rather than patched at this one call site: if
    // no candidate carries a caption there is nothing to disambiguate WITH, and
    // the refusal says so instead of pretending the conversation can continue.
    //
    // ⚠️ AND THE EMPTY LIST WAS ONLY THE LOUDEST SHAPE OF THAT DEAD END — F24-S3.
    // A list can be non-empty and still admit no answer that narrows anything.
    // The certified template carries `Saphenous Tributary Vein <<insert
    // location>>` THREE TIMES IN EACH LEG — they are blank slots the doctor
    // fills in, so the labels are identical by design. Every candidate then
    // shares one caption, and "tell me which one" is a question whose only
    // available answer has already been given. Distinguishing the two cases is
    // the difference between a refusal a doctor can act on and a loop.
    const captions = matches.map((m) => m.caption);
    // ⚠️ DISCRIMINATION IS KEYED ON THE CAPTION *AS WRITTEN*, NEVER THROUGH
    // `norm` — FOUND BY THE ADVERSARIAL PASS ON THIS DIFF'S FIRST DRAFT.
    //
    // `norm` deletes a trailing parenthetical, which is right for a COLUMN
    // ("DIAMETER (mm)" is the column a doctor calls "diameter") and wrong for a
    // CAPTION, where the parenthetical is often the whole laterality signal.
    // Keyed on `norm`, `GSV (Right)` and `GSV (Left)` collapsed into ONE bucket
    // and this branch told the doctor the row appears twice in the SAME TABLE —
    // about two DIFFERENT tables — while suppressing the two captions `main`
    // had been showing them. A refusal that states something false about the
    // note is worse than the ambiguous one it replaced.
    //
    // `norm` still governs MATCHING a caller's answer above; only the decision
    // "can any answer discriminate?" uses this stricter key.
    const key = (c: string | null) =>
      c === null ? NO_CAPTION : c.trim().toLowerCase().replace(/\s+/g, ' ');
    // `null` is its own bucket: "every candidate is uncaptioned" and "every
    // candidate shares a caption" are both unanswerable, for different reasons,
    // and they get different refusals because the doctor's next move differs.
    const distinct = new Set(captions.map(key));
    if (distinct.size === 1) {
      return captions[0] === null
        ? { ok: false, reason: 'caption_not_found' }
        : { ok: false, reason: 'row_ambiguous_same_table' };
    }
    return {
      ok: false,
      reason: 'row_ambiguous',
      // Say what the caller may pick BETWEEN. Asking "which one?" while
      // offering no way to answer is how the bilateral case — the main
      // ultrasound case — became simply uneditable.
      //
      // DEDUPED: three identical rows under one caption used to emit that
      // caption three times, so the doctor was offered "Right Leg" as though it
      // were three different choices.
      //
      // ⚠️ DEDUPED ON THE SAME KEY THE AMBIGUITY DECISION USES, not on the raw
      // string. With two different keys, `Right Leg` and `Right leg` counted as
      // two choices here while narrowing treated them as one table — so the
      // doctor was offered an option that, fed back verbatim, is a non-answer.
      // The RAW text of the first occurrence is what gets displayed, because
      // that is what is actually printed in their note.
      // ⚠️ FIRST occurrence wins. `new Map(entries)` keeps the LAST value for a
      // repeated key, so the tidy one-liner displayed the case-variant further
      // down the note instead of the caption the doctor reads first. The arm
      // asserting this reddened against its own author on first execution.
      choices: captions
        .filter((c): c is string => c !== null)
        .filter((c, i, all) => all.findIndex((o) => key(o) === key(c)) === i),
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
  caption_not_found:
    'That row appears in more than one table here, and neither table has a heading I can tell them apart by. Name each table — "Right leg", "Left leg" — and I will change it.',
  // Deliberately does NOT ask "which one?" — the whole point is that naming the
  // table cannot answer it. It says what IS true and where the doctor can act.
  row_ambiguous_same_table:
    'That row appears more than once in the same table, so naming the table cannot tell them apart. I have left the note unchanged — edit the row directly in the document.',
  ragged_table:
    "That table's header and its rows don't line up, so I can't tell which column is which.",
  illegal_value: "A measurement can't contain a line break or a “|”.",
};
