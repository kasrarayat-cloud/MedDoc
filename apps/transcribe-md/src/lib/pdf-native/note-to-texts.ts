// ============================================================================
// Map a visit's note + template → the { anchorKey → text } fill map for the PDF
// native fill engine (feat/pdf-native-fill). Deterministic; no AI.
//   - sections: split the note markdown by its `## <label>` headings, matched to
//     the template's section labels; the body under each heading is the answer.
//   - header fields: values via the GOAL-8 deterministic rules
//     (resolveHeaderFields) — NAME/DATE from the visit record, SURGEON from the
//     note, DOB/ID blank unless dictated.
// A key with no content is simply omitted → the engine leaves that region blank.
// ============================================================================
import type { NoteTemplateHeaderField } from '@/worker/note-templates/system-default-template';
import { resolveHeaderFields } from '@/lib/visit-export';
import { EMPTY_SECTION_PLACEHOLDER } from '@/lib/soap-format';

const norm = (s: string): string => s.toLowerCase().replace(/\s+/g, ' ').replace(/[:*_]+$/g, '').trim();

interface Heading {
  /** Normalized heading key (for matching to section/header labels). */
  key: string;
  /** The heading text as written in the note (for an addendum-page title). */
  label: string;
  body: string;
}

/** Split note markdown into an ORDERED LIST of headings. A LIST, not a Map, so two
 *  headings that normalize to the same key (e.g. a signed note with two
 *  `## Impression` sections, or `## IMPRESSION` + `## Impression`) BOTH survive —
 *  a Map would drop the first body (last-write-wins) and silently lose real,
 *  physician-authored content. Same-key bodies are later concatenated into their
 *  section (or each becomes its own addendum), never dropped. */
function splitByHeadings(noteText: string): Heading[] {
  const out: Heading[] = [];
  const lines = noteText.split('\n');
  let current: { key: string; label: string } | null = null;
  let buf: string[] = [];
  const flush = () => {
    if (current) out.push({ key: current.key, label: current.label, body: buf.join('\n').trim() });
    buf = [];
  };
  for (const line of lines) {
    const m = line.match(/^#{1,6}\s+(.+?)\s*$/);
    if (m) {
      flush();
      current = { key: norm(m[1]), label: m[1].replace(/[:*_]+$/g, '').trim() };
    } else if (current) {
      buf.push(line);
    }
  }
  flush();
  return out;
}

/** A body that is a set-aside/empty placeholder counts as no content (blank). */
function meaningful(body: string): string {
  const t = body.trim();
  if (!t || t === EMPTY_SECTION_PLACEHOLDER) return '';
  if (/^_?\[.*(set aside|not documented).*\]_?$/i.test(t)) return '';
  // Strip leading markdown bullets/numbering for a cleaner form fill.
  return t
    .split('\n')
    .map((l) => l.replace(/^\s*(?:[-*]|\d+\.)\s+/, '').trim())
    .filter(Boolean)
    .join(' ');
}

export interface BuildFillTextsInput {
  /** The visit note (signedSoap ?? soapFinal), already export-sanitized. */
  noteText: string;
  /** Template section {key,label} in order. */
  sections: ReadonlyArray<{ key: string; label: string }>;
  /** Template header fields (labels only). */
  headerFields: ReadonlyArray<NoteTemplateHeaderField>;
  /** Header-fill context (GOAL-8). */
  headerCtx: { patientName: string | null; visitDate: Date; soapText: string };
}

export interface BuildFillTextsOutput {
  /** anchorKey → text to draw into the form's blank region. */
  texts: Record<string, string>;
  /** Note sections with real content that match NO form label — carried to a
   *  labeled "Additional documentation" continuation page (never dropped, never
   *  drawn over the doctor's ink). */
  addenda: Array<{ label: string; text: string }>;
}

/** Build the anchorKey → text map + the unmatched-section addenda. */
export function buildPdfFillTexts(input: BuildFillTextsInput): BuildFillTextsOutput {
  const texts: Record<string, string> = {};

  const headings = splitByHeadings(input.noteText);
  const sectionKeys = new Set(input.sections.map((s) => norm(s.label)));

  // Section fill: CONCATENATE every note heading that matches this section's
  // label (duplicates/case-variants included) so no body is ever dropped; the
  // engine wraps + overflows the combined text.
  for (const s of input.sections) {
    const nl = norm(s.label);
    const bodies = headings
      .filter((h) => h.key === nl)
      .map((h) => meaningful(h.body))
      .filter(Boolean);
    if (bodies.length) texts[s.key] = bodies.join('\n\n');
  }

  // Header values keyed by the field key (resolveHeaderFields preserves the
  // sorted-by-order sequence, so index-align it back to the keys). Track which
  // header LABELS actually produced a value — only those suppress an addendum
  // (a header field that yields no value must not silently swallow a note section
  // that happens to share its label).
  const sorted = [...input.headerFields].sort((a, b) => a.order - b.order);
  const rendered = resolveHeaderFields(sorted, input.headerCtx);
  const filledHeaderKeys = new Set<string>();
  sorted.forEach((f, i) => {
    const v = rendered[i]?.value?.trim();
    if (v) {
      texts[f.key] = v;
      filledHeaderKeys.add(norm(f.label));
    }
  });

  // Addenda: every note heading NOT consumed by a section and NOT naming a filled
  // header field, with real content — each occurrence preserved (never dropped).
  const addenda: Array<{ label: string; text: string }> = [];
  for (const h of headings) {
    if (sectionKeys.has(h.key) || filledHeaderKeys.has(h.key)) continue;
    const text = meaningful(h.body);
    if (text) addenda.push({ label: h.label, text });
  }

  return { texts, addenda };
}
