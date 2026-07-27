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
    .filter(
      (l, i) => !RULE_RE.test(l) && !(ROW_RE.test(l) && RULE_RE.test(lines[i + 1] ?? '')),
    )
    .map((l) => claimProse(l.trim(), note))
    .join('\n')
    .trim();

  // An otherwise-empty section reads the same way the drawn page does.
  return spoken || EXPORT_EMPTY_SECTION_TEXT;
}
