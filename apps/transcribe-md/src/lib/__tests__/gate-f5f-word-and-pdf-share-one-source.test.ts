import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

/**
 * F5-f — ONE RECORD, ONE DOCUMENT, EVERY FORMAT.
 *
 * ⚠️ MEASURED ON THE OWNER'S FIRST CERTIFIED-TWIN VISIT, 2026-08-21. The Word
 * download was his own letterhead — a VERIFIED fill manifest, 49,418 bytes,
 * roundTripVerified — and the PDF download of THE SAME RECORD was QuillMD's
 * generic layout.
 *
 * Ruling #113 established ONE builder ONE truth, and `visit-pdf.ts` still
 * carries the diagram asserting Word and PDF share a source. The Template Twin
 * native path was added to the WORD route only; the diagram silently stopped
 * being true and nothing watched it.
 *
 * ⚠️ AND THE PDF ROUTE LOOKED COVERED, WHICH IS WHY IT SURVIVED REVIEW. It has
 * a native branch — `nativePdfExport` — but that is the FLAT PDF TEMPLATE
 * feature, gated on `styleProfile.pdfNativeCertified`. The owner's template is
 * a DOCX-derived twin and carries no such key, so it declined and fell through
 * to the styled render. Two features named "native"; the wrong one wired.
 *
 * This is a SOURCE gate deliberately. The defect is which FUNCTION a route
 * calls; a mock of the export stack is what let two routes drift apart while
 * both had passing tests.
 */
const ROUTES = join(__dirname, '..', '..', 'app', 'api', 'visits', '[id]', 'export');
const read = (p: string) => readFileSync(p, 'utf8');
const codeOf = (p: string) =>
  read(p)
    .split('\n')
    .filter((l) => {
      const t = l.trim();
      return !t.startsWith('//') && !t.startsWith('*') && !t.startsWith('/*');
    })
    .join('\n');

const DOCX = join(ROUTES, 'docx', 'route.ts');
const PDF = join(ROUTES, 'pdf', 'route.ts');

describe('the Word and PDF routes resolve the SAME document', () => {
  it('the scan is non-vacuous — both routes exist and export a handler', () => {
    // The routes export `const GET = withApiHandler(...)`, not a bare function —
    // measured rather than assumed, after this arm caught the assumption.
    expect(codeOf(DOCX)).toMatch(/export const GET = withApiHandler/);
    expect(codeOf(PDF)).toMatch(/export const GET = withApiHandler/);
  });

  it('⚠️ BOTH routes ask `resolveVisitDocx` — one question, one answer', () => {
    expect(codeOf(DOCX)).toMatch(/resolveVisitDocx\(/);
    expect(codeOf(PDF)).toMatch(/resolveVisitDocx\(/);
  });

  it('⚠️ NEITHER route builds its own document behind the shared resolver', () => {
    // The defect in one line: the PDF route called a builder directly while the
    // Word route asked the resolver. Either route regrowing its own call is the
    // divergence coming back.
    for (const [name, p] of [['docx', DOCX], ['pdf', PDF]] as const) {
      expect(codeOf(p), `${name} route calls generateVisitDocx directly`).not.toMatch(
        /generateVisitDocx\(/,
      );
      expect(
        codeOf(p),
        `${name} route loads the native twin itself instead of via the resolver`,
      ).not.toMatch(/loadOrComputeNativeTemplateDocxForVisit\(/);
    }
  });

  it('⚠️ the PDF is a CONVERSION of the resolved bytes, not a second render', () => {
    const pdf = codeOf(PDF);
    expect(pdf).toMatch(/renderVisitPdfFromDocx\(\s*source\.bytes\s*\)/);
    // `renderVisitPdf(data)` re-derives from `generateVisitDocx` internally —
    // that call is exactly the defect.
    expect(pdf).not.toMatch(/renderVisitPdf\(\s*data\s*\)/);
  });

  it('the twin decision is LOGGED on the PDF path — a silent fallback hid this for a day', () => {
    expect(codeOf(PDF)).toMatch(/nativeTwinDocx=/);
  });

  it('the flat-PDF path still short-circuits first, and is NOT the twin path', () => {
    // `nativePdfExport` is a different feature and stays. The bug was treating
    // its decline as "no native document exists".
    const pdf = codeOf(PDF);
    expect(pdf).toMatch(/nativePdfExport\(/);
    expect(pdf).toMatch(/if \(nativePdf\)/);
  });
});

describe('the shared resolver is the only place the choice is made', () => {
  const SRC = join(__dirname, '..', 'visit-docx-source.ts');

  it('it resolves the native twin, and degrades rather than throwing', () => {
    const c = codeOf(SRC);
    expect(c).toMatch(/loadOrComputeNativeTemplateDocxForVisit\(/);
    expect(c).toMatch(/templateNativeDocxEnabled\(\)/);
    expect(c).toMatch(/generateVisitDocx\(/); // the styled fallback
    expect(c).toMatch(/catch/); // a native failure must not 500 the download
  });

  it('⚠️ it reports WHY the doctor\'s own document was not used', () => {
    // A styled fallback that says nothing is how this class survives.
    expect(codeOf(SRC)).toMatch(/reason/);
  });
});
