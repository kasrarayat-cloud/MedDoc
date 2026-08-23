// ============================================================================
// A suggestion should read like something a person said.
// ----------------------------------------------------------------------------
// Verifier-demoted claims are quoted verbatim from the note, and when the note
// carries a measurements table that means a card can read:
//
//     | GSV at the Knee | 3.4 | 1.8 |
//
// which is a fragment of markup, not a clinical statement. A doctor is being
// asked to decide whether that belongs in a patient's record; they should be
// shown a sentence.
//
// The column names come from the note's OWN header row, so the phrasing is the
// doctor's vocabulary rather than ours, and a cell we cannot pair with a column
// is left out rather than guessed at. Anything that is not a table row is
// returned untouched — this only ever reformats markup, never content.
// ============================================================================

import { parseMarkdownRow, MARKDOWN_RULE_ROW_RE } from './markdown-row';
import { captionCandidate } from './table-caption';

/** ONE reader, five callers — `lib/markdown-row.ts`.
 *
 *  ⚠️ THE `>= 2` RULE IS THIS CALLER'S, AND IT STAYS HERE. The primitive
 *  parses; each caller decides what it will accept. A one-cell pipe line is a
 *  table row as far as markdown is concerned and is not a measurement row as
 *  far as claim prose is concerned — folding that judgement into the shared
 *  reader would impose it on the export renderers, which must render whatever
 *  the note carries. */
function cells(line: string): string[] | null {
  const parsed = parseMarkdownRow(line);
  if (!parsed) return null;
  return parsed.cells.length >= 2 ? parsed.cells : null;
}

/** "DIAMETER (mm)" -> { label: 'diameter', unit: 'mm' } */
function readHeading(raw: string): { label: string; unit: string | null } {
  const paren = /^(.*?)\s*\(([^)]+)\)\s*$/.exec(raw.trim());
  const label = (paren ? paren[1] : raw).trim().toLowerCase();
  return { label, unit: paren ? paren[2].trim() : null };
}

/** A cell that says nothing. */
function isBlank(cell: string): boolean {
  const t = cell.trim();
  return t === '' || t === '—' || t === '-' || /^\[not documented\]$/i.test(t);
}

/**
 * Find the header row of the table this row belongs to.
 *
 * Scans upward from the matching row in the note: the first pipe row above the
 * alignment rule is the header. Returns null when the row is not in a table we
 * can read, in which case the caller leaves the claim alone.
 */
function headerFor(note: string, rowText: string): { header: string[]; caption: string | null } | null {
  const lines = note.split('\n');
  const target = rowText.trim();
  const hits = lines.reduce<number[]>((acc, l, i) => (l.trim() === target ? [...acc, i] : acc), []);
  // AMBIGUOUS. A bilateral study renders one table per leg with identical
  // segment labels; pairing against whichever table came first would label a
  // left-leg measurement with the right leg's columns, in the doctor's own
  // vocabulary, which reads as authoritative. One match or nothing.
  if (hits.length !== 1) return null;
  const at = hits[0];
  for (let i = at - 1; i >= 0; i -= 1) {
    const line = lines[i];
    if (MARKDOWN_RULE_ROW_RE.test(line)) {
      const head = cells(lines[i - 1] ?? '');
      if (!head || head.length < 2) return null;
      // The line above the header is usually the table's own caption, and on a
      // bilateral study it is what carries the laterality. A card that says
      // "GSV at the Knee" without saying WHICH LEG is not enough to decide on.
      //
      // ⚠️ WHETHER A LINE *IS* A CAPTION IS NOT DECIDED HERE — F24-CAPTION-
      // VALIDATION, 2026-08-23. It is `lib/table-caption.ts`, shared with
      // `note-table-edit.ts`. This file used to hold its own inline version
      // (`above && !cells(above) && !HEADING`), and `note-table-edit.ts`'s own
      // comment named the divergence as a wrong-table edit waiting to happen:
      // one reader labels a CARD with a leg and the other narrows a WRITE by
      // it, so the moment they disagree about which line is the caption, a
      // doctor is shown one table and edits another.
      //
      // Both readers therefore now accept exactly the same lines — including
      // the one-blank-up shape, which this file previously refused too. Reading
      // the caption for a card and writing to that table are the same question
      // asked twice.
      const raw = captionCandidate(lines, i - 1);
      // ⚠️ THE TAIL SPLIT IS A *DISPLAY* REDUCTION AND STAYS LOCAL, DELIBERATELY.
      // "DIAMETER AND REFLUX TIME — Right Leg" is worth SHOWING as "Right Leg":
      // the title repeats what the column names already say, and the LEG is the
      // part a decision turns on. That is a judgement about a card, not about
      // what a caption is, so it is applied AFTER the shared acceptance and is
      // not pushed into the shared module — `note-table-edit.ts` narrows by
      // substring and would be strictly worse for having the title removed.
      //
      // Measured on production 2026-08-23: 0 of 25 caption candidates carry a
      // ` — ` / ` – ` / ` - ` separator, against a control of 94 lines carrying
      // one elsewhere in the corpus. So the two readers return BYTE-IDENTICAL
      // strings on every caption production holds today, and this reduction is
      // currently unexercised. RE-ARMING CONDITION: one template emitting a
      // titled caption, with no code change anywhere.
      const caption = raw ? (raw.split(/\s+[—–-]\s+/).pop() ?? raw).trim() : null;
      return { header: head, caption };
    }
    // A blank line or a heading means we left the table without finding a rule.
    if (!line.trim() || /^\s*#{1,6}\s/.test(line)) return null;
  }
  return null;
}

/**
 * Render a claim for display.
 *
 * A markdown table row becomes prose when its table's header can be found;
 * everything else is returned exactly as it is.
 */
export function claimProse(claimText: string, note: string): string {
  const row = cells(claimText);
  if (!row) return claimText;

  const found = headerFor(note, claimText);
  if (!found || found.header.length !== row.length) return claimText;
  const { header, caption } = found;

  const [rowLabel, ...values] = row;
  const parts: string[] = [];
  values.forEach((value, i) => {
    if (isBlank(value)) return; // not documented — say nothing rather than "—"
    const { label, unit } = readHeading(header[i + 1] ?? '');
    // Do not append a unit the cell already carries: "6.2 mm" must not become
    // "6.2 mm mm".
    //
    // A PLAIN STRING COMPARE, never a constructed RegExp. `unit` is whatever is
    // in the doctor's own column header — parse-note-to-template copies columns
    // VERBATIM — so `REFLUX (+/-)` yielded `new RegExp('+/-\\s*$')` and threw
    // "Nothing to repeat". claimProse runs inside the render of every
    // suggestion card, so that SyntaxError took the whole review surface down
    // for the one doctor whose form used a presence/absence column. `(*)`,
    // `(?)` and `([x])` are the same bug. Escaping would also work; not
    // building a pattern out of user text is better.
    const needsUnit =
      unit && !value.trimEnd().toLowerCase().endsWith(unit.toLowerCase());
    parts.push(label ? `${label} ${value}${needsUnit ? ` ${unit}` : ''}` : value);
  });

  const subject = caption ? `${caption} — ${rowLabel}` : rowLabel;
  if (parts.length === 0) {
    // Every measurement was blank: the row asserts nothing.
    return `${subject}: nothing documented`;
  }
  return `${subject}: ${parts.join(', ')}`;
}
