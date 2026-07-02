// ============================================================================
// parseNoteSections — DISPLAY-ONLY section splitter for the review screen.
// ----------------------------------------------------------------------------
// Custom note templates (Settings → My Note Format) and the ultrasound
// IMAGING-REPORT template emit `## <label>` headings that are NOT
// Subjective/Objective/Assessment/Plan. The legacy display parser
// (parse-soap-sections.ts) recognises only the four SOAP names, so every
// non-SOAP note rendered as four empty blocks with all content invisible
// in read mode (custom-template QA, 2026-07-02, finding F-1).
//
// This parser renders ANY `#`/`##`/`###` heading as its own section,
// preserving the note's own labels and order. For classic SOAP notes it
// DELEGATES to parseSoapSections so the default-template render stays
// byte-identical (canonical S→O→A→P order, missing-as-empty, preamble
// dropped, trailing text appended to Plan).
//
// DISPLAY ONLY. parse-soap-sections.ts is untouched and remains the
// input for the E/M deterministic counters — do NOT import this module
// from lib/em-coding or any scoring/gate path.
// ============================================================================

import {
  parseSoapSections,
  type SoapSectionKey,
} from '@/lib/parse-soap-sections';

export interface NoteSection {
  /** Stable per-render id (label slug + position — labels may repeat). */
  id: string;
  /** Eyebrow chip: 'S'/'O'/'A'/'P' for canonical sections, else the
   *  1-based section number as a string. */
  letter: string;
  /** Heading text verbatim (canonical label for SOAP sections). */
  label: string;
  /** Markdown body of this section (heading line stripped). */
  body: string;
  /** Canonical SOAP key when the heading is a SOAP name — keeps the
   *  E/M rail pulse-hints + bump-highlight wiring working for classic
   *  notes. null for custom/imaging sections. */
  soapKey: SoapSectionKey | null;
}

const SOAP_ALTS: Record<string, SoapSectionKey> = {
  subjective: 'S',
  s: 'S',
  objective: 'O',
  o: 'O',
  assessment: 'A',
  a: 'A',
  plan: 'P',
  p: 'P',
};

const HEADING_RE = /^\s{0,3}#{1,3}\s+(.+?)\s*$/;

function normHeading(h: string): string {
  return h.toLowerCase().replace(/[^a-z]/g, '');
}

function slug(label: string, i: number): string {
  const s = label.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '');
  return `${s || 'section'}-${i}`;
}

/** True when the note is a classic SOAP note: has at least one heading and
 *  every heading is a canonical SOAP name. Blank notes also count (the
 *  legacy empty-scaffold render). */
function isClassicSoap(markdown: string): boolean {
  if (!markdown || markdown.trim() === '') return true;
  let sawHeading = false;
  for (const raw of markdown.split('\n')) {
    const m = HEADING_RE.exec(raw);
    if (!m) continue;
    sawHeading = true;
    if (!(normHeading(m[1]) in SOAP_ALTS)) return false;
  }
  return sawHeading;
}

/** Split a note into display sections. Classic SOAP notes delegate to
 *  parseSoapSections (byte-identical render); anything else — custom
 *  templates, imaging reports, mixed or heading-less notes — renders
 *  every heading with its own verbatim label so no content is hidden. */
export function parseNoteSections(markdown: string): NoteSection[] {
  if (isClassicSoap(markdown)) {
    return parseSoapSections(markdown).map((s) => ({
      id: `soap-${s.key}`,
      letter: s.key,
      label: s.label,
      body: s.body,
      soapKey: s.key,
    }));
  }

  const out: NoteSection[] = [];
  let label: string | null = null;
  let buf: string[] = [];
  const flush = () => {
    if (label === null) {
      // preamble before the first heading — show it rather than drop it
      const body = buf.join('\n').replace(/\s+$/, '');
      if (body.trim()) out.push({ id: slug('note', out.length), letter: '', label: 'Note', body, soapKey: null });
    } else {
      out.push({
        id: slug(label, out.length),
        letter: '',
        label,
        body: buf.join('\n').replace(/\s+$/, ''),
        soapKey: SOAP_ALTS[normHeading(label)] ?? null,
      });
    }
    buf = [];
  };

  for (const raw of markdown.split('\n')) {
    const m = HEADING_RE.exec(raw);
    if (m) {
      flush();
      label = m[1];
      continue;
    }
    buf.push(raw);
  }
  flush();

  // eyebrow chips: canonical letters where they apply, else section number
  out.forEach((s, i) => {
    s.letter = s.soapKey ?? String(i + 1);
  });
  return out;
}
