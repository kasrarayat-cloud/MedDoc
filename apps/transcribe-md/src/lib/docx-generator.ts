// ============================================================================
// DOCX generator (T-M7)
// ----------------------------------------------------------------------------
// Built on the `docx` package (same version meddoc-pro uses). Simpler
// than the PDF path — Word/Pages/LibreOffice do the typography for us.
// Output is a few dozen KB, which is noticeably smaller than the PDF
// and matches what clinicians expect when they "Save as DOCX" from
// their EHR.
// ============================================================================

import {
  AlignmentType,
  BorderStyle,
  Document,
  HeadingLevel,
  LevelFormat,
  Packer,
  Paragraph,
  Table,
  TableCell,
  TableRow,
  TextRun,
  WidthType,
} from 'docx';

import {
  type VisitExportData,
  prescriptionOneLine,
  formatVisitDate,
} from './visit-export';

export async function generateVisitDocx(
  data: VisitExportData
): Promise<Buffer> {
  // T-M22.2: section body now holds Tables too (the patient info
  // bar is an invisible-border Word table). The docx library
  // accepts a heterogeneous array on `sections[].children`.
  const children: (Paragraph | Table)[] = [];

  // ── Header ────────────────────────────────────────────────────────
  children.push(
    new Paragraph({
      spacing: { after: 120 },
      children: [
        new TextRun({
          text: 'QUILLMD',
          bold: true,
          color: '7C3AED',
          size: 18, // half-points
        }),
      ],
    })
  );
  children.push(
    new Paragraph({
      spacing: { after: 240 },
      children: [
        new TextRun({
          text: data.clinicianName
            ? `${data.clinicianName} · ${data.specialty}`
            : data.specialty,
          bold: true,
          size: 32,
        }),
      ],
    })
  );

  // ── Patient block ─────────────────────────────────────────────────
  // T-M22.2: horizontal info bar matching the PDF T-M21.2 design.
  // Word table with all borders set to NONE, one row, N cells
  // (N = 2 when minimal visit data, up to 4 with chief complaint
  // + signed). Each cell holds two paragraphs: label on top
  // (bold uppercase muted), value below (regular, larger).
  children.push(renderPatientInfoBar(data));
  children.push(spacer());

  // ── SOAP note ─────────────────────────────────────────────────────
  children.push(...renderSoapParagraphs(data.soapText));

  // ── Diagnoses ─────────────────────────────────────────────────────
  if (data.icdCodes.length > 0) {
    children.push(sectionHeading('Diagnoses'));
    for (const c of data.icdCodes) {
      children.push(
        new Paragraph({
          spacing: { after: 60 },
          children: [
            new TextRun({ text: c.code, bold: true }),
            new TextRun({ text: `   ${c.description}` }),
          ],
        })
      );
    }
    children.push(spacer());
  }

  // ── Procedures / E&M ─────────────────────────────────────────────
  if (
    data.em ||
    data.procedures.length > 0 ||
    data.modifiers.length > 0
  ) {
    children.push(sectionHeading('Procedures / E&M'));
    if (data.em) {
      children.push(
        new Paragraph({
          spacing: { after: 60 },
          children: [
            new TextRun({ text: data.em.code, bold: true }),
            new TextRun({ text: `   ${data.em.description}` }),
          ],
        })
      );
    }
    for (const p of data.procedures) {
      children.push(
        new Paragraph({
          spacing: { after: 60 },
          children: [
            new TextRun({ text: p.code, bold: true }),
            new TextRun({ text: `   ${p.description}` }),
          ],
        })
      );
    }
    for (const m of data.modifiers) {
      children.push(
        new Paragraph({
          spacing: { after: 60 },
          children: [
            new TextRun({
              text: `Modifier -${m.code}: ${m.rationale}`,
              italics: true,
              size: 20,
              color: '666666',
            }),
          ],
        })
      );
    }
    children.push(spacer());
  }

  // ── Medications ──────────────────────────────────────────────────
  if (data.prescriptions.length > 0 || data.rxWarnings.length > 0) {
    children.push(sectionHeading('Medications'));
    for (const rx of data.prescriptions) {
      children.push(
        new Paragraph({
          spacing: { after: 60 },
          children: [new TextRun({ text: prescriptionOneLine(rx) })],
        })
      );
    }
    if (data.rxWarnings.length > 0) {
      children.push(
        new Paragraph({
          spacing: { before: 80, after: 60 },
          children: [
            new TextRun({
              text: 'Rx safety warnings — review before sending.',
              bold: true,
              color: 'B91C1C',
              size: 20,
            }),
          ],
        })
      );
      for (const w of data.rxWarnings) {
        const color = w.severity === 'critical' ? 'B91C1C' : 'B45309';
        children.push(
          new Paragraph({
            spacing: { after: 40 },
            children: [
              new TextRun({
                text: `[${w.severity.toUpperCase()}] `,
                bold: true,
                color,
                size: 20,
              }),
              new TextRun({
                text: `${w.rx_drug} — ${w.message}`,
                color: '555555',
                size: 20,
              }),
            ],
          })
        );
      }
    }
    children.push(spacer());
  }

  // ── Referrals ────────────────────────────────────────────────────
  if (data.referrals.length > 0) {
    children.push(sectionHeading('Referrals'));
    for (const r of data.referrals) {
      children.push(
        new Paragraph({
          spacing: { after: 40 },
          children: [
            new TextRun({ text: `→ ${r.to}`, bold: true }),
            new TextRun({
              text: `   (${r.urgency})`,
              color: '666666',
              size: 20,
            }),
          ],
        })
      );
      children.push(
        new Paragraph({
          spacing: { after: 40 },
          children: [new TextRun({ text: `    ${r.reason}` })],
        })
      );
      if (r.relevant_history) {
        children.push(
          new Paragraph({
            spacing: { after: 80 },
            children: [
              new TextRun({
                text: `    ${r.relevant_history}`,
                italics: true,
                color: '666666',
                size: 20,
              }),
            ],
          })
        );
      }
    }
    children.push(spacer());
  }

  // ── Patient summary ──────────────────────────────────────────────
  if (data.patientSummary) {
    children.push(sectionHeading('Patient Summary'));
    for (const block of data.patientSummary.trim().split(/\n\n+/)) {
      children.push(
        new Paragraph({
          spacing: { after: 120 },
          children: [new TextRun({ text: block })],
        })
      );
    }
  }

  // ── Footer ──────────────────────────────────────────────────────
  children.push(spacer());
  children.push(
    new Paragraph({
      alignment: AlignmentType.CENTER,
      children: [
        new TextRun({
          text: data.signedAt
            ? `Signed electronically by ${data.clinicianName ?? 'Clinician'} on ${formatVisitDate(
                data.signedAt
              )}.`
            : 'Not yet signed.',
          color: '666666',
          size: 18,
          italics: true,
        }),
      ],
    })
  );

  const doc = new Document({
    creator: data.clinicianName ?? 'QuillMD',
    title: `Visit — ${data.patientName ?? 'Anonymous'}`,
    description: `QuillMD visit note exported ${formatVisitDate(new Date())}`,
    numbering: {
      // Unused today — declared so future Plan sections can render as a
      // real Word numbered list without adding another Document option.
      config: [
        {
          reference: 'plan-numbering',
          levels: [
            { level: 0, format: LevelFormat.DECIMAL, text: '%1.', start: 1 },
          ],
        },
      ],
    },
    sections: [{ children }],
  });

  return Packer.toBuffer(doc) as unknown as Buffer;
}

