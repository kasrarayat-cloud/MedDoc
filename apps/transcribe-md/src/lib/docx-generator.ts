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
  type RenderedHeaderField,
  prescriptionOneLine,
  formatVisitDate,
  procedureProvenanceNote,
} from './visit-export';
import { formSignatureLines } from './form-only';
import {
  EXPORT_FONT,
  PAGE_PT,
  TYPE_PT,
  toHalfPt,
  toTwip,
  EXPORT_COLOR,
  RULE_PT,
  SECTION_MARK,
  SECTION_TRACKING_PT,
  EMPTY_VALUE,
  META_LABEL_COL_PT,
  CONTENT_WIDTH_PT,
  LOCKUP_PT,
  toEighthPt,
  bareHex,
} from './export-page';

/** R1.4 — the hairline both generators draw, in the unit `docx` takes. */
const HAIRLINE = {
  style: BorderStyle.SINGLE,
  size: toEighthPt(RULE_PT),
  color: bareHex(EXPORT_COLOR.rule),
  space: 2,
} as const;

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
  body:  EXPORT_FONT.body,
  label: EXPORT_FONT.label,
} as const;

export async function generateVisitDocx(
  data: VisitExportData
): Promise<Buffer> {
  // T-M22.2: section body now holds Tables too (the patient info
  // bar is an invisible-border Word table). The docx library
  // accepts a heterogeneous array on `sections[].children`.
  const children: (Paragraph | Table)[] = [];

  // ── Header ────────────────────────────────────────────────────────
  // Form-only: render EXACTLY the doctor's form — the form's own title (centered,
  // as on the form), NO QuillMD wordmark, NO account/specialty line.
  if (data.formOnly) {
    children.push(
      new Paragraph({
        alignment: AlignmentType.CENTER,
        spacing: { after: toTwip(LOCKUP_PT.ruleToBody) },
        children: [
          new TextRun({
            text: (data.formTitle ?? '').trim().toUpperCase() || 'NOTE',
            bold: true,
            size: toHalfPt(TYPE_PT.title),
          }),
        ],
      })
    );
  } else {
    children.push(
      new Paragraph({
        spacing: { after: toTwip(LOCKUP_PT.eyebrowToTitle) },
        children: [
          new TextRun({
            text: 'QUILLMD',
            bold: true,
            color: bareHex(EXPORT_COLOR.accent),
            size: toHalfPt(TYPE_PT.small),
            font: FONTS.label,
            // docx's character-spacing unit is 1/20 pt, which is what
            // `toTwip` converts to. It was the literal 24 with a comment
            // explaining the arithmetic — right, and unable to follow the
            // point value if anyone changed it.
            characterSpacing: toTwip(SECTION_TRACKING_PT),
          }),
        ],
      })
    );
    children.push(
      new Paragraph({
        // R1.4: the title now carries the rule the PDF has always drawn under
        // it. A paragraph bottom border is how Word draws a full-measure rule
        // — there is no line primitive — and `space` is the gap above it, in
        // points, which is exactly the lockup token.
        border: { bottom: { ...HAIRLINE, space: LOCKUP_PT.titleToRule } },
        spacing: { after: toTwip(LOCKUP_PT.ruleToBody) },
        children: [
          new TextRun({
            text: data.clinicianName
              ? `${data.clinicianName} · ${data.specialty}`
              : data.specialty,
            bold: true,
            size: toHalfPt(TYPE_PT.title),
          }),
        ],
      })
    );
  }

  // ── Patient block ─────────────────────────────────────────────────
  // T-M22.2: horizontal info bar matching the PDF T-M21.2 design.
  // Word table with all borders set to NONE, one row, N cells
  // (N = 2 when minimal visit data, up to 4 with chief complaint
  // + signed). Each cell holds two paragraphs: label on top
  // (bold uppercase muted), value below (regular, larger).
  // feat/template-header-fields: when the doctor's form defines its own labeled
  // header (PATIENT NAME / DATE OF SURGERY / SURGEON / …), render THAT block in
  // place of the app's generic patient info bar — same slot, no duplicate
  // "Patient" line. Deterministically filled; blanks render as "—".
  if (data.headerFields.length > 0) {
    children.push(renderHeaderFieldsBlock(data.headerFields));
  } else {
    children.push(renderPatientInfoBar(data));
  }
  children.push(spacer());

  // ── SOAP note ─────────────────────────────────────────────────────
  // Form-only omits the injected "CLINICAL NOTE" heading — the form has no such
  // title; its own sections speak for themselves.
  children.push(...renderSoapParagraphs(data.soapText, data.formOnly));

  // ── Diagnoses ─────────────────────────────────────────────────────
  // feat/template-header-fields: a "form-only" template suppresses these
  // appended coding/summary blocks so the export is strictly the doctor's form.
  if (!data.formOnly && data.icdCodes.length > 0) {
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
    !data.formOnly &&
    (data.em || data.procedures.length > 0 || data.modifiers.length > 0)
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
            ...(procedureProvenanceNote(p)
              ? [new TextRun({ text: `   (${procedureProvenanceNote(p)})`, italics: true })]
              : []),
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
              size: toHalfPt(TYPE_PT.body),
              color: '666666',
            }),
          ],
        })
      );
    }
    children.push(spacer());
  }

  // ── Medications ──────────────────────────────────────────────────
  // Prescriptions only. The Rx safety-warning banner + [SEVERITY] blocks are
  // internal review chrome: they stay on the review screen and in the audit
  // trail (rx-warning-audit) but never render in an exported clinical document.
  if (!data.formOnly && data.prescriptions.length > 0) {
    children.push(sectionHeading('Medications'));
    for (const rx of data.prescriptions) {
      children.push(
        new Paragraph({
          spacing: { after: 60 },
          children: [new TextRun({ text: prescriptionOneLine(rx) })],
        })
      );
    }
    children.push(spacer());
  }

  // ── Referrals ────────────────────────────────────────────────────
  if (!data.formOnly && data.referrals.length > 0) {
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
              size: toHalfPt(TYPE_PT.body),
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
                size: toHalfPt(TYPE_PT.body),
              }),
            ],
          })
        );
      }
    }
    children.push(spacer());
  }

  // ── Patient summary ──────────────────────────────────────────────
  if (!data.formOnly && data.patientSummary) {
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

  // ── Footer / signature ──────────────────────────────────────────
  children.push(spacer());
  if (data.formOnly) {
    // The form's OWN signature block — "Electronically Signed – <name> <date>"
    // (+ DD:/DT: when the form has them). No QuillMD signed line.
    for (const line of formSignatureLines(data.clinicianName, data.signedAt, data.formSignature)) {
      children.push(
        new Paragraph({
          spacing: { after: 20 },
          children: [new TextRun({ text: line, size: toHalfPt(TYPE_PT.body) })],
        })
      );
    }
  } else {
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
  }

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
    sections: [
      {
        // ⚠️ C2-b — THIS WAS `sections: [{ children }]`, WITH NO PAGE AT ALL.
        // The `docx` library then uses its own default, A4 (11906x16838
        // twips). The PDF has always been US Letter. Since the on-screen
        // preview is Gotenberg's render of THIS file, the doctor read A4 and
        // downloaded Letter — and no text-comparison parity check could see it.
        properties: {
          page: {
            size: { width: toTwip(PAGE_PT.width), height: toTwip(PAGE_PT.height) },
            margin: {
              top: toTwip(PAGE_PT.margin),
              right: toTwip(PAGE_PT.margin),
              bottom: toTwip(PAGE_PT.margin),
              left: toTwip(PAGE_PT.margin),
            },
          },
        },
        children,
      },
    ],
  });

  return Packer.toBuffer(doc) as unknown as Buffer;
}

