// ============================================================================
// PDF native fill engine (feat/pdf-native-fill, 2026-07-23).
// ----------------------------------------------------------------------------
// Draws generated answers into the BLANK REGIONS of the doctor's OWN flat PDF
// template — the original page bytes are the export background, never altered.
// PHI-safe + deterministic: no AI here; it consumes already-resolved text +
// pre-extracted anchors (label position + the blank region below/beside it).
//
// Rules (per spec):
//  - font matched to the form (Arial family → Helvetica, metric-compatible),
//    left-aligned, drawn under/into the region.
//  - overflow: shrink-to-fit down to a readable floor (MIN_PT). Past that, the
//    region shows the lead text + " (continued)" and the remainder flows to an
//    APPENDED continuation page carrying the section label — never a silent
//    truncation, never drawn over the form's own ink (clipped to the region).
//  - unfilled sections: nothing drawn (the form's blank space IS the honest
//    blank; no "Not documented." stamped on his page).
//  - signed-status line: small, in the bottom page margin, not over his layout.
// ============================================================================
import { PDFDocument, StandardFonts, rgb, type PDFFont, type PDFPage } from 'pdf-lib';

/** A fillable region on a template page: the label's position + the blank area
 *  to draw into (PDF user space, origin bottom-left). Produced by the anchor
 *  extractor at certify time, stored, and re-derivable — never client-trusted. */
export interface PdfFillAnchor {
  /** Section/header-field key (matches the text map + continuation heading). */
  key: string;
  /** The doctor's own label text — used ONLY for the continuation-page heading;
   *  it is already printed on his form, so the engine never redraws it. */
  label: string;
  /** 0-based page index the region lives on. */
  page: number;
  /** Left edge of the fill region. */
  x: number;
  /** Top of the region (just below the label) — text starts here, going down. */
  yTop: number;
  /** Bottom of the region — text must not cross below this (next label / margin). */
  yBottom: number;
  /** Region width; text wraps within it. */
  width: number;
  /** The form's label font size (pt) — the fill matches it as a starting size. */
  fontSize: number;
}

export interface PdfFillInput {
  /** The doctor's ORIGINAL template PDF bytes — the verbatim canvas. */
  canvasPdf: Uint8Array;
  /** Fill regions, in reading order. */
  anchors: readonly PdfFillAnchor[];
  /** key → the text to draw. A key absent / mapped to '' is left blank. */
  texts: Readonly<Record<string, string>>;
  /** Small signed-status line for the bottom margin (optional). */
  signedStatusLine?: string | null;
}

const MIN_PT = 8; // readable floor for shrink-to-fit
const DEFAULT_PT = 10;
const LINE_GAP = 1.18; // line-height multiplier
const REGION_PAD = 2; // pt inset so fill never kisses the form ink
const CONTINUED = ' (continued)';

/** Greedy word-wrap: returns the lines that fit within `maxWidth` at `size`. */
function wrapLines(text: string, font: PDFFont, size: number, maxWidth: number): string[] {
  const out: string[] = [];
  for (const rawLine of text.split('\n')) {
    if (rawLine.trim() === '') {
      out.push('');
      continue;
    }
    let line = '';
    for (const word of rawLine.split(/\s+/)) {
      const trial = line ? `${line} ${word}` : word;
      if (font.widthOfTextAtSize(trial, size) <= maxWidth || !line) {
        line = trial;
      } else {
        out.push(line);
        line = word;
      }
    }
    if (line) out.push(line);
  }
  return out;
}

/** How many lines fit vertically in a region of the given height at `size`. */
function linesThatFit(regionHeight: number, size: number): number {
  const lineH = size * LINE_GAP;
  return Math.max(0, Math.floor(regionHeight / lineH));
}

interface Overflow {
  key: string;
  label: string;
  text: string;
}

