// ============================================================================
// UPLOAD-AND-CERTIFIED · S2 — PDF FORMS → a faithful prose DOCX (then the S1 twin).
// ----------------------------------------------------------------------------
// A doctor uploads a PDF form. A PDF has no `word/document.xml`, so S1's
// `deriveProseTwin` (which inserts controls into an existing DOCX) cannot run on
// it directly. This module is the missing FIRST step: it reads the PDF's text
// layer WITH POSITIONS, reconstructs the form's visible lines in reading order,
// and emits a minimal prose DOCX — one `<w:p>` per line — of exactly the shape
// S1 already consumes. The caller then runs `deriveProseTwin` on these bytes, so
// the SAME derive → compile → propose → certify path produces the twin. This is
// the owner's S2, ruled STRUCTURAL fidelity (ruling S2-1): the twin captures the
// form's labels / blanks / section order and their text, not a pixel-perfect
// reproduction of the PDF's visual layout (the pdf-native canvas path already
// covers exact-look export, and it COEXISTS — ruling S2-3).
//
// ⚠️ SCANNED / IMAGE-ONLY PDFs ARE OUT OF SCOPE, AND FAIL SAFE (ruling S2-2). A
// PDF with no text layer extracts to zero items → this returns null → the caller
// declines cleanly (no twin, a clear message). We never OCR — the codebase never
// has, and OCR'd text on a clinical form is an accuracy/PHI hazard.
//
// ⚠️ FAITHFUL, NOT INVENTED. The reconstruction only re-orders and joins text
// that is ACTUALLY in the PDF's text layer. It never synthesizes a fill blank:
// a label followed by a DRAWN rule line (a vector line, not underscore
// characters) carries no text-layer affordance, so S1 leaves it as prose and the
// doctor adds it at the confirmation step — the same conservative posture S1's
// affordance rule takes for an ambiguous DOCX line. Underscore/dot blanks that
// are real text DO survive and become controls.
// ============================================================================
import JSZip from 'jszip';

/** The minimal pdfjs document-proxy shape unpdf's `getDocumentProxy` returns —
 *  identical to the one `pdf-native/anchors.ts` reads. */
export interface PdfjsProxy {
  numPages: number;
  getPage(n: number): Promise<{
    getViewport(o: { scale: number }): { width: number; height: number };
    getTextContent(): Promise<{
      items: Array<{ str: string; transform: number[]; width: number; height: number }>;
    }>;
  }>;
}

/** One positioned text token, page-local. `y` is the pdfjs baseline (increases
 *  UPWARD), so a line's items share ~one `y` and pages read top-to-bottom as `y`
 *  DESCENDING. */
export interface PlacedItem {
  str: string;
  x: number;
  y: number;
  height: number;
  page: number;
}

/**
 * Is this upload a PDF, by its CONTENT? A ZIP (DOCX) always opens with
 * `PK\x03\x04`, so that is rejected outright; otherwise it is a PDF iff `%PDF-`
 * appears within the first 1KB.
 *
 * ⚠️ THE HEADER IS NOT REQUIRED AT OFFSET 0. pdf.js / unpdf — and every PDF
 * viewer — accept a leading UTF-8 BOM, whitespace, or newline before `%PDF-`,
 * and `extract-note-file` already routes such a file as a PDF by name/mime.
 * Requiring the header at byte 0 misrouted a perfectly readable PDF to the DOCX
 * compiler (a false rejection of exactly the capability S2 adds) — adversarial
 * pass, 2026-09-14. Scanning the first 1KB matches what the PDF reader itself
 * accepts, so create-draft's classifier agrees with extract-note-file's.
 */
export function isPdfSource(bytes: Uint8Array): boolean {
  // A ZIP / DOCX opens with `PK\x03\x04` — never a PDF, whatever follows.
  if (
    bytes.length >= 4 &&
    bytes[0] === 0x50 && bytes[1] === 0x4b && bytes[2] === 0x03 && bytes[3] === 0x04
  ) {
    return false;
  }
  const limit = Math.min(bytes.length - 5, 1024);
  for (let i = 0; i <= limit; i++) {
    if (
      bytes[i] === 0x25 && // %
      bytes[i + 1] === 0x50 && // P
      bytes[i + 2] === 0x44 && // D
      bytes[i + 3] === 0x46 && // F
      bytes[i + 4] === 0x2d //   -
    ) {
      return true;
    }
  }
  return false;
}

/**
 * Reconstruct the form's visible lines, in reading order, from positioned text
 * tokens. PURE (no I/O) so it is exhaustively unit-testable without a real PDF.
 *
 * Order: page ascending, then `y` DESCENDING (top-to-bottom), then `x` ascending
 * (left-to-right). Items whose baselines fall within a height-relative tolerance
 * are one line; the line's `y` anchor is its first (topmost) item and does not
 * drift, so a subscript/superscript does not split the line. Tokens are joined
 * with single spaces and collapsed — enough for S1's label/affordance detection,
 * which tolerates a space before the colon (`\s*:`).
 */
