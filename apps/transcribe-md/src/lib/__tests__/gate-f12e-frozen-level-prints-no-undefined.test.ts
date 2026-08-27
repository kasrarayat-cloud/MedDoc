// ============================================================================
// F12-e, SECOND HALF — A FROZEN LEVEL WITH NO PROSE PRINTS THE CODE, NEVER
// `undefined`.
// ----------------------------------------------------------------------------
// FOUND BY THIS ITEM'S OWN ADVERSARIAL PASS, ON ITS OWN DIFF, AND IT WAS A
// DEFECT INTRODUCED BY THE FIX RATHER THAN ONE THE FIX INHERITED.
//
// F12-e makes `sign/route.ts` freeze `cptCodes.em.signedCode` whenever E/M
// applies to the note being signed — including on the 12 measured production
// visits (10 SIGNED) whose L7b run emitted no `em` blob at all. The blob it
// synthesises there is `{ signedCode }`: a code, and no `description`.
//
// `CptEm.description` was declared REQUIRED, so every renderer was entitled to
// interpolate it blind, and two did:
//
//     ehr-formatters.ts:231   `  ${data.em.code} — ${data.em.description}`
//     docx-generator.ts:259   `   ${data.em.description}`
//
// ⚠️ THE RESULTING STRING IS `99214 — undefined`, AND THAT EXACT STRING HAS
// REACHED AN EHR ONCE ALREADY — `projectDisplayedEmCode`'s own comment records
// it, from the window when the specialty-label bug exposed the level surface on
// imaging visits. So the fix, unrepaired, would have traded an ABSENT E/M for a
// WRONG one, and this house ranks the second worse:
//
//     AN ABSENT FIELD IS CONTENT THE DOCTOR DID NOT SEE.
//     A WRONG FIELD SAYS THE OPPOSITE OF THE RECORD BEING SIGNED.
//
// THE FIX IS NOT TO INVENT PROSE. There is no non-AMA descriptor set in this
// repository, and authoring a billing string is what ruling #149(d) forbids.
// The code alone is the honest artifact, so the SEPARATOR is conditional and
// `CptEm.description` is now OPTIONAL — which is the load-bearing half, because
// it makes a future renderer fail to TYPECHECK rather than print `undefined`.
//
// WHAT WOULD MAKE THIS FILE FAIL: restoring either unconditional interpolation.
// Mutation-proved in the item's record, both sites.
// ============================================================================

import { describe, expect, it } from 'vitest';
import JSZip from 'jszip';

import { formatForEhr } from '../ehr-formatters';
import { generateVisitDocx } from '../docx-generator';
import type { VisitExportData } from '../visit-export';

/** The blob F12-e's freeze synthesises when L7b emitted no `em`. */
const FROZEN_WITHOUT_PROSE = {
  code: '99214',
  signedCode: '99214',
  reasoning: { problems: [], data: '', risk: '' },
  evidence_quote: '',
} as VisitExportData['em'];

/** The ordinary blob, which must be unchanged by any of this. */
const FROZEN_WITH_PROSE = {
  code: '99214',
  signedCode: '99214',
  description: 'Established patient, moderate complexity',
  reasoning: { problems: [], data: '', risk: '' },
  evidence_quote: '',
} as VisitExportData['em'];

function data(em: VisitExportData['em']): VisitExportData {
  return {
    visitId: 'v-f12e',
    patientName: 'P',
    specialty: 'gastroenterology',
    chiefComplaint: null,
    status: 'SIGNED',
    createdAt: new Date('2026-08-27T09:00:00.000Z'),
    signedAt: new Date('2026-08-27T11:00:00.000Z'),
    clinicianName: 'Dr. Test',
    clinicianEmail: 'doc@test.dev',
    soapText: '## Subjective\nx\n\n## Plan\ny',
    icdCodes: [],
    em,
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
  } as unknown as VisitExportData;
}

/** The DOCX text, from a REAL rendered document — the same route the signed
 *  Word download and (via Gotenberg) the signed PDF take. A source assertion
 *  could not tell a conditional run from a deleted one. */
async function docxText(em: VisitExportData['em']): Promise<string> {
  const buf = await generateVisitDocx(data(em));
  const zip = await JSZip.loadAsync(buf);
  const xml = await zip.file('word/document.xml')!.async('string');
  return xml.replace(/<\/w:p>/g, '\n').replace(/<[^>]+>/g, ' ');
}

// Every clipboard format goes through `cptSection`, so the arm is run across
// all of them rather than against the one that happened to be read. A
// per-format renderer added later that re-implements the line would escape a
// single-format assertion.
const FORMATS = ['epic', 'athena', 'cerner', 'eclinicalworks'] as const;

describe('F12-e — a frozen level with no prose never prints `undefined`', () => {
  for (const fmt of FORMATS) {
    it(`${fmt}: prints the CODE and no undefined`, () => {
      const out = formatForEhr(fmt, data(FROZEN_WITHOUT_PROSE));
      expect(out).toContain('99214');
      expect(out).not.toContain('undefined');
      // and specifically not the dangling separator
      expect(out).not.toMatch(/99214\s+—\s*$/m);
    });
  }

  it('the CONTROL — the same assertion FAILS to be vacuous: prose still prints when present', () => {
    // Without this, `not.toContain('undefined')` would pass just as happily on
    // a renderer that had stopped printing the E/M line altogether.
    const out = formatForEhr('epic', data(FROZEN_WITH_PROSE));
    expect(out).toContain('99214 — Established patient, moderate complexity');
  });

  // ── THE DOCX SURFACE — the signed Word download, and the signed PDF via
  //    Gotenberg, both converge on `generateVisitDocx`. Same defect, second
  //    site: `docx-generator.ts:259` interpolated the description into its own
  //    TextRun, so the document carried a run reading "   undefined".
  it('DOCX: a frozen level with no prose renders the code and no `undefined`', async () => {
    const text = await docxText(FROZEN_WITHOUT_PROSE);
    expect(text).toContain('99214');
    expect(text).not.toContain('undefined');
  });

  it('DOCX CONTROL — prose still renders when present, so the arm above is not vacuous', async () => {
    const text = await docxText(FROZEN_WITH_PROSE);
    expect(text).toContain('99214');
    expect(text).toContain('Established patient, moderate complexity');
  });

  it('the E/M line is actually REACHED — non-vacuity on the section itself', () => {
    // `cptSection` returns [] when there is no em, no procedure and no
    // modifier. If that early return fired, every assertion above would pass
    // for the wrong reason.
    const out = formatForEhr('epic', data(FROZEN_WITHOUT_PROSE));
    expect(out).toMatch(/PROCEDURES \/ E&M|PROCEDURES\/E&M/i);
  });
});
