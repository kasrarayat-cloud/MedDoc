// ============================================================================
// PDF generator (T-M7)
// ----------------------------------------------------------------------------
// Stays on node:22-alpine — no chromium, no base-image churn. pdfkit is
// pure JS, deterministic, ~2MB. The tradeoff is no HTML/CSS; we lay out
// the doc by hand with x/y coordinates. For a SOAP note that's
// strictly text + section headings, it's the right size tool.
// ============================================================================

import { join } from 'node:path';

import PDFDocument from 'pdfkit';

import {
  type VisitExportData,
  prescriptionOneLine,
  formatVisitDate,
  procedureProvenanceNote,
} from './visit-export';
import { formSignatureLines } from './form-only';
import { PAGE_PT, TYPE_PT } from './export-page';

// ---------------------------------------------------------------------------
// Font assets — bundled in apps/transcribe-md/fonts/ (committed to repo,
// COPY'd into the runner image by the Dockerfile). Charter is
// purpose-built for print at small sizes (Bitstream → Matthew
// Butterick); Inter Tight matches the marketing site's brand voice
// for labels + the QUILLMD wordmark.
//
// Path defaults to the absolute Docker path because both contexts
// that generate PDFs (the transcribe-md runner with WORKDIR /app and
// the db-migrate one-off with WORKDIR /app/packages/db) put the
// fonts at exactly /app/apps/transcribe-md/fonts. Override via
// PDF_FONTS_DIR env var for local dev where the path differs.
// ---------------------------------------------------------------------------

const FONTS_DIR =
  process.env.PDF_FONTS_DIR ?? '/app/apps/transcribe-md/fonts';

// ---------------------------------------------------------------------------
// Page + type tokens. Keeping them at module top so every helper reads
// from the same grid.
// ---------------------------------------------------------------------------

// C2-b: the page comes from `export-page.ts` so the Word file can be built
// from the SAME numbers. It was `size: 'LETTER'` here and nothing at all in the
// docx generator, which is how the preview ended up A4 while this stayed Letter.
const PAGE = {
  // US Letter (612 x 792 pts), 1" margins — expressed explicitly rather than by
  // pdfkit's 'LETTER' alias, so one module owns the number both sides read.
  size: [PAGE_PT.width, PAGE_PT.height] as [number, number],
  margin: PAGE_PT.margin,
};

const COLORS = {
  textPrimary: '#111111',
  textSecondary: '#333333',
  textMuted: '#666666',
  rule: '#dddddd',
  accent: '#7C3AED',
};

const FONTS = {
  // T-M21: replaced PDFKit's built-in Times-Roman / Helvetica with
  // Charter (body) + Inter Tight (labels + brand). Charter is tuned
  // for print at small sizes — exactly the PDF use case — while
  // Fraunces (the marketing display serif) is optical-size'd for
  // screen and would distort below 14pt. Inter Tight tracks the
  // marketing-site label font for visual continuity.
  bodyRegular:  'Charter',
  bodyBold:     'Charter-Bold',
  bodyItalic:   'Charter-Italic',
  labelRegular: 'InterTight',           // footer signed-by line
  labelBold:    'InterTight-SemiBold',  // section heads + per-row labels
  brand:        'InterTight-Medium',    // QUILLMD wordmark (header + watermark)
} as const;

const SIZE = {
  title: TYPE_PT.title,
  sectionHead: TYPE_PT.sectionHead,
  body: TYPE_PT.body,
  small: TYPE_PT.small,
  footer: TYPE_PT.footer,
};

// ---------------------------------------------------------------------------
// Public API — stream → Buffer so the route handler can drop it into a
// NextResponse body without waiting on file I/O.
// ---------------------------------------------------------------------------

