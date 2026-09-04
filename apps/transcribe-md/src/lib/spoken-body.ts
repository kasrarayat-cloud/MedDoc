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

      // ⚠️ THE HEADER IS DROPPED ONLY WHEN ITS RESTORATION ACTUALLY HAPPENED.
      // The old rule deleted it unconditionally, justified by "every data row
      // already carries its own column names". That is true only while
      // `claimProse` can rewrite the rows — and it cannot when two rows of the
      // same section share their text, because `headerFor` requires a UNIQUE
      // hit. A bilateral study whose legs carry identical rows then reached a
      // listener as `| GSV at the Knee | 6.2 | 1.8 |`: numbers with no column,
      // no unit, and raw pipes, while the drawn document showed the full
      // header. The claim was checkable and was not checked.
      //
      // So: look ahead at this table's own rows. If every one of them comes
      // back from `claimProse` without pipes, the columns did survive inside
      // the sentences and the header is redundant — drop it, as before. If any
      // row still carries markup, the header is the only thing naming those
      // numbers, and it is spoken instead of deleted.
      const body: string[] = [];
      for (let k = i + 2; k < lines.length && ROW_RE.test(lines[k]); k++) body.push(lines[k]);
      const allRewritten =
        body.length > 0 && body.every((r) => !claimProse(r.trim(), note).includes('|'));
      if (allRewritten) return null;
      const cols = l
        .split('|')
        .map((c) => c.trim())
        .filter(Boolean);
      return cols.length ? `Columns: ${cols.join(', ')}.` : null;
    })
    .filter((l): l is string => l !== null)
    .join('\n')
    .trim();

  // An otherwise-empty section reads the same way the drawn page does.
  return spoken || EXPORT_EMPTY_SECTION_TEXT;
}
