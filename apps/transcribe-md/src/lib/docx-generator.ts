// ============================================================================
// DOCX generator (T-M7)
// ----------------------------------------------------------------------------
// Built on the `docx` package (same version meddoc-pro uses). Simpler
// than the PDF path — Word/Pages/LibreOffice do the typography for us.
// Output is a few dozen KB, which is noticeably smaller than the PDF
// and matches what clinicians expect when they "Save as DOCX" from
// their EHR.
// ============================================================================

import { parseMarkdownRow, MARKDOWN_RULE_ROW_RE } from './markdown-row';
import {
  AlignmentType,
  BorderStyle,
  Document,
  Footer,
  HeadingLevel,
  type IRunOptions,
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
  signedAttestationLine,
  DRAFT_FOOTER_LINE,
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

// ---------------------------------------------------------------------------
// F6.1 — A LINE BREAK INSIDE FREE TEXT IS CONTENT, NOT WHITESPACE
// ---------------------------------------------------------------------------
// ⚠️ A LITERAL `\n` INSIDE `<w:t>` IS NOT A LINE BREAK IN OOXML. Word collapses
// it to a space. So `new TextRun({ text: 'a\nb' })` emits
// `<w:t xml:space="preserve">a\nb</w:t>` — which LOOKS like it preserved the
// break (the attribute even says `preserve`) and renders as `a b`. The only
// thing Word treats as a line break inside a paragraph is `<w:br/>`, which the
// `docx` package emits from a run's `break` option, BEFORE that run's text.
// (Measured, not assumed: `break: 2` emits exactly two `<w:br/>` ahead of the
// `<w:t>`.)
//
// This mattered on every production visit that had one. Measured 2026-08-17
// against prod: **43 of 43** visits with a non-empty `patientSummary` satisfy
// the defect's OWN predicate — split the text on `/\n\n+/` as the renderer
// does, and at least one resulting block still contains a `\n` that was being
// silently flattened. Not an edge case; the universal case.
//
// ⚠️ AND IT WAS NEVER A DOCX-ONLY DEFECT, THOUGH THE LEDGER ROW SAYS "in the
// DOCX". Since F3 the pre-sign preview, the signed preview, the Word download
// and the PDF download ALL converge on `generateVisitDocx` (see
// `visit-pdf.ts`), so one flattening reached four surfaces. Meanwhile
// `ehr-formatters.ts:423` pushes `patientSummary.trim()` into the EHR clipboard
// text as-is, where `\n` survives natively — so the clipboard and the document
// disagreed about what the note said.
//
// THE TREATMENT LIVES HERE, ON A SHARED HELPER, RATHER THAN ON THE FOUR CALL
// SITES — a per-caller list is kept complete by hand, and hand-kept lists are
// wrong eventually. A future free-text field inherits it by using this helper.
//
// ⚠️ IT IS A NO-OP FOR TEXT WITH NO LINE BREAK: one run, no `break` key, byte-
// identical to what shipped. That is asserted by the gate, because a fidelity
// fix that also restyles every unaffected document is a bigger change than
// anybody reviewed.
interface FreeTextRunOptions extends Omit<IRunOptions, 'text' | 'break' | 'children'> {
  /** Prepended to EVERY line, not just the first — so an indented block stays
   *  aligned when it carries on past line one. Without it, a referral's second
   *  line hangs left of its first and reads as a different field. */
  linePrefix?: string;
}

/** Doctor- and model-authored free text → `TextRun[]`, with every line break
 *  the author wrote surviving as a real `<w:br/>`. */
function freeTextRuns(text: string, opts: FreeTextRunOptions = {}): TextRun[] {
  const { linePrefix = '', ...run } = opts;
  // `\r\n` and a bare `\r` are line breaks too. A note that round-tripped
  // through a Windows EHR carries them, and splitting on `\n` alone would
  // leave a stray `\r` inside the run.
  return text.split(/\r\n|\r|\n/).map(
    (line, i) =>
      new TextRun({
        ...run,
        text: `${linePrefix}${line}`,
        // `break` is OMITTED on the first run rather than set to 0, so the
        // single-line case produces exactly the object it always did.
        ...(i === 0 ? {} : { break: 1 }),
      })
  );
}

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
          // ⚠️ THE DESCRIPTION RUN IS OMITTED WHEN THERE IS NO DESCRIPTION —
          // same reason as `ehr-formatters.ts`, which has printed
          // `99212 — undefined` into an EHR once already. F12-e freezes a
          // `signedCode` on visits where L7b emitted no `em` blob, so the
          // prose is genuinely absent and there is no non-AMA descriptor set
          // here to fill it from. The code alone is the honest artifact.
          children: [
            new TextRun({ text: data.em.code, bold: true }),
            ...(data.em.description
              ? [new TextRun({ text: `   ${data.em.description}` })]
              : []),
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
          // The `Modifier -NN: ` label rides line one; only the rationale's own
          // breaks continue below it, with no indent — which is what the single
          // run used to look like for the no-break case.
          children: freeTextRuns(`Modifier -${m.code}: ${m.rationale}`, {
            italics: true,
            size: toHalfPt(TYPE_PT.body),
            color: '666666',
          }),
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
          // `linePrefix`, not a `    ` baked into the string: the indent has to
          // reach line two as well, or a two-line reason reads as two fields.
          children: freeTextRuns(r.reason, { linePrefix: '    ' }),
        })
      );
      if (r.relevant_history) {
        children.push(
          new Paragraph({
            spacing: { after: 80 },
            children: freeTextRuns(r.relevant_history, {
              linePrefix: '    ',
              italics: true,
              color: '666666',
              size: toHalfPt(TYPE_PT.body),
            }),
          })
        );
      }
    }
    children.push(spacer());
  }

  // ── Patient summary ──────────────────────────────────────────────
  if (!data.formOnly && data.patientSummary) {
    children.push(sectionHeading('Patient Summary'));
    // The split on `\n\n+` makes a real PARAGRAPH per block, which is right and
    // is not what F6.1 was about. `freeTextRuns` restores the SINGLE breaks
    // WITHIN each block, which the one-run-per-block shape used to swallow.
    for (const block of data.patientSummary.trim().split(/\n\n+/)) {
      children.push(
        new Paragraph({
          spacing: { after: 120 },
          children: freeTextRuns(block),
        })
      );
    }
  }

  // ── Footer / signature ──────────────────────────────────────────
  children.push(spacer());
  if (data.formOnly) {
    // The form's OWN signature block — "Electronically Signed – <name> <date>"
    // (+ DD:/DT: when the form has them). No QuillMD signed line.
    for (const line of formSignatureLines({
      clinicianName: data.clinicianName,
      signedAt: data.signedAt,
      encounterDate: data.createdAt,
      sig: data.formSignature,
    })) {
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
            // RULING #117(b) — the SAME source as the section footer. This
            // used to compose the string inline; the footer would have been a
            // second copy of it.
            text: data.signedAt
              ? signedAttestationLine(data.clinicianName, data.signedAt)
              : 'Not yet signed.',
            color: '666666',
            size: 18,
            italics: true,
          }),
        ],
      })
    );
  }

  const pageFooter = attestationFooter(data);

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
      // ⚠️ GENUINELY UNUSED NOW, AND THIS COMMENT IS THE CORRECTED ONE.
      // It said "unused today" while the numbered-line branch below was
      // actively attaching it — true when written, false for however long
      // afterwards, and the sentence is what stopped anyone looking. The
      // branch now renders the note's own markers as text (see there), so
      // nothing references this config. It is kept, declared and inert,
      // because a future list that SHOULD be Word-numbered would want it —
      // but if that day comes, the fidelity test is the thing to read first.
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
        // RULING #117 — a SECTION footer, so Word/LibreOffice repeat it on
        // every page by construction. The retired PDF builder painted its
        // equivalent with a manual `pageAdded` hook, which is why converging
        // the two dropped it silently: the property lived in the renderer, not
        // in the document.
        ...(pageFooter ? { footers: { default: pageFooter } } : {}),
        children,
      },
    ],
  });

  return Packer.toBuffer(doc) as unknown as Buffer;
}