// ---------------------------------------------------------------------------
// Primitives
// ---------------------------------------------------------------------------

/** T-M22.2: patient info bar as a Word table with all borders set
 *  to NONE. One row, N cells where N is the count of populated
 *  fields (2 minimum — Patient + Visit Date; up to 4 with Chief
 *  Complaint + Status). Cell layout mirrors PDF T-M21.2: label
 *  on top (bold, uppercase, muted), value below (regular, larger). */
function renderPatientInfoBar(data: VisitExportData): Table {
  const cells: Array<{ label: string; value: string }> = [
    { label: 'Patient', value: data.patientName?.trim() || 'Anonymous' },
    {
      label: 'Visit date',
      value: formatVisitDate(data.signedAt ?? data.createdAt),
    },
  ];
  if (data.chiefComplaint) {
    cells.push({ label: 'Chief complaint', value: data.chiefComplaint });
  }
  if (data.signedAt) {
    cells.push({ label: 'Status', value: 'Signed' });
  }

  const invisibleBorder = {
    style: BorderStyle.NONE,
    size: 0,
    color: 'FFFFFF',
  } as const;
  const invisibleBorders = {
    top: invisibleBorder,
    bottom: invisibleBorder,
    left: invisibleBorder,
    right: invisibleBorder,
    insideHorizontal: invisibleBorder,
    insideVertical: invisibleBorder,
  };

  return new Table({
    width: { size: 100, type: WidthType.PERCENTAGE },
    borders: invisibleBorders,
    rows: [
      new TableRow({
        children: cells.map(
          ({ label, value }) =>
            new TableCell({
              borders: invisibleBorders,
              children: [
                new Paragraph({
                  spacing: { after: 20 },
                  children: [
                    new TextRun({
                      text: label.toUpperCase(),
                      bold: true,
                      color: '666666',
                      size: 16, // 8pt label
                    }),
                  ],
                }),
                new Paragraph({
                  children: [
                    new TextRun({
                      text: value,
                      size: 22, // 11pt value
                    }),
                  ],
                }),
              ],
            })
        ),
      }),
    ],
  });
}

