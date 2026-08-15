// ============================================================================
// RENDERED NUMBERS === STORED NUMBERS.
//
// ⚠️ THE NOTE'S OWN "1. 2. 3." ARE CONTENT, NOT STYLING. The DOCX builder used
// to drop them and attach `numbering: { reference: 'plan-numbering' }`, letting
// Word paint the number. ONE numbering instance is shared by the whole
// document, so a second numbered section CONTINUED the first — a note storing
// RECOMMENDATIONS 1/2/3 exported as 4/5/6.
//
// Measured on the real signed visit before the fix, not on a fixture:
//   NUMID-SEQUENCE  => ["2","2","2","2","2","2"]   (all six, one instance)
//   LITERAL-MARKERS-SURVIVE => false               (author's numbers discarded)
//
// "Recommendation 1" is something a doctor wrote and may refer to elsewhere. A
// renderer that silently calls it 4 has changed the record while claiming to
// style it. This test is the invariant: whatever the note stores is what the
// document shows.
//
// ⚠️ IT ASSERTS THE ORDERED SEQUENCE, NOT A SET. `toEqual` on the array is
// deliberate — a set comparison passes on 1,2,3,1,2,3 rendered in the wrong
// order, and an order defect in a numbered clinical list is exactly as wrong
// as a renumber.
// ============================================================================
import { describe, expect, it } from 'vitest';
import JSZip from 'jszip';

import { generateVisitDocx } from '@/lib/docx-generator';

const SECTION_A = ['1. Alpha finding', '2. Beta finding', '3. Gamma finding'];
const SECTION_B = ['1. First recommendation', '2. Second recommendation'];

const NOTE = [
  '## POSTOPERATIVE FINDINGS',
  '',
  ...SECTION_A,
  '',
  '## RECOMMENDATIONS',
  '',
  ...SECTION_B,
  '',
].join('\n');

const DATA = {
  visitId: 'v_fidelity',
  patientName: 'Numbering Fidelity',
  specialty: 'gastroenterology',
  chiefComplaint: null,
  status: 'READY',
  createdAt: new Date('2026-08-15T00:00:00Z'),
  signedAt: new Date('2026-08-15T00:00:00Z'),
  clinicianName: 'Dr Test',
  clinicianEmail: 't@example.invalid',
  soapText: NOTE,
  icdCodes: [],
  em: null,
  procedures: [],
  modifiers: [],
  prescriptions: [],
  rxWarnings: [],
  referrals: [],
  patientSummary: null,
  headerFields: [],
} as never;

async function documentXml(): Promise<string> {
  const buf = await generateVisitDocx(DATA);
  const zip = await JSZip.loadAsync(buf);
  return zip.file('word/document.xml')!.async('string');
}

/** Every `N.` that appears as VISIBLE TEXT, in document order. */
function renderedMarkers(xml: string): string[] {
  return [...xml.matchAll(/<w:t[^>]*>\s*(\d+)\.\s/g)].map((m) => m[1]);
}

describe('DOCX numbered lists reproduce the note’s own numbers', () => {
  it('the stored note really does restart at 1 — the fixture is not begging the question', () => {
    // NON-VACUITY. If the fixture itself ran 1..5 the test would pass on a
    // builder that renumbers, which is the defect.
    expect(SECTION_A.map((l) => l[0])).toEqual(['1', '2', '3']);
    expect(SECTION_B.map((l) => l[0])).toEqual(['1', '2']);
  });

  it('RENDERED NUMBERS === STORED NUMBERS, across two adjacent sections', async () => {
    const xml = await documentXml();
    expect(
      renderedMarkers(xml),
      'the exported numbers differ from the ones the note stores — the second ' +
        'numbered section is continuing the first instead of restarting, which ' +
        'changes what the signed record says',
    ).toEqual(['1', '2', '3', '1', '2']);
  });

  it('no numbered paragraph delegates its number to Word', async () => {
    const xml = await documentXml();
    // ⚠️ THE MECHANISM, PINNED SEPARATELY FROM THE SYMPTOM. Numbers could be
    // right today and repainted tomorrow by a numbering reference creeping
    // back; this arm fails the moment one does.
    expect(
      (xml.match(/<w:numId w:val="\d+"/g) ?? []).length,
      'a paragraph carries a Word numbering reference again — Word will repaint ' +
        'the numbers and a second section will continue the first',
    ).toBe(0);
  });

  it('the markers survive as literal text', async () => {
    const xml = await documentXml();
    expect(/<w:t[^>]*>\s*1\.\s/.test(xml)).toBe(true);
  });
});
