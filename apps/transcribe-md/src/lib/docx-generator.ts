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

// T-M22.4: typography tokens. Font NAMES are set on every TextRun
// so Word renders Charter (body) and Inter Tight (labels + brand)
// when those fonts are installed locally; Word's font-substitution
// falls back to the user's default (typically Calibri) when they
// aren't. The docx library doesn't expose the fontTable.xml /
// fontEmbed mechanism that would bundle the TTFs into the .docx
// itself — full typography parity with the PDF would require a
// separate milestone (T-M23) manipulating that XML directly.
// PDFs keep rendering in embedded Charter + Inter Tight; DOCX
// typography is best-effort.
const FONTS = {
  body:  'Charter',
  label: 'Inter Tight',
} as const;

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
          size: 18, // half-points (9pt)
          font: FONTS.label,
          // T-M22.5: match PDF's 1.2pt letterspacing on the brand
          // wordmark. docx character-spacing unit is 1/20 pt, so 24
          // ≈ 1.2pt — same visual rhythm as the pdf-generator's
          // `characterSpacing: 1.2` in the section-heading primitive.
          characterSpacing: 24,
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
              font: FONTS.label,
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
                font: FONTS.label,
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
    // docProps/core.xml survives every Word/Pages/LibreOffice
    // round-trip and shows up in Spotlight / Explorer previews —
    // keep it PHI-free. visitId is opaque; clinician name belongs
    // in the body footer, not metadata.
    creator: 'QuillMD',
    title: `Visit ${data.visitId}`,
    description: `QuillMD visit note exported ${formatVisitDate(new Date())}`,
    // T-M22.4: Charter as the document-level default body font.
    // Every TextRun inherits it unless a specific run overrides
    // with `font: FONTS.label` (Inter Tight — brand + labels).
    // Word substitutes to Calibri when Charter isn't installed on
    // the reader's system; graceful degradation, no error.
    styles: {
      default: {
        document: {
          run: { font: FONTS.body },
        },
      },
    },
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
                      font: FONTS.label,
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
        font: FONTS.label,
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

// Structure-aware note line shapes. A table row is any line that starts
// and ends with a pipe; separator rows (|---|:---|) are dropped at flush
// time. Task lines are GitHub-style checklist items (- [x] / - [ ]).
const TABLE_ROW_RE = /^\s*\|.*\|\s*$/;
const TABLE_SEPARATOR_ROW_RE = /^\s*\|[\s:|-]+\|\s*$/;
const TASK_LINE_RE = /^\s*[-*]\s+\[( |x|X)\]\s+(.*)$/;

/** Walk markdown-ish SOAP text and emit Paragraphs (plus real Word
 *  Tables for GitHub-style markdown tables). Supports `##` headings,
 *  `**Label:** content` / `*Label:* content`, `**bold**` + `*italic*`
 *  inline, `-` bullets, `- [x]` task lines, and `| a | b |` tables —
 *  everything else renders as a plain paragraph. */
function renderSoapParagraphs(soap: string): (Paragraph | Table)[] {
  const out: (Paragraph | Table)[] = [];
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
  // Consecutive pipe rows collect here and flush as one Table on the
  // first non-pipe line (and at end-of-note). Prose-only notes never
  // populate the buffer, so their output is unchanged.
  let tableBuffer: string[] = [];
  const flushTable = () => {
    if (tableBuffer.length === 0) return;
    const table = renderMarkdownTable(tableBuffer);
    tableBuffer = [];
    if (table) out.push(table);
  };
  for (const raw of soap.split('\n')) {
    const line = raw.trimEnd();
    if (TABLE_ROW_RE.test(line)) {
      tableBuffer.push(line);
      continue;
    }
    flushTable();
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
    // Task-list lines — checked BEFORE the bullet branch so they don't
    // render as Word bullets with literal "[x]" text. U+2612/U+2610
    // glyphs resolve via Word's automatic font fallback (Segoe UI
    // Symbol / MS Gothic); the documented degradation is that a reader
    // without those fonts sees the ASCII-equivalent substitution box.
    const task = line.match(TASK_LINE_RE);
    if (task) {
      const checked = task[1].toLowerCase() === 'x';
      out.push(
        new Paragraph({
          spacing: { after: 40 },
          children: [
            new TextRun({ text: checked ? '☒ ' : '☐ ' }),
            ...renderInlineRuns(task[2]),
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
  flushTable();
  return out;
}

/** `| a | b |` → `['a', 'b']` — trims the outer pipes + per-cell whitespace. */
function parseTableRow(line: string): string[] {
  return line
    .trim()
    .replace(/^\|/, '')
    .replace(/\|$/, '')
    .split('|')
    .map((c) => c.trim());
}

/** A run of markdown table rows → a real Word Table. First non-separator
 *  row is the header (bold, Inter Tight); body cells keep inline
 *  **bold** / *italic* via renderInlineRuns. Unlike the invisible-border
 *  patient info bar, note tables carry VISIBLE hairline borders — the
 *  grid is content here, not layout. */
function renderMarkdownTable(lines: string[]): Table | null {
  const rows = lines
    .filter((l) => !TABLE_SEPARATOR_ROW_RE.test(l))
    .map(parseTableRow);
  if (rows.length === 0) return null;

  const hairline = {
    style: BorderStyle.SINGLE,
    size: 4, // eighths of a point — 0.5pt hairline
    color: 'DDDDDD',
  } as const;
  const hairlineBorders = {
    top: hairline,
    bottom: hairline,
    left: hairline,
    right: hairline,
    insideHorizontal: hairline,
    insideVertical: hairline,
  };

  const [header, ...body] = rows;
  return new Table({
    width: { size: 100, type: WidthType.PERCENTAGE },
    borders: hairlineBorders,
    rows: [
      new TableRow({
        tableHeader: true,
        children: header.map(
          (cell) =>
            new TableCell({
              borders: hairlineBorders,
              children: [
                new Paragraph({
                  children: [
                    new TextRun({
                      // Header cells are labels — strip inline markers
                      // instead of nesting formatting inside the bold run.
                      text: cell.replace(/\*\*([^*]+?)\*\*/g, '$1').replace(/\*([^*]+?)\*/g, '$1'),
                      bold: true,
                      size: 18, // 9pt label
                      font: FONTS.label,
                    }),
                  ],
                }),
              ],
            })
        ),
      }),
      ...body.map(
        (cells) =>
          new TableRow({
            children: cells.map(
              (cell) =>
                new TableCell({
                  borders: hairlineBorders,
                  children: [
                    new Paragraph({ children: renderInlineRuns(cell) }),
                  ],
                })
            ),
          })
      ),
    ],
  });
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
  // T-M22.4: bold labels use Inter Tight (mirrors PDF's
  // InterTight-SemiBold at the run level); italic labels stay
  // on Charter-Italic since the PDF convention is Charter-Italic
  // for italic labels, not Inter Tight italic.
  const labelRun = new TextRun(
    style === 'italic'
      ? { text: `${label}:${content ? ' ' : ''}`, italics: true }
      : {
          text: `${label}:${content ? ' ' : ''}`,
          bold: true,
          font: FONTS.label,
        }
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
