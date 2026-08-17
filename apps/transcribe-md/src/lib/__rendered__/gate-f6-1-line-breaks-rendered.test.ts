// ============================================================================
// F6.1 — THE AUTHORED LINE BREAK, AS LIBREOFFICE ACTUALLY PAINTS IT
// ----------------------------------------------------------------------------
// ⚠️ WHY THIS FILE EXISTS WHEN `gate-f6-1-free-text-line-breaks.test.ts` ALREADY
// PASSES. That guard is STRUCTURAL: it reads `word/document.xml` and asserts a
// `<w:br/>` sits between two runs. It is a good guard and `<w:br/>` is the
// correct OOXML primitive — but "correct primitive" is a claim about a SPEC, and
// the thing F6.1 promises a doctor is a claim about a RENDERER.
//
//     A primitive nobody rendered is a proxy, and this house has paid for
//     proxies. #117(e) removed exactly this one for the footer.
//
// It matters more here than usual because of where the fix lands. Since F3 the
// pre-sign preview, the signed preview, the Word download and the PDF download
// all converge on `generateVisitDocx` → Gotenberg (`visit-pdf.ts`). So the
// STRUCTURAL guard covers the DOCX a doctor opens in Word, and THIS file covers
// the other three — every surface where the note is read as a PDF.
//
// ----------------------------------------------------------------------------
// ⚠️ IT IS A DIFFERENTIAL, AND THAT IS THE LOAD-BEARING DESIGN CHOICE.
//
// The naive form — "assert the extracted text contains a newline between the two
// lines" — cannot distinguish `LibreOffice honoured the break` from `the PDF
// text extractor happens to insert newlines`. Both produce a pass, and only one
// of them is the thing being proved.
//
// So each arm renders TWO documents that differ ONLY in whether the author wrote
// a break, and asserts they come out DIFFERENT:
//
//     'ALPHA one\nALPHA two'   must extract as TWO lines
//     'ALPHA one ALPHA two'    must extract as ONE line
//
// If the extractor cannot tell those apart, the control arm goes RED and says
// so, instead of the proof quietly passing on an instrument that measures
// nothing. That is the emptiness-test discipline aimed at a renderer.
// ============================================================================
import { describe, expect, it, beforeAll } from 'vitest';
import { extractText, getDocumentProxy } from 'unpdf';

import { generateVisitDocx } from '@/lib/docx-generator';
import type { VisitExportData } from '@/lib/visit-export';

const GOTENBERG_URL = process.env.GOTENBERG_URL ?? 'http://gotenberg:3000';
const CONVERT_URL = `${GOTENBERG_URL.replace(/\/$/, '')}/forms/libreoffice/convert`;
const HEALTH_URL = `${GOTENBERG_URL.replace(/\/$/, '')}/health`;

/** LibreOffice cold-starts on the first conversion. */
const CONVERT_TIMEOUT_MS = 60_000;

async function convert(docx: Uint8Array, filename: string): Promise<Uint8Array> {
  const form = new FormData();
  form.set(
    'files',
    new Blob([docx as unknown as BlobPart], {
      type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    }),
    filename
  );
  const res = await fetch(CONVERT_URL, {
    method: 'POST',
    body: form,
    signal: AbortSignal.timeout(CONVERT_TIMEOUT_MS),
  });
  if (!res.ok) {
    throw new Error(
      `gotenberg refused the conversion: ${res.status} ${res.statusText}`
    );
  }
  return new Uint8Array(await res.arrayBuffer());
}

function data(over: Partial<VisitExportData>): VisitExportData {
  return {
    visitId: 'v_f61_rendered',
    patientName: 'F61 Rendered',
    specialty: 'gastroenterology',
    chiefComplaint: null,
    status: 'READY',
    createdAt: new Date('2026-08-17T00:00:00Z'),
    signedAt: null,
    clinicianName: 'Dr Rendered',
    clinicianEmail: 't@example.invalid',
    soapText: '## SUBJECTIVE\nthe note body',
    icdCodes: [],
    em: null,
    procedures: [],
    modifiers: [],
    prescriptions: [],
    rxWarnings: [],
    referrals: [],
    patientSummary: null,
    headerFields: [],
    formOnly: false,
    formTitle: null,
    formSignature: null,
    ...over,
  } as VisitExportData;
}