export async function generateVisitPdf(
  data: VisitExportData
): Promise<Buffer> {
  const doc = new PDFDocument({
    size: PAGE.size,
    margins: {
      top: PAGE.margin,
      bottom: PAGE.margin,
      left: PAGE.margin,
      right: PAGE.margin,
    },
    info: {
      // /Info persists in every viewer (Preview, Acrobat, finder
      // previews, Spotlight) and survives forwarding — keep it
      // PHI-free. visitId is opaque; clinician name belongs in the
      // body footer, not metadata.
      Title: `Visit ${data.visitId}`,
      Author: 'QuillMD',
      Creator: 'QuillMD',
      Producer: 'QuillMD PDF Generator (pdfkit)',
    },
  });

  const chunks: Buffer[] = [];
  doc.on('data', (c: Buffer) => chunks.push(c));
  const done = new Promise<Buffer>((resolve, reject) => {
    doc.on('end', () => resolve(Buffer.concat(chunks)));
    doc.on('error', reject);
  });

  // T-M21: register the bundled font files BEFORE any renderer touches
  // them. The names on the left are the aliases used by `doc.font(…)`
  // throughout this module via the FONTS constant. The Dockerfile
  // copies apps/transcribe-md/fonts/ into /app at runner-stage build
  // time so the join(cwd, …) path resolves under the standalone
  // server's working directory.
  doc.registerFont(FONTS.bodyRegular,  join(FONTS_DIR, 'Charter-Regular.ttf'));
  doc.registerFont(FONTS.bodyBold,     join(FONTS_DIR, 'Charter-Bold.ttf'));
  doc.registerFont(FONTS.bodyItalic,   join(FONTS_DIR, 'Charter-Italic.ttf'));
  doc.registerFont(FONTS.labelRegular, join(FONTS_DIR, 'InterTight-Regular.ttf'));
  doc.registerFont(FONTS.labelBold,    join(FONTS_DIR, 'InterTight-SemiBold.ttf'));
  doc.registerFont(FONTS.brand,        join(FONTS_DIR, 'InterTight-Medium.ttf'));

  // T-M21 hot-fix: pdfkit's paragraph-finalize line advance pulls from
  // the TTF font's OS/2 ascent+descent. Charter reports ~0.74 × fontSize
  // (~7.8pt at body size 10.5) — much tighter than the ~1.2 × fontSize
  // (~12.6pt) that built-in Helvetica/Times produced. Without a
  // compensating gap, consecutive `doc.text(...)` calls collapse into
  // each other — patient-block rows, Plan numbered items, and any
  // multi-line bullet list all stack with 4-5pt of overlap.
  //
  // Setting lineGap globally adds the missing space on every paragraph
  // boundary. 4pt lands body lines at ~11.8pt advance — within a
  // half-point of the pre-T-M21 rhythm and tight enough that single-
  // line chunks (section headings, footer, etc.) still read right.
  doc.lineGap(4);

  renderHeader(doc, data);
  // feat/template-header-fields: the doctor's form header (when present) renders
  // in place of the generic patient info bar — no duplicate "Patient" line.
  if (data.headerFields.length > 0) {
    renderHeaderFieldsBlock(doc, data);
  } else {
    renderPatientBlock(doc, data);
  }
  renderSoap(doc, data);
  // A "form-only" template suppresses the appended coding/summary blocks so the
  // export is strictly the doctor's form + note body.
  if (!data.formOnly) {
    renderIcd(doc, data);
    renderCpt(doc, data);
    renderRx(doc, data);
    renderReferrals(doc, data);
    renderPatientSummary(doc, data);
  }

  // Form-only: NO QuillMD watermark + NO QuillMD "Signed electronically" footer.
  // The form's OWN signature block renders inline at the end of the content.
  if (data.formOnly) {
    renderFormSignature(doc, data);
  } else {
    // Watermark + footer on every page — hook the doc's pageAdded event
    // for pages after the first; apply to the current page manually here
    // because the event only fires for subsequent adds.
    drawWatermark(doc);
    drawFooter(doc, data);
    doc.on('pageAdded', () => {
      drawWatermark(doc);
      drawFooter(doc, data);
    });
  }

  doc.end();
  return done;
}

// ---------------------------------------------------------------------------
// Sections
// ---------------------------------------------------------------------------

function renderHeader(
  doc: PDFKit.PDFDocument,
  data: VisitExportData
): void {
  // Form-only: EXACTLY the doctor's form — its own title, centered as on the
  // form, no QuillMD wordmark, no account/specialty line, no rule.
  if (data.formOnly) {
    doc.font(FONTS.bodyBold).fontSize(SIZE.title).fillColor(COLORS.textPrimary);
    doc.text((data.formTitle ?? '').trim().toUpperCase() || 'NOTE', { align: 'center' });
    doc.moveDown(0.8);
    return;
  }
  doc.font(FONTS.brand).fontSize(SIZE.small).fillColor(COLORS.accent);
  doc.text('QUILLMD', { align: 'left' });
  doc.moveDown(0.25);

  doc.font(FONTS.bodyBold).fontSize(SIZE.title).fillColor(COLORS.textPrimary);
  const clinicianHeading = data.clinicianName
    ? `${data.clinicianName} · ${data.specialty}`
    : data.specialty;
  doc.text(clinicianHeading);
  doc.moveDown(0.5);
  drawRule(doc);
  doc.moveDown(0.8);
}

/** T-M21.2: patient metadata as a horizontal info bar (columns, not
 *  stacked rows). Each cell is label-on-top / value-below with
 *  absolute x-positioning so the columns align cleanly regardless
 *  of the value's character count. The old inline-continued layout
 *  stacked everything in one column because `\n` between rows plus
 *  the lineGap(4) advance produced a vertical list — fine for
 *  transcript blocks but wrong for a chart-header info bar. */