/** Draw one region's text; return an Overflow if the remainder must continue. */
function drawRegion(
  page: PDFPage,
  font: PDFFont,
  anchor: PdfFillAnchor,
  text: string
): Overflow | null {
  const x = anchor.x + REGION_PAD;
  const maxWidth = Math.max(1, anchor.width - REGION_PAD * 2);
  const regionHeight = Math.max(0, anchor.yTop - anchor.yBottom - REGION_PAD);

  // Shrink-to-fit: from the form's size down to MIN_PT, pick the largest size at
  // which ALL lines fit; if none fits (even at MIN_PT), we overflow at MIN_PT.
  let size = Math.max(MIN_PT, Math.min(anchor.fontSize || DEFAULT_PT, 14));
  let lines = wrapLines(text, font, size, maxWidth);
  while (size > MIN_PT && lines.length > linesThatFit(regionHeight, size)) {
    size -= 0.5;
    lines = wrapLines(text, font, size, maxWidth);
  }

  const capacity = linesThatFit(regionHeight, size);
  let overflow: Overflow | null = null;
  let drawn = lines;

  if (lines.length > capacity) {
    // Reserve the last visible line for the lead text + "(continued)".
    const keep = Math.max(1, capacity);
    drawn = lines.slice(0, keep);
    // Append the continued marker to the last kept line if it fits; else replace.
    const last = drawn[keep - 1] ?? '';
    const withMark = `${last}${CONTINUED}`;
    drawn[keep - 1] =
      font.widthOfTextAtSize(withMark, size) <= maxWidth ? withMark : CONTINUED.trim();
    // The remainder (from the first not-drawn line) flows to a continuation page.
    const remainder = lines.slice(keep).join(' ').trim();
    if (remainder) overflow = { key: anchor.key, label: anchor.label, text: remainder };
  }

  const lineH = size * LINE_GAP;
  let y = anchor.yTop - size; // baseline of the first line
  for (const line of drawn) {
    if (y < anchor.yBottom) break; // hard clip — never cross the region floor
    if (line) page.drawText(line, { x, y, size, font, color: rgb(0.1, 0.12, 0.14) });
    y -= lineH;
  }
  return overflow;
}

/** Append continuation page(s) for regions that overflowed, each headed by the
 *  section label, in a single readable column. */
function drawContinuationPages(
  doc: PDFDocument,
  font: PDFFont,
  fontBold: PDFFont,
  overflows: Overflow[]
): void {
  if (overflows.length === 0) return;
  const PAGE_W = 612;
  const PAGE_H = 792; // Letter
  const M = 54;
  const maxWidth = PAGE_W - M * 2;
  let page = doc.addPage([PAGE_W, PAGE_H]);
  let y = PAGE_H - M;

  const ensureRoom = (needed: number) => {
    if (y - needed < M) {
      page = doc.addPage([PAGE_W, PAGE_H]);
      y = PAGE_H - M;
    }
  };

  page.drawText('CONTINUATION', { x: M, y, size: 9, font: fontBold, color: rgb(0.4, 0.4, 0.4) });
  y -= 20;

  for (const ov of overflows) {
    ensureRoom(40);
    page.drawText(ov.label, { x: M, y, size: 11, font: fontBold, color: rgb(0.1, 0.12, 0.14) });
    y -= 16;
    for (const line of wrapLines(ov.text, font, 10, maxWidth)) {
      ensureRoom(14);
      if (line) page.drawText(line, { x: M, y, size: 10, font, color: rgb(0.1, 0.12, 0.14) });
      y -= 12;
    }
    y -= 10;
  }
}

/** Fill the doctor's template PDF with the resolved texts. Returns new PDF bytes;
 *  the original page content is preserved verbatim (only overlays + appended
 *  continuation pages are added). */
export async function fillPdfTemplate(input: PdfFillInput): Promise<Uint8Array> {
  const doc = await PDFDocument.load(input.canvasPdf);
  const font = await doc.embedFont(StandardFonts.Helvetica);
  const fontBold = await doc.embedFont(StandardFonts.HelveticaBold);
  const pages = doc.getPages();
  const overflows: Overflow[] = [];

  for (const anchor of input.anchors) {
    const text = (input.texts[anchor.key] ?? '').trim();
    if (!text) continue; // unfilled → leave his blank space blank
    const page = pages[anchor.page];
    if (!page) continue;
    const ov = drawRegion(page, font, anchor, text);
    if (ov) overflows.push(ov);
  }

  drawContinuationPages(doc, font, fontBold, overflows);

  // Signed-status line in the bottom margin of page 1 — small, out of the layout.
  if (input.signedStatusLine && pages[0]) {
    const p0 = pages[0];
    p0.drawText(input.signedStatusLine, {
      x: 54,
      y: 24,
      size: 7,
      font,
      color: rgb(0.5, 0.5, 0.5),
    });
  }

  return doc.save();
}