/** Build → convert → read the rendered text back, as an array of lines with
 *  blank lines dropped and inner whitespace normalised. Line IDENTITY is the
 *  measurement, so lines are never joined here. */
async function renderedLines(
  label: string,
  over: Partial<VisitExportData>
): Promise<string[]> {
  const docx = await generateVisitDocx(data(over));
  const pdf = await convert(new Uint8Array(docx), `${label}.docx`);
  const doc = await getDocumentProxy(pdf);
  // ⚠️ `mergePages: false` AND THE ARRAY GUARD, BOTH DELIBERATE. `extractText`'s
  // return shape is not fixed — the sibling #117(e) proof guards it the same
  // way. With `mergePages: true` a returned ARRAY would be coerced by
  // `String(...)` into a COMMA-joined string, silently destroying the very
  // newlines this differential measures: the control and the positive arm would
  // then agree, and the proof would pass having measured nothing. Ask what
  // SHAPE the data is before asking what it contains.
  const { text } = await extractText(doc, { mergePages: false });
  const pages = Array.isArray(text) ? text : [String(text)];
  return pages
    .join('\n')
    .split('\n')
    .map((l) => l.replace(/\s+/g, ' ').trim())
    .filter(Boolean);
}

// ⚠️ THIS FILE MUST NOT LEARN TO SKIP. A rendered proof that no-ops when the
// sidecar is absent is a green that cannot go red.
beforeAll(async () => {
  const res = await fetch(HEALTH_URL, { signal: AbortSignal.timeout(15_000) });
  if (!res.ok) {
    throw new Error(
      `the gotenberg sidecar is not healthy (${res.status}). This gate FAILS ` +
        'rather than skips — an unrun rendered proof is indistinguishable ' +
        'from a passing one.'
    );
  }
}, 30_000);

describe('F6.1 rendered — LibreOffice honours the authored break', () => {
  it(
    'a break-separated summary renders on TWO lines; the same words with a ' +
      'SPACE render on ONE',
    async () => {
      const broken = await renderedLines('f61-broken', {
        patientSummary: 'ALPHA one\nALPHA two',
      });
      const flat = await renderedLines('f61-flat', {
        patientSummary: 'ALPHA one ALPHA two',
      });

      // ⚠️ THE CONTROL FIRST. If the flattened document ALSO comes back as two
      // lines, this extractor is inserting newlines of its own and nothing
      // below is evidence about LibreOffice.
      expect(
        flat,
        'the CONTROL document — the same words separated by a SPACE — did not ' +
          'render as one line. The instrument cannot discriminate, so the ' +
          'positive arm proves nothing. Do not read it.'
      ).toContain('ALPHA one ALPHA two');

      // The positive claim: with a break authored, the words do NOT share a
      // line. This is the assertion that goes red if `<w:br/>` is dropped
      // anywhere between the generator and the page.
      expect(
        broken,
        'the two authored lines rendered as ONE line in the PDF — the ' +
          'authored line break did not survive to the page, which is F6.1 ' +
          'reaching the doctor through the PDF/preview surfaces.'
      ).not.toContain('ALPHA one ALPHA two');

      expect(broken).toContain('ALPHA one');
      expect(broken).toContain('ALPHA two');
    },
    CONVERT_TIMEOUT_MS * 2
  );

  it(
    'a summary with NO authored break is not split — the fix invents nothing',
    async () => {
      const lines = await renderedLines('f61-nobreak', {
        patientSummary: 'BRAVO a single unbroken sentence in the summary',
      });
      expect(
        lines,
        'a summary with no authored break came back split. The fix would be ' +
          'inventing line breaks — a fidelity defect in the opposite ' +
          'direction, and one a doctor would read as the note stuttering.'
      ).toContain('BRAVO a single unbroken sentence in the summary');
    },
    CONVERT_TIMEOUT_MS * 2
  );
});
