// ============================================================================
// REGRESSION — appending a continuation page to a ReportLab (xref-STREAM)
// template must not corrupt the output (owner finding, 2026-09-14).
// ----------------------------------------------------------------------------
// THE BUG. The owner re-uploaded Colonoscopy_Operative_Template.pdf and the
// Note-format preview came back a SOLID WHITE page. Cause, named: the preview
// fills the form with pdf-lib and, when the sample content overflows the form's
// small blank regions, APPENDS a continuation page (drawAppendedSection →
// doc.addPage). pdf-lib's DEFAULT save (useObjectStreams: true) then writes a
// cross-reference STREAM whose /Root reference resolves to a bad entry —
// but ONLY when a page was appended to a template that ITSELF uses xref streams,
// which every ReportLab-generated form does. The browser's pdfjs cannot recover
// and paints a blank white page. It is a latent SIGNED-EXPORT defect too, not
// only a preview one: any filled note that overflowed onto a continuation page
// was shipping a corrupt PDF.
//
// WHY THE EXISTING fill-engine tests missed it: their canvas is built with
// `PDFDocument.create()` — a pdf-lib-NATIVE PDF with a classic xref table, which
// does not reproduce the xref-stream + addPage interaction. Only a REAL
// ReportLab document does, which is why this test is armed with the owner's own
// BLANK form as a fixture (labels + rule lines + empty numbered slots, no
// patient data — verified by text extraction before it was committed).
//
// THE ASSERTION IS FONT-FREE. We do not rasterise (the test env has no browser
// canvas). Instead we build each page's OPERATOR LIST: on the corrupt output
// pdfjs throws "Bad (uncompressed) XRef entry" while building the appended
// page's ops — the exact signal, with no font or canvas dependency. The fix
// (`doc.save({ useObjectStreams: false })`, a classic xref table) makes every
// page's op list build cleanly. Reverting the fix turns this test RED with that
// message (mutation-verified 2026-09-14).
// ============================================================================
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

import { describe, expect, it } from 'vitest';
import { getDocumentProxy } from 'unpdf';

import { fillPdfTemplate, type PdfFillAnchor } from '../fill-engine';

const FIXTURE = join(
  dirname(fileURLToPath(import.meta.url)),
  '__fixtures__',
  'colon-operative-reportlab.pdf',
);

/** Build every page's operator list. A corrupt xref makes pdfjs throw while
 *  resolving the appended page's objects — no rasterisation, no fonts needed. */
async function pagesBuildOpLists(bytes: Uint8Array): Promise<{ pages: number; failures: string[] }> {
  // pdfjs emits recovery WARNINGS on a broken xref before it throws; silence
  // them so a green run is quiet, then let the throw surface as a failure.
  const warn = console.warn;
  console.warn = () => {};
  try {
    const doc = await getDocumentProxy(bytes.slice());
    const failures: string[] = [];
    for (let p = 1; p <= doc.numPages; p += 1) {
      try {
        const page = await doc.getPage(p);
        await page.getOperatorList();
      } catch (e) {
        failures.push(`page ${p}: ${(e as Error).message}`);
      }
    }
    return { pages: doc.numPages, failures };
  } finally {
    console.warn = warn;
  }
}

// A tiny region on the fixture's first page + long text: the fill draws one
// line then OVERFLOWS, which appends a continuation page — the exact trigger.
const OVERFLOW_ANCHOR: PdfFillAnchor[] = [
  { key: 'x', label: 'X', page: 0, yTop: 300, yBottom: 292, firstLineX: 120, wrapX: 54, rightEdge: 558, fontSize: 9 },
];
const LONG = Array.from(
  { length: 60 },
  (_, i) => `Overflow sentence ${i} that is pushed onto the appended continuation page.`,
).join(' ');

describe('fillPdfTemplate — appending a page to a ReportLab xref-stream template', () => {
  it('appends the continuation page AND leaves every page renderable (no corrupt xref)', async () => {
    const canvasPdf = new Uint8Array(readFileSync(FIXTURE));
    const out = await fillPdfTemplate({ canvasPdf, anchors: OVERFLOW_ANCHOR, texts: { x: LONG } });

    const { pages, failures } = await pagesBuildOpLists(out);
    // The continuation page WAS appended — so the corruption trigger is actually
    // exercised (a test that filled without overflowing would prove nothing).
    expect(pages).toBeGreaterThanOrEqual(2);
    // …and nothing is corrupt: every page's ops build. Reverting the save fix
    // makes THIS line fail with "Bad (uncompressed) XRef entry".
    expect(failures).toEqual([]);
  });

  it('a fill with no overflow (no appended page) is also clean', async () => {
    // The single-page path was never broken; pin it so a future "fix" that only
    // guards the overflow branch cannot regress the common case.
    const canvasPdf = new Uint8Array(readFileSync(FIXTURE));
    const out = await fillPdfTemplate({ canvasPdf, anchors: OVERFLOW_ANCHOR, texts: { x: 'Short.' } });
    const { pages, failures } = await pagesBuildOpLists(out);
    expect(pages).toBe(1);
    expect(failures).toEqual([]);
  });
});
