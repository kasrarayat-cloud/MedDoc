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
  Document,
  HeadingLevel,
  LevelFormat,
  Packer,
  Paragraph,
  TextRun,
} from 'docx';

import {
  type VisitExportData,
  prescriptionOneLine,
  formatVisitDate,
} from './visit-export';

export async function generateVisitDocx(
  data: VisitExportData
): Promise<Buffer> {
  const children: Paragraph[] = [];

  // ── Header ────────────────────────────────────────────────────────
  children.push(
    new Paragraph({
      spacing: { after: 120 },
      children: [
        new TextRun({
          text: 'TRANSCRIBEMD',
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
  children.push(
    labelledLine('Patient', data.patientName?.trim() || 'Anonymous')
  );
  children.push(
    labelledLine('Visit date', formatVisitDate(data.signedAt ?? data.createdAt))
  );
  if (data.chiefComplaint) {
    children.push(labelledLine('Chief complaint', data.chiefComplaint));
  }
  if (data.signedAt) {
    children.push(labelledLine('Status', 'Signed'));
  }
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
    creator: data.clinicianName ?? 'TranscribeMD',
    title: `Visit — ${data.patientName ?? 'Anonymous'}`,
    description: `TranscribeMD visit note exported ${formatVisitDate(new Date())}`,
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

function labelledLine(label: string, value: string): Paragraph {
  return new Paragraph({
    spacing: { after: 60 },
    children: [
      new TextRun({
        text: `${label.toUpperCase()}  `,
        bold: true,
        color: '666666',
        size: 18,
      }),
      new TextRun({ text: value, size: 22 }),
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

/** Walk markdown-ish SOAP text and emit Paragraphs. Supports `##`
 *  headings, `**bold**` inline, and `-` bullets — everything else
 *  renders as a plain paragraph. */
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
      const body = line.replace(/^\s*[-*]\s+/, '');
      out.push(
        new Paragraph({
          spacing: { after: 40 },
          indent: { left: 360 },
          children: inlineRuns(`•  ${body}`),
        })
      );
      continue;
    }
    out.push(
      new Paragraph({
        spacing: { after: 60 },
        children: inlineRuns(line),
      })
    );
  }
  return out;
}

/** `**bold**` inline → bold TextRun; everything else stays regular. */
function inlineRuns(line: string): TextRun[] {
  const parts = line.split(/(\*\*[^*]+\*\*)/g);
  return parts.map((part) => {
    if (part.startsWith('**') && part.endsWith('**')) {
      return new TextRun({ text: part.slice(2, -2), bold: true });
    }
    return new TextRun({ text: part });
  });
}
