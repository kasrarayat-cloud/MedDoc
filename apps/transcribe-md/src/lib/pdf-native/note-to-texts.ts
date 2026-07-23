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

/** Split note markdown into { normalizedHeading → body }. */
function splitByHeadings(noteText: string): Map<string, string> {
  const out = new Map<string, string>();
  const lines = noteText.split('\n');
  let current: string | null = null;
  let buf: string[] = [];
  const flush = () => {
    if (current) out.set(current, buf.join('\n').trim());
    buf = [];
  };
  for (const line of lines) {
    const m = line.match(/^#{1,6}\s+(.+?)\s*$/);
    if (m) {
      flush();
      current = norm(m[1]);
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

/** Build the anchorKey → text map. */
export function buildPdfFillTexts(input: BuildFillTextsInput): Record<string, string> {
  const texts: Record<string, string> = {};

  const headings = splitByHeadings(input.noteText);
  for (const s of input.sections) {
    const body = headings.get(norm(s.label));
    const text = body ? meaningful(body) : '';
    if (text) texts[s.key] = text;
  }

  // Header values keyed by the field key (resolveHeaderFields preserves the
  // sorted-by-order sequence, so index-align it back to the keys).
  const sorted = [...input.headerFields].sort((a, b) => a.order - b.order);
  const rendered = resolveHeaderFields(sorted, input.headerCtx);
  sorted.forEach((f, i) => {
    const v = rendered[i]?.value?.trim();
    if (v) texts[f.key] = v;
  });

  return texts;
}
