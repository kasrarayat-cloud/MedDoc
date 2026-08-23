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
import { classifyHeaderCell } from './table-header-shape';
import { readNoteSection } from './splice-note-section';
import { captionCandidate } from './table-caption';

/** `| --- | :--- |` — a table's alignment rule, never content. */
/** Any `| … | … |` line. */
/** `## HEADING` */
const HEADING_RE = /^\s*#{1,6}\s/;

/** Sentinel bucket for "this candidate has no caption at all", kept distinct
 *  from any real caption text so the two unanswerable cases stay separable. */
const NO_CAPTION = ' no-caption';

/**
 * The key that decides whether two captions are THE SAME TABLE to a caller.
 *
 * ⚠️ DELIBERATELY NOT `norm`, AND THERE IS ONE COPY OF IT ON PURPOSE. `norm`
 * deletes a trailing parenthetical, which is right for a COLUMN and wrong for a
 * CAPTION, where the parenthetical is often the whole laterality signal —
 * keyed on `norm`, `GSV (Right)` and `GSV (Left)` collapse into one bucket and
 * the refusal tells the doctor something false about their note.
 *
 * It was defined twice for about ten minutes — once in the ambiguity refusal
 * and once in the ordinal's cross-table guard — which is the shape canon names:
 * a second copy drifts from the first the day either is fixed, and here the two
 * copies decide the SAME question (is this one table or two?) for two different
 * refusals. Two answers to that question is a wrong-leg write waiting to
 * happen.
 */
function captionKey(c: string | null): string {
  return c === null ? NO_CAPTION : c.trim().toLowerCase().replace(/\s+/g, ' ');
}

/** The captions a caller may pick BETWEEN — deduped on `captionKey`, showing
 *  the RAW text of the FIRST occurrence, because that is what is printed in
 *  their note. `new Map(entries)` would keep the LAST, which shows a
 *  case-variant further down instead of the caption they read first. */
