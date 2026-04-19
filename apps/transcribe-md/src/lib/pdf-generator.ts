// ============================================================================
// PDF generator (T-M7)
// ----------------------------------------------------------------------------
// Stays on node:22-alpine — no chromium, no base-image churn. pdfkit is
// pure JS, deterministic, ~2MB. The tradeoff is no HTML/CSS; we lay out
// the doc by hand with x/y coordinates. For a SOAP note that's
// strictly text + section headings, it's the right size tool.
// ============================================================================

import PDFDocument from 'pdfkit';

import {
  type VisitExportData,
  prescriptionOneLine,
  formatVisitDate,
} from './visit-export';

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
  // PDFKit ships Helvetica + Times-Roman + Courier by default. We use
  // the built-in Times-Bold for headings (gives the "letter from your
  // doctor" feel without needing to embed a custom font file).
  bodyRegular: 'Times-Roman',
  bodyBold: 'Times-Bold',
  bodyItalic: 'Times-Italic',
  labelRegular: 'Helvetica',
  labelBold: 'Helvetica-Bold',
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
      Author: data.clinicianName ?? 'TranscribeMD',
      Creator: 'TranscribeMD',
      Producer: 'TranscribeMD PDF Generator (pdfkit)',
    },
  });

  const chunks: Buffer[] = [];
  doc.on('data', (c: Buffer) => chunks.push(c));
  const done = new Promise<Buffer>((resolve, reject) => {
    doc.on('end', () => resolve(Buffer.concat(chunks)));
    doc.on('error', reject);
  });

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
  doc.font(FONTS.labelBold).fontSize(SIZE.small).fillColor(COLORS.accent);
  doc.text('TRANSCRIBEMD', { align: 'left' });
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

function renderSoap(doc: PDFKit.PDFDocument, data: VisitExportData): void {
  sectionHeading(doc, 'Clinical Note');
  const soap = data.soapText.trim();
  if (!soap) {
    muted(doc, 'No SOAP note available.');
    return;
  }
  // Walk the markdown line-by-line. We support:
  //  ## Heading     →  body-bold, slightly larger
  //  **bold text**  →  body-bold inline
  //  - bullet       →  indented bullet
  //  (everything else → body-regular)
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
      const body = line.replace(/^\s*[-*]\s+/, '');
      renderInlineWithBold(doc, `•  ${body}`, { indent: 18 });
      continue;
    }
    renderInlineWithBold(doc, line);
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
      doc
        .font(FONTS.labelBold)
        .fontSize(SIZE.small)
        .fillColor(tone)
        .text(`  [${w.severity.toUpperCase()}]`, { continued: true });
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

/** Render a line that may contain **bold** segments. pdfkit doesn't
 *  parse markdown, so we split on `**…**` and toggle fonts. */
function renderInlineWithBold(
  doc: PDFKit.PDFDocument,
  line: string,
  opts: { indent?: number } = {}
): void {
  const parts = line.split(/(\*\*[^*]+\*\*)/g);
  doc.font(FONTS.bodyRegular).fontSize(SIZE.body).fillColor(COLORS.textSecondary);
  if (opts.indent) doc.text('', { continued: true, indent: opts.indent });
  parts.forEach((part, i) => {
    const last = i === parts.length - 1;
    if (part.startsWith('**') && part.endsWith('**')) {
      doc.font(FONTS.bodyBold).fillColor(COLORS.textPrimary);
      doc.text(part.slice(2, -2), { continued: !last });
      doc.font(FONTS.bodyRegular).fillColor(COLORS.textSecondary);
    } else {
      doc.text(part, { continued: !last });
    }
  });
}

function drawWatermark(doc: PDFKit.PDFDocument): void {
  // Tiny lower-right mark — clinicians expect "this came from a tool"
  // to be visible in case the page is shared.
  const y = doc.page.height - 36;
  doc
    .save()
    .font(FONTS.labelRegular)
    .fontSize(7)
    .fillColor('#cccccc')
    .text(
      'TRANSCRIBEMD',
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