// ---------------------------------------------------------------------------
// Primitives
// ---------------------------------------------------------------------------

/** R1.4 — one metadata row: LABEL | value, in a borderless two-column table.
 *  The PDF draws the same grid at the same sizes from the same tokens. */
function metaRows(
  cells: Array<{ label: string; value: string }>,
): Table {
  const invisible = {
    style: BorderStyle.NONE,
    size: 0,
    color: 'FFFFFF',
  } as const;
  const invisibleBorders = {
    top: invisible,
    bottom: invisible,
    left: invisible,
    right: invisible,
    insideHorizontal: invisible,
    insideVertical: invisible,
  };
  // The label column is a POINT width shared with the PDF, expressed to Word
  // in twips. A percentage would have made it a different measure on any page
  // size — and this document's page size was A4-by-accident until C2-b.
  const labelW = toTwip(META_LABEL_COL_PT);
  const valueW = toTwip(CONTENT_WIDTH_PT - META_LABEL_COL_PT);

  return new Table({
    width: { size: toTwip(CONTENT_WIDTH_PT), type: WidthType.DXA },
    borders: invisibleBorders,
    rows: cells.map(({ label, value }) => {
      const v = value.trim() || EMPTY_VALUE;
      return new TableRow({
        children: [
          new TableCell({
            width: { size: labelW, type: WidthType.DXA },
            borders: invisibleBorders,
            children: [
              new Paragraph({
                spacing: { after: 30 },
                children: [
                  new TextRun({
                    text: label.toUpperCase(),
                    bold: true,
                    color: bareHex(EXPORT_COLOR.textMuted),
                    size: toHalfPt(TYPE_PT.fieldLabel),
                    font: FONTS.label,
                  }),
                ],
              }),
            ],
          }),
          new TableCell({
            width: { size: valueW, type: WidthType.DXA },
            borders: invisibleBorders,
            children: [
              new Paragraph({
                spacing: { after: 30 },
                children: [
                  new TextRun({
                    text: v,
                    // Muted when it is an em-dash: the absence of a value is
                    // not a value, and it should not read with the same weight
                    // as one.
                    color:
                      v === EMPTY_VALUE
                        ? bareHex(EXPORT_COLOR.textMuted)
                        : bareHex(EXPORT_COLOR.textPrimary),
                    size: toHalfPt(TYPE_PT.fieldValue),
                  }),
                ],
              }),
            ],
          }),
        ],
      });
    }),
  });
}

/** The doctor's parsed form header (feat/template-header-fields), in the same
 *  grid as everything else. It was `**LABEL:** value` paragraphs — a third
 *  presentation of metadata in a document that should have one. */
function renderHeaderFieldsBlock(fields: RenderedHeaderField[]): Table {
  return metaRows(fields.map((f) => ({ label: f.label, value: f.value })));
}

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
  // R1.4: was ONE row of N side-by-side cells at `100% / n` each, so the
  // layout got narrower the more facts the visit had. Now one row per field.
  return metaRows(cells);
}

function sectionHeading(text: string): Paragraph {
  return new Paragraph({
    heading: HeadingLevel.HEADING_2,
    spacing: { before: 240, after: 80 },
    border: { bottom: HAIRLINE },
    children: [
      new TextRun({
        text: `${SECTION_MARK}  ${text.toUpperCase()}`,
        bold: true,
        color: bareHex(EXPORT_COLOR.accent),
        characterSpacing: toTwip(SECTION_TRACKING_PT),
        size: toHalfPt(TYPE_PT.sectionHead),
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
function renderSoapParagraphs(soap: string, formOnly = false): (Paragraph | Table)[] {
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
  // Form-only omits the injected "CLINICAL NOTE" heading (not on the form).
  if (!formOnly) out.push(sectionHeading('Clinical Note'));
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
