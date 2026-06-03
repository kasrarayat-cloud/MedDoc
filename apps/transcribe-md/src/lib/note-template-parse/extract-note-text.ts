// ============================================================================
// Note-format customization — Phase 2b: file → note text extraction
// ----------------------------------------------------------------------------
// Turns an uploaded note file into clean text for the parse engine. PASTE is
// the guaranteed path; uploads are best-effort with reliable libs only:
//   - .txt  → UTF-8 decode (reliable)
//   - .docx → mammoth raw-text extraction (reliable; dynamically imported)
//   - .pdf  → DEFERRED to paste. Server-side PDF text extraction is
//             unreliable for clinical notes (column collapse, OCR gaps — see
//             the bug-hunt). Rather than ship flaky extraction we ask the
//             doctor to paste. No PDF lib is bundled.
//
// `normalizeExtractedText` is PURE + unit-tested — it repairs the artifacts the
// bug-hunt found: mid-sentence line-wrap newlines, unicode punctuation
// (en/em-dash, NBSP, smart quotes), and repeating multi-page header/footer
// bleed. The RAW FILE IS NEVER PERSISTED — the action holds the buffer in
// memory, extracts, and discards it.
// ============================================================================

export type SupportedUpload = 'txt' | 'docx';

export interface ExtractOk {
  ok: true;
  text: string;
  kind: SupportedUpload;
}
export interface ExtractFallback {
  ok: false;
  /** True when the right move is "paste the text instead" (unsupported/unreliable
   *  format) rather than a hard error. */
  fallbackToPaste: boolean;
  error: string;
}
export type ExtractResult = ExtractOk | ExtractFallback;

/** Page-furniture lines we strip outright (running headers/footers). */
const PAGE_FURNITURE_RE = [
  /^\s*page\s+\d+(\s+of\s+\d+)?\s*$/i,
  /^\s*\d+\s*\/\s*\d+\s*$/,
  /^\s*-\s*\d+\s*-\s*$/,
];

/** Normalize raw extracted text: unicode punctuation, wrapped-line rejoin, and
 *  repeating header/footer de-bleed. Deterministic + pure. */
export function normalizeExtractedText(raw: string): string {
  if (!raw) return '';

  // 1. Unicode punctuation → ASCII the rest of the pipeline (and the PHI regex)
  //    expects. NFC first so combining marks fold.
  let t = raw.normalize('NFC');
  t = t
    .replace(/﻿/g, '') // BOM
    .replace(/ /g, ' ') // NBSP
    .replace(/[‐‑‒–—−]/g, '-') // hyphen/en/em/minus
    .replace(/[‘’‛]/g, "'") // smart single quotes
    .replace(/[“”]/g, '"') // smart double quotes
    .replace(/…/g, '...') // ellipsis
    .replace(/[·•]/g, '- ') // middot / bullet → list dash
    .replace(/\r\n?/g, '\n'); // CRLF/CR → LF

  // 2. Drop page-furniture lines + de-bleed repeating headers/footers. A short
  //    line that recurs 3+ times verbatim across the doc is almost certainly a
  //    running header/footer (e.g. a clinic name banner), not note content.
  const lines = t.split('\n');
  const freq = new Map<string, number>();
  for (const ln of lines) {
    const k = ln.trim();
    if (k) freq.set(k, (freq.get(k) ?? 0) + 1);
  }
  const kept = lines.filter((ln) => {
    const k = ln.trim();
    if (PAGE_FURNITURE_RE.some((re) => re.test(k))) return false;
    if (k.length > 0 && k.length <= 60 && (freq.get(k) ?? 0) >= 3) return false;
    return true;
  });
  t = kept.join('\n');

  // 3. Rejoin mid-sentence line wraps. A lone newline between a line that ends
  //    mid-clause (lowercase / comma) and a continuation that starts lowercase
  //    is a hard-wrap artifact, not a real break — join with a space. Blank-line
  //    paragraph boundaries and heading-like lines are preserved.
  t = t.replace(/([a-z0-9,;:])\n(?!\n)([a-z])/g, '$1 $2');

  // 4. Collapse runs of blank lines + trailing spaces.
  t = t
    .replace(/[ \t]+\n/g, '\n')
    .replace(/\n{3,}/g, '\n\n')
    .replace(/[ \t]{2,}/g, ' ')
    .trim();

  return t;
}

/** Classify an upload by filename + mime. Returns the handler kind or 'pdf' /
 *  'unsupported' (both route to paste). */
export function classifyUpload(filename: string, mime: string): SupportedUpload | 'pdf' | 'unsupported' {
  const name = (filename || '').toLowerCase();
  const m = (mime || '').toLowerCase();
  if (name.endsWith('.txt') || m === 'text/plain') return 'txt';
  if (
    name.endsWith('.docx') ||
    m === 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
  ) {
    return 'docx';
  }
  if (name.endsWith('.pdf') || m === 'application/pdf') return 'pdf';
  return 'unsupported';
}

/** Extract note text from an uploaded file's bytes. Server-only (mammoth is
 *  dynamically imported). Never writes the bytes anywhere. */
export async function extractNoteTextFromUpload(
  bytes: Uint8Array,
  filename: string,
  mime: string
): Promise<ExtractResult> {
  const kind = classifyUpload(filename, mime);

  if (kind === 'pdf') {
    return {
      ok: false,
      fallbackToPaste: true,
      error:
        "We can't reliably read PDFs — the text often comes out scrambled. Open the PDF, copy the note, and paste it instead.",
    };
  }
  if (kind === 'unsupported') {
    return {
      ok: false,
      fallbackToPaste: true,
      error: 'Upload a .docx or .txt file, or paste the note text directly.',
    };
  }

  try {
    let rawText: string;
    if (kind === 'txt') {
      rawText = new TextDecoder('utf-8', { fatal: false }).decode(bytes);
    } else {
      // .docx — mammoth turns the document XML into plain text. Buffer required.
      const m = await import('mammoth');
      const mammoth = (m.default ?? m) as typeof import('mammoth');
      const result = await mammoth.extractRawText({ buffer: Buffer.from(bytes) });
      rawText = result.value;
    }
    const text = normalizeExtractedText(rawText);
    if (text.trim().length === 0) {
      return {
        ok: false,
        fallbackToPaste: true,
        error: "That file looked empty once read. Paste the note text instead.",
      };
    }
    return { ok: true, text, kind };
  } catch {
    return {
      ok: false,
      fallbackToPaste: true,
      error: "We couldn't read that file. Paste the note text instead.",
    };
  }
}
