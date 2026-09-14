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

import { extractRuleSegments, type RuleSegment } from './pdf-geometry';

export type { RuleSegment } from './pdf-geometry';

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

/** One reconstructed line WITH its geometry — the unit the affordance annotator
 *  reasons over (ruling #320). `x0`/`x1` are the line's horizontal extent, `y`
 *  its anchor baseline (topmost item), `height` its tallest item. */
export interface LineBox {
  text: string;
  page: number;
  y: number;
  x0: number;
  x1: number;
  height: number;
}

/**
 * Group positioned text tokens into reconstructed lines WITH geometry, in reading
 * order. PURE. Order: page ascending, then `y` DESCENDING (top-to-bottom), then
 * `x` ascending (left-to-right). Items whose baselines fall within a
 * height-relative tolerance are one line; the line's `y` anchor is its first
 * (topmost) item and does not drift, so a subscript/superscript does not split
 * the line. Tokens are joined with single spaces and collapsed.
 */
/** A token's estimated RIGHT edge. `x` is its LEFT edge and pdfjs does not expose
 *  per-token advance here, so width is approximated from character count × a
 *  fraction of height. A slight under/over-estimate is harmless — the empty-span
 *  and column-gap tests both use generous thresholds. */
function estRight(it: PlacedItem): number {
  return it.x + Math.max(it.str.length * (it.height || 10) * 0.5, it.height || 10);
}

// A column boundary is a gap wider than this MULTIPLE of the line height — well
// above a word space (~0.25×) and below a typical gutter (~1×+). Height-relative,
// not an absolute pt floor: an absolute 48pt missed a real ~1×-height gutter and
// FUSED the two fields into one line S1 then parsed as ZERO controls, losing both
// (adversarial pass, 2026-09-14).
const COLUMN_GAP_FACTOR = 0.8;

/** Has this segment reached a COMPLETED field — a colon label, a bare marker
 *  slot, or a label whose underscore blank has been consumed ("Name: ____")? A
 *  following gap after a completed field is a column gutter, not intra-label
 *  spacing. */
function isFieldBoundary(text: string): boolean {
  const t = text.trim();
  return /:$/.test(t) || PDF_MARKER_ONLY_RE.test(t) || /_{2,}\s*$/.test(t);
}

/** Does the next token BELONG to the current field (its underscore blank) rather
 *  than start a NEW column? "Name: ____" — the "____" is Name's blank, so the row
 *  must NOT split there (it is one field, not two columns). */
function isTrailingBlank(str: string): boolean {
  return /^\s*_{2,}/.test(str);
}

/**
 * Split one row's items into READING-ORDER columns (ruling #320: "two-column rows
 * yield two controls in reading order"). Splits at an internal gap wider than
 * `COLUMN_GAP_FACTOR × height` where the LEFT side is a completed field AND the
 * NEXT token starts a NEW field (not this field's own underscore blank). So
 * "PATIENT NAME: ____   DOB: ____" and "DD:  DT:" and "1.  2." split into two,
 * while "Name: ______" (label + its blank) and "DATE OF SURGERY:" (one wide
 * label) stay whole. Splitting reliably is what stops a fused multi-colon line
 * reaching S1, which parses it as zero controls (its label class excludes ':').
 */
function splitRowIntoColumns(sortedItems: PlacedItem[]): PlacedItem[][] {
  const cols: PlacedItem[][] = [];
  let seg: PlacedItem[] = [];
  for (let i = 0; i < sortedItems.length; i += 1) {
    seg.push(sortedItems[i]);
    const next = sortedItems[i + 1];
    if (!next) break;
    const gap = next.x - estRight(sortedItems[i]);
    const threshold = (sortedItems[i].height || 10) * COLUMN_GAP_FACTOR;
    const leftText = seg.map((s) => s.str).join(' ').replace(/\s+/g, ' ').trim();
    if (gap >= threshold && isFieldBoundary(leftText) && !isTrailingBlank(next.str)) {
      cols.push(seg);
      seg = [];
    }
  }
  if (seg.length) cols.push(seg);
  return cols.length ? cols : [sortedItems];
}