/** Render the doctor's parsed form header (feat/template-header-fields) as a
 *  vertical labeled list — one "LABEL: value" line per field, blanks as "—".
 *  Presentation-only; values were filled deterministically. */
function renderHeaderFieldsBlock(
  doc: PDFKit.PDFDocument,
  data: VisitExportData
): void {
  const LABEL_SIZE = 9;
  for (const f of data.headerFields) {
    doc
      .font(FONTS.labelBold)
      .fontSize(LABEL_SIZE)
      .fillColor(COLORS.textMuted)
      .text(`${f.label}:  `, PAGE.margin, doc.y, {
        continued: true,
        lineBreak: false,
      });
    doc
      .font(FONTS.bodyRegular)
      .fontSize(LABEL_SIZE + 1)
      .fillColor(COLORS.textPrimary)
      .text(f.value.trim() ? f.value.trim() : '—');
  }
  doc.x = PAGE.margin;
  doc.moveDown(0.6);
}

function renderPatientBlock(
  doc: PDFKit.PDFDocument,
  data: VisitExportData
): void {
  const cells: Array<{ label: string; value: string }> = [
    { label: 'Patient', value: data.patientName?.trim() || 'Anonymous' },
    { label: 'Visit date', value: formatVisitDate(data.signedAt ?? data.createdAt) },
  ];
  if (data.chiefComplaint) {
    cells.push({ label: 'Chief complaint', value: data.chiefComplaint });
  }
  if (data.signedAt) {
    cells.push({ label: 'Status', value: 'Signed' });
  }

  const n = cells.length;
  const availableWidth = doc.page.width - PAGE.margin * 2;
  const colWidth = availableWidth / n;
  const colInnerGap = 10; // right-side padding inside each column
  const startY = doc.y;

  // Typography tokens for this block — tuned for a chart-header look:
  // label smaller + uppercase + muted, value larger + primary.
  const LABEL_SIZE = 8;
  const VALUE_SIZE = 11;
  const LABEL_VALUE_GAP = 2; // pts between the label baseline and the value top

  let maxY = startY;
  for (let i = 0; i < n; i++) {
    const { label, value } = cells[i];
    const x = PAGE.margin + i * colWidth;
    const cellWidth = colWidth - colInnerGap;

    // Label (top line): InterTight-SemiBold, small, uppercase, muted.
    doc
      .font(FONTS.labelBold)
      .fontSize(LABEL_SIZE)
      .fillColor(COLORS.textMuted)
      .text(label.toUpperCase(), x, startY, {
        width: cellWidth,
        lineBreak: false,
      });
    const afterLabelY = doc.y;

    // Value (below label): Charter, larger, primary. Wrap within the
    // column on overflow so a long Chief Complaint doesn't bleed
    // into the neighbouring cell — the maxY tally below handles the
    // uneven-column-height case.
    doc
      .font(FONTS.bodyRegular)
      .fontSize(VALUE_SIZE)
      .fillColor(COLORS.textPrimary)
      .text(value, x, afterLabelY + LABEL_VALUE_GAP, {
        width: cellWidth,
      });

    if (doc.y > maxY) maxY = doc.y;
  }

  // Reset cursor to after the tallest column so the next block
  // (renderSoap → sectionHeading('Clinical Note')) starts below
  // every cell regardless of which one wrapped furthest.
  doc.x = PAGE.margin;
  doc.y = maxY;
  doc.moveDown(0.6);
}

// T-M21.1: line-level label patterns. `**Label:**` (bold) takes priority
// over `*Label:*` (italic) so `**foo:**` doesn't accidentally match the
// italic pattern. Both capture (label, content); content may be empty
// when the AI emits just the label and supplies the value in bullets
// below (e.g. `**PMH:**\n- item`).
const BOLD_LABEL_LINE_RE = /^\*\*([^*]+?):\*\*\s*(.*)$/;
const ITALIC_LABEL_LINE_RE = /^\*([^*]+?):\*\s*(.*)$/;

// Inline markdown tokenizer — matches either `**bold**` or `*italic*`
// non-greedy so `**foo**` consumed before its inner `*`s trigger an
// italic match. Nested `*italic with **bold** inside*` is NOT handled
// — the inner `**bold**` wins and the outer single `*`s stay as
// literal characters. Rare enough in clinical prose that the simpler
// tokenizer is fine for the common cases.
const INLINE_MARKDOWN_RE = /(\*\*[^*]+?\*\*|\*[^*]+?\*)/g;

// Structure-aware note line shapes. A table row is any line that starts
// and ends with a pipe; separator rows (|---|:---|) are dropped at flush
// time. Task lines are GitHub-style checklist items (- [x] / - [ ]).
const TABLE_ROW_RE = /^\s*\|.*\|\s*$/;
const TABLE_SEPARATOR_ROW_RE = /^\s*\|[\s:|-]+\|\s*$/;
const TASK_LINE_RE = /^\s*[-*]\s+\[( |x|X)\]\s+(.*)$/;

