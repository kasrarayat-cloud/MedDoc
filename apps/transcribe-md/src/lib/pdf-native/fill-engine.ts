// ============================================================================
// PDF native fill engine (feat/pdf-native-fill, 2026-07-23).
// ----------------------------------------------------------------------------
// Draws generated answers into the BLANK REGIONS of the doctor's OWN flat PDF
// template — the original page bytes are the export background, never altered.
// PHI-safe + deterministic: no AI; consumes already-resolved text + pre-extracted
// anchors (label position + the blank region to its right/below).
//
// HANGING-INDENT model (matches real operative-note forms): the answer's first
// line starts to the RIGHT of the printed label (on the label's baseline);
// continuation lines wrap BELOW at the region's left edge, down to the next
// label. A short header field is just a one-line region to the right of its
// label. Rules: font matched to the form (Helvetica ≈ Arial), left-aligned;
// shrink-to-fit to an 8pt floor; overflow → lead text + " (continued)" and the
// remainder flows to an APPENDED continuation page carrying the section label
// (never silent truncation, never below the region floor / over the form ink);
// unfilled regions left blank; signed-status line small in the bottom margin.
// ============================================================================
import { PDFDocument, StandardFonts, rgb, type PDFFont, type PDFPage } from 'pdf-lib';

/** A fillable region: where the answer's first line starts (right of the label)
 *  and how it wraps below. PDF user space, origin bottom-left. Produced by the
 *  anchor extractor at certify time; stored; re-derivable; never client-trusted. */
export interface PdfFillAnchor {
  /** Section/header-field key (matches the text map + continuation heading). */
  key: string;
  /** The doctor's own label text — used ONLY for the continuation-page heading;
   *  already printed on his form, so the engine never redraws it. */
  label: string;
  /** 0-based page index. */
  page: number;
  /** Baseline y of the first line (= the label's baseline). */
  yTop: number;
  /** Text must never cross below this (next label / margin). */
  yBottom: number;
  /** X where the FIRST line starts — just past the printed label. */
  firstLineX: number;
  /** X where wrapped continuation lines start (left edge of the region). */
  wrapX: number;
  /** Right boundary for wrapping (page width − right margin). */
  rightEdge: number;
  /** The form's label font size (pt) — the fill matches it as the starting size. */
  fontSize: number;
}

export interface PdfFillInput {
  /** The doctor's ORIGINAL template PDF bytes — the verbatim canvas. */
  canvasPdf: Uint8Array;
  /** Fill regions, in reading order. */
  anchors: readonly PdfFillAnchor[];
  /** key → the text to draw. A key absent / mapped to '' is left blank. */
  texts: Readonly<Record<string, string>>;
  /** Note sections with content but NO region on the form — rendered on a labeled
   *  "Additional documentation" continuation page (never dropped, never over his
   *  ink). Distinct from `(continued)` overflow of an anchored region. */
  addenda?: ReadonlyArray<{ label: string; text: string }>;
  /** Small signed-status line for the bottom margin (optional). */
  signedStatusLine?: string | null;
}

const MIN_PT = 8;
const DEFAULT_PT = 11;
const LINE_GAP = 1.2;
const CONTINUED = ' (continued)';
const INK = rgb(0.1, 0.12, 0.14);

/** Greedy wrap where the FIRST line has `firstWidth` and the rest `restWidth`
 *  (hanging indent). Honors explicit newlines. */
function wrapHanging(
  text: string,
  font: PDFFont,
  size: number,
  firstWidth: number,
  restWidth: number
): string[] {
  const out: string[] = [];
  const widthFor = (i: number) => (out.length === 0 && i === 0 ? firstWidth : restWidth);
  for (const rawLine of text.split('\n')) {
    if (rawLine.trim() === '') {
      out.push('');
      continue;
    }
    let line = '';
    for (const word of rawLine.split(/\s+/)) {
      const trial = line ? `${line} ${word}` : word;
      const w = out.length === 0 ? firstWidth : restWidth;
      if (font.widthOfTextAtSize(trial, size) <= w || !line) {
        line = trial;
      } else {
        out.push(line);
        line = word;
      }
    }
    if (line) out.push(line);
  }
  void widthFor;
  return out;
}

function capacity(yTop: number, yBottom: number, size: number): number {
  return Math.max(1, Math.floor((yTop - yBottom) / (size * LINE_GAP)) + 1);
}

interface Overflow {
  key: string;
  label: string;
  text: string;
}

