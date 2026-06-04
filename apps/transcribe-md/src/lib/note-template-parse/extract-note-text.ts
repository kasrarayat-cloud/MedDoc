// ============================================================================
// Note-format customization — Phase 2b: file → note text extraction
// ----------------------------------------------------------------------------
// Turns an uploaded note file into clean text for the parse engine. PASTE is
// the guaranteed path; uploads are best-effort with reliable libs only:
//   - .txt / .md → UTF-8 decode (reliable; Markdown is just text)
//   - .docx → mammoth raw-text extraction (via ./docx-to-text, bundled lazily)
//   - .pdf  → unpdf text-layer extraction (via ./pdf-to-text, bundled lazily);
//             image-only/scanned PDFs (no text layer) + encrypted/malformed
//             PDFs fall back to paste with a clear message — never OCR, never
//             a crash. A page bound guards against DoS.
//   - anything else (.rtf, images, …) → paste fallback. We don't ship flaky
//     extraction; if a format can't be read cleanly the doctor pastes.
//
// SAFETY: extraction only produces TEXT. That text flows into the SAME
// validated parse + PHI gate as pasted text — adding input formats does not
// change the safety path. The RAW FILE IS NEVER PERSISTED — the action holds
// the buffer in memory, extracts, and discards it.
//
// `normalizeExtractedText` is PURE + unit-tested — it repairs the artifacts the
// bug-hunt found: mid-sentence line-wrap newlines, unicode punctuation
// (en/em-dash, NBSP, smart quotes), and repeating multi-page header/footer
// bleed.
// ============================================================================

export type SupportedUpload = 'txt' | 'md' | 'docx' | 'pdf';

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

/** Classify an upload by filename + mime. Returns the handler kind or
 *  'unsupported' (routes to paste). */
export function classifyUpload(filename: string, mime: string): SupportedUpload | 'unsupported' {
  const name = (filename || '').toLowerCase();
  const m = (mime || '').toLowerCase();
  if (name.endsWith('.pdf') || m === 'application/pdf') return 'pdf';
  if (
    name.endsWith('.docx') ||
    m === 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
  ) {
    return 'docx';
  }
  if (name.endsWith('.md') || name.endsWith('.markdown') || m === 'text/markdown') return 'md';
  if (name.endsWith('.txt') || m === 'text/plain') return 'txt';
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

  if (kind === 'unsupported') {
    return {
      ok: false,
      fallbackToPaste: true,
      error:
        'Upload a PDF, Word (.docx), text (.txt), or Markdown (.md) file — or paste the note text directly.',
    };
  }

  try {
    let rawText: string;
    if (kind === 'txt' || kind === 'md') {
      // Plain text / Markdown — decode as UTF-8 (Markdown is read as-is; the
      // parse engine treats the prose like any pasted note).
      rawText = new TextDecoder('utf-8', { fatal: false }).decode(bytes);
    } else if (kind === 'docx') {
      // Lazy local helpers with STATIC lib imports → webpack bundles the lib
      // (a bare dynamic import of the package is not traced into standalone —
      // the #275 mammoth lesson). Lazy so .txt/.md/paste never load them.
      const { docxToText } = await import('./docx-to-text');
      rawText = await docxToText(bytes);
    } else {
      const { pdfToText } = await import('./pdf-to-text');
      rawText = await pdfToText(bytes);
    }
    const text = normalizeExtractedText(rawText);
    if (text.trim().length === 0) {
      return {
        ok: false,
        fallbackToPaste: true,
        error:
          kind === 'pdf'
            ? "We couldn't find any text in that PDF — it may be a scan or image. Paste the note text instead."
            : 'That file looked empty once read. Paste the note text instead.',
      };
    }
    return { ok: true, text, kind };
  } catch (err) {
    // Page-bound exceeded → a specific, actionable message.
    if (err && typeof err === 'object' && (err as { code?: string }).code === 'PDF_TOO_LONG') {
      const pages = (err as { pages?: number }).pages;
      return {
        ok: false,
        fallbackToPaste: true,
        error: `That PDF is long (${pages ?? 'many'} pages). Upload a single note, or paste the text.`,
      };
    }
    // Encrypted / malformed / unreadable → graceful paste fallback, never a crash.
    return {
      ok: false,
      fallbackToPaste: true,
      error:
        kind === 'pdf'
          ? "We couldn't read that PDF — it may be encrypted or damaged. Paste the note text instead."
          : "We couldn't read that file. Paste the note text instead.",
    };
  }
}
