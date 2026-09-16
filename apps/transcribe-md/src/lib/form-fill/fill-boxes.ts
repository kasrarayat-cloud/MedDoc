// Stage 4 (fill) — draw values into detected boxes with pdf-lib (#326).
// The doctor's original page bytes are the background and are never altered; the
// value is drawn on top, wrapped to the box, one line per stacked box. A value
// that overflows its boxes spills to a CONTINUATION page appended at the end,
// under its label — never silently truncated, never overlapping the form.

import { PDFDocument, StandardFonts, rgb, type PDFFont } from 'pdf-lib';

import type { DetectedBox, FormField } from './types';

const INK = rgb(0.08, 0.08, 0.1);
const PAD = 2; // left/inside padding, points
const MARGIN = 54; // continuation-page margin

export interface FillDetectedInput {
  /** the original uploaded PDF (flat, or Word→PDF) */
  originalPdf: Uint8Array;
  fields: FormField[];
  /** fieldId → value text */
  values: Map<string, string>;
}

export interface FillDetectedResult {
  pdf: Uint8Array;
  /** fields whose value did not fit their boxes and spilled to a continuation page */
  overflowed: Array<{ id: string; label: string; lines: number }>;
  filledFields: number;
}

function fontSizeFor(h: number): number {
  return Math.max(7, Math.min(11, Math.round(h * 0.6)));
}

/** Greedy word-wrap; a single word wider than maxWidth is hard-broken by char. */
function wrap(text: string, font: PDFFont, size: number, maxWidth: number): string[] {
  const out: string[] = [];
  let line = '';
  const push = () => {
    if (line) out.push(line);
    line = '';
  };
  for (const word of text.split(/\s+/).filter(Boolean)) {
    const trial = line ? `${line} ${word}` : word;
    if (font.widthOfTextAtSize(trial, size) <= maxWidth) {
      line = trial;
      continue;
    }
    push();
    if (font.widthOfTextAtSize(word, size) <= maxWidth) {
      line = word;
      continue;
    }
    // hard-break a too-long token
    let chunk = '';
    for (const ch of word) {
      if (font.widthOfTextAtSize(chunk + ch, size) <= maxWidth) chunk += ch;
      else {
        if (chunk) out.push(chunk);
        chunk = ch;
      }
    }
    line = chunk;
  }
  push();
  return out;
}

/**
 * Take as many leading `words` as fit ONE line of `maxWidth`, and return the
 * line plus the unconsumed words. A single word wider than maxWidth is
 * hard-broken so a line NEVER exceeds its own box's width — the value can only
 * overflow to a continuation page, never past a box edge over the form.
 */
export function packLine(
  words: string[],
  font: PDFFont,
  size: number,
  maxWidth: number,
): { line: string; rest: string[] } {
  let line = '';
  let i = 0;
  for (; i < words.length; i += 1) {
    const word = words[i]!;
    const trial = line ? `${line} ${word}` : word;
    if (font.widthOfTextAtSize(trial, size) <= maxWidth) {
      line = trial;
      continue;
    }
    if (line) break; // this word starts the next line
    // first word alone is too wide — hard-break it
    let chunk = '';
    for (const ch of word) {
      if (font.widthOfTextAtSize(chunk + ch, size) <= maxWidth) chunk += ch;
      else break;
    }
    // A box too narrow for even one character holds NOTHING — return an empty
    // line so the caller overflows the value rather than drawing past the edge.
    if (!chunk) return { line: '', rest: words };
    return { line: chunk, rest: [word.slice(chunk.length), ...words.slice(i + 1)] };
  }
  return { line, rest: words.slice(i) };
}

/** draw one line into a box, baseline near the box's text row */
function drawInBox(page: ReturnType<PDFDocument['getPage']>, font: PDFFont, box: DetectedBox, text: string, size: number): void {
  const baseline = box.y + Math.max(2, (box.h - size) / 2) + size * 0.12;
  page.drawText(text, { x: box.x + PAD, y: baseline, size, font, color: INK });
}

export async function fillDetectedForm(input: FillDetectedInput): Promise<FillDetectedResult> {
  const doc = await PDFDocument.load(input.originalPdf);
  const font = await doc.embedFont(StandardFonts.Helvetica);
  const fontBold = await doc.embedFont(StandardFonts.HelveticaBold);
  const pages = doc.getPages();

  const overflowed: FillDetectedResult['overflowed'] = [];
  const continuation: Array<{ label: string; lines: string[] }> = [];
  let filledFields = 0;

  for (const field of input.fields) {
    const value = (input.values.get(field.id) ?? '').trim();
    if (!value) continue;
    const textBoxes = field.boxes.filter((b) => b.type === 'TextBox');
    if (textBoxes.length === 0) continue;

    const page = pages[field.page];
    if (!page) continue;

    const size = fontSizeFor(Math.min(...textBoxes.map((b) => b.h)));

    // Fill each box using ITS OWN width, top box first, so a wrapped line can
    // never exceed the box it is drawn into (the value overflows to the
    // continuation page, never past a box edge over the form).
    const boxesTopDown = [...textBoxes].sort((a, b) => b.y - a.y);
    let words = value.split(/\s+/).filter(Boolean);
    for (const box of boxesTopDown) {
      if (words.length === 0) break;
      // pack to the box's OWN interior width — no floor, so a line can never be
      // wider than the box it is drawn into (a too-narrow box packs nothing and
      // the value overflows to the continuation page, never over the form).
      const { line, rest } = packLine(words, font, size, box.w - PAD * 2);
      if (line) drawInBox(page, font, box, line, size);
      words = rest;
    }
    filledFields += 1;

    if (words.length > 0) {
      const remainder = words.join(' ');
      const widest = Math.max(...boxesTopDown.map((b) => b.w)) - PAD * 2;
      const restLines = wrap(remainder, font, size, Math.max(20, widest)).length;
      overflowed.push({ id: field.id, label: field.label || field.id, lines: restLines });
      continuation.push({ label: field.label || field.id, lines: [remainder] });
    }
  }

  if (continuation.length > 0) {
    drawContinuation(doc, font, fontBold, continuation);
  }

  // ⚠️ useObjectStreams:false is LOAD-BEARING — pdf-lib's default xref stream
  // renders WHITE in some viewers on ReportLab-origin PDFs (see PDF-native fill).
  const pdf = await doc.save({ useObjectStreams: false });
  return { pdf, overflowed, filledFields };
}

function drawContinuation(
  doc: PDFDocument,
  font: PDFFont,
  fontBold: PDFFont,
  sections: Array<{ label: string; lines: string[] }>,
): void {
  const first = doc.getPage(0);
  const { width, height } = first.getSize();
  let page = doc.addPage([width, height]);
  let y = height - MARGIN;
  const lh = 14;

  page.drawText('Continued', { x: MARGIN, y, size: 12, font: fontBold, color: INK });
  y -= lh * 1.6;

  const maxW = width - MARGIN * 2;
  for (const s of sections) {
    if (y < MARGIN + lh * 2) {
      page = doc.addPage([width, height]);
      y = height - MARGIN;
    }
    page.drawText(s.label, { x: MARGIN, y, size: 10, font: fontBold, color: INK });
    y -= lh;
    for (const raw of s.lines) {
      for (const line of wrap(raw, font, 10, maxW)) {
        if (y < MARGIN) {
          page = doc.addPage([width, height]);
          y = height - MARGIN;
        }
        page.drawText(line, { x: MARGIN, y, size: 10, font, color: INK });
        y -= lh;
      }
    }
    y -= lh * 0.5;
  }
}
