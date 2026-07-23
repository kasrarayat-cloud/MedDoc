// ============================================================================
// PDF anchor extraction — on a synthetic canvas with known label positions.
// (Hardened against the real colon template's text layer at certify-QA time.)
// ============================================================================
import { describe, expect, it } from 'vitest';
import { PDFDocument, StandardFonts } from 'pdf-lib';
import { getDocumentProxy, extractText } from 'unpdf';

import { extractPdfAnchors, missingAnchors, type AnchorLabelSpec } from '../anchors';
import { fillPdfTemplate } from '../fill-engine';

async function makeFormCanvas(): Promise<Uint8Array> {
  const doc = await PDFDocument.create();
  const page = doc.addPage([612, 792]);
  const bold = await doc.embedFont(StandardFonts.HelveticaBold);
  page.drawText('PATIENT NAME:', { x: 54, y: 740, size: 11, font: bold });
  page.drawText('SURGEON:', { x: 54, y: 715, size: 11, font: bold });
  page.drawText('PROCEDURE:', { x: 54, y: 660, size: 11, font: bold });
  page.drawText('RECOMMENDATIONS:', { x: 54, y: 300, size: 11, font: bold });
  return doc.save();
}

const SPECS: AnchorLabelSpec[] = [
  { key: 'patient_name', label: 'PATIENT NAME:', kind: 'inline' },
  { key: 'surgeon', label: 'SURGEON:', kind: 'inline' },
  { key: 'procedure', label: 'PROCEDURE:', kind: 'block' },
  { key: 'recommendations', label: 'RECOMMENDATIONS:', kind: 'block' },
];

// unpdf's getDocumentProxy returns a pdfjs proxy compatible with our interface.
async function proxyFor(bytes: Uint8Array) {
  return (await getDocumentProxy(bytes)) as unknown as Parameters<typeof extractPdfAnchors>[0];
}

describe('extractPdfAnchors', () => {
  it('locates every label and produces sane regions', async () => {
    const anchors = await extractPdfAnchors(await proxyFor(await makeFormCanvas()), SPECS);
    const byKey = Object.fromEntries(anchors.map((a) => [a.key, a]));
    expect(anchors.map((a) => a.key).sort()).toEqual(
      ['patient_name', 'procedure', 'recommendations', 'surgeon'].sort()
    );
    // Inline (PATIENT NAME:) first line starts to the RIGHT of the label; it's a
    // single-line region.
    expect(byKey.patient_name.firstLineX).toBeGreaterThan(54 + 60);
    expect(byKey.patient_name.yTop - byKey.patient_name.yBottom).toBeLessThan(20);
    // Block (PROCEDURE:) first line right of the label, wraps below at x=54, down
    // to the next label region.
    expect(byKey.procedure.firstLineX).toBeGreaterThan(54 + 60);
    expect(byKey.procedure.wrapX).toBeCloseTo(54, 0);
    expect(byKey.procedure.yBottom).toBeGreaterThan(300); // bounded by RECOMMENDATIONS:
  });

  it('reports labels that do not anchor (never silently dropped)', async () => {
    const missing = await missingAnchors(await proxyFor(await makeFormCanvas()), [
      ...SPECS,
      { key: 'nonexistent', label: 'ANESTHESIA TYPE:', kind: 'block' },
    ]);
    expect(missing).toEqual(['nonexistent']);
  });

  it('end-to-end: extract anchors → fill → generated text lands on the page', async () => {
    const canvas = await makeFormCanvas();
    // getDocumentProxy detaches its input ArrayBuffer — extract from a COPY so the
    // original canvas bytes survive for the fill (prod stores the two separately).
    const anchors = await extractPdfAnchors(await proxyFor(canvas.slice()), SPECS);
    const out = await fillPdfTemplate({
      canvasPdf: canvas,
      anchors,
      texts: {
        patient_name: 'KUK',
        surgeon: 'Dr. Shabatian',
        procedure: 'Screening colonoscopy with sigmoid polypectomy.',
        // recommendations left blank on purpose
      },
    });
    const proxy = await getDocumentProxy(out);
    const { text } = await extractText(proxy, { mergePages: true });
    const flat = Array.isArray(text) ? text.join('\n') : text;
    expect(flat).toContain('PATIENT NAME:'); // form ink preserved
    expect(flat).toContain('KUK');
    expect(flat).toContain('Dr. Shabatian');
    expect(flat).toContain('Screening colonoscopy');
    expect(flat).not.toMatch(/not documented/i); // blank recommendations stays blank
  });
});
