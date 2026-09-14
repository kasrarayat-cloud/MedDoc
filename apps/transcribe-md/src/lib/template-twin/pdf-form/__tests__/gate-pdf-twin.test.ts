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
  groupLineBoxes,
  annotateAffordances,
  extractProseLinesFromProxy,
  isPdfSource,
  linesToProseDocx,
  linesToDocumentXml,
  type PdfjsProxy,
  type PlacedItem,
  type LineBox,
  type RuleSegment,
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
  it('extracts the form lines, MATERIALISING a blank on a colon label with empty span (ruling #320)', async () => {
    const lines = await extractProseLinesFromProxy(await proxyFor(await makeFormPdf()));
    expect(lines).not.toBeNull();
    expect(lines).toEqual([
      'OPERATIVE NOTE', // no colon → stays prose (still a negative control)
      'Patient Name: ______________________', // real underscores → untouched
      'Date of Service: ______________________',
      'Weight: ______',
      'Procedure Performed: ______________________',
      // ⚠️ RULING #320: a colon label with an empty writable span IS an
      // affordance now — the old "bare LABEL: stays prose" was AMENDED. So the
      // annotator materialises the blank and S1 derives it.
      'Assessment and Plan: ______',
    ]);
  });

  it('the reconstructed prose DOCX derives an S1 twin: one control per affordance label', async () => {
    const lines = await extractProseLinesFromProxy(await proxyFor(await makeFormPdf()));
    const docx = await linesToProseDocx(lines!);
    const twin = await deriveProseTwin(docx, verify);
    expect(twin).not.toBeNull();
    // The four underscore labels PLUS "Assessment and Plan:" (colon + empty span,
    // ruling #320) become controls; the no-colon heading stays prose. "Weight"
    // is a measurement kind — accepted.
    expect(twin!.slots.map((s) => s.alias)).toEqual([
      'Patient Name', 'Date of Service', 'Weight', 'Procedure Performed', 'Assessment and Plan',
    ]);
    const ir = compileTemplateDocx(twin!.bytes);
    expect(ir.stats.blockingUnsupported).toBe(0);
    expect(ir.fields.find((f) => f.originalLabel === 'Weight')?.kind).toBe('measurement');
    // The no-colon heading survived as prose, not a control (negative control).
    expect(twin!.documentXml).toContain('<w:t xml:space="preserve">OPERATIVE NOTE</w:t>');
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

describe('S2 — isPdfSource: content detection agrees with the PDF reader', () => {
  const PDF = [0x25, 0x50, 0x44, 0x46, 0x2d]; // %PDF-
  const bufWith = (...prefix: number[]) => new Uint8Array([...prefix, ...PDF, 0x31, 0x2e, 0x34]);

  it('accepts %PDF- at offset 0', () => {
    expect(isPdfSource(bufWith())).toBe(true);
  });

  it('⚠️ fixed — accepts a PDF led by a UTF-8 BOM / whitespace / newline (pdf.js does)', () => {
    expect(isPdfSource(bufWith(0xef, 0xbb, 0xbf))).toBe(true); // BOM
    expect(isPdfSource(bufWith(0x0a))).toBe(true); // newline
    expect(isPdfSource(bufWith(0x20, 0x20, 0x20))).toBe(true); // spaces
    expect(isPdfSource(bufWith(0x0d, 0x0a))).toBe(true); // CRLF
  });

  it('accepts a real pdf-lib PDF and rejects a real prose DOCX', async () => {
    const doc = await PDFDocument.create();
    doc.addPage([612, 792]);
    expect(isPdfSource(await doc.save())).toBe(true);
    const docx = await linesToProseDocx(['Patient Name: ______']); // a ZIP (PK\x03\x04)
    expect(isPdfSource(docx)).toBe(false);
  });

  it('rejects plain text, empty, and a %PDF- header beyond the first 1KB', () => {
    expect(isPdfSource(new Uint8Array([0x68, 0x69]))).toBe(false); // "hi"
    expect(isPdfSource(new Uint8Array())).toBe(false);
    const farHeader = new Uint8Array(2000);
    farHeader.set(PDF, 1500); // header at offset 1500 — past the 1KB scan window
    expect(isPdfSource(farHeader)).toBe(false);
  });
});

// ── RULING #320 — the union blank affordance (pure) ────────────────────────
describe('S2 #320 — annotateAffordances: colon/number + empty span OR drawn line', () => {
  const W = (): number => 612; // page width; margin comes from the boxes' min x0
  function box(text: string, over?: Partial<LineBox>): LineBox {
    return { text, page: 0, y: 700, x0: 54, x1: 120, height: 11, ...over };
  }

  it('appends a blank to a COLON LABEL with an empty span to the right margin', () => {
    expect(annotateAffordances([box('PATIENT NAME:')], [], W)).toEqual(['PATIENT NAME: ______']);
  });

  it('appends a blank to a BARE NUMBERED SLOT ("1.") — the owner-file findings', () => {
    expect(annotateAffordances([box('1.', { x1: 64 })], [], W)).toEqual(['1. ______']);
    expect(annotateAffordances([box('•', { x1: 60 })], [], W)).toEqual(['• ______']);
  });

  it('leaves a NO-COLON title and a DASH-terminated line as prose (negative controls)', () => {
    expect(annotateAffordances([box('OPERATIVE NOTE', { x0: 250, x1: 360 })], [], W)).toEqual(['OPERATIVE NOTE']);
    expect(annotateAffordances([box('Electronically Signed -')], [], W)).toEqual(['Electronically Signed -']);
  });

  it('leaves a line that ALREADY carries an underscore run untouched (S1 owns it)', () => {
    expect(annotateAffordances([box('Total time: ______')], [], W)).toEqual(['Total time: ______']);
  });

  it('does NOT append when a colon label fills the row (no span, no gap, no line)', () => {
    // x1 = 574 is within SPAN_MARGIN (40) of the right edge (612 - margin 54 = 558)… use a wide label.
    expect(annotateAffordances([box('A VERY WIDE LABEL FILLING THE ROW:', { x1: 556 })], [], W)).toEqual([
      'A VERY WIDE LABEL FILLING THE ROW:',
    ]);
  });

  it('appends via a NEXT-LINE GAP when there is no same-row span (a block field)', () => {
    const boxes = [
      box('DESCRIPTION OF PROCEDURE:', { x1: 556, y: 400 }),
      box('RECOMMENDATIONS:', { x1: 556, y: 280 }), // 120pt below → a writing area
    ];
    expect(annotateAffordances(boxes, [], W)[0]).toBe('DESCRIPTION OF PROCEDURE: ______');
  });

  it('appends via a DRAWN RULE LINE following the label (branch b), even with no span', () => {
    const boxes = [box('SIGNATURE:', { x1: 556, y: 200 })];
    const segs: RuleSegment[] = [{ page: 0, y: 200, x0: 300, x1: 560 }];
    expect(annotateAffordances(boxes, segs, W)).toEqual(['SIGNATURE: ______']);
    // …and a WHITE (absent) line is never passed here — the extractor drops it —
    // so with no segment the same label stays prose:
    expect(annotateAffordances(boxes, [], W)).toEqual(['SIGNATURE:']);
  });
});

describe('S2 #320 — groupLineBoxes: two-column reading order', () => {
  it('splits a two-column header row into two boxes, left then right', () => {
    const items: PlacedItem[] = [
      { str: 'PATIENT NAME:', x: 54, y: 700, height: 11, page: 0 },
      { str: 'DOB:', x: 360, y: 700, height: 11, page: 0 }, // far right, big gap → second column
    ];
    const boxes = groupLineBoxes(items);
    expect(boxes.map((b) => b.text)).toEqual(['PATIENT NAME:', 'DOB:']);
  });

  it('does NOT split a single wide label with only normal word gaps', () => {
    const items: PlacedItem[] = [
      { str: 'DATE', x: 54, y: 700, height: 11, page: 0 },
      { str: 'OF', x: 90, y: 700, height: 11, page: 0 },
      { str: 'SURGERY:', x: 110, y: 700, height: 11, page: 0 },
    ];
    expect(groupLineBoxes(items).map((b) => b.text)).toEqual(['DATE OF SURGERY:']);
  });
});

describe('S2 #320 — end-to-end: an operative note with NO underscore blanks derives controls', () => {
  // The owner's file shape: colon labels + numbered slots drawn with NO underscore
  // characters (the blanks are drawn/whitespace). Before #320 this derived ZERO.
  async function makeOpNotePdf(): Promise<Uint8Array> {
    const doc = await PDFDocument.create();
    const page = doc.addPage([612, 792]);
    const bold = await doc.embedFont(StandardFonts.HelveticaBold);
    const font = await doc.embedFont(StandardFonts.Helvetica);
    const L = (t: string, y: number, f = font, x = 54) => page.drawText(t, { x, y, size: 11, font: f });
    L('OPERATIVE NOTE', 740, bold, 250); // title (centred-ish, no colon) → prose
    L('PATIENT NAME:', 710);
    L('SURGEON:', 688);
    L('PROCEDURE:', 666);
    L('POSTOPERATIVE FINDINGS:', 640);
    L('1.', 620, font, 58);
    L('2.', 604, font, 58);
    L('3.', 588, font, 58);
    L('DESCRIPTION OF PROCEDURE:', 560);
    L('The findings were reviewed with the patient.', 300); // sentence, no colon → prose
    return doc.save();
  }

  it('derives one control per colon label + numbered slot; title/sentence stay prose', async () => {
    const lines = await extractProseLinesFromProxy(await proxyFor(await makeOpNotePdf()));
    const twin = await deriveProseTwin(await linesToProseDocx(lines!), verify);
    expect(twin).not.toBeNull();
    // 5 colon labels + 3 numbered slots = 8 controls; the title and the trailing
    // sentence (no colon, no marker) stay prose.
    expect(twin!.slots.map((s) => s.alias)).toEqual([
      'PATIENT NAME', 'SURGEON', 'PROCEDURE', 'POSTOPERATIVE FINDINGS',
      'Fill-in', 'Fill-in', 'Fill-in', 'DESCRIPTION OF PROCEDURE',
    ]);
    expect(twin!.documentXml).toContain('<w:t xml:space="preserve">OPERATIVE NOTE</w:t>');
    expect(twin!.documentXml).toContain(
      '<w:t xml:space="preserve">The findings were reviewed with the patient.</w:t>',
    );
    // Every derived field is a fillable plain-text kind (keystone) — 0 blocking.
    const ir = compileTemplateDocx(twin!.bytes);
    expect(ir.stats.blockingUnsupported).toBe(0);
  });
})