function sectionHeading(text: string): Paragraph {
  return new Paragraph({
    heading: HeadingLevel.HEADING_2,
    spacing: { before: 240, after: 80 },
    children: [
      new TextRun({
        text: text.toUpperCase(),
        bold: true,
        color: '7C3AED',
        characterSpacing: 20,
        size: 22,
      }),
    ],
  });
}

function spacer(): Paragraph {
  return new Paragraph({ spacing: { before: 120, after: 0 }, children: [] });
}

// T-M22.1: line-level label patterns (mirrors pdf-generator.ts). Bold
// check runs first so `**foo:**` never falls through to the italic
// match. Content may be empty when the AI emits just the label
// (e.g. `**PMH:**` with bullets supplying the value below).
const BOLD_LABEL_LINE_RE = /^\*\*([^*]+?):\*\*\s*(.*)$/;
const ITALIC_LABEL_LINE_RE = /^\*([^*]+?):\*\s*(.*)$/;

// Inline markdown tokenizer — matches `**bold**` or `*italic*`
// non-greedy. Nested `*italic with **bold** inside*` is not
// supported; the inner bold wins and the outer `*`s stay literal.
const INLINE_MARKDOWN_RE = /(\*\*[^*]+?\*\*|\*[^*]+?\*)/g;

/** Walk markdown-ish SOAP text and emit Paragraphs. Supports `##`
 *  headings, `**Label:** content` / `*Label:* content`, `**bold**`
 *  + `*italic*` inline, and `-` bullets — everything else renders
 *  as a plain paragraph. */