/** RULING #117 — the attestation footer, repeated on every rendered page.
 *
 *  |           | SIGNED                          | UNSIGNED                  |
 *  |-----------|---------------------------------|---------------------------|
 *  | standard  | (b) the attestation             | (a) DRAFT — Not yet…      |
 *  | form-only | (c) NONE — the doctor's paper    | (a) DRAFT — Not yet…      |
 *
 *  ⚠️ (c) IS NOT AN OVERSIGHT AND MUST NOT BE "FIXED". On a FINAL document the
 *  doctor's own form holds the attestation slot (Electronically Signed / DD /
 *  DT) and the form's field IS the attestation — QuillMD chrome there would be
 *  a second, competing signature on a record that already has one.
 *
 *  ⚠️ AND (a) DELIBERATELY OVERRIDES THAT for the unsigned case. A draft is a
 *  draft on anyone's paper; safety outranks chrome for non-final documents.
 *  The chrome-free contract applies to FINAL documents, which is exactly the
 *  collision #117 resolves — so the ORDER of these two branches is the ruling,
 *  not a preference. Swapping them silently unmarks every form-only draft.
 *
 *  Returns undefined for the ONE cell that carries no footer.
 */
function attestationFooter(data: VisitExportData): Footer | undefined {
  if (!data.signedAt) return footerLine(DRAFT_FOOTER_LINE); // (a) — form-only included
  if (data.formOnly) return undefined; // (c)
  return footerLine(signedAttestationLine(data.clinicianName, data.signedAt)); // (b)
}

