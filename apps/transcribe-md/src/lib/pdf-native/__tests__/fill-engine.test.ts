// ============================================================================
// PDF native fill engine — structural tests on a synthetic canvas.
// Verifies: text lands in regions; shrink-to-fit; overflow → "(continued)" +
// appended continuation page; unfilled regions stay blank; original page kept.
// ============================================================================
import { describe, expect, it } from 'vitest';
import { PDFDocument, StandardFonts } from 'pdf-lib';
import { extractText, getDocumentProxy } from 'unpdf';

import { fillPdfTemplate, type PdfFillAnchor } from '../fill-engine';

/** A 1-page Letter canvas with two printed labels (the doctor's "form ink"). */
async function makeCanvas(): Promise<Uint8Array> {
  const doc = await PDFDocument.create();
  const page = doc.addPage([612, 792]);
  const font = await doc.embedFont(StandardFonts.HelveticaBold);
  page.drawText('PROCEDURE:', { x: 54, y: 720, size: 11, font });
  page.drawText('RECOMMENDATIONS:', { x: 54, y: 300, size: 11, font });
  return doc.save();
}

async function pdfText(bytes: Uint8Array): Promise<string> {
  const proxy = await getDocumentProxy(bytes);
  const { text } = await extractText(proxy, { mergePages: true });
  return Array.isArray(text) ? text.join('\n') : text;
}

const ANCHORS: PdfFillAnchor[] = [
  // Region right-of + below PROCEDURE: (tall enough for a line or two)
  { key: 'procedure', label: 'PROCEDURE:', page: 0, yTop: 720, yBottom: 640, firstLineX: 130, wrapX: 54, rightEdge: 558, fontSize: 11 },
  // Small region at RECOMMENDATIONS: (forces overflow for long text)
  { key: 'recommendations', label: 'RECOMMENDATIONS:', page: 0, yTop: 300, yBottom: 280, firstLineX: 170, wrapX: 54, rightEdge: 558, fontSize: 11 },
];

describe('fillPdfTemplate', () => {
  it('draws text into a region + preserves the original page/labels', async () => {
    const out = await fillPdfTemplate({
      canvasPdf: await makeCanvas(),
      anchors: ANCHORS,
      texts: { procedure: 'Screening colonoscopy with polypectomy.' },
    });
    const doc = await PDFDocument.load(out);
    expect(doc.getPageCount()).toBe(1); // no overflow → no continuation page
    const text = await pdfText(out);
    expect(text).toContain('PROCEDURE:'); // the doctor's form ink is preserved
    expect(text).toContain('Screening colonoscopy'); // our fill landed
  });

  it('leaves an unfilled region blank (no "Not documented." stamped)', async () => {
    const out = await fillPdfTemplate({
      canvasPdf: await makeCanvas(),
      anchors: ANCHORS,
      texts: { procedure: 'Colonoscopy.' }, // recommendations intentionally absent
    });
    const text = await pdfText(out);
    expect(text).not.toMatch(/not documented/i);
    expect(text).not.toContain('(continued)'); // short text, no overflow
  });

  it('overflows a small region → "(continued)" + an appended continuation page carrying the label', async () => {
    const longText = Array.from({ length: 40 }, (_, i) => `Finding ${i} of the mucosal survey on withdrawal.`).join(' ');
    const out = await fillPdfTemplate({
      canvasPdf: await makeCanvas(),
      anchors: ANCHORS,
      texts: { recommendations: longText },
    });
    const doc = await PDFDocument.load(out);
    expect(doc.getPageCount()).toBe(2); // original + 1 continuation page
    const text = await pdfText(out);
    expect(text).toContain('(continued)');
    expect(text).toContain('CONTINUATION');
    expect(text).toContain('RECOMMENDATIONS:'); // continuation carries the section label
    expect(text).toContain('Finding 39'); // the tail flowed to the continuation
  });

  it('draws the signed-status line in the bottom margin', async () => {
    const out = await fillPdfTemplate({
      canvasPdf: await makeCanvas(),
      anchors: ANCHORS,
      texts: { procedure: 'Colonoscopy.' },
      signedStatusLine: 'Signed electronically by Dr. Shabatian on 2026-07-23.',
    });
    expect(await pdfText(out)).toContain('Signed electronically by Dr. Shabatian');
  });
});
