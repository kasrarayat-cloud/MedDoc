// ============================================================================
// The note, for a screen reader.
// ----------------------------------------------------------------------------
// The document is drawn to a canvas, so the DOM copy of the note IS the reading
// order a screen reader uses. Every artifact the sighted surface kills has to
// die here too, or the accessible path becomes the one that still shows markup
// — the worse failure, because nobody looks at it to notice.
//
// Presentation only. The stored note is never touched, exactly as the export
// sanitiser treats it.
//
// Lives in lib/ rather than beside the component so it can be tested as the
// pure function it is: importing the view pulls in next-auth and the whole
// client tree, which no unit runner should have to stand up to check a string.
// ============================================================================

import { claimProse } from '@/lib/claim-prose';
import { parseMarkdownRow, MARKDOWN_RULE_ROW_RE } from '@/lib/markdown-row';
import { EMPTY_SECTION_PLACEHOLDER } from '@/lib/soap-format';
import { EXPORT_EMPTY_SECTION_TEXT } from '@/lib/visit-export';

/** `| --- | :--- |` — a table's alignment rule, never content. */
const RULE_RE = /^\s*\|[\s:|-]+\|\s*$/;
/** Any `| … | … |` line. */
const ROW_RE = /^\s*\|.*\|\s*$/;

export function spokenBody(body: string, note: string): string {
  const lines = body
    .split('\n')
    // SUBSTITUTE, do not drop. Filtering the marker left the section silent
    // for a listener while a sighted doctor read "Not documented." — removing
    // the only signal that AI-drafted content is waiting on their review.
    .map((l) =>
      l.trim() === EMPTY_SECTION_PLACEHOLDER
        ? 'Set aside for your review — see the suggestions below.'
        : l,
    );

  const spoken = lines
    // Drop the alignment rule AND the HEADER ROW above it.
    //
    // The header is the one line claimProse structurally cannot rewrite: it
    // rewrites a row by reading that table's header, and a header has no header
    // of its own, so it came back verbatim and reached a listener as
    // `| Segment | DIAMETER (mm) | REFLUX TIME (seconds) |` — the last raw
    // markup on this surface, sitting in the middle of a section that had
    // otherwise been turned into sentences. Dropping it loses nothing: every
    // data row already carries its own column names ("diameter 6.2 mm").
    .map((l, i) => {
      // The alignment rule is never content.
      if (RULE_RE.test(l)) return null;
      const isHeader = ROW_RE.test(l) && RULE_RE.test(lines[i + 1] ?? '');
      if (!isHeader) return claimProse(l.trim(), note);

      // ⚠️ THE HEADER IS DROPPED ONLY WHEN ITS RESTORATION ACTUALLY HAPPENED,
      // AND NAMED ONLY WHEN THE NAMES CAN BE TRUSTED.
      //
      // The old rule deleted it unconditionally, justified by "every data row
      // already carries its own column names". That holds only while
      // `claimProse` can rewrite the rows — and it cannot when two rows of the
      // same section share their text, because `headerFor` requires a UNIQUE
      // hit. A bilateral study whose legs carry identical rows then reached a
      // listener as `| GSV at the Knee | 6.2 | 1.8 |`: numbers with no column,
      // no unit, and raw pipes.
      //
      // ⚠️ AND THE FIRST VERSION OF THIS FIX SPOKE A COLUMN LIST THAT DID NOT
      // MATCH THE ROW — the adversarial pass proved it on the shipped
      // generator's own header. `build-soap-prompt.ts:411-416` deliberately
      // emits an UNNAMED leading cell (`|  | DIAMETER (mm) | REFLUX TIME (ms) |`)
      // whenever the template's first column is a data column, which is the real
      // customer form. Compacting that away with `split('|').filter(Boolean)`
      // announced TWO names over a THREE-value row, so a listener pairing them
      // left-to-right hears a 6.2 mm diameter as a 6.2 ms reflux time and the
      // real value falls off the end unnamed.
      //
      // ⚠️ A PARTIAL MAPPING IS WORSE THAN NONE, and this repository already
      // says so twice: `claim-prose.ts:60-64` refuses a partial pairing because
      // it "reads as authoritative", and `:123` refuses when header and row
      // lengths disagree. This block was the only reader emitting a partial
      // mapping for a shape everything else declines to map.
      //
      // So: read the header AND the rows through the SHARED `parseMarkdownRow`
      // — not a sixth hand-rolled splitter — keep cell POSITIONS rather than
      // compacting, and speak the list only when every collected row has the
      // same cell count as the header. Otherwise say nothing about columns.
      const header = parseMarkdownRow(l);
      if (!header) return claimProse(l.trim(), note);

      // ⚠️ COLLECT WITH THE TOLERANT READER, NOT spoken-body's STRICT ROW_RE.
      // `claimProse` reads rows through `parseMarkdownRow`, which accepts a
      // trailing annotation (`| … | [S1: "small saphenous"]`) that the strict
      // `/^\s*\|.*\|\s*$/` rejects. Terminating the scan on the first strict
      // miss decided `allRewritten` over a PREFIX of the table and dropped the
      // header while a row further down still spoke as raw pipes — and the
      // truncation is unidirectional toward that harm, because a shorter list
      // makes `every()` more likely true. `markdown-row.ts:13-25` records those
      // annotation forms as OBSERVED FROM L4.
      const body: string[] = [];
      for (let k = i + 2; k < lines.length; k++) {
        if (MARKDOWN_RULE_ROW_RE.test(lines[k])) continue;
        if (parseMarkdownRow(lines[k]) === null) break;
        body.push(lines[k]);
      }
      const allRewritten =
        body.length > 0 && body.every((r) => !claimProse(r.trim(), note).includes('|'));
      if (allRewritten) return null;

      // Every row must agree with the header on width, or the names cannot be
      // aligned to the values and naming them would be a guess.
      //
      // ⚠️ THE SAME `[].every()` SHAPE APPEARS TWICE HERE WITH OPPOSITE CORRECT
      // ANSWERS, which is why the two guards differ deliberately.
      //   · `allRewritten` above needs `body.length > 0`: with no rows, "every
      //     row was rewritten" is vacuously TRUE and would drop a header that
      //     nothing replaced.
      //   · `widthsAgree` here does NOT: with no rows there is nothing the names
      //     can be misaligned AGAINST, so the header is the section's only
      //     content and naming it is both safe and the whole of what there is.
      //
      // Guarding this one the same way was my first version, and the arm below
      // caught it: a header-and-rule-only table dropped everything, the section
      // emptied, and `spokenBody`'s fallback announced "Not documented." over a
      // note that documents a table.
      const widthsAgree = body.every(
        (r) => (parseMarkdownRow(r)?.cells.length ?? -1) === header.cells.length,
      );
      if (!widthsAgree) return null;

      // A header of nothing but blanks names nothing — say nothing rather than
      // fall through to an empty `Columns:` line.
      const named = header.cells.filter((c) => c.length > 0);
      if (named.length === 0) return null;

      // POSITIONS PRESERVED: an intentionally blank column is spoken as such, so
      // the list and the row stay in step instead of silently shifting left.
      const spokenCols = header.cells.map((c) => (c.length ? c : '(unnamed)'));
      return `Columns: ${spokenCols.join(', ')}.`;
    })
    .filter((l): l is string => l !== null)
    .join('\n')
    .trim();

  // An otherwise-empty section reads the same way the drawn page does.
  return spoken || EXPORT_EMPTY_SECTION_TEXT;
}