/** `| a | b |` → `['a', 'b']` — trims the outer pipes + per-cell whitespace. */
function parseTableRow(line: string): string[] {
  return line
    .trim()
    .replace(/^\|/, '')
    .replace(/\|$/, '')
    .split('|')
    .map((c) => c.trim());
}

/** The form's OWN signature block (form-only) — "Electronically Signed – <name>
 *  <date>" (+ DD:/DT: when the form has them). No QuillMD chrome. */
function renderFormSignature(doc: PDFKit.PDFDocument, data: VisitExportData): void {
  doc.moveDown(1.2);
  doc.font(FONTS.bodyRegular).fontSize(SIZE.small).fillColor(COLORS.textPrimary);
  for (const line of formSignatureLines(data.clinicianName, data.signedAt, data.formSignature)) {
    doc.text(line);
    doc.moveDown(0.15);
  }
}

function renderSoap(doc: PDFKit.PDFDocument, data: VisitExportData): void {
  // Form-only omits the injected "CLINICAL NOTE" heading (not on the form).
  if (!data.formOnly) sectionHeading(doc, 'Clinical Note');
  const soap = data.soapText.trim();
  if (!soap) {
    muted(doc, 'No SOAP note available.');
    return;
  }
  // Consecutive markdown-table rows collect here and flush as one grid on
  // the first non-pipe line (and at end-of-note). Prose-only notes never
  // populate the buffer, so their layout is unchanged.
  let tableBuffer: string[] = [];
  const flushTable = () => {
    if (tableBuffer.length === 0) return;
    const rows = tableBuffer
      .filter((l) => !TABLE_SEPARATOR_ROW_RE.test(l))
      .map(parseTableRow);
    tableBuffer = [];
    renderMarkdownTable(doc, rows);
  };
  // Walk the markdown line-by-line. Dispatch order matters:
  //   | table row |         →  buffered, flushed via renderMarkdownTable
  //   ## Heading           →  body-bold, slightly larger
  //   - [x] task           →  renderTaskItem (vector checkbox — the
  //                            bundled fonts have no U+2610/U+2612 glyphs)
  //   bullet               →  renderBullet (may also be label-shape)
  //   **Label:** content   →  renderLabelContent (bold label)
  //   *Label:* content     →  renderLabelContent (italic label)
  //   everything else      →  renderInlineMarkdown (bold + italic spans)
  for (const raw of soap.split('\n')) {
    const line = raw.trimEnd();
    if (TABLE_ROW_RE.test(line)) {
      tableBuffer.push(line);
      continue;
    }
    flushTable();
    if (!line.trim()) {
      doc.moveDown(0.4);
      continue;
    }
    if (/^##\s+/.test(line)) {
      doc
        .font(FONTS.bodyBold)
        .fontSize(SIZE.body + 1)
        .fillColor(COLORS.textPrimary)
        .text(line.replace(/^##\s+/, ''));
      continue;
    }
    const task = line.match(TASK_LINE_RE);
    if (task) {
      renderTaskItem(doc, task[1].toLowerCase() === 'x', task[2]);
      continue;
    }
    if (/^\s*[-*]\s+/.test(line)) {
      renderBullet(doc, line.replace(/^\s*[-*]\s+/, ''));
      continue;
    }
    const boldLabel = line.match(BOLD_LABEL_LINE_RE);
    if (boldLabel) {
      renderLabelContent(doc, boldLabel[1], boldLabel[2], 'bold');
      continue;
    }
    const italicLabel = line.match(ITALIC_LABEL_LINE_RE);
    if (italicLabel) {
      renderLabelContent(doc, italicLabel[1], italicLabel[2], 'italic');
      continue;
    }
    // Plain prose with possible inline **bold**/*italic* spans.
    renderInlineMarkdown(doc, line);
  }
  flushTable();
  doc.moveDown(0.8);
}

function renderIcd(doc: PDFKit.PDFDocument, data: VisitExportData): void {
  if (data.icdCodes.length === 0) return;
  sectionHeading(doc, 'Diagnoses');
  for (const c of data.icdCodes) {
    doc
      .font(FONTS.labelBold)
      .fontSize(SIZE.body)
      .fillColor(COLORS.textPrimary)
      .text(c.code, { continued: true });
    doc
      .font(FONTS.bodyRegular)
      .fillColor(COLORS.textSecondary)
      .text(`  ${c.description}`);
  }
  doc.moveDown(0.6);
}

function renderCpt(doc: PDFKit.PDFDocument, data: VisitExportData): void {
  if (!data.em && data.procedures.length === 0 && data.modifiers.length === 0) {
    return;
  }
  sectionHeading(doc, 'Procedures / E&M');
  if (data.em) {
    doc
      .font(FONTS.labelBold)
      .fontSize(SIZE.body)
      .fillColor(COLORS.textPrimary)
      .text(data.em.code, { continued: true });
    doc
      .font(FONTS.bodyRegular)
      .fillColor(COLORS.textSecondary)
      .text(`  ${data.em.description}`);
  }
  for (const p of data.procedures) {
    doc
      .font(FONTS.labelBold)
      .fillColor(COLORS.textPrimary)
      .text(p.code, { continued: true });
    const note = procedureProvenanceNote(p);
    doc
      .font(FONTS.bodyRegular)
      .fillColor(COLORS.textSecondary)
      .text(`  ${p.description}${note ? `  (${note})` : ''}`);
  }
  if (data.modifiers.length > 0) {
    doc.moveDown(0.2);
    for (const m of data.modifiers) {
      doc
        .font(FONTS.bodyItalic)
        .fontSize(SIZE.small)
        .fillColor(COLORS.textMuted)
        .text(`Modifier -${m.code}: ${m.rationale}`);
    }
  }
  doc.moveDown(0.6);
}

function renderRx(doc: PDFKit.PDFDocument, data: VisitExportData): void {
  // Prescriptions only. The Rx safety-warning banner + [SEVERITY] blocks are
  // internal review chrome — they stay on the review screen and in the audit
  // trail, never in an exported clinical document.
  if (data.prescriptions.length === 0) return;
  sectionHeading(doc, 'Medications');
  for (const rx of data.prescriptions) {
    doc
      .font(FONTS.bodyRegular)
      .fontSize(SIZE.body)
      .fillColor(COLORS.textPrimary)
      .text(prescriptionOneLine(rx));
  }
  doc.moveDown(0.6);
}

function renderReferrals(
  doc: PDFKit.PDFDocument,
  data: VisitExportData
): void {
  if (data.referrals.length === 0) return;
  sectionHeading(doc, 'Referrals');
  for (const r of data.referrals) {
    doc
      .font(FONTS.labelBold)
      .fontSize(SIZE.body)
      .fillColor(COLORS.textPrimary)
      .text(`→  ${r.to}`, { continued: true });
    doc
      .font(FONTS.bodyRegular)
      .fillColor(COLORS.textMuted)
      .fontSize(SIZE.small)
      .text(`   (${r.urgency})`);
    doc
      .font(FONTS.bodyRegular)
      .fontSize(SIZE.body)
      .fillColor(COLORS.textSecondary)
      .text(`    ${r.reason}`);
    if (r.relevant_history) {
      doc
        .font(FONTS.bodyItalic)
        .fontSize(SIZE.small)
        .fillColor(COLORS.textMuted)
        .text(`    ${r.relevant_history}`);
    }
    doc.moveDown(0.3);
  }
  doc.moveDown(0.3);
}

function renderPatientSummary(
  doc: PDFKit.PDFDocument,
  data: VisitExportData
): void {
  if (!data.patientSummary) return;
  sectionHeading(doc, 'Patient Summary');
  doc
    .font(FONTS.bodyRegular)
    .fontSize(SIZE.body)
    .fillColor(COLORS.textSecondary)
    .text(data.patientSummary.trim(), { align: 'left' });
  doc.moveDown(0.6);
}

// ---------------------------------------------------------------------------
// Primitives
// ---------------------------------------------------------------------------

function sectionHeading(doc: PDFKit.PDFDocument, text: string): void {
  doc.moveDown(0.3);
  doc
    .font(FONTS.labelBold)
    .fontSize(SIZE.sectionHead)
    .fillColor(COLORS.accent)
    .text(text.toUpperCase(), { characterSpacing: 1.2 });
  doc
    .moveTo(doc.x, doc.y + 2)
    .lineTo(doc.x + 200, doc.y + 2)
    .lineWidth(0.4)
    .strokeColor(COLORS.rule)
    .stroke();
  doc.moveDown(0.3);
}

function drawRule(doc: PDFKit.PDFDocument): void {
  const y = doc.y;
  doc
    .moveTo(PAGE.margin, y)
    .lineTo(doc.page.width - PAGE.margin, y)
    .lineWidth(0.5)
    .strokeColor(COLORS.rule)
    .stroke();
}

function muted(doc: PDFKit.PDFDocument, s: string): void {
  doc
    .font(FONTS.bodyItalic)
    .fontSize(SIZE.small)
    .fillColor(COLORS.textMuted)
    .text(s);
}

/** Task-list line (`- [x] Foo` / `- [ ] Foo`). The bundled Charter /
 *  Inter Tight TTFs carry NO ballot-box glyphs (U+2610/U+2612 would
 *  render as tofu), so the checkbox is vector-drawn: a 7pt hairline
 *  rect, plus two diagonal check strokes when checked. Body text keeps
 *  inline **bold** / *italic* spans via the shared span logic, laid out
 *  at an absolute x past the box (renderPatientBlock idiom, cursor
 *  reset at the end). */
function renderTaskItem(
  doc: PDFKit.PDFDocument,
  checked: boolean,
  body: string
): void {
  const BOX = 7;
  const GAP = 6;
  // Keep the box and the first text line together across page breaks.
  // After a manual addPage the pageAdded hook (watermark + footer) has
  // moved doc.x/doc.y via absolute-position text calls — reset to the
  // top-left margin explicitly.
  if (doc.y + BOX + 6 > doc.page.height - PAGE.margin) {
    doc.addPage();
    doc.x = PAGE.margin;
    doc.y = PAGE.margin;
  }
  const boxX = PAGE.margin;
  const textX = boxX + BOX + GAP;
  const textWidth = doc.page.width - PAGE.margin - textX;
  const startY = doc.y;
  // Optically align the box with the cap-height of 10.5pt body text.
  const boxY = startY + 1.2;

  doc
    .save()
    .rect(boxX, boxY, BOX, BOX)
    .lineWidth(0.6)
    .strokeColor(COLORS.rule)
    .stroke();
  if (checked) {
    const inset = 1.6;
    doc
      .moveTo(boxX + inset, boxY + inset)
      .lineTo(boxX + BOX - inset, boxY + BOX - inset)
      .moveTo(boxX + BOX - inset, boxY + inset)
      .lineTo(boxX + inset, boxY + BOX - inset)
      .lineWidth(0.9)
      .strokeColor(COLORS.textSecondary)
      .stroke();
  }
  doc.restore();

  const parts = body.split(INLINE_MARKDOWN_RE).filter((p) => p !== '');
  doc.fontSize(SIZE.body);
  if (parts.length === 0) {
    // Empty body — still advance one line past the box.
    doc
      .font(FONTS.bodyRegular)
      .fillColor(COLORS.textSecondary)
      .text(' ', textX, startY, { width: textWidth });
  } else {
    parts.forEach((part, i) => {
      const last = i === parts.length - 1;
      let font: string = FONTS.bodyRegular;
      let color: string = COLORS.textSecondary;
      let text = part;
      if (part.startsWith('**') && part.endsWith('**') && part.length > 4) {
        font = FONTS.bodyBold;
        color = COLORS.textPrimary;
        text = part.slice(2, -2);
      } else if (part.startsWith('*') && part.endsWith('*') && part.length > 2) {
        font = FONTS.bodyItalic;
        text = part.slice(1, -1);
      }
      doc.font(font).fillColor(color);
      if (i === 0) {
        // First span pins the absolute position + wrap width; pdfkit
        // caches the wrapper across the continued chain.
        doc.text(text, textX, startY, { width: textWidth, continued: !last });
      } else {
        doc.text(text, { continued: !last });
      }
    });
  }
  // Absolute-position calls leave doc.x at textX — reset (same idiom
  // as renderPatientBlock).
  doc.x = PAGE.margin;
}

/** A run of markdown-table rows → a hand-drawn grid. Layout follows the
 *  renderPatientBlock absolute-x column pattern: equal column split of
 *  the content width, per-row height measured via heightOfString, an
 *  explicit page-break check per row (the header row is re-drawn after
 *  a break; the pageAdded hook re-applies watermark + footer), hairline
 *  grid strokes in COLORS.rule, and the cursor-reset idiom at the end.
 *  Cell text goes through stripInlineMarkdown — a grid cell is a value,
 *  not prose. */
function renderMarkdownTable(
  doc: PDFKit.PDFDocument,
  rows: string[][]
): void {
  if (rows.length === 0) return;
  const cols = Math.max(1, ...rows.map((r) => r.length));
  const x0 = PAGE.margin;
  const tableWidth = doc.page.width - PAGE.margin * 2;
  const colWidth = tableWidth / cols;
  const PAD_X = 6;
  const PAD_Y = 4;
  const cellTextWidth = colWidth - PAD_X * 2;
  const bottomLimit = doc.page.height - PAGE.margin;

  const [header, ...body] = rows;

  const measureRow = (cells: string[], font: string, size: number): number => {
    doc.font(font).fontSize(size);
    let h = 0;
    for (const cell of cells) {
      const cellH = doc.heightOfString(stripInlineMarkdown(cell) || ' ', {
        width: cellTextWidth,
      });
      if (cellH > h) h = cellH;
    }
    return h + PAD_Y * 2;
  };

  const drawCells = (
    cells: string[],
    font: string,
    size: number,
    color: string,
    y: number
  ): void => {
    for (let c = 0; c < cols; c++) {
      const text = stripInlineMarkdown(cells[c] ?? '').trim();
      if (!text) continue;
      doc
        .font(font)
        .fontSize(size)
        .fillColor(color)
        .text(text, x0 + c * colWidth + PAD_X, y + PAD_Y, {
          width: cellTextWidth,
        });
    }
  };

  const drawGrid = (y: number, h: number): void => {
    doc.save().lineWidth(0.4).strokeColor(COLORS.rule);
    doc.moveTo(x0, y).lineTo(x0 + tableWidth, y);
    doc.moveTo(x0, y + h).lineTo(x0 + tableWidth, y + h);
    for (let c = 0; c <= cols; c++) {
      const vx = x0 + c * colWidth;
      doc.moveTo(vx, y).lineTo(vx, y + h);
    }
    doc.stroke().restore();
  };

  const drawHeader = (y: number): number => {
    const h = measureRow(header, FONTS.labelBold, SIZE.small);
    drawCells(header, FONTS.labelBold, SIZE.small, COLORS.textPrimary, y);
    drawGrid(y, h);
    return y + h;
  };

  // After a manual addPage the pageAdded hook draws watermark + footer
  // via absolute-position text, leaving doc.y at the footer — reset to
  // the top margin before laying out the continued rows.
  const newPageTop = (): number => {
    doc.addPage();
    doc.x = PAGE.margin;
    doc.y = PAGE.margin;
    return PAGE.margin;
  };

  doc.moveDown(0.3);
  let y = doc.y;
  if (y + measureRow(header, FONTS.labelBold, SIZE.small) > bottomLimit) {
    y = newPageTop();
  }
  y = drawHeader(y);
  for (const cells of body) {
    const h = measureRow(cells, FONTS.bodyRegular, SIZE.body);
    if (y + h > bottomLimit) {
      y = newPageTop();
      y = drawHeader(y);
    }
    drawCells(cells, FONTS.bodyRegular, SIZE.body, COLORS.textSecondary, y);
    drawGrid(y, h);
    y += h;
  }

  // Cursor-reset idiom (renderPatientBlock) — next block starts below
  // the grid at the left margin.
  doc.x = PAGE.margin;
  doc.y = y;
  doc.moveDown(0.4);
}

/** T-M21: explicit two-text-call renderer for the dominant SOAP line
 *  shape `**Label:** content` (or T-M21.1 `*Label:* content`).
 *  Replaces T-M20.1's split-and-toggle approach which still left
 *  edge cases where pdfkit's `continued` state didn't finalize
 *  cleanly between lines.
 *
 *  When content is empty (e.g. `**PMH:**` followed by bullets on
 *  subsequent lines), render just the label as its own paragraph —
 *  letting the bullets that follow supply the field's content.
 *  Faking "[not documented]" here would incorrectly paint that
 *  placeholder above legitimate multi-line content.
 *
 *  labelStyle picks the label font: 'bold' → InterTight-SemiBold
 *  (the default, for `**Label:**`), 'italic' → Charter-Italic (for
 *  T-M21.1 `*Label:*` patterns like nested ROS sub-labels).
 */
function renderLabelContent(
  doc: PDFKit.PDFDocument,
  label: string,
  content: string,
  labelStyle: 'bold' | 'italic' = 'bold'
): void {
  const trimmed = stripInlineMarkdown(content).trim();
  const labelFont = labelStyle === 'italic' ? FONTS.bodyItalic : FONTS.labelBold;
  const labelColor =
    labelStyle === 'italic' ? COLORS.textSecondary : COLORS.textPrimary;
  doc
    .font(labelFont)
    .fontSize(SIZE.body)
    .fillColor(labelColor);
  if (!trimmed) {
    doc.text(`${label}:`);
    return;
  }
  doc.text(`${label}: `, { continued: true });
  doc
    .font(FONTS.bodyRegular)
    .fillColor(COLORS.textSecondary)
    .text(trimmed);
}

/** Bullet line. If the body is a label-content shape (bold OR italic),
 *  render with the same explicit-two-call pattern after a bullet
 *  marker; if the body is plain prose, render with inline markdown
 *  handling applied to the body text. */
function renderBullet(doc: PDFKit.PDFDocument, body: string): void {
  const bold = body.match(BOLD_LABEL_LINE_RE);
  const italic = !bold ? body.match(ITALIC_LABEL_LINE_RE) : null;
  const match = bold ?? italic;
  if (match) {
    const labelStyle: 'bold' | 'italic' = bold ? 'bold' : 'italic';
    const trimmed = stripInlineMarkdown(match[2]).trim();
    doc
      .font(FONTS.bodyRegular)
      .fontSize(SIZE.body)
      .fillColor(COLORS.textSecondary)
      .text('•  ', { continued: true });
    const labelFont = labelStyle === 'italic' ? FONTS.bodyItalic : FONTS.labelBold;
    const labelColor =
      labelStyle === 'italic' ? COLORS.textSecondary : COLORS.textPrimary;
    doc.font(labelFont).fillColor(labelColor);
    if (!trimmed) {
      doc.text(`${match[1]}:`);
      return;
    }
    doc.text(`${match[1]}: `, { continued: true });
    doc
      .font(FONTS.bodyRegular)
      .fillColor(COLORS.textSecondary)
      .text(trimmed);
    return;
  }
  // Plain-body bullet with possibly embedded inline markdown.
  // Emits the bullet marker with a continued chain, then hands off
  // to renderMarkdownSpans so *italic* + **bold** inside the bullet
  // keep their formatting rather than getting stripped to plain text.
  const parts = body.split(INLINE_MARKDOWN_RE).filter((p) => p !== '');
  if (parts.length === 0) return;
  doc
    .font(FONTS.bodyRegular)
    .fontSize(SIZE.body)
    .fillColor(COLORS.textSecondary)
    .text('•  ', { continued: true, indent: 18 });
  renderMarkdownSpans(doc, parts);
}

/** T-M21.1: render a line with possibly embedded **bold** and *italic*
 *  spans. Tokenizes via INLINE_MARKDOWN_RE, filters empty slots (same
 *  insight as T-M20.1), then chains `continued: true` text calls with
 *  the matching font per span. The final span defaults to
 *  `continued: false` which finalizes the paragraph. Relies on the
 *  T-M21 `doc.lineGap(4)` compensator set at document start so the
 *  advance between paragraphs is right; without it the chain would
 *  re-introduce the T-M20.1-era overlap bug. */
function renderInlineMarkdown(doc: PDFKit.PDFDocument, line: string): void {
  const parts = line.split(INLINE_MARKDOWN_RE).filter((p) => p !== '');
  if (parts.length === 0) return;
  doc.fontSize(SIZE.body);
  renderMarkdownSpans(doc, parts);
}

/** Shared span emitter used by renderInlineMarkdown (whole-line plain
 *  text) and renderBullet (the plain-bullet path). Caller is expected
 *  to have set fontSize + any prefix text (e.g. `•  `) with
 *  `continued: true` before calling; this helper picks up at the
 *  current cursor and finalizes the paragraph on the last span. */
function renderMarkdownSpans(
  doc: PDFKit.PDFDocument,
  parts: string[]
): void {
  parts.forEach((part, i) => {
    const last = i === parts.length - 1;
    let font: string = FONTS.bodyRegular;
    let color: string = COLORS.textSecondary;
    let text = part;
    if (part.startsWith('**') && part.endsWith('**') && part.length > 4) {
      font = FONTS.bodyBold;
      color = COLORS.textPrimary;
      text = part.slice(2, -2);
    } else if (part.startsWith('*') && part.endsWith('*') && part.length > 2) {
      font = FONTS.bodyItalic;
      color = COLORS.textSecondary;
      text = part.slice(1, -1);
    }
    doc.font(font).fillColor(color).text(text, { continued: !last });
  });
}

/** Strip residual `**…**` AND `*…*` markers from a string. Used for
 *  content that goes into renderLabelContent (label context doesn't
 *  support inline formatting) and as a defense-in-depth for any
 *  downgraded render path where markers would otherwise show as
 *  literal asterisks. */
function stripInlineMarkdown(s: string): string {
  return s
    .replace(/\*\*([^*]+?)\*\*/g, '$1')
    .replace(/\*([^*]+?)\*/g, '$1');
}

function drawWatermark(doc: PDFKit.PDFDocument): void {
  // Tiny lower-right mark — clinicians expect "this came from a tool"
  // to be visible in case the page is shared.
  const y = doc.page.height - 36;
  doc
    .save()
    .font(FONTS.brand)
    .fontSize(7)
    .fillColor('#cccccc')
    .text(
      'QUILLMD',
      doc.page.width - PAGE.margin - 80,
      y,
      { width: 80, align: 'right', lineBreak: false }
    )
    .restore();
}

function drawFooter(doc: PDFKit.PDFDocument, data: VisitExportData): void {
  const y = doc.page.height - 54;
  const signedLine = data.signedAt
    ? `Signed electronically by ${data.clinicianName ?? 'Clinician'} on ${formatVisitDate(
        data.signedAt
      )}.`
    : 'Not yet signed.';
  doc
    .save()
    .font(FONTS.labelRegular)
    .fontSize(SIZE.footer)
    .fillColor(COLORS.textMuted)
    .text(
      signedLine,
      PAGE.margin,
      y,
      {
        width: doc.page.width - PAGE.margin * 2,
        align: 'center',
        lineBreak: false,
      }
    )
    .restore();
}