function drawRegion(page: PDFPage, font: PDFFont, a: PdfFillAnchor, text: string): Overflow | null {
  const firstWidth = Math.max(1, a.rightEdge - a.firstLineX);
  const restWidth = Math.max(1, a.rightEdge - a.wrapX);

  // Shrink-to-fit: from the form's size down to MIN_PT, largest size where all
  // lines fit vertically; if none fits even at MIN_PT, overflow at MIN_PT.
  let size = Math.max(MIN_PT, Math.min(a.fontSize || DEFAULT_PT, 12));
  let lines = wrapHanging(text, font, size, firstWidth, restWidth);
  while (size > MIN_PT && lines.length > capacity(a.yTop, a.yBottom, size)) {
    size -= 0.5;
    lines = wrapHanging(text, font, size, firstWidth, restWidth);
  }

  const cap = capacity(a.yTop, a.yBottom, size);
  let drawn = lines;
  let overflow: Overflow | null = null;
  if (lines.length > cap) {
    const keep = Math.max(1, cap);
    const last = lines[keep - 1] ?? '';
    const withMark = `${last}${CONTINUED}`;
    const wLast = keep === 1 ? firstWidth : restWidth;
    if (font.widthOfTextAtSize(withMark, size) <= wLast) {
      // The marker fits beside the last kept line — append it; overflow is the rest.
      drawn = lines.slice(0, keep);
      drawn[keep - 1] = withMark;
      const remainder = lines.slice(keep).join(' ').trim();
      if (remainder) overflow = { key: a.key, label: a.label, text: remainder };
    } else {
      // ⚠️ THE MARKER DOES NOT FIT — DO NOT DISCARD THE LINE IT WOULD REPLACE.
      // The old code set the last kept line to a bare "(continued)" AND started
      // the remainder AFTER it, so that line's clinical text vanished from the
      // page AND the continuation (adversarial pass, 2026-09-15). Instead keep a
      // bare "(continued)" pointer and push that line's text into the OVERFLOW,
      // so nothing is dropped.
      drawn = lines.slice(0, keep - 1);
      drawn.push(CONTINUED.trim());
      const remainder = lines.slice(keep - 1).join(' ').trim();
      if (remainder) overflow = { key: a.key, label: a.label, text: remainder };
    }
  }

  const lineH = size * LINE_GAP;
  drawn.forEach((line, i) => {
    const y = a.yTop - i * lineH;
    if (y < a.yBottom - 0.01) return; // hard clip at the region floor
    const x = i === 0 ? a.firstLineX : a.wrapX;
    if (line) page.drawText(line, { x, y, size, font, color: INK });
  });
  return overflow;
}

/** Append one or more letter-size pages titled `title`, listing `{label,text}`
 *  blocks. Used for both region overflow ("CONTINUATION") and off-form note
 *  sections ("ADDITIONAL DOCUMENTATION"). */
function drawAppendedSection(
  doc: PDFDocument,
  font: PDFFont,
  fontBold: PDFFont,
  title: string,
  subtitle: string | null,
  items: ReadonlyArray<{ label: string; text: string }>
): void {
  if (items.length === 0) return;
  const W = 612;
  const H = 792;
  const M = 54;
  const maxWidth = W - M * 2;
  let page = doc.addPage([W, H]);
  let y = H - M;
  const room = (n: number) => {
    if (y - n < M) {
      page = doc.addPage([W, H]);
      y = H - M;
    }
  };
  page.drawText(title, { x: M, y, size: 9, font: fontBold, color: rgb(0.4, 0.4, 0.4) });
  y -= subtitle ? 13 : 22;
  if (subtitle) {
    page.drawText(subtitle, { x: M, y, size: 8, font, color: rgb(0.5, 0.5, 0.5) });
    y -= 16;
  }
  for (const it of items) {
    room(40);
    page.drawText(it.label, { x: M, y, size: 11, font: fontBold, color: INK });
    y -= 16;
    for (const line of wrapHanging(it.text, font, 10, maxWidth, maxWidth)) {
      room(14);
      if (line) page.drawText(line, { x: M, y, size: 10, font, color: INK });
      y -= 12;
    }
    y -= 10;
  }
}

/** Fill the doctor's template PDF. Returns new PDF bytes; the original page
 *  content is preserved verbatim (only overlays + appended continuation pages). */
export async function fillPdfTemplate(input: PdfFillInput): Promise<Uint8Array> {
  const doc = await PDFDocument.load(input.canvasPdf);
  const font = await doc.embedFont(StandardFonts.Helvetica);
  const fontBold = await doc.embedFont(StandardFonts.HelveticaBold);
  const pages = doc.getPages();
  const overflows: Overflow[] = [];

  for (const a of input.anchors) {
    const text = (input.texts[a.key] ?? '').trim();
    if (!text) continue; // unfilled → leave his blank space blank
    const page = pages[a.page];
    if (!page) continue;
    const ov = drawRegion(page, font, a, text);
    if (ov) overflows.push(ov);
  }

  drawAppendedSection(doc, font, fontBold, 'CONTINUATION', null, overflows);
  drawAppendedSection(
    doc,
    font,
    fontBold,
    'ADDITIONAL DOCUMENTATION',
    'Sections from this note that are not fields on the original form.',
    input.addenda ?? []
  );

  if (input.signedStatusLine && pages[0]) {
    pages[0].drawText(input.signedStatusLine, { x: 54, y: 22, size: 7, font, color: rgb(0.5, 0.5, 0.5) });
  }

  // ⚠️ useObjectStreams: false is LOAD-BEARING, not a size preference.
  // pdf-lib's default save (useObjectStreams: true) writes a cross-reference
  // STREAM. When we APPEND a continuation page (drawAppendedSection → addPage)
  // to a template that ITSELF uses xref streams — which ReportLab-generated
  // forms do, e.g. the owner's Colonoscopy_Operative_Template.pdf — that save
  // emits a broken xref whose /Root reference resolves to a bad entry
  // ("Bad (uncompressed) XRef entry", "/Pages tree /Count: N"). The browser's
  // pdfjs cannot recover and paints a SOLID WHITE page (owner finding,
  // 2026-09-14). It is reproducible ONLY with the addPage step present: load +
  // draw + save is fine; load + draw + addPage + save corrupts. A classic xref
  // TABLE (useObjectStreams: false) is what every real PDF viewer reads without
  // recovery, so it is the correct serialisation for a document we hand to a
  // renderer — a slightly larger file for a PDF that actually opens. This
  // guards the SIGNED EXPORT too, not only the preview: any filled note whose
  // content overflowed onto a continuation page was shipping corrupt before.
  return doc.save({ useObjectStreams: false });
}