export function reconstructLines(items: PlacedItem[]): string[] {
  const usable = items.filter((it) => it.str && it.str.trim().length > 0);
  if (usable.length === 0) return [];
  const sorted = [...usable].sort(
    (a, b) => a.page - b.page || b.y - a.y || a.x - b.x,
  );
  const lines: string[] = [];
  let cur: PlacedItem[] = [];
  let curPage = sorted[0].page;
  let curY = sorted[0].y;

  const flush = (): void => {
    if (cur.length === 0) return;
    cur.sort((a, b) => a.x - b.x);
    const text = cur.map((i) => i.str).join(' ').replace(/\s+/g, ' ').trim();
    if (text) lines.push(text);
    cur = [];
  };

  for (const it of sorted) {
    const tol = Math.max(2, (it.height || 10) * 0.6);
    if (cur.length > 0 && (it.page !== curPage || Math.abs(it.y - curY) > tol)) {
      flush();
    }
    if (cur.length === 0) {
      curPage = it.page;
      curY = it.y; // anchor the line to its first (topmost, leftmost) item
    }
    cur.push(it);
  }
  flush();
  return lines;
}

/** Read every positioned token across all pages from a pdfjs proxy — mirrors
 *  `pdf-native/anchors.ts` `placedItems`. The `transform` matrix is `[a,b,c,d,e,f]`;
 *  `e`/`f` are the token's x/y, `|d|` its height. */
async function placedItems(proxy: PdfjsProxy): Promise<PlacedItem[]> {
  const items: PlacedItem[] = [];
  for (let p = 1; p <= proxy.numPages; p++) {
    const page = await proxy.getPage(p);
    const content = await page.getTextContent();
    for (const it of content.items) {
      if (!it.str || !it.str.trim()) continue;
      const t = it.transform;
      items.push({
        str: it.str,
        x: t[4],
        y: t[5],
        height: Math.abs(t[3]) || it.height || 10,
        page: p - 1,
      });
    }
  }
  return items;
}

/**
 * Extract the form's prose lines from a pdfjs proxy. Returns null when the PDF
 * carries no text layer (scanned / image-only — ruling S2-2, fail safe). Proxy
 * in (not raw bytes) so the unpdf import stays at the I/O boundary and this is
 * testable with a pdf-lib-built fixture, exactly like `extractPdfAnchors`.
 */
export async function extractProseLinesFromProxy(
  proxy: PdfjsProxy,
): Promise<string[] | null> {
  const lines = reconstructLines(await placedItems(proxy));
  return lines.length > 0 ? lines : null;
}

function xmlText(s: string): string {
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

function para(text: string): string {
  return `<w:p><w:r><w:t xml:space="preserve">${xmlText(text)}</w:t></w:r></w:p>`;
}

const CONTENT_TYPES_XML =
  `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>` +
  `<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">` +
  `<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>` +
  `<Default Extension="xml" ContentType="application/xml"/>` +
  `<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>` +
  `</Types>`;

const RELS_XML =
  `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>` +
  `<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">` +
  `<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>` +
  `</Relationships>`;

/** Build the reconstructed `word/document.xml` — one paragraph per line, no
 *  controls (S1 inserts those). Exposed for the byte-preservation / furniture
 *  proofs. */
export function linesToDocumentXml(lines: string[]): string {
  return (
    `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>` +
    `<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>` +
    lines.map(para).join('') +
    `<w:sectPr><w:pgSz w:w="12240" w:h="15840"/></w:sectPr>` +
    `</w:body></w:document>`
  );
}

/** Reconstructed lines → a minimal prose DOCX of the shape S1 consumes. PURE. */
export async function linesToProseDocx(lines: string[]): Promise<Uint8Array> {
  const zip = new JSZip();
  zip.file('[Content_Types].xml', CONTENT_TYPES_XML);
  zip.file('_rels/.rels', RELS_XML);
  zip.file('word/document.xml', linesToDocumentXml(lines));
  return zip.generateAsync({ type: 'uint8array' });
}

/**
 * PDF bytes → a faithful prose DOCX (or null for a scanned / text-less PDF). The
 * unpdf import is dynamic so the compiler graph that pulls this module in
 * (create-draft) does not force pdfjs into the bundle — unpdf is a
 * `serverExternalPackages` entry. The result is the INPUT to `deriveProseTwin`.
 */
export async function pdfToProseDocx(pdfBytes: Uint8Array): Promise<Uint8Array | null> {
  let proxy: PdfjsProxy;
  try {
    const { getDocumentProxy } = await import('unpdf');
    proxy = (await getDocumentProxy(pdfBytes)) as unknown as PdfjsProxy;
  } catch {
    return null; // unreadable / malformed PDF — caller declines cleanly
  }
  const lines = await extractProseLinesFromProxy(proxy);
  if (!lines) return null; // no text layer — scanned, out of scope (ruling S2-2)
  return linesToProseDocx(lines);
}
