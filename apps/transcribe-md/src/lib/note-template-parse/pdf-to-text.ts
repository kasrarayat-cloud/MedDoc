// ============================================================================
// Note-format customization: .pdf → text (unpdf, server-external helper)
// ----------------------------------------------------------------------------
// unpdf is imported STATICALLY here and added to serverExternalPackages in
// next.config. THE #275 MAMMOTH LESSON + THE 2026-06-04 INCIDENT: a node-only
// parse lib must be externalized (so webpack doesn't try to bundle pdfjs) AND
// then be present in the standalone's node_modules at runtime. unpdf (an ESM
// dual-package wrapping pdfjs) is NOT copied there by node-file-trace — it
// silently missed (MODULE_NOT_FOUND in the shipped image → .pdf advertised-but-
// failed). unpdf works fine once present and is self-contained (zero deps,
// vendored pdfjs), so the Dockerfile copies its single dir into the runner
// EXPLICITLY, and a build-time bundle-assert FAILS THE BUILD if it's ever
// absent. extract-note-text.ts dynamically imports THIS local module, so unpdf
// loads lazily (only for an actual .pdf).
//
// (We tried pdf-parse — it traces cleanly but its 2018 vendored pdfjs hangs on
// Node 22, failing extraction; unpdf extracts reliably. So: unpdf + explicit
// COPY, not a library swap.)
//
// unpdf extracts a clean text layer. Image-only / scanned PDFs have no text
// layer → it returns empty (caller maps that to a paste fallback, never an OCR
// attempt). Encrypted / malformed PDFs throw → caller falls back.
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
