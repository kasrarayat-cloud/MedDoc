// ============================================================================
// UPLOAD-AND-CERTIFIED · S2 — PDF form → faithful prose DOCX → S1 twin.
// ----------------------------------------------------------------------------
// Proves the S2 core end-to-end against the REAL PDF text-layer extractor (unpdf
// / pdfjs, exactly as pdf-native/anchors.test.ts uses it) and the REAL S1 twin
// path: a pdf-lib-built form → positioned extraction → reconstructed prose lines
// → prose DOCX → deriveProseTwin inserts one control per affordance label. Plus
// pure reconstructLines tests (ordering, line grouping, multi-page) and the
// fail-safe (no text layer → null).
// ============================================================================
import { describe, expect, it } from 'vitest';
import { PDFDocument, StandardFonts } from 'pdf-lib';
import { getDocumentProxy } from 'unpdf';

import { compileTemplateDocx } from '@/lib/note-template-docx';
import { deriveProseTwin, derivedTwinProbeIsValid } from '../../prose-form/derive-prose-twin';
import {
  reconstructLines,
  extractProseLinesFromProxy,
  linesToProseDocx,
  linesToDocumentXml,
  type PdfjsProxy,
  type PlacedItem,
} from '../pdf-to-prose-docx';

const verify = async (bytes: Uint8Array, expected: number): Promise<boolean> => {
  try {
    return derivedTwinProbeIsValid(compileTemplateDocx(bytes), expected);
  } catch {
    return false;
  }
};

async function proxyFor(bytes: Uint8Array): Promise<PdfjsProxy> {
  return (await getDocumentProxy(bytes)) as unknown as PdfjsProxy;
}

/** A synthetic operative/consult PDF form: a heading, colon labels WITH
 *  underscore affordances (real text), and a bare heading-shaped colon line. */
async function makeFormPdf(): Promise<Uint8Array> {
  const doc = await PDFDocument.create();
  const page = doc.addPage([612, 792]);
  const bold = await doc.embedFont(StandardFonts.HelveticaBold);
  const font = await doc.embedFont(StandardFonts.Helvetica);
  const L = (t: string, y: number, f = font) => page.drawText(t, { x: 54, y, size: 11, font: f });
  L('OPERATIVE NOTE', 740, bold);
  L('Patient Name: ______________________', 710);
  L('Date of Service: ______________________', 688);
  L('Weight: ______', 666);
  L('Procedure Performed: ______________________', 644);
  L('Assessment and Plan:', 610, bold); // heading, no affordance → must stay prose
  return doc.save();
}

describe('S2 — pdfToProseDocx: reconstruct + build (pure)', () => {
  it('reconstructLines orders by page, then top-to-bottom, then left-to-right', () => {
    // y DESCENDING = top-to-bottom; two tokens on one line join left-to-right.
    const items: PlacedItem[] = [
      { str: 'Name:', x: 54, y: 700, height: 11, page: 0 },
      { str: '______', x: 120, y: 700, height: 11, page: 0 }, // same line as Name:
      { str: 'SECOND', x: 54, y: 680, height: 11, page: 0 },
      { str: 'FIRST', x: 54, y: 720, height: 11, page: 0 }, // higher y → earlier
      { str: 'PAGE2', x: 54, y: 900, height: 11, page: 1 }, // later page → last
    ];
    expect(reconstructLines(items)).toEqual(['FIRST', 'Name: ______', 'SECOND', 'PAGE2']);
  });

  it('reconstructLines groups items within a height-relative y tolerance onto one line', () => {
    const items: PlacedItem[] = [
      { str: 'A', x: 10, y: 500.0, height: 11, page: 0 },
      { str: 'B', x: 30, y: 502.5, height: 11, page: 0 }, // within ~0.6*11 tol → same line
      { str: 'C', x: 10, y: 470, height: 11, page: 0 }, // far below → new line
    ];
    expect(reconstructLines(items)).toEqual(['A B', 'C']);
  });

  it('reconstructLines ignores empty/whitespace tokens and returns [] for none', () => {
    expect(reconstructLines([])).toEqual([]);
    expect(reconstructLines([{ str: '   ', x: 1, y: 1, height: 11, page: 0 }])).toEqual([]);
  });

  it('linesToDocumentXml emits one <w:p> per line, XML-escaped, no controls', () => {
    const xml = linesToDocumentXml(['A & B: ______', 'Plan:']);
    expect(xml).toContain('<w:t xml:space="preserve">A &amp; B: ______</w:t>');
    expect(xml).toContain('<w:t xml:space="preserve">Plan:</w:t>');
    expect(xml).not.toContain('<w:sdt>'); // prose only — S1 adds controls
  });
});

describe('S2 — end-to-end: real PDF → extract → prose DOCX → S1 twin', () => {
  it('extracts the form lines in reading order from a real PDF text layer', async () => {
    const lines = await extractProseLinesFromProxy(await proxyFor(await makeFormPdf()));
    expect(lines).not.toBeNull();
    expect(lines).toEqual([
      'OPERATIVE NOTE',
      'Patient Name: ______________________',
      'Date of Service: ______________________',
      'Weight: ______',
      'Procedure Performed: ______________________',
      'Assessment and Plan:',
    ]);
  });

  it('the reconstructed prose DOCX derives an S1 twin: one control per affordance label', async () => {
    const lines = await extractProseLinesFromProxy(await proxyFor(await makeFormPdf()));
    const docx = await linesToProseDocx(lines!);
    const twin = await deriveProseTwin(docx, verify);
    expect(twin).not.toBeNull();
    // The four affordance labels become controls; heading + bare "Assessment and
    // Plan:" (no affordance) stay prose. "Weight" is a measurement kind — accepted.
    expect(twin!.slots.map((s) => s.alias)).toEqual([
      'Patient Name', 'Date of Service', 'Weight', 'Procedure Performed',
    ]);
    const ir = compileTemplateDocx(twin!.bytes);
    expect(ir.fields.map((f) => f.originalLabel)).toEqual([
      'Patient Name', 'Date of Service', 'Weight', 'Procedure Performed',
    ]);
    expect(ir.stats.blockingUnsupported).toBe(0);
    expect(ir.fields.find((f) => f.originalLabel === 'Weight')?.kind).toBe('measurement');
    // The heading survived as prose, not a control.
    expect(twin!.documentXml).toContain('<w:t xml:space="preserve">OPERATIVE NOTE</w:t>');
    expect(/Assessment and Plan:<\/w:t><\/w:r><\/w:p>/.test(twin!.documentXml)).toBe(true);
  });

  it('a text-less (scanned/image-only) PDF extracts to null — fail safe (ruling S2-2)', async () => {
    // A page with only a drawn rectangle, no text tokens.
    const doc = await PDFDocument.create();
    const page = doc.addPage([612, 792]);
    page.drawRectangle({ x: 100, y: 100, width: 200, height: 50 });
    const proxy = await proxyFor(await doc.save());
    expect(await extractProseLinesFromProxy(proxy)).toBeNull();
  });
});