function distinctCaptions(captions: (string | null)[]): string[] {
  return captions
    .filter((c): c is string => c !== null)
    .filter((c, i, all) => all.findIndex((o) => captionKey(o) === captionKey(c)) === i);
}

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
  /** The header is short by exactly one cell and NOTHING SETTLES WHICH END.
   *  ⚠️ Distinct from `ragged_table`, which is a grid that genuinely does not
   *  line up. This one lines up under exactly one of two readings and the
   *  evidence does not pick between them — ruling #140. Collapsing the two
   *  would put a refusal and an unknowable in one bucket, and then no count
   *  could ever answer "did my change break this?". */
  | 'label_column_unresolved'
  /** A `rowOrdinal` was supplied that is not a whole number >= 1. The caller
   *  invented an index rather than echoing one this module issued. */
  | 'row_ordinal_invalid'
  /** A `rowOrdinal` was supplied that names no candidate — there are N
   *  identical-label rows and the caller asked for the (N+k)th.
   *  ⚠️ NEVER CLAMPED. Canon, *ERR TOWARD THE EDGE — THE EDGE HAS A FENCE*:
   *  an over-shoot that fails closed is a visibly missing edit, and a
   *  clamp-to-last is a real neighbouring row overwritten silently. */
  | 'row_ordinal_out_of_range'
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
  /**
   * On `row_ambiguous_same_table`: the identical-label candidates, numbered in
   * NOTE ORDER, each carrying the cells that DO distinguish it.
   *
   * ⚠️ THIS IS WHAT MAKES THAT REFUSAL ANSWERABLE, AND THE NUMBER IS ISSUED
   * HERE RATHER THAN INVENTED THERE. The certified template carries
   * `Saphenous Tributary Vein <<insert location>>` three times per leg — blank
   * slots the doctor fills in, so the labels are identical BY DESIGN and no
   * caption can separate them. Offering a bare count would be the same dead
   * end in a new costume: "row 2 of 3" is not a thing a doctor knows about
   * their own note. The row's OTHER cells are, so they travel with the
   * ordinal and the question becomes one a person can actually answer.
   */
  rowChoices?: { ordinal: number; cells: string[] }[];
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
  // ⚠️ THE DEFINITION IS NOT HERE ANY MORE — F24-CAPTION-VALIDATION, 2026-08-23.
  //
  // It lives in `lib/table-caption.ts`, because `claim-prose.ts` reads the same
  // line for a clinical READ and this module reads it for a clinical WRITE. Two
  // readers holding two definitions of "caption" is a wrong-table edit waiting
  // to happen, and that hazard was recorded in this comment for two days before
  // anything shared the code.
  //
  // ⚠️ THE PREVIOUS BODY WAS `return whatever line sits above`, WITH NO TEST OF
  // ANY KIND, and the version before THAT reached one blank line further and was
  // WITHDRAWN for writing a RIGHT-leg correction into the LEFT leg. Both the
  // reproduction and the measured predicate that replaces it are in
  // `table-caption.ts`'s header — read it there rather than trusting this
  // sentence, because that is the file a future edit will change.
  //
  // What changed for THIS caller: a caption ONE BLANK LINE UP is returned when
  // it satisfies the shape AND its section is uniformly captioned (new —
  // reaches 16 of the 20 previously-blocked headers). Everything unrecognised
  // still returns null, which every branch below already handles.
  //
  // ⚠️ THE ADJACENT SLOT IS NOT SHAPE-CHECKED, AND THIS COMMENT SAID IT WAS.
  // Corrected by the independent adversarial pass, 2026-08-23. The struck
  // sentence read: *"the adjacent line is now also shape-checked (strictly
  // narrower — 9 of 9 production captions still pass)"*. That was true of the
  // FIRST design and false of the shipped one — applying the shape rule to the
  // adjacent slot removed the 7-word TITLED caption the product supports, so it
  // was withdrawn the same hour, and the asymmetry became the argument.
  //
  // ⚠️ IT MATTERED BECAUSE OF *WHICH* PROPERTY IT CLAIMED. The shape rule's
  // both-sides clause is the one that stops a line naming BOTH legs from
  // narrowing a substring match to whichever table it happens to hit. A reader
  // who believed this sentence would believe that hole is closed. It is not —
  // measured by driving this very function:
  //
  //     captionCandidate(['The right leg was normal; the left GSV is
  //                        dilated.', ...TABLE], 1)
  //       -> returns the sentence   (isCaptionShaped refuses it)
  //
  //     editTableCell(row 'GSV at the SFJ', tableCaption 'right', 6.8) on a
  //     note whose RIGHT table is uncaptioned and whose LEFT table carries the
  //     adjacent line `Right and left legs`
  //       -> ok:true, before:"6.2"  <- THE LEFT LEG, reported as success
  //
  // That is `main`'s behaviour too, unchanged by this item and disclosed in
  // `table-caption.ts` with its production count (0 of 8) and its re-arming
  // condition. It is pinned end-to-end by the gate so it cannot decay from a
  // named residual into an assumption. **A comment that closes a hole the code
  // leaves open is worse than no comment**, because the next reader stops
  // looking.
  return captionCandidate(lines, headerIdx);
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
  /**
   * Optional: WHICH of several identical-label rows, 1-based, in note order,
   * applied AFTER any caption narrowing.
   *
   * ⚠️ THIS IS AN ECHO, NOT AN INFERENCE. The legitimate value is one this
   * module itself issued in `rowChoices` on a previous `row_ambiguous_same_table`
   * refusal, or one the TWIN derived from the document's own row order. It is
   * never a number a model counted off a note it was reading — that is the
   * unvalidated route which wrote a RIGHT-leg correction into the LEFT leg
   * (Slice 1b), and an index is harder to sanity-check than a caption, not
   * easier.
   *
   * Out of range REFUSES. See `row_ordinal_out_of_range`.
   */
  rowOrdinal?: number;
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

  // ── THE TWIN-SUPPLIED ORDINAL — F24-S4 ────────────────────────────────────
  //
  // Applied AFTER caption narrowing, deliberately: the caption says WHICH
  // TABLE and the ordinal says WHICH ROW WITHIN IT, so an ordinal is counted
  // over the candidates the caption already survived. Reversing the two would
  // make "the 2nd tributary" mean a different row depending on whether a
  // caption was supplied, which is the kind of coupling nobody can hold in
  // their head at the moment they are correcting a measurement.
  //
  // ⚠️ VALIDATED BEFORE IT IS USED, AND OUT-OF-RANGE REFUSES RATHER THAN
  // CLAMPING. Canon, *ERR TOWARD THE EDGE — THE EDGE HAS A FENCE*: the two
  // directions of an indexed clinical write are not symmetric in safety. An
  // ordinal past the end that fails closed leaves the cell visibly unchanged
  // and the doctor retypes. An ordinal past the end that clamps to the last
  // candidate silently overwrites a REAL NEIGHBOURING MEASUREMENT and reports
  // success — the wrong-cell class this arc has already paid for three times.
  if (params.rowOrdinal !== undefined) {
    const n = params.rowOrdinal;
    if (!Number.isInteger(n) || n < 1) return { ok: false, reason: 'row_ordinal_invalid' };
    // ⚠️ AN ORDINAL SAYS WHICH ROW. IT NEVER SAYS WHICH TABLE — AND APPLYING IT
    // ACROSS TABLES IS A WRONG-LEG WRITE. Found by this change's own census arm,
    // on the `captioned-blank-line` shape: `captionFor` reads the adjacent line
    // only, so a caption above a blank line narrows NOTHING, all six candidates
    // survive, and a twin ordinal of 1..3 — which counts within ONE leg —
    // selects from whichever leg happens to come first in the note. A LEFT-leg
    // correction then lands in the RIGHT leg and is reported as success, which
    // is precisely the defect Slice 1b removed, re-introduced through a new
    // door.
    //
    // So the ordinal is refused unless the candidates have already been reduced
    // to a single table. The caller is told the TABLE is still ambiguous, which
    // is the thing they actually have to supply, rather than being silently
    // served a row from the wrong one.
    const tables = new Set(matches.map((m) => m.header));
    if (tables.size > 1) {
      const captions = matches.map((m) => m.caption);
      return new Set(captions.map(captionKey)).size === 1
        ? { ok: false, reason: 'caption_not_found' }
        : { ok: false, reason: 'row_ambiguous', choices: distinctCaptions(captions) };
    }
    // ⚠️ `> matches.length` AND NOT `>=`. Asking for the 1st of 1 is a
    // legitimate, fully-specified request — it is how a caller that always
    // supplies an ordinal addresses an unambiguous row — and refusing it would
    // make the ordinal unusable as a default rather than as an escape hatch.
    if (n > matches.length) return { ok: false, reason: 'row_ordinal_out_of_range' };
    matches = [matches[n - 1]];
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
    // `null` is its own bucket: "every candidate is uncaptioned" and "every
    // candidate shares a caption" are both unanswerable, for different reasons,
    // and they get different refusals because the doctor's next move differs.
    const distinct = new Set(captions.map(captionKey));
    if (distinct.size === 1) {
      // ⚠️ THE ORDINALS TRAVEL WITH THE REFUSAL, SO IT STOPS BEING A DEAD END.
      // `row_ambiguous_same_table` was correct and terminal: the labels are
      // identical by design, so no answer the doctor could give would narrow
      // it. Numbering the candidates HERE — in note order, beside the cells
      // that actually differ — is what lets the next turn resolve, and it
      // keeps the index something this module issued rather than something a
      // model counted.
      //
      // ⚠️ OFFERED ONLY WHEN AN ORDINAL COULD ACTUALLY BE ACCEPTED — FOUND BY
      // THE INDEPENDENT ADVERSARIAL PASS ON THIS DIFF.
      //
      // The ordinal path above refuses unless the candidates have already been
      // narrowed to ONE table, because an ordinal says which ROW and never
      // which TABLE. This branch, however, is reached whenever every candidate
      // shares one caption KEY — and `null` is a key. Two UNCAPTIONED tables on
      // a bilateral study therefore land here with six candidates spanning both
      // legs, which is the ordinary production shape: canon records 20 of 45
      // headers with a blank line above them, and a blank line yields a null
      // caption.
      //
      // Numbering all six offered the doctor a list in which EVERY entry was
      // guaranteed to be refused — `chat-edit-visit.ts` renders `rowChoices` in
      // preference to `choices`, so they were shown six numbered rows, and
      // echoing any of them came back `caption_not_found` with the list now
      // gone. That is the dead end this slice set out to remove, wearing the
      // costume of the fix, and it is worse than the honest dead end it
      // replaced because the doctor spends a turn on it first.
      //
      // So the offer and the acceptance are keyed on the SAME predicate. A
      // second, looser copy of "can an ordinal resolve this?" is exactly the
      // drift `captionKey` was unified to prevent, one question further down.
      //
      // ⚠️ AND `row_ambiguous_same_table` NOW MEANS WHAT ITS NAME AND ITS
      // MESSAGE SAY: ONE table, the label repeated inside it. It used to be
      // selected purely on "every candidate shares a caption key", which is
      // also true of TWO tables captioned identically — so the message
      // "that row appears more than once in the same table" was already false
      // for that shape on `main`, and this slice's new clause ("tell me which
      // of the rows I listed") would have made it doubly false by promising a
      // list that cannot exist there.
      //
      // Both multi-table shapes are the same problem for the doctor: nothing
      // they can say resolves it — not a caption, because the captions do not
      // discriminate, and not an ordinal, because an ordinal cannot cross a
      // table. `caption_not_found` is exactly that statement, and its message
      // points at the one thing that DOES fix it: give the tables headings
      // that differ.
      // So the split is on the TABLE COUNT, which is the property both
      // messages actually describe — not on caption nullity, which describes
      // neither. Each reason is now true of every note that reaches it, and
      // every list that is offered can be answered.
      const oneTable = new Set(matches.map((m) => m.header)).size === 1;
      if (!oneTable) return { ok: false, reason: 'caption_not_found' };
      return {
        ok: false,
        reason: 'row_ambiguous_same_table',
        rowChoices: matches.map((m, i) => ({
          ordinal: i + 1,
          cells: (cells(lines[m.line]) ?? []).map((c) => c.trim()),
        })),
      };
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
      //
      // Both rules now live in `distinctCaptions`, once — the ordinal's
      // cross-table guard asks the same question and must not answer it
      // differently.
      choices: distinctCaptions(captions),
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
  //     delta = +1 : 237 rows      delta = 0 : 204 rows      delta OTHER : 0
  //
  // ⚠️ CORRECTED 2026-08-23 — this line read `339 / 331 / 0`. The original
  // join had no upper bound on the data row, so each header collected rows
  // from later tables in the same note. `delta OTHER : 0` — the fact that
  // licenses this widen — is unchanged under the corrected measurement.
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
  // (+1 -> 237, 0 -> 204, other -> 0), and delta is invariant under which end
  // is short. An observation that cannot come out the other way is not
  // evidence for the thing it was cited for.
  //
  // SO THE WIDEN TURNS ON EVIDENCE ABOUT THE HEADER — AND SINCE RULING #140 ON
  // THE TWIN'S EVIDENCE FIRST, WITH THE TEXT VOCABULARY AS THE UNTEMPLATED
  // FALLBACK ONLY.
  //
  // ⚠️ AND THE FALLBACK NOW HAS A THIRD ANSWER. The text test fired on ANY
  // trailing parenthetical and on any cell CONTAINING a measurement word, so
  // `Vein Size`, `Segment (right leg)` and `Site (see key)` — all row-label
  // columns — read as data and licensed the widen. That is #140's defect, and
  // its cost is not a refusal but a WRITE into the neighbouring cell reported
  // as success. Those three now return `label_column_unresolved`.
  //
  // ⚠️ THE PRECONDITIONS ARE UNCHANGED AND ARE CHECKED FIRST, DELIBERATELY: a
  // header that is not short by exactly one, or a table whose data rows
  // disagree with each other, never reaches either resolver and still falls to
  // `ragged_table`. #140 narrows WHEN the widen may fire; it does not widen the
  // set of grids that reach it.
  // ⚠️ EVERY HEADER CELL IS CLASSIFIED, NOT ONLY THE FIRST — AND THE
  // ADVERSARIAL PASS IS WHY. Asking only about cell 0 says "does the header
  // START with a data column?", which is a weaker question than "does the
  // header consist ONLY of data columns?" — and it is the second one that means
  // "there is no label column here". A vitals table shows the gap:
  //
  //     | Time | HEART RATE |          edit HEART RATE := 88
  //     | 08:00 | 72 | 120/80 |    ->  ok:true, before "120/80"
  //
  // `Time` is made entirely of measurement nouns, so cell-0-only read it as
  // data and widened; the BLOOD PRESSURE was destroyed and the doctor was told
  // the heart rate changed. `HEART RATE` is not measurement vocabulary at all,
  // so requiring EVERY cell to be `data` refuses this grid — while the three
  // header lines production actually widens are unaffected, because every cell
  // of all three is a unit or a measurement noun. Measured, not hoped:
  //
  //     | DIAMETER (mm) | REFLUX TIME (ms) |       13 lines / 7 visits
  //     | DIAMETER (mm) | REFLUX TIME (seconds) |  13 lines / 7 visits
  //     | DIAMETER | REFLUX TIME |                  1 line  / 1 visit
  //
  // ⚠️ AND THE TWIN ROUTE THAT STOOD HERE WAS REMOVED, DELIBERATELY. It read
  // `dataColumnCount === rawHeaderCells.length`, and THAT IS A COUNT: a header
  // of {label + N-1 data} and a header of {N data} both have N cells, so it is
  // invariant under which end is short — the identical axis error this file's
  // own comment above diagnoses in the production delta census. It also WIDENED
  // GRIDS THE TEXT ROUTE CORRECTLY REFUSES (`| VEIN | DIAMETER (mm) |`), which
  // is strictly worse than the defect #140 closed.
  //
  // ⚠️ AND THE REPLACEMENT MECHANISM THIS COMMENT FIRST PROPOSED — "the twin can
  // say whether its own header row's first cell is EMPTY" — IS REFUTED BY
  // MEASUREMENT. Production's single CERTIFIED compiled version, table 0:
  //
  //     row 0 (header)  cell0 HAS TEXT  cell1 HAS TEXT  cell2 HAS TEXT  0 fields
  //     row 1 (data)    cell0 HAS TEXT  cell1 1 field   cell2 1 field
  //
  // The twin's header row NAMES ALL THREE COLUMNS while the note carries a TWO
  // -cell header, so the twin knows column 0 is the label and STILL cannot say
  // which header cell the note dropped — that needs the header cells' TEXT, and
  // the IR stores only `staticTextSha256`. The evidence lives in the SOURCE
  // ARTIFACT, not the IR. See `table-header-shape.ts` for the full record.
  const shortByExactlyOne = rawHeaderCells.length === rowCells.length - 1;
  const gridIsRegular = everyDataRowAgrees && dataRowCounts[0] === rowCells.length;

  let widen = false;
  let unresolved = false;
  if (shortByExactlyOne && gridIsRegular && rawHeaderCells.length > 0) {
    const verdicts = rawHeaderCells.map(classifyHeaderCell);
    // A cell nothing settles is its own refusal; a cell that plainly names a
    // label column is an ordinary ragged grid. Different remedies, so different
    // reasons — see `label_column_unresolved`.
    unresolved = verdicts.includes('cannot_tell');
    widen = !unresolved && verdicts.every((v) => v === 'data');
  }
  if (unresolved) return { ok: false, reason: 'label_column_unresolved' };
  const headerCells = widen ? ['', ...rawHeaderCells] : rawHeaderCells;

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
    // ⚠️ AN UNNAMED COLUMN IS NEVER A TARGET, AND `x.i > 0` WAS NOT ENOUGH.
    // `norm` strips a trailing parenthetical, so a `columnLabel` that is
    // ENTIRELY one — `(mm)`, which the MODEL authors — normalises to `''`, and
    // an empty header cell anywhere in the table then matched it. Measured:
    //
    //   | DIAMETER (mm) |  | REFLUX TIME (ms) |   columnLabel '(mm)'
    //   | GSV at the SFJ | 6.2 | 1.1 | 3.4 |   ->  ok:true, before "1.1",
    //                                              column "" (an EMPTY name)
    //
    // The value landed in the unnamed column and the confirmation the doctor
    // reads — `chat-edit-visit.ts` renders `${row} · ${column}` — ended in a
    // bare separator with nothing after it. The old comment justified this
    // filter as "the first column is the row label"; that is true of index 0
    // and says nothing about the other empty cells a widened table can carry.
    .filter((x) => x.i > 0 && x.h !== '' && x.h === wantCol)
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
  // ⚠️ THIS NO LONGER ENDS THE CONVERSATION, AND THE WORDING HAD TO MOVE WITH
  // THE BEHAVIOUR. It used to say "edit the row directly in the document",
  // which was honest when nothing could resolve it and is now FALSE: the
  // refusal carries `rowChoices`, so there is an answer the doctor can give.
  // A refusal that describes a dead end which no longer exists sends them to
  // do by hand what the surface would now do for them.
  row_ambiguous_same_table:
    'That row appears more than once in the same table, so naming the table cannot tell them apart. I have left the note unchanged — tell me which of the rows I listed you mean and I will change it.',
  row_ordinal_invalid:
    "I couldn't tell which of the repeated rows you meant, so I left the note unchanged.",
  // Says what is true and does NOT invite a retry at a different index — the
  // caller asked for a row that is not there, and guessing again is how an
  // index lands on a real neighbouring measurement.
  row_ordinal_out_of_range:
    "That row number is past the end of the rows with that label, so I've left the note unchanged. Tell me which of the rows I listed you mean.",
  ragged_table:
    "That table's header and its rows don't line up, so I can't tell which column is which.",
  // Says what is true and where the doctor can act, and deliberately does NOT
  // ask them to rephrase — no rewording of the request can supply the column
  // heading the note is missing.
  label_column_unresolved:
    "That table's header is missing a heading for its first column, so I can't tell which column your value belongs in. I've left the note unchanged — edit that cell directly in the document.",
  illegal_value: "A measurement can't contain a line break or a “|”.",
};