function renderSoapParagraphs(soap: string): Paragraph[] {
  const out: Paragraph[] = [];
  if (!soap.trim()) {
    out.push(
      new Paragraph({
        children: [
          new TextRun({
            text: 'No SOAP note available.',
            italics: true,
            color: '666666',
          }),
        ],
      })
    );
    return out;
  }
  out.push(sectionHeading('Clinical Note'));
  for (const raw of soap.split('\n')) {
    const line = raw.trimEnd();
    if (!line.trim()) {
      out.push(new Paragraph({ spacing: { after: 80 }, children: [] }));
      continue;
    }
    if (/^##\s+/.test(line)) {
      out.push(
        new Paragraph({
          spacing: { before: 160, after: 80 },
          children: [
            new TextRun({
              text: line.replace(/^##\s+/, ''),
              bold: true,
              size: 24,
            }),
          ],
        })
      );
      continue;
    }
    if (/^\s*[-*]\s+/.test(line)) {
      // T-M22.3: proper Word bulleted list via the `bullet` prop
      // on Paragraph — previously used a literal "• " prefix with
      // a manual left-indent, which works but doesn't integrate
      // with Word's list-promotion / outline features.
      const body = line.replace(/^\s*[-*]\s+/, '');
      out.push(
        new Paragraph({
          spacing: { after: 40 },
          bullet: { level: 0 },
          children: renderInlineRuns(body),
        })
      );
      continue;
    }
    const numbered = line.match(/^(\d+)\.\s+(.*)$/);
    if (numbered) {
      // T-M22.3: numbered Plan items go through the "plan-numbering"
      // Numbering config declared on the Document. Previously these
      // fell through to the plain-paragraph branch so "1." / "2." /
      // "3." rendered as literal text without Word's numbering
      // machinery (no auto-renumbering on edit, no indent).
      out.push(
        new Paragraph({
          spacing: { after: 40 },
          numbering: { reference: 'plan-numbering', level: 0 },
          children: renderInlineRuns(numbered[2]),
        })
      );
      continue;
    }
    const boldLabel = line.match(BOLD_LABEL_LINE_RE);
    if (boldLabel) {
      out.push(
        new Paragraph({
          spacing: { after: 60 },
          children: renderLabelledRuns(boldLabel[1], boldLabel[2], 'bold'),
        })
      );
      continue;
    }
    const italicLabel = line.match(ITALIC_LABEL_LINE_RE);
    if (italicLabel) {
      out.push(
        new Paragraph({
          spacing: { after: 60 },
          children: renderLabelledRuns(italicLabel[1], italicLabel[2], 'italic'),
        })
      );
      continue;
    }
    out.push(
      new Paragraph({
        spacing: { after: 60 },
        children: renderInlineRuns(line),
      })
    );
  }
  return out;
}

/** T-M22.1: emit a TextRun[] for a `**Label:** content` or
 *  `*Label:* content` shape. Label gets bold or italic depending
 *  on `style`; content goes through renderInlineRuns so any nested
 *  formatting inside the content keeps its bold/italic spans. */
function renderLabelledRuns(
  label: string,
  content: string,
  style: 'bold' | 'italic'
): TextRun[] {
  const labelRun = new TextRun(
    style === 'italic'
      ? { text: `${label}:${content ? ' ' : ''}`, italics: true }
      : { text: `${label}:${content ? ' ' : ''}`, bold: true }
  );
  if (!content.trim()) return [labelRun];
  return [labelRun, ...renderInlineRuns(content)];
}

/** T-M22.1: `**bold**` / `*italic*` inline markdown → TextRun[].
 *  Filter empty segments the same way pdf-generator.ts does — the
 *  split-on-capturing-regex produces empty slots at the string
 *  boundaries that would otherwise emit zero-content runs. */
function renderInlineRuns(line: string): TextRun[] {
  const parts = line.split(INLINE_MARKDOWN_RE).filter((p) => p !== '');
  return parts.map((part) => {
    if (part.startsWith('**') && part.endsWith('**') && part.length > 4) {
      return new TextRun({ text: part.slice(2, -2), bold: true });
    }
    if (part.startsWith('*') && part.endsWith('*') && part.length > 2) {
      return new TextRun({ text: part.slice(1, -1), italics: true });
    }
    return new TextRun({ text: part });
  });
}
