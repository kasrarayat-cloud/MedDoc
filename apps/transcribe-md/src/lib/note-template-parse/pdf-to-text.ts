// ============================================================================
// Note-format customization: .pdf → text (webpack-bundled helper)
// ----------------------------------------------------------------------------
// unpdf is imported STATICALLY here so Next/webpack bundles it (and add it to
// serverExternalPackages in next.config — the #275 mammoth lesson: a bare
// dynamic import of the package is NOT traced into the standalone build and the
// format silently degrades to paste in prod). extract-note-text.ts dynamically
// imports THIS local module, so unpdf loads lazily (only for an actual .pdf).
//
// unpdf is a serverless-oriented wrapper over pdfjs (pure JS, no native deps,
// no worker file) — it extracts a clean text layer. Image-only / scanned PDFs
// have no text layer → it returns empty (caller maps that to a paste fallback,
// never an OCR attempt). Encrypted / malformed PDFs throw → caller falls back.
// ============================================================================

import { extractText, getDocumentProxy } from 'unpdf';

/** Page ceiling — a clinical note is a handful of pages; this bounds extraction
 *  work so a pathologically large PDF can't DoS the request. Final SIZE
 *  enforcement is downstream: parseNoteTemplateAction rejects text over
 *  MAX_NOTE_CHARS (50k) before any AI cost, so a page-bounded-but-text-dense
 *  PDF is still capped there — the two bounds guard different stages. */
export const MAX_PDF_PAGES = 50;

/** Wall-clock ceiling per parse step so a malformed-but-non-throwing PDF that
 *  makes pdfjs spin can't HANG the request thread — it times out into the
 *  caller's graceful paste fallback. */
const PDF_STEP_TIMEOUT_MS = 20_000;

/** Thrown when a PDF exceeds {@link MAX_PDF_PAGES}; caller surfaces a clear
 *  "too long" message rather than the generic unreadable fallback. */
export class PdfTooLongError extends Error {
  readonly code = 'PDF_TOO_LONG';
  constructor(public readonly pages: number) {
    super(`PDF has ${pages} pages (max ${MAX_PDF_PAGES})`);
    this.name = 'PdfTooLongError';
  }
}

function withTimeout<T>(p: Promise<T>, ms: number): Promise<T> {
  let timer: ReturnType<typeof setTimeout>;
  const timeout = new Promise<never>((_, reject) => {
    timer = setTimeout(
      () => reject(Object.assign(new Error('PDF extraction timed out'), { code: 'PDF_TIMEOUT' })),
      ms,
    );
  });
  return Promise.race([p, timeout]).finally(() => clearTimeout(timer));
}

/** Extract the text layer from a PDF's bytes. Server-only. Never persists.
 *  Throws PdfTooLongError when over the page bound; throws on encrypted /
 *  malformed / timed-out input (caller catches → paste fallback). The page
 *  count is checked BEFORE extractText walks page content, so the bound
 *  actually limits work. */
export async function pdfToText(
  bytes: Uint8Array,
  maxPages: number = MAX_PDF_PAGES
): Promise<string> {
  const pdf = await withTimeout(getDocumentProxy(bytes), PDF_STEP_TIMEOUT_MS);
  if (pdf.numPages > maxPages) throw new PdfTooLongError(pdf.numPages);
  const { text } = await withTimeout(extractText(pdf, { mergePages: true }), PDF_STEP_TIMEOUT_MS);
  return text;
}
