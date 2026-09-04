// ============================================================================
// spokenSections — the note as a screen reader should hear it
// ----------------------------------------------------------------------------
// The visit document renders to <canvas> bitmaps, so the DOM copy of the note
// IS the reading order for anyone using assistive technology. That copy was
// built by mapping `parseNoteSections()` and calling `spokenBody()` on each
// section — and the adversarial pass over PR #948 proved that pipeline says
// three things the signed record does not:
//
//   1. CONTENT ABOVE THE FIRST SOAP HEADING WAS DROPPED. `parse-soap-sections`
//      says so in its own docstring. Measured: an "ADDENDUM … ALLERGIC TO
//      PENICILLIN" line above `## Subjective` reached the drawn document and
//      not the listener.
//   2. ABSENT SOAP HEADINGS WERE ANNOUNCED AS "Not documented." The parser
//      returns all four of S/O/A/P unconditionally, so a note carrying only
//      `## Subjective` told a listener the physician documented no assessment
//      and no plan. The export prints those words ONLY under a heading that
//      exists, so the two disagreed.
//   3. TABLE HEADERS WERE DELETED unconditionally — fixed in `spoken-body.ts`.
//
// ⚠️ THIS IS A NEW PROJECTION, NOT A CHANGED PARSER, AND THAT IS DELIBERATE.
// `parseSoapSections` feeds the E/M scorers (`em-coding/score.ts`,
// `em-coding/deterministic.ts`), the SOAP editor and the status route. Changing
// what it returns would move CLINICAL SCORING to fix an accessibility defect,
// which is not a trade worth making. The parser gained two ADDITIVE fields that
// every existing consumer ignores; this file is the only thing that reads them.
//
// ⚠️ AND THE PARITY THAT MUST NOT BREAK: where a heading is PRESENT but empty,
// the export prints "Not documented." and so does this. Suppressing empties
// would fix defect 2 by introducing a new disagreement in the other direction.
// ============================================================================

import { parseSoapSplit } from '@/lib/parse-soap-sections';
import { parseNoteSections, isClassicSoap } from '@/lib/parse-note-sections';
import { spokenBody } from '@/lib/spoken-body';

export interface SpokenSection {
  id: string;
  label: string;
  body: string;
}

/** The label for content that precedes the first SOAP heading. */
export const PREAMBLE_LABEL = 'Before the note';

/**
 * The note, as sections a screen reader should be read.
 *
 * @param note the FROZEN text for a signed visit (`signedSoap ?? soapFinal`),
 *             or `soapFinal` pre-sign. Never an adopted draft on a signed note.
 */
export function spokenSections(note: string): SpokenSection[] {
  const text = note ?? '';
  if (!text.trim()) return [];

  // Non-SOAP notes (custom templates, imaging reports) take the generic
  // splitter, which already keeps a preamble as its own "Note" section and
  // emits only the headings that exist. Nothing to correct there.
  if (!isClassicSoap(text)) {
    return parseNoteSections(text).map((s) => ({
      id: s.id,
      label: s.label,
      body: spokenBody(s.body, text),
    }));
  }

  const { sections, preamble } = parseSoapSplit(text);
  const out: SpokenSection[] = [];

  // 1 · the preamble, first, because that is where it is on the page.
  if (preamble.trim()) {
    out.push({ id: 'preamble', label: PREAMBLE_LABEL, body: spokenBody(preamble, text) });
  }

  // 2 · only the headings the note actually carries. A section that IS present
  //     but empty keeps its "Not documented." — that is what the export says.
  for (const s of sections) {
    if (!s.present) continue;
    out.push({ id: `soap-${s.key}`, label: s.label, body: spokenBody(s.body, text) });
  }

  return out;
}
