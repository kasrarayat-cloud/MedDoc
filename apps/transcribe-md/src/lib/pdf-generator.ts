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
} from './visit-export';

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

const PAGE = {
  // US Letter (612 x 792 pts), 1" margins.
  size: 'LETTER' as const,
  margin: 72,
};

const COLORS = {
  textPrimary: '#111111',
  textSecondary: '#333333',
  textMuted: '#666666',
  rule: '#dddddd',
  accent: '#7C3AED',
  warningRed: '#B91C1C',
  warningAmber: '#B45309',
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
  title: 16,
  sectionHead: 12,
  body: 10.5,
  small: 9,
  footer: 8.5,
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
      Title: `Visit — ${data.patientName ?? 'Anonymous'} — ${formatVisitDate(
        data.signedAt ?? data.createdAt
      )}`,
      Author: data.clinicianName ?? 'QuillMD',
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
  renderPatientBlock(doc, data);
  renderSoap(doc, data);
  renderIcd(doc, data);
  renderCpt(doc, data);
  renderRx(doc, data);
  renderReferrals(doc, data);
  renderPatientSummary(doc, data);

  // Watermark + footer on every page — hook the doc's pageAdded event
  // for pages after the first; apply to the current page manually here
  // because the event only fires for subsequent adds.
  drawWatermark(doc);
  drawFooter(doc, data);
  doc.on('pageAdded', () => {
    drawWatermark(doc);
    drawFooter(doc, data);
  });

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

function renderPatientBlock(
  doc: PDFKit.PDFDocument,
  data: VisitExportData
): void {
  const labels: [string, string][] = [
    ['Patient', data.patientName?.trim() || 'Anonymous'],
    ['Visit date', formatVisitDate(data.signedAt ?? data.createdAt)],
  ];
  if (data.chiefComplaint) labels.push(['Chief complaint', data.chiefComplaint]);
  if (data.signedAt) labels.push(['Status', 'Signed']);

  for (const [k, v] of labels) {
    doc.font(FONTS.labelBold).fontSize(SIZE.small).fillColor(COLORS.textMuted);
    doc.text(`${k.toUpperCase()}  `, { continued: true });
    doc.font(FONTS.bodyRegular).fontSize(SIZE.body).fillColor(COLORS.textPrimary);
    doc.text(v);
  }
  doc.moveDown(0.8);
}

// Detects the dominant SOAP line shape: `**Label:** content` (content
// may be empty when the AI emits just `**Label:**` with no value).
// Captures (label, content). Used by the bullet + plain renderers
// below to pick the explicit two-text-call rendering path that
// supersedes T-M20.1's filtered-split workaround.
const LABEL_LINE_RE = /^\*\*([^*]+?):\*\*\s*(.*)$/;

function renderSoap(doc: PDFKit.PDFDocument, data: VisitExportData): void {
  sectionHeading(doc, 'Clinical Note');
  const soap = data.soapText.trim();
  if (!soap) {
    muted(doc, 'No SOAP note available.');
    return;
  }
  // Walk the markdown line-by-line. We support:
  //  ## Heading           →  body-bold, slightly larger
  //  **Label:** content   →  explicit label-content (label in
  //                          InterTight-SemiBold, content in Charter)
  //  - bullet             →  indented; bullet body may also be a
  //                          label-content shape
  //  (everything else)    →  Charter regular, residual **bold** marks
  //                          stripped so they don't show as literal *
  for (const raw of soap.split('\n')) {
    const line = raw.trimEnd();
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
    if (/^\s*[-*]\s+/.test(line)) {
      renderBullet(doc, line.replace(/^\s*[-*]\s+/, ''));
      continue;
    }
    const labelMatch = line.match(LABEL_LINE_RE);
    if (labelMatch) {
      renderLabelContent(doc, labelMatch[1], labelMatch[2]);
      continue;
    }
    // Plain line — strip residual bold markers so they don't render
    // as literal `**`. SOAP rarely uses inline bold outside the
    // label pattern, so accepting "bold lost" here is fine.
    doc
      .font(FONTS.bodyRegular)
      .fontSize(SIZE.body)
      .fillColor(COLORS.textSecondary)
      .text(stripInlineBold(line));
  }
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
    doc
      .font(FONTS.bodyRegular)
      .fillColor(COLORS.textSecondary)
      .text(`  ${p.description}`);
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
  if (data.prescriptions.length === 0 && data.rxWarnings.length === 0) return;
  sectionHeading(doc, 'Medications');
  for (const rx of data.prescriptions) {
    doc
      .font(FONTS.bodyRegular)
      .fontSize(SIZE.body)
      .fillColor(COLORS.textPrimary)
      .text(prescriptionOneLine(rx));
  }
  if (data.rxWarnings.length > 0) {
    doc.moveDown(0.3);
    doc
      .font(FONTS.labelBold)
      .fontSize(SIZE.small)
      .fillColor(COLORS.warningRed)
      .text('Rx safety warnings — review before sending.');
    for (const w of data.rxWarnings) {
      const tone =
        w.severity === 'critical' ? COLORS.warningRed : COLORS.warningAmber;
      // T-M21.1: dropped the two-space leading indent that preceded
      // `[CRITICAL]`. In InterTight-SemiBold at 9pt those spaces
      // rendered with enough visual weight to read as a glyph
      // placeholder in some PDF viewers. Flush-left tags line up
      // cleanly with the "Rx safety warnings — review before sending"
      // header above them and read as an obvious list.
      doc
        .font(FONTS.labelBold)
        .fontSize(SIZE.small)
        .fillColor(tone)
        .text(`[${w.severity.toUpperCase()}]`, { continued: true });
      doc
        .font(FONTS.bodyRegular)
        .fillColor(COLORS.textSecondary)
        .text(`  ${w.rx_drug} — ${w.message}`);
    }
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

/** T-M21: explicit two-text-call renderer for the dominant SOAP line
 *  shape `**Label:** content`. Replaces T-M20.1's split-and-toggle
 *  approach which still left edge cases where pdfkit's `continued`
 *  state didn't finalize cleanly between lines.
 *
 *  Pattern when content is present: bold label with `continued: true`,
 *  regular content with default `continued: false` (finalizes the
 *  paragraph and advances y). Predictable, single cycle per line,
 *  no empty-string slots feeding pdfkit.
 *
 *  When content is empty (`**PMH:**` followed by bullets on subsequent
 *  lines), render just the label as its own paragraph — letting the
 *  bullets that follow supply the field's content. Faking
 *  "[not documented]" here would incorrectly paint that placeholder
 *  above legitimate multi-line content.
 */
function renderLabelContent(
  doc: PDFKit.PDFDocument,
  label: string,
  content: string
): void {
  const trimmed = stripInlineBold(content).trim();
  doc
    .font(FONTS.labelBold)
    .fontSize(SIZE.body)
    .fillColor(COLORS.textPrimary);
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

/** Bullet line. If the body is a label-content shape, render with
 *  the same explicit-two-call pattern after a bullet marker; if the
 *  body is plain prose, just render the bullet + text. */
function renderBullet(doc: PDFKit.PDFDocument, body: string): void {
  const labelMatch = body.match(LABEL_LINE_RE);
  doc
    .font(FONTS.bodyRegular)
    .fontSize(SIZE.body)
    .fillColor(COLORS.textSecondary);
  if (labelMatch) {
    const trimmed = stripInlineBold(labelMatch[2]).trim();
    doc.text('•  ', { continued: true });
    doc
      .font(FONTS.labelBold)
      .fillColor(COLORS.textPrimary);
    if (!trimmed) {
      doc.text(`${labelMatch[1]}:`);
      return;
    }
    doc.text(`${labelMatch[1]}: `, { continued: true });
    doc
      .font(FONTS.bodyRegular)
      .fillColor(COLORS.textSecondary)
      .text(trimmed);
    return;
  }
  doc.text(`•  ${stripInlineBold(body)}`, { indent: 18 });
}

/** Strip residual `**…**` markers without trying to render them as
 *  bold. SOAP almost never uses inline bold outside the dominant
 *  label-content shape; the few stray cases get downgraded to plain
 *  Charter rather than risk re-introducing the T-M20.1 overlap. */
function stripInlineBold(s: string): string {
  return s.replace(/\*\*([^*]+?)\*\*/g, '$1');
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