/** One centered muted line, matching the in-body signature block's treatment so
 *  the two do not read as different voices. */
function footerLine(text: string): Footer {
  return new Footer({
    children: [
      new Paragraph({
        alignment: AlignmentType.CENTER,
        children: [
          new TextRun({ text, color: '666666', size: 18, italics: true }),
        ],
      }),
    ],
  });
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
      // Ruling #115 — the VISIT date is the ENCOUNTER's date. `signedAt` belongs
      // only in the signature chrome (the signed line above), never here.
      value: formatVisitDate(data.createdAt),
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
const TASK_LINE_RE = /^\s*[-*]\s+\[( |x|X)\]\s+(.*)$/;

/** A markdown section heading at ANY depth — group 1 is the hashes (depth),
 *  group 2 is the heading TEXT. Deliberately the same shape as
 *  `note-shape.ts:291`'s `NOTE_SECTION_HEADING_RE`, so the renderer and the
 *  note-shape classifier cannot disagree about what a heading line is. */
const NOTE_HEADING_LINE_RE = /^[ \t]*(#{1,6})[ \t]+(.+?)[ \t]*$/;

/** Walk markdown-ish SOAP text and emit Paragraphs (plus real Word
 *  Tables for GitHub-style markdown tables). Supports `##` headings,
 *  `**Label:** content` / `*Label:* content`, `**bold**` + `*italic*`
 *  inline, `-` bullets, `- [x]` task lines, and `| a | b |` tables —
 *  everything else renders as a plain paragraph. */
function renderSoapParagraphs(soap: string, formOnly = false): (Paragraph | Table)[] {
  // ⚠️ F6.2 — THE INJECTED HEADING IS DECIDED BY THE RENDERED BODY, NOT BY THE
  // RAW STRING. This used to return early on `!soap.trim()` and push the
  // heading immediately after, which guards the WRONG PREDICATE: a note whose
  // text is non-blank can still render to nothing. `|---|---|` is the reachable
  // instance — `.trim()` is non-empty so no early return fired, the line was
  // swallowed by the table buffer, and `renderMarkdownTable` returned null for
  // a separator-only run. The document then carried `§  CLINICAL NOTE` with the
  // signature paragraph directly beneath it and nothing in between.
  //
  // So the body is built FIRST and the chrome is decided afterwards.
  //
  // ⚠️ AND THE SCOPE IS THE INJECTED CHROME ONLY. A heading the NOTE ITSELF
  // contains — `## FINDINGS` with nothing under it, which one production visit
  // holds twice — still renders. Suppressing that would be the renderer editing
  // the record, which is ruling #112's class ("the note's own numbers are
  // CONTENT") and precisely what F1/F6.1/F6.4 exist to prevent.
  //
  // Proved by `gate-f62-injected-heading-labels-content.test.ts`, which pins
  // BOTH directions: a note with prose still gets the heading, so a renderer
  // that simply stopped emitting it would go red.
  const out: (Paragraph | Table)[] = [];
  // Blank source lines emit a spacer paragraph, which is layout and not
  // content. Counting them is what lets `out.length === blankCount` mean
  // "the body rendered nothing" without re-deriving the loop's own rules.
  let blankCount = 0;
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
    // ⚠️ THE TOLERANT READ, VIA THE SHARED PRIMITIVE. The strict matcher here
    // rejected any row carrying a trailing annotation after its last pipe — a
    // shape L4 emits in three forms — so the row never entered the table buffer
    // and was rendered as a plain paragraph of raw markdown inside the DOCX,
    // between two properly-drawn rows. The fill path read the same row the
    // whole time.
    if (parseMarkdownRow(line) !== null || MARKDOWN_RULE_ROW_RE.test(line)) {
      tableBuffer.push(line);
      continue;
    }
    flushTable();
    if (!line.trim()) {
      out.push(new Paragraph({ spacing: { after: 80 }, children: [] }));
      blankCount++;
      continue;
    }
    // ⚠️ EVERY MARKDOWN HEADING DEPTH RENDERS AS A HEADING — F6.4, ruling #133.
    //
    // This matched `^##\s+` ONLY. A `###` line therefore fell through to the
    // plain-paragraph branch at the bottom of this loop and printed ITS OWN
    // HASHES into the signed document — while `ehr-formatters.ts:88` strips
    // `^#{1,6}\s+`, so the clipboard read the same note correctly. Two
    // surfaces, one note, two different records.
    //
    // ⚠️ AND SINCE F3 THE BLAST RADIUS IS FOUR SURFACES, NOT ONE: the pre-sign
    // preview, the signed preview, the Word download and the PDF download all
    // converge on `generateVisitDocx`.
    //
    // MEASURED ON PRODUCTION 2026-08-20, not inferred: `##` 282 heading lines
    // across 47 visits; `###` **8 lines across 3 visits**; `#` none; headings
    // with LEADING whitespace **0** — so the `[ \t]*` tolerance below (which
    // matches `note-shape.ts:291`'s `NOTE_SECTION_HEADING_RE`) is forward-only
    // and moves nothing today.
    //
    // TWO TIERS, DELIBERATELY, AND NO LADDER WAS INVENTED. `#`/`##` keep
    // today's treatment BYTE-IDENTICALLY, so the 282 existing lines do not
    // move. `###`–`######` render bold at BODY size — a weight the document
    // already uses for `**Label:**` runs — so a subsection reads as
    // subordinate to its section instead of shouting at the same size. A
    // six-level size ladder would be a new visual vocabulary nobody ruled.
    const heading = line.match(NOTE_HEADING_LINE_RE);
    if (heading) {
      const subsection = heading[1].length >= 3;
      out.push(
        new Paragraph({
          spacing: { before: subsection ? 120 : 160, after: 80 },
          children: [
            new TextRun({
              text: heading[2],
              bold: true,
              ...(subsection ? {} : { size: 24 }),
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
      // ⚠️ THE NOTE'S OWN NUMBERS ARE CONTENT, NOT STYLING — SO THEY ARE
      // RENDERED, NOT REPAINTED.
      //
      // This used to attach `numbering: { reference: 'plan-numbering' }` and
      // emit only the text AFTER the marker, letting Word paint the number.
      // One numbering instance is shared by the whole document, so a second
      // numbered section CONTINUES the first: a note storing
      //
      //     ## POSTOPERATIVE FINDINGS   1. 2. 3.
      //     ## RECOMMENDATIONS          1. 2. 3.
      //
      // exported as RECOMMENDATIONS **4. 5. 6.** Measured on the real signed
      // visit, not a fixture: all six paragraphs carried `w:numId 2`, and no
      // literal marker survived anywhere in `document.xml`.
      //
      // A clinical note is a record. "Recommendation 1" is a thing the doctor
      // wrote and may be referred to elsewhere; a renderer that silently calls
      // it 4 has changed the record's content while claiming to style it. The
      // auto-renumber convenience is not worth that, and the doctor edits the
      // note in the app, not in Word.
      //
      // The marker is therefore emitted as TEXT, with a hanging indent so it
      // still reads as a list. Rendered numbers === stored numbers, exactly,
      // and `docx-numbering-fidelity.test.ts` asserts precisely that across two
      // adjacent numbered sections.
      out.push(
        new Paragraph({
          spacing: { after: 40 },
          indent: { left: toTwip(18), hanging: toTwip(18) },
          children: renderInlineRuns(`${numbered[1]}. ${numbered[2]}`),
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

  // F6.2 — nothing but spacers means the note rendered no content, whatever the
  // raw string looked like. Emit the placeholder ALONE: no chrome heading, and
  // not the spacers either, since they were the layout around content that does
  // not exist.
  if (out.length === blankCount) {
    return [
      new Paragraph({
        children: [
          new TextRun({
            text: 'No SOAP note available.',
            italics: true,
            color: '666666',
          }),
        ],
      }),
    ];
  }

  // Form-only omits the injected "CLINICAL NOTE" heading (not on the form) —
  // its own sections speak for themselves.
  return formOnly ? out : [sectionHeading('Clinical Note'), ...out];
}

/** `| a | b |` → `['a', 'b']` — trims the outer pipes + per-cell whitespace. */
/** ONE reader, five callers — `lib/markdown-row.ts`. */
function parseTableRow(line: string): string[] {
  return parseMarkdownRow(line)?.cells ?? [];
}


/** A run of markdown table rows → a real Word Table. First non-separator
 *  row is the header (bold, Inter Tight); body cells keep inline
 *  **bold** / *italic* via renderInlineRuns. Unlike the invisible-border
 *  patient info bar, note tables carry VISIBLE hairline borders — the
 *  grid is content here, not layout. */
function renderMarkdownTable(lines: string[]): Table | null {
  // ⚠️ THE TRAILING ANNOTATION IS CARRIED INTO THE TABLE, NOT DROPPED.
  //
  // This renderer read only `.cells`, and the adversarial pass proved what that
  // cost against the real generateVisitDocx:
  //   · an evidence annotation vanished from word/document.xml while the EHR
  //     paste kept it — one note, two records, the defect this slice exists to
  //     close, reintroduced in the other direction;
  //   · `| Side of exam | Right` (closing pipe omitted by L4) parsed as one
  //     cell plus a suffix, and `Right` — THE SIDE OF EXAM — was deleted from a
  //     signed imaging report.
  // Both latent (0 of 49 production notes) and neither had a guard: the slice's
  // own arm asserted survival against `flattenTables` ONLY, so this surface sat
  // outside its watched set.
  //
  // It rides as an extra cell in THIS renderer, which is a table and can hold
  // one — not in the shared primitive. `visit-fill-defects.test.ts` pins that
  // the FILL must never see it as a cell, because the fill writes cells into
  // the doctor's own form and prose there becomes a measurement.
  const rows = lines
    .filter((l) => !MARKDOWN_RULE_ROW_RE.test(l))
    .map((l) => {
      const parsed = parseMarkdownRow(l);
      if (!parsed) return [];
      return parsed.suffix ? [...parsed.cells, parsed.suffix] : parsed.cells;
    });
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
