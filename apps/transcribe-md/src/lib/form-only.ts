// ============================================================================
// Form-only export helpers (feat/form-only-export).
// ----------------------------------------------------------------------------
// When a template's `formOnlyExport` is ON, the styled DOCX/PDF must render
// EXACTLY the doctor's form — no QuillMD chrome, no appended coding/summary
// blocks, no QuillMD signed line. These pure helpers back that mode:
//   - renumberFormSections: turn multi-sentence findings/recommendations PROSE
//     into a numbered list (matching the practice's real note style), so the
//     generators' existing `\d+.`-markdown rendering emits a proper Word/PDF list.
//   - formSignatureLines: the form's own "Electronically Signed – <name> <date>"
//     block (with DD:/DT: lines when the form has them, captured at certify).
// Deterministic; no AI. Applied ONLY in form-only mode (toggle-OFF byte-identical).
// ============================================================================
import { formatVisitDate } from './visit-export';

/** The form's captured signature style (from the PDF footer at certify). The
 *  "Electronically Signed – …" line is the standard form signature (always
 *  rendered — every clinical export carries a signature attestation); these
 *  flags add the form's own DD:/DT: date lines when it has them. */
export interface FormSignatureStyle {
  /** The form has a "DD:" (dictation date) line. */
  dd?: boolean;
  /** The form has a "DT:" (transcription date) line. */
  dt?: boolean;
}

/** Sections that conventionally enumerate (findings / recommendations / plan /
 *  impression). Only these are renumbered — narrative sections stay prose. */
const ENUMERABLE_SECTION_RE = /\b(findings?|recommendations?|impression|plan)\b/i;
// Note headings are emitted as `## {label}` (build-soap-prompt / build-ultrasound-
// prompt); the generators detect a section with `/^##\s+/`. Match the SAME level
// so renumber's notion of a "section" agrees with the generators (a bilateral
// `### Right`/`### Left` sub-block is not a section boundary).
const SECTION_HEADING_RE = /^##\s+(.+?)\s*$/;
const ANY_SECTION_HEADING_RE = /^##\s+/;

/**
 * Rewrite enumerable sections whose body is multi-sentence PROSE (no existing
 * list markers) into numbered markdown, so the generators render a real numbered
 * list. Splits ONLY on a period followed by 2+ spaces (the note-gen's sentence
 * delimiter) or a blank line — never inside a decimal/measurement ("8.5 mm" has
 * no double space). Sections already carrying 1./2. or bullets, single-item
 * sections, and set-aside placeholders are left untouched. Pure + deterministic.
 */
export function renumberFormSections(soap: string): string {
  const lines = soap.split('\n');
  const out: string[] = [];
  let i = 0;
  while (i < lines.length) {
    const h = lines[i].match(SECTION_HEADING_RE);
    if (!h || !ENUMERABLE_SECTION_RE.test(h[1])) {
      out.push(lines[i]);
      i++;
      continue;
    }
    out.push(lines[i]); // the heading
    i++;
    const body: string[] = [];
    while (i < lines.length && !ANY_SECTION_HEADING_RE.test(lines[i])) {
      body.push(lines[i]);
      i++;
    }
    out.push(...renumberBody(body));
  }
  return out.join('\n');
}

function renumberBody(bodyLines: string[]): string[] {
  const trimmed = bodyLines.join('\n').trim();
  if (!trimmed) return bodyLines; // empty section — leave (rendered as blank)
  // Already a list, a set-aside placeholder, or STRUCTURED content (a markdown
  // table, or `### Right`/`### Left` sub-blocks — e.g. a bilateral imaging study)
  // → leave untouched; renumber only clean prose.
  if (/^\s*(\d+\.|[-*])\s/m.test(trimmed)) return bodyLines;
  if (/set aside|not documented/i.test(trimmed)) return bodyLines;
  if (/^\s*\|/m.test(trimmed) || /^#{3,}\s/m.test(trimmed)) return bodyLines;
  // Sentence split: period + 2+ spaces (the note-gen delimiter) OR a blank line
  // OR a single newline separating items.
  const parts = trimmed
    .split(/(?<=[.;])\s{2,}|\n+/)
    .map((s) => s.replace(/\s+/g, ' ').trim())
    .filter(Boolean);
  if (parts.length < 2) return bodyLines; // single item → not a list
  return ['', ...parts.map((p, n) => `${n + 1}. ${p}`)];
}

/**
 * The form's own signature block. Signed → "Electronically Signed – <name>
 * <date>" (+ DD:/DT: <date> when the form has them). Unsigned → the blank form
 * stubs ("Electronically Signed –", "DD:", "DT:"). Returns the lines in order.
 */
export function formSignatureLines(
  name: string | null,
  signedAt: Date | null,
  sig?: FormSignatureStyle | null
): string[] {
  const who = (name ?? '').trim();
  const when = signedAt ? formatVisitDate(signedAt) : '';
  const lines: string[] = [];
  lines.push(
    signedAt
      ? `Electronically Signed – ${who}${who ? '   ' : ''}${when}`.trim()
      : 'Electronically Signed –'
  );
  if (sig?.dd) lines.push(signedAt ? `DD: ${when}` : 'DD:');
  if (sig?.dt) lines.push(signedAt ? `DT: ${when}` : 'DT:');
  return lines;
}

/** Coerce a stored styleProfile.formSignature into the typed shape (or null). */
export function coerceFormSignature(raw: unknown): FormSignatureStyle | null {
  if (!raw || typeof raw !== 'object') return null;
  const o = raw as Record<string, unknown>;
  const s: FormSignatureStyle = { dd: o.dd === true, dt: o.dt === true };
  return s.dd || s.dt ? s : null;
}