export function groupLineBoxes(items: PlacedItem[]): LineBox[] {
  const usable = items.filter((it) => it.str && it.str.trim().length > 0);
  if (usable.length === 0) return [];
  const sorted = [...usable].sort(
    (a, b) => a.page - b.page || b.y - a.y || a.x - b.x,
  );
  const boxes: LineBox[] = [];
  let cur: PlacedItem[] = [];
  let curPage = sorted[0].page;
  let curY = sorted[0].y;

  const flush = (): void => {
    if (cur.length === 0) return;
    cur.sort((a, b) => a.x - b.x);
    // Reading-order columns: a single-column row yields one group; a two-column
    // header yields two, left then right (ruling #320).
    for (const col of splitRowIntoColumns(cur)) {
      const text = col.map((i) => i.str).join(' ').replace(/\s+/g, ' ').trim();
      if (!text) continue;
      boxes.push({
        text,
        page: curPage,
        y: curY,
        x0: Math.min(...col.map((i) => i.x)),
        x1: Math.max(...col.map(estRight)),
        height: Math.max(...col.map((i) => i.height || 10)),
      });
    }
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
  return boxes;
}

/**
 * Reconstruct the form's visible lines (text only), in reading order. PURE, and
 * the thin string projection of `groupLineBoxes` — one reader of the grouping so
 * geometry and text can never disagree.
 */
export function reconstructLines(items: PlacedItem[]): string[] {
  return groupLineBoxes(items).map((b) => b.text);
}

// ── RULING #320 — the union blank-affordance annotation ────────────────────
// A line already carrying a real underscore run flows through S1 untouched. For a
// line that does NOT, we APPEND a synthetic underscore run iff the geometry proves
// a blank: (a) it is a colon label or a bare numbered/bulleted slot AND has an
// empty writable span (rest of row to the right margin, or a big gap to the next
// line); OR (b) a VISIBLE drawn rule line follows the label on its row or the row
// below. S1 then derives exactly one control per annotated line, and S1's own
// label-shape guards + the keystone re-compile backstop precision.

const SPAN_MARGIN = 40; // pt of empty width to the right that counts as "writable"
const GAP_LINES = 1.9; // a vertical gap > this × line-height is a writing area below
const AFFORDANCE = ' ______'; // the materialised blank S1 consumes (>= 2 underscores)

/** A leading list/enumeration marker (digit/bracket/bullet/checkbox) FOLLOWED by
 *  label text — the SAME set S1 strips, so a `1. Primary Dx:` slot is recognised
 *  identically on both sides. Single letters are deliberately excluded (they
 *  collide with clinical shorthand — "T. Bili", "(R) Knee"). */
const PDF_LEADING_MARKER_RE =
  /^\s*(?:[-*•▪◦·‣⁃>|]+|[([]?\d{1,3}[.)\]]|[☐☑☒□■▢◻◼✓✔])\s+/;

/** A line that is ONLY a list/enumeration marker — a bare `1.`, `2)`, `•`, `☐` —
 *  the numbered fill SLOTS of an operative note (Findings 1–3). ⚠️ No trailing
 *  `\s+` here (the marker is the WHOLE line, nothing follows), which is exactly
 *  why `PDF_LEADING_MARKER_RE` alone missed them. Single letters stay excluded. */
const PDF_MARKER_ONLY_RE =
  /^\s*(?:[-*•▪◦·‣⁃>|]+|[([]?\d{1,3}[.)\]]|[☐☑☒□■▢◻◼✓✔])\s*$/;

/** A colon-terminated line that is a LEAD-IN SENTENCE, not a fill label — its
 *  value is the prose/list BELOW, not an inline slot ("Findings were as follows:",
 *  "The following were noted:"). ⚠️ THIS GUARD EXISTS BECAUSE #320 MANUFACTURES
 *  THE AFFORDANCE S1's own fix relied on: S1 left a bare `LABEL:` as prose, but
 *  the annotator appends underscores, and S1's ≤48-char label guard does NOT
 *  reject a short sentence (adversarial pass, 2026-09-14). A sentence carries a
 *  finite verb / connective a noun-phrase form label does not — that is the tell.
 *  The set is TIGHT (clear sentence words that never appear in a form label);
 *  "Performed", "Reviewed", "Diagnosis" stay label words. */
const SENTENCE_MARKER_RE = /\b(?:was|were|is|are|am|be|been|being|following|follows|then)\b/i;
function looksLikeSentence(phrase: string): boolean {
  return SENTENCE_MARKER_RE.test(phrase) || phrase.split(/\s+/).filter(Boolean).length > 8;
}

/** Does this line, on its own text, look like a label/slot that WANTS a blank —
 *  i.e. it is a bare numbered/bullet slot (`1.`), or after dropping one leading
 *  marker it ends with a colon AND reads as a label (noun phrase), not a lead-in
 *  sentence? A title/sentence without a trailing colon never qualifies. */
function wantsBlank(text: string): boolean {
  const t = text.trim();
  if (!t) return false;
  if (PDF_MARKER_ONLY_RE.test(t)) return true; // bare "1." / "•" slot
  const afterMarker = t.replace(PDF_LEADING_MARKER_RE, '').trim();
  if (!/:$/.test(afterMarker)) return false; // must be colon-terminated
  return !looksLikeSentence(afterMarker.replace(/:$/, '').trim()); // …and not a sentence
}

/** Already carries a real fill affordance (underscore run) — leave it for S1. */
function hasTextAffordance(text: string): boolean {
  return /_{2,}/.test(text);
}

/** A colon-LESS line that still reads as a fill LABEL (for branch (b): a drawn
 *  rule line following it is the affordance). Starts with a letter, is short (S1's
 *  own label cap), and is not a lead-in sentence. A colon label is handled by
 *  `wantsBlank`, so this is the no-colon case only. */
function isLabelShaped(text: string): boolean {
  const t = text.trim().replace(PDF_LEADING_MARKER_RE, '').trim();
  return /^[A-Za-z]/.test(t) && t.length <= 48 && !looksLikeSentence(t);
}

/**
 * Annotate reconstructed line-boxes with materialised blank affordances per
 * ruling #320. PURE. `pageWidth(page)` gives the page's width in the same units
 * as the boxes' x; `segments` are visible drawn rule lines (may be empty).
 * Returns the line TEXTS in reading order, with ` ______` appended where a blank
 * was proven — the input to `linesToProseDocx` → `deriveProseTwin`.
 */
export function annotateAffordances(
  boxes: LineBox[],
  segments: ReadonlyArray<RuleSegment>,
  pageWidth: (page: number) => number,
): string[] {
  if (boxes.length === 0) return [];
  // Per-page left margin (min x0) → right writable edge R = pageWidth − margin.
  const leftMargin = new Map<number, number>();
  for (const b of boxes) {
    const cur = leftMargin.get(b.page);
    if (cur === undefined || b.x0 < cur) leftMargin.set(b.page, b.x0);
  }

  return boxes.map((b, i) => {
    if (hasTextAffordance(b.text)) return b.text; // already has a real underscore run — S1 owns it

    const next = i + 1 < boxes.length && boxes[i + 1].page === b.page ? boxes[i + 1] : null;

    // A visible rule line on this line's row (right of the label) or on the row
    // just below it — branch (b). `y` is baseline (up), so "below" is a smaller y.
    const lowerY = next ? next.y : b.y - (b.height || 10) * 3;
    const hasDrawnLine = segments.some(
      (s) =>
        s.page === b.page &&
        s.x1 > b.x1 + 2 &&
        s.y <= b.y + (b.height || 10) &&
        s.y >= lowerY - (b.height || 10),
    );

    if (wantsBlank(b.text)) {
      // Branch (a): a colon/marker label with an empty writable span — same-row
      // to the right margin, or a big gap to the next line — OR a drawn line.
      const margin = leftMargin.get(b.page) ?? 0;
      const hasSameRowSpan = pageWidth(b.page) - margin - b.x1 >= SPAN_MARGIN;
      const hasNextLineGap = next !== null && b.y - next.y > (b.height || 10) * GAP_LINES;
      return hasSameRowSpan || hasNextLineGap || hasDrawnLine ? b.text + AFFORDANCE : b.text;
    }

    // Branch (b) for a COLON-LESS label: a drawn rule line following a
    // label-shaped line IS the affordance ("Weight ____line____"). The line is the
    // signal; a title/sentence is excluded by isLabelShaped, and S1's colon-less
    // form still requires the appended blank to END the line.
    if (hasDrawnLine && isLabelShaped(b.text)) return b.text + AFFORDANCE;
    return b.text;
  });
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

/** Page widths from a pdfjs proxy, keyed 0-based (matching PlacedItem.page). */
async function pageWidths(proxy: PdfjsProxy): Promise<Map<number, number>> {
  const widths = new Map<number, number>();
  for (let p = 1; p <= proxy.numPages; p++) {
    const page = await proxy.getPage(p);
    widths.set(p - 1, page.getViewport({ scale: 1 }).width);
  }
  return widths;
}

/**
 * Extract the form's prose lines from a pdfjs proxy, WITH ruling #320 blank
 * affordances materialised. Returns null when the PDF carries no text layer
 * (scanned / image-only — ruling S2-2, fail safe). Proxy in (not raw bytes) so
 * the unpdf import stays at the I/O boundary and this is testable with a
 * pdf-lib-built fixture. `segments` (visible drawn rule lines) is injected so the
 * pure annotation stays unit-testable; the real caller extracts them.
 */
export async function extractProseLinesFromProxy(
  proxy: PdfjsProxy,
  segments: ReadonlyArray<RuleSegment> = [],
): Promise<string[] | null> {
  const boxes = groupLineBoxes(await placedItems(proxy));
  if (boxes.length === 0) return null;
  const widths = await pageWidths(proxy);
  return annotateAffordances(boxes, segments, (page) => widths.get(page) ?? 612);
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
  // Branch (b): visible drawn rule lines, fail-safe to none (branch (a) covers a
  // text-labelled form on its own — the owner's file has no visible lines).
  const segments = await extractRuleSegments(proxy as unknown as Parameters<typeof extractRuleSegments>[0]);
  const lines = await extractProseLinesFromProxy(proxy, segments);
  if (!lines) return null; // no text layer — scanned, out of scope (ruling S2-2)
  return linesToProseDocx(lines);
}
