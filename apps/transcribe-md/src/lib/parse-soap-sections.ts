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
  /** ⚠️ ADDITIVE, 2026-09-04 — `body: ''` CANNOT TELL "the doctor wrote a
   *  Plan heading and left it blank" from "there is no Plan heading at all",
   *  and the two must be spoken differently: the export prints
   *  "Not documented." only under a heading that EXISTS, so announcing it for
   *  an absent one asserts something the signed record does not.
   *
   *  Every existing consumer ignores this field, which is why it is a new
   *  field rather than a change to `body`. `parseSoapSections` feeds the E/M
   *  scorers (`em-coding/score.ts`, `em-coding/deterministic.ts`), the SOAP
   *  editor and the status route — changing an existing output would move
   *  clinical scoring, and nothing here is worth that. */
  present: boolean;
}

/** What `parseSoapSections` found, plus the text it has always discarded. */
export interface SoapSplit {
  sections: SoapSection[];
  /** ⚠️ CONTENT ABOVE THE FIRST SOAP HEADING, which `parseSoapSections` drops
   *  and has always dropped — its own docstring says so. That is correct for
   *  the four-pane display it was written for, and WRONG for any consumer
   *  claiming to reproduce the note: an addendum carrying an allergy, written
   *  above the first heading, reaches the drawn document and not the listener.
   *
   *  This file already applies the opposite principle to the TAIL — trailing
   *  text is appended to Plan "so doctor-added freeform notes don't disappear
   *  silently". The head simply never got the same treatment. */
  preamble: string;
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
  const seen: Record<SoapSectionKey, boolean> = { S: false, O: false, A: false, P: false };
  const pre: string[] = [];
  if (!markdown || markdown.trim() === '') {
    return ORDER.map((o) => ({
      key: o.key,
      letter: o.key,
      label: o.label,
      body: '',
      present: false,
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
        seen[found.key] = true;
        continue;
      }
    }
    if (current !== null) {
      sections[current] = sections[current] + (sections[current] ? '\n' : '') + raw;
    } else {
      // Before the first recognised heading. Kept rather than discarded — see
      // `SoapSplit.preamble`. The four-section return below is UNCHANGED, so
      // no existing consumer sees any difference.
      pre.push(raw);
    }
  }
  return ORDER.map((o) => ({
    key: o.key,
    letter: o.key,
    label: o.label,
    body: (sections[o.key] || '').replace(/\s+$/, ''),
    present: seen[o.key],
  }));
}

/** `parseSoapSections`, plus the preamble it discards.
 *
 *  A separate entry point rather than a changed return type, so the FIVE
 *  existing call sites — the two E/M scorers, the SOAP editor, the status route
 *  and `parseNoteSections` — keep the exact array they have always received.
 *
 *  ⚠️ The count read "twelve" until the adversarial pass checked it: measured,
 *  it is five. A number nobody verified, overstating the blast radius this
 *  design avoids, is the kind of detail that gets cited later as if it were
 *  measured. */
export function parseSoapSplit(markdown: string): SoapSplit {
  const sections = parseSoapSections(markdown);
  if (!markdown || markdown.trim() === '') return { sections, preamble: '' };
  const lines = markdown.split('\n');
  const out: string[] = [];
  for (const raw of lines) {
    const m = /^\s{0,3}#{1,3}\s+(.+?)\s*$/.exec(raw);
    if (m) {
      const heading = m[1].toLowerCase().replace(/[^a-z]/g, '');
      if (ORDER.some((o) => o.alts.includes(heading))) break;
    }
    out.push(raw);
  }
  return { sections, preamble: out.join('\n').replace(/\s+$/, '') };
}
