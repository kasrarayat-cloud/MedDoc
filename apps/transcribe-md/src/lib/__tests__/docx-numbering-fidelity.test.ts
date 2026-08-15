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
// ----------------------------------------------------------------------------
// ⚠️ THE FIRST VERSION OF THIS GUARD PASSED 4 OF 4 AGAINST TWO REGRESSIONS THAT
// EACH CHANGE A SIGNED RECORD. Both were measured against the real generator,
// with the mutation asserted as applied, before this rewrite:
//
//   · A PER-SECTION RENUMBERER written in JS instead of OOXML — the identical
//     defect one layer up — rendered ["1","2","3","1","2"] and PASSED, because
//     the old fixture STORED exactly 1,2,3 / 1,2. A fixture holding the
//     canonical restart sequence cannot tell "rendered === stored" apart from
//     "rendered === canonical 1..n", which is the entire question.
//   · DELETING EVERY NUMBERED ITEM'S CLINICAL TEXT PASSED, because the marker
//     regex stopped at the marker: `<w:t>1. </w:t>` satisfies it with the
//     finding gone. An absent finding is content the doctor did not see.
//
// So the fixture now stores numbers NO RENUMBERER CAN PRODUCE — a gap where an
// item was deleted (1, 2, 4) and a list that starts at 2 — and the arms assert
// the WHOLE LINE, never the marker alone.
//
// ⚠️ AND IT CARRIES BULLETS ON PURPOSE. Word bullets emit `w:numId` too, so the
// old document-wide `w:numId === 0` arm was green only because the fixture had
// no bullets. That is an invariant which could never be checked against a
// realistically shaped note, and a false RED waiting for whoever first made the
// fixture realistic — whose cheapest response would be to loosen the only arm
// pinning the mechanism. It is now scoped to the numbered paragraphs, and keeps
// the bullets as its positive control.
// ============================================================================
import { describe, expect, it } from 'vitest';
import JSZip from 'jszip';

import { generateVisitDocx } from '@/lib/docx-generator';

/** ⚠️ NOT 1,2,3 — the gap is deliberate: a doctor deleted the third finding.
 *  No renumbering scheme, continuous or per-section, emits this. */
const SECTION_A = ['1. Alpha finding', '2. Beta finding', '4. Delta finding'];
/** ⚠️ NOT starting at 1, for the same reason. Carries inline markdown so the
 *  line-equality arm covers formatted content too. */
const SECTION_B = ['2. **Second** recommendation', '3. Third recommendation'];
/** Ordinary bullets — what every real note has, and the mechanism arm's
 *  positive control. */
const BULLETS = ['- Ambulate as tolerated', '- Diet as before'];

const NUMBERED = [...SECTION_A, ...SECTION_B];

const NOTE = [
  '## POSTOPERATIVE FINDINGS',
  '',
  ...SECTION_A,
  '',
  '## RECOMMENDATIONS',
  '',
  ...SECTION_B,
  '',
  '## DISCHARGE INSTRUCTIONS',
  '',
  ...BULLETS,
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

/** Each `<w:p>` element's body. `<w:pPr>` and `<w:pStyle>` do NOT match — the
 *  split requires a space or `>` immediately after `<w:p`. */
function paragraphs(xml: string): string[] {
  return xml.split(/<w:p[ >]/).slice(1);
}

/** Everything the reader actually sees in one paragraph, runs concatenated. */
function visibleText(paragraph: string): string {
  return [...paragraph.matchAll(/<w:t[^>]*>([\s\S]*?)<\/w:t>/g)]
    .map((m) => m[1])
    .join('');
}

/** Inline markdown is styling, so it is not part of the visible text. */
const plain = (line: string) => line.replace(/\*/g, '');

/** `N.` at the start of what the reader sees — the shape this guard is about. */
const LEADING_MARKER = /^\s*(\d+)\.\s/;

describe('DOCX numbered lists reproduce the note’s own numbers', () => {
  it('the STORED numbers are ones no renumberer could produce', () => {
    // ⚠️ NON-VACUITY — AND THE ARM THE FIRST VERSION GOT BACKWARDS. Asserting
    // "each section restarts at 1" PINNED the fixture to the exact sequence a
    // per-section renumberer emits, which is what made that regression
    // invisible. The property that matters is the opposite one.
    const stored = NUMBERED.map((l) => l.match(LEADING_MARKER)![1]);
    expect(stored).toEqual(['1', '2', '4', '2', '3']);

    const continuous = NUMBERED.map((_, i) => String(i + 1));
    const perSection = [
      ...SECTION_A.map((_, i) => String(i + 1)),
      ...SECTION_B.map((_, i) => String(i + 1)),
    ];
    expect(stored, 'a continuous renumberer would be indistinguishable').not.toEqual(continuous);
    expect(stored, 'a per-section renumberer would be indistinguishable').not.toEqual(perSection);
  });

  it('EVERY numbered line renders EXACTLY as stored, in order', async () => {
    const numbered = paragraphs(await documentXml())
      .map(visibleText)
      .filter((t) => LEADING_MARKER.test(t));

    // ⚠️ THE WHOLE LINE, NOT THE MARKER. Asserting only the markers passed with
    // every finding's text deleted.
    // ⚠️ AND AS AN ORDERED SEQUENCE: a set comparison passes on the right
    // numbers in the wrong order, and misordering a numbered clinical list is
    // as wrong as renumbering it.
    expect(
      numbered,
      'the exported numbered lines differ from the ones the note stores — the ' +
        'export has changed what the signed record says',
    ).toEqual(NUMBERED.map(plain));
  });

  it('no NUMBERED paragraph delegates its number to Word — while bullets still do', async () => {
    const paras = paragraphs(await documentXml());
    const delegating = paras.filter((p) => p.includes('<w:numId'));

    // ⚠️ THE MECHANISM, PINNED SEPARATELY FROM THE SYMPTOM. The numbers could be
    // right today and repainted tomorrow by a numbering reference creeping back;
    // this fails the moment one does, even if the numbers look right that day.
    for (const p of delegating) {
      expect(
        visibleText(p),
        'a numbered paragraph carries a Word numbering reference again — Word ' +
          'will repaint the numbers and a second section will continue the first',
      ).not.toMatch(LEADING_MARKER);
    }

    // ⚠️ POSITIVE CONTROL, AND IT IS WHY THIS ARM IS SCOPED RATHER THAN A
    // DOCUMENT-WIDE ZERO. Bullets legitimately delegate. A document-wide
    // `w:numId === 0` was satisfiable by a document containing no lists at all.
    expect(
      delegating.length,
      'the fixture’s bullets should still be a real Word list',
    ).toBe(BULLETS.length);
  });

  it('the markers survive as literal text', async () => {
    // ⚠️ IMPLIED BY THE LINE-EQUALITY ARM ABOVE — kept for the failure message
    // and NOT counted as independent coverage. The two discriminating arms are
    // the line-equality one and the mechanism one.
    const xml = await documentXml();
    expect(/<w:t[^>]*>\s*4\.\s/.test(xml)).toBe(true);
  });
});
