// ============================================================================
// parseSoapSections — split a SOAP markdown blob into S / O / A / P bodies
// ----------------------------------------------------------------------------
// Phase 5.1 — visit-detail SOAP V3 Split Pane needs the four SOAP sections
// rendered as discrete clickable blocks (left pane), so we split the
// markdown by `## Subjective`, `## Objective`, `## Assessment`, `## Plan`
// headings produced by Layer 4. The schema is plain markdown — no
// structured citations field exists yet, so the right-hand "sources" rail
// falls back to all transcript turns. This file does NOT change the
// underlying contract: the SOAP text remains the single byte-identical
// source of truth (signedSoap / soapFinal). We only parse it for display.
// ============================================================================

export type SoapSectionKey = 'S' | 'O' | 'A' | 'P';

export interface SoapSection {
  key: SoapSectionKey;
  /** Eyebrow letter ("S", "O", …) and full label ("Subjective"). */
  letter: SoapSectionKey;
  label: 'Subjective' | 'Objective' | 'Assessment' | 'Plan';
  /** Markdown body of this section (heading line stripped). Empty
   *  string when the SOAP is missing this section entirely (e.g. an
   *  early draft). */
  body: string;
}

const ORDER: { key: SoapSectionKey; label: SoapSection['label']; alts: string[] }[] = [
  { key: 'S', label: 'Subjective', alts: ['subjective', 's'] },
  { key: 'O', label: 'Objective', alts: ['objective', 'o'] },
  { key: 'A', label: 'Assessment', alts: ['assessment', 'a'] },
  { key: 'P', label: 'Plan', alts: ['plan', 'p'] },
];

/** Splits a SOAP markdown blob into the four SOAP sections in canonical
 *  order. Tolerant of:
 *   - missing sections (returns body: '')
 *   - case variations ("## subjective", "## SUBJECTIVE")
 *   - leading whitespace
 *   - sections appearing out of order in the source (we still emit S→O→A→P)
 *
 *  Anything before the first SOAP heading is dropped. Anything after the
 *  last recognised heading is appended to the Plan body so doctor-added
 *  freeform notes don't disappear silently. */
export function parseSoapSections(markdown: string): SoapSection[] {
  const sections: Record<SoapSectionKey, string> = { S: '', O: '', A: '', P: '' };
  if (!markdown || markdown.trim() === '') {
    return ORDER.map((o) => ({
      key: o.key,
      letter: o.key,
      label: o.label,
      body: '',
    }));
  }
  const lines = markdown.split('\n');
  let current: SoapSectionKey | null = null;
  for (const raw of lines) {
    const m = /^\s{0,3}#{1,3}\s+(.+?)\s*$/.exec(raw);
    if (m) {
      const heading = m[1].toLowerCase().replace(/[^a-z]/g, '');
      const found = ORDER.find((o) => o.alts.includes(heading));
      if (found) {
        current = found.key;
        continue;
      }
    }
    if (current !== null) {
      sections[current] = sections[current] + (sections[current] ? '\n' : '') + raw;
    }
  }
  return ORDER.map((o) => ({
    key: o.key,
    letter: o.key,
    label: o.label,
    body: (sections[o.key] || '').replace(/\s+$/, ''),
  }));
}
