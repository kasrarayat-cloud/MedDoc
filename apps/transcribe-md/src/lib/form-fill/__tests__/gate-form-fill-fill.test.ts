import { PDFDocument, StandardFonts } from 'pdf-lib';
import { describe, it, expect } from 'vitest';

import { fillDetectedForm, packLine } from '../fill-boxes';
import type { DetectedBox, FormField } from '../types';

// Ruling #326, Slice A: fill draws values into detected boxes; a value that
// overflows its boxes spills to a continuation page, never truncated silently.

async function blankPdf(pages = 1): Promise<Uint8Array> {
  const doc = await PDFDocument.create();
  for (let i = 0; i < pages; i += 1) doc.addPage([612, 792]);
  return doc.save();
}

function tbox(x: number, y: number, w: number, h: number): DetectedBox {
  return { x, y, w, h, type: 'TextBox', label: '', labelSource: '' };
}

function field(id: string, boxes: DetectedBox[], label = id): FormField {
  return { id, label, page: 0, boxes, multiline: boxes.length > 1 };
}

describe('fill-boxes (draw + overflow)', () => {
  it('fills a short value into its box and produces a loadable PDF', async () => {
    const base = await blankPdf();
    const fields = [field('f0', [tbox(120, 690, 300, 16)])];
    const values = new Map([['f0', 'Jane Doe']]);
    const { pdf, filledFields, overflowed } = await fillDetectedForm({
      originalPdf: base,
      fields,
      values,
    });
    expect(filledFields).toBe(1);
    expect(overflowed).toHaveLength(0);
    const reload = await PDFDocument.load(pdf);
    expect(reload.getPageCount()).toBe(1); // no continuation
  });

  it('spills an over-long value to a continuation page and reports it', async () => {
    const base = await blankPdf();
    // one narrow single-line box; a long value cannot fit in one line
    const fields = [field('f0', [tbox(120, 690, 120, 14)])];
    const long = Array.from({ length: 60 }, (_, i) => `word${i}`).join(' ');
    const { pdf, filledFields, overflowed } = await fillDetectedForm({
      originalPdf: base,
      fields,
      values: new Map([['f0', long]]),
    });
    expect(filledFields).toBe(1);
    expect(overflowed).toHaveLength(1);
    expect(overflowed[0]!.id).toBe('f0');
    expect(overflowed[0]!.lines).toBeGreaterThan(0);
    const reload = await PDFDocument.load(pdf);
    expect(reload.getPageCount()).toBeGreaterThan(1); // continuation appended
  });

  it('distributes wrapped lines across a multi-line field\'s stacked boxes', async () => {
    const base = await blankPdf();
    // three stacked lines, generous width → three wrapped lines, no overflow
    const boxes = [
      tbox(45, 400, 520, 16),
      tbox(45, 382, 520, 16),
      tbox(45, 364, 520, 16),
    ];
    const value = Array.from({ length: 40 }, (_, i) => `t${i}`).join(' ');
    const { overflowed, filledFields } = await fillDetectedForm({
      originalPdf: base,
      fields: [field('sec', boxes)],
      values: new Map([['sec', value]]),
    });
    expect(filledFields).toBe(1);
    // 40 short tokens across 520pt lines fit within three lines
    expect(overflowed).toHaveLength(0);
  });

  it('packLine never returns a line wider than the box, and always progresses (adversarial #4/#7)', async () => {
    const doc = await PDFDocument.create();
    const font = await doc.embedFont(StandardFonts.Helvetica);
    const size = 9;
    const words =
      'Estimated blood loss 250 milliliters patient tolerated the procedure well supercalifragilisticexpialidocious and was transferred to recovery in stable condition'.split(
        ' ',
      );
    for (const maxWidth of [30, 60, 120, 400]) {
      let rest = words;
      let guard = 0;
      while (rest.length > 0 && guard < 500) {
        const before = rest.length;
        const { line, rest: next } = packLine(rest, font, size, maxWidth);
        // the line NEVER exceeds the box width — this is the clinical-safety invariant
        expect(font.widthOfTextAtSize(line, size)).toBeLessThanOrEqual(maxWidth + 0.01);
        // forward progress: either fewer words remain, or the same count with a shorter head
        expect(rest.length === before ? next.length : next.length).toBeLessThan(before + 1);
        expect(next.length).toBeLessThanOrEqual(before);
        if (next.length === before) expect(next[0]!.length).toBeLessThan(rest[0]!.length);
        rest = next;
        guard += 1;
      }
      expect(guard).toBeLessThan(500); // terminated
    }
    // a box too narrow for even one character packs NOTHING (overflow, no draw)
    const tiny = packLine(['10'], font, size, 3);
    expect(tiny.line).toBe('');
    expect(tiny.rest).toEqual(['10']);
  });

  it('a sub-16pt box draws NOTHING over the form — the value overflows (adv pass2 #1)', async () => {
    const base = await blankPdf();
    const narrow: DetectedBox = {
      x: 100,
      y: 500,
      w: 8,
      h: 14,
      type: 'TextBox',
      label: '',
      labelSource: '',
    };
    const { overflowed, filledFields } = await fillDetectedForm({
      originalPdf: base,
      fields: [field('t', [narrow])],
      values: new Map([['t', '10']]),
    });
    // nothing fit → the whole value overflows to the continuation page
    expect(filledFields).toBe(1);
    expect(overflowed).toHaveLength(1);
    expect(overflowed[0]!.id).toBe('t');
  });

  it('a line landing in a NARROW stacked box does not exceed it — overflow instead', async () => {
    const base = await blankPdf();
    // box0 wide, box1 narrow: a long value fills box0, box1 takes what fits, rest overflows
    const boxes = [tbox(45, 400, 400, 14), tbox(45, 382, 60, 14)];
    const value = Array.from({ length: 40 }, (_, i) => `token${i}`).join(' ');
    const { overflowed, filledFields } = await fillDetectedForm({
      originalPdf: base,
      fields: [field('sec', boxes)],
      values: new Map([['sec', value]]),
    });
    expect(filledFields).toBe(1);
    // the narrow box cannot hold the remainder → continuation, never drawn past its edge
    expect(overflowed).toHaveLength(1);
  });

  it('skips fields with no value and non-text widgets', async () => {
    const base = await blankPdf();
    const sig: DetectedBox = {
      x: 45,
      y: 400,
      w: 200,
      h: 20,
      type: 'Signature',
      label: '',
      labelSource: '',
    };
    const { filledFields } = await fillDetectedForm({
      originalPdf: base,
      fields: [field('a', [tbox(45, 500, 200, 16)]), field('s', [sig])],
      values: new Map([['a', '']]), // empty → skipped; 's' has no value
    });
    expect(filledFields).toBe(0);
  });
});
