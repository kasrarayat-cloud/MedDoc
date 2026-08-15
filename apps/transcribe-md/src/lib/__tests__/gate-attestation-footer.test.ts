// ============================================================================
// RULING #117 — AN UNSIGNED EXPORT IS MARKED ON EVERY PAGE.
//
// The retired PDF builder painted `Signed electronically by …` / `Not yet
// signed.` on EVERY page through a `pageAdded` hook (`pdf-generator.ts:190`).
// The DOCX builder rendered it ONCE, in the body, on the last page — and
// `new Footer(` appeared ZERO times in the file against a control of 29
// `new Paragraph(`. So converging export onto the DOCX (F3 / ruling #113)
// would have dropped per-page draft marking silently.
//
// ⚠️ AND THE DEFECT IS LIVE ON `main` TODAY, INDEPENDENT OF F3. The Word
// download and the on-screen preview are BOTH renders of this builder's bytes,
// so pages 1..n-1 of an unsigned three-page note are already typographically
// indistinguishable from a finished record. F3 is what makes it reach the PDF
// too; it is not what creates it.
//
// THE MATRIX THIS GUARD PINS — all four cells, both directions:
//
//   |           | SIGNED                       | UNSIGNED               |
//   |-----------|------------------------------|------------------------|
//   | standard  | (b) the attestation          | (a) DRAFT — Not yet…   |
//   | form-only | (c) NO footer at all         | (a) DRAFT — Not yet…   |
//
// ⚠️ ASSERTING ONLY THE CELLS #117 ADDS WOULD LET A FUTURE EDIT REMOVE (c),
// which was already correct — reproducing the original defect inverted. Every
// cell is asserted, and the failure messages name which side went.
//
// ----------------------------------------------------------------------------
// ⚠️ THREE TRAPS THIS FILE IS BUILT AROUND, EACH ONE ALREADY PAID FOR HERE:
//
//   · SUBSTRING. `DRAFT — Not yet signed.` CONTAINS the in-body `Not yet
//     signed.`. A `toContain` over document.xml is satisfied by the in-body
//     line alone and would have been green before this change existed. Every
//     text assertion is an EXACT match, scoped to the footer PART.
//
//   · TEXT PRESENCE IS NOT MEMBERSHIP — AND NEITHER IS REFERENCE PRESENCE.
//     ⚠️ THIS ARM WAS WRONG ON ITS FIRST WRITING AND THE MUTATION PROOF IS
//     WHAT SAID SO. It asserted `footerReferences > 0`, which a one-line edit
//     attaching the footer as `{ first: … }` instead of `{ default: … }`
//     satisfies perfectly — 5 of 5 GREEN. Measured on the emitted OOXML:
//
//         <w:footerReference w:type="first" r:id="rId7"/>     titlePg: false
//
//     A first-page footer is honoured ONLY when `w:titlePg` is set on the
//     section, and `docx` does not set it. So that mutation produces a valid
//     footer part, a valid reference, and a draft marked on ZERO pages — a
//     strictly worse document than the defect #117 exists to fix, passing a
//     guard written to prevent exactly it. The TYPE is the property; presence
//     never was.
//
//   · VACUITY. Every arm here could pass on a builder that emits an empty
//     document, so the non-vacuity arm asserts the note's own body text made
//     it through the same call.
//
// ----------------------------------------------------------------------------
// HONEST LIMITS — MEASURED, so this guard is not read wider than it is.
//
//   · ⚠️ IT WATCHES ONE OF FOUR ATTESTATION EMITTERS. Measured: re-drifting
//     `pdf-generator.ts` back to its own inline string leaves this file
//     **7 of 7 GREEN**. `pdf-native/export.ts` (unsigned → NOTHING on any
//     page; signed → page 1 only) and `ehr-formatters.ts` (a third date
//     format) are likewise unwatched. The shared source in `visit-export.ts`
//     is what holds them together, and nothing here enforces its adoption.
//
//   · ⚠️ IT PROVES THE OOXML, NOT THE RENDER. Ruling #117(e) asks for a
//     multi-page proof THROUGH THE REAL CONVERTER, "because PAGE COUNT IS
//     LIBREOFFICE'S". This fixture is ONE page, so "on every page" is
//     asserted over a set of size one, and `w:type="default"` is a PROXY for
//     what LibreOffice actually paints. #117(e) is NOT delivered here.
//     The `titlePg` / even-odd / `vanish` / section-count arms below exist
//     precisely because they are the ways that proxy comes apart — but they
//     are still structure, not pixels.
// ============================================================================
import { describe, expect, it } from 'vitest';
import JSZip from 'jszip';

import { generateVisitDocx } from '@/lib/docx-generator';
import {
  DRAFT_FOOTER_LINE,
  signedAttestationLine,
  type VisitExportData,
} from '@/lib/visit-export';

const SIGNED_AT = new Date('2026-08-15T00:00:00Z');
/** A line from the note body — the non-vacuity control. */
const BODY_MARKER = 'Alpha finding recorded at the bedside';

function data(over: Partial<VisitExportData>): VisitExportData {
  return {
    visitId: 'v_footer',
    patientName: 'Footer Fixture',
    specialty: 'gastroenterology',
    chiefComplaint: null,
    status: 'READY',
    createdAt: new Date('2026-08-10T00:00:00Z'),
    signedAt: null,
    clinicianName: 'Dr Test',
    clinicianEmail: 't@example.invalid',
    soapText: `## FINDINGS\n\n${BODY_MARKER}\n`,
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

interface Packed {
  /** Every `word/footer*.xml` part, as visible text. */
  footerTexts: string[];
  /** Every `word/footer*.xml` part, RAW — the visible text says what the runs
   *  contain, not whether they render. `w:vanish`, a white fill or a 1pt size
   *  leave `<w:t>` byte-identical and the footer unreadable. */
  footerXml: string[];
  /** `<w:titlePg/>` — "different first page". ⚠️ With it set and no `first`
   *  footer defined, page 1 renders NO footer, so page 1 of every one-page
   *  draft is unmarked while the `default` reference still reads correct. */
  titlePg: boolean;
  /** `word/settings.xml`'s `w:evenAndOddHeaders`. ⚠️ Enabled, the `default`
   *  footer stops applying to EVEN pages — pages 2 and 4 of a 4-page draft go
   *  bare with `document.xml` byte-unchanged. */
  evenAndOddHeaders: boolean;
  /** How many sections the document has. ⚠️ Footers attach PER SECTION, so an
   *  appended second section is unmarked in its entirety and the reference set
   *  of the first is unchanged. */
  sectionCount: number;
  /** The `w:type` of every footer the SECTION references, in document order.
   *  ⚠️ `'default'` is the ONLY type that renders on every page. `'first'`
   *  needs `w:titlePg` (never set here) and `'even'` needs the document-level
   *  even/odd setting, so either one marks a subset of pages or none at all. */
  footerReferenceTypes: string[];
  documentText: string;
}

async function pack(over: Partial<VisitExportData>): Promise<Packed> {
  const zip = await JSZip.loadAsync(await generateVisitDocx(data(over)));

  const footerTexts: string[] = [];
  const footerXml: string[] = [];
  for (const name of Object.keys(zip.files).sort()) {
    if (!/^word\/footer\d*\.xml$/.test(name)) continue;
    const raw = await zip.file(name)!.async('string');
    footerXml.push(raw);
    footerTexts.push(visibleText(raw));
  }

  // `<w:evenAndOddHeaders w:val="false"/>` is the OFF state docx emits; the
  // element with no `w:val`, or a truthy one, is ON.
  const settings = (await zip.file('word/settings.xml')?.async('string')) ?? '';
  const evenOdd = settings.match(/<w:evenAndOddHeaders([^>]*)\/>/);

  const documentXml = await zip.file('word/document.xml')!.async('string');
  // ⚠️ SCOPED TO `w:sectPr`. A footerReference is only a reference where the
  // section properties are; matching the whole document would count one
  // sitting anywhere.
  // ⚠️ AND THE BOUND IS ASSERTED RATHER THAN ASSUMED. `indexOf` returns -1 when
  // absent, and `slice(-1)` is the LAST CHARACTER — which yields zero matches
  // and would silently SATISFY the signed-form-only arm, whose expected value
  // is []. An emptiness answer computed from a missing haystack is the
  // broken-instrument failure, so the haystack is established first.
  const sectPrAt = documentXml.indexOf('<w:sectPr');
  expect(sectPrAt, 'no <w:sectPr> — the reference scan would measure nothing').toBeGreaterThan(-1);
  const sectPr = documentXml.slice(sectPrAt);
  return {
    footerTexts,
    footerXml,
    // ⚠️ THE ARM THAT SEPARATES "the part exists" FROM "every page shows it".
    footerReferenceTypes: [
      ...sectPr.matchAll(/<w:footerReference[^>]*w:type="([^"]+)"/g),
    ].map((m) => m[1]),
    titlePg: /<w:titlePg[ />]/.test(documentXml),
    evenAndOddHeaders: evenOdd ? !/w:val="(false|0)"/.test(evenOdd[1]) : false,
    sectionCount: [...documentXml.matchAll(/<w:sectPr[ >]/g)].length,
    documentText: visibleText(documentXml),
  };
}

/** Everything a reader sees, runs concatenated. */
function visibleText(xml: string): string {
  return [...xml.matchAll(/<w:t[^>]*>([\s\S]*?)<\/w:t>/g)].map((m) => m[1]).join('');
}

describe('RULING #117 — the attestation footer', () => {
  it('THE LITERAL STRINGS ARE PINNED — every other arm compares output to these', () => {
    // ⚠️ WITHOUT THIS ARM EVERY TEXT ASSERTION IN THIS FILE IS A TAUTOLOGY.
    // They compare the emitted text to a constant imported FROM THE MODULE
    // UNDER TEST, so `DRAFT_FOOTER_LINE = ''` ships a footer paragraph with no
    // characters — a draft "marked" on every page with nothing on it — and
    // `= 'Not yet signed.'` silently discards the DRAFT word, which is the one
    // edit the constant's own doc-comment argues against. Both were MEASURED
    // green against the previous version of this file. The output must be
    // pinned to the ruling's words, not to itself.
    expect(DRAFT_FOOTER_LINE).toBe('DRAFT — Not yet signed.');
    expect(DRAFT_FOOTER_LINE.startsWith('DRAFT'), 'a draft leads with the word').toBe(true);
    expect(signedAttestationLine('Dr Test', SIGNED_AT)).toBe(
      'Signed electronically by Dr Test on 2026-08-15.'
    );
    // The fallback a null clinician takes — an attestation naming nobody is
    // still an attestation, and it must not read as an empty signature.
    expect(signedAttestationLine(null, SIGNED_AT)).toBe(
      'Signed electronically by Clinician on 2026-08-15.'
    );
  });

  it('NOTHING OUTSIDE THE FOOTER CAN UNMARK IT — the four measured false greens', async () => {
    // ⚠️ EVERY ONE OF THESE PASSED 5 OF 5 AGAINST THE PREVIOUS VERSION OF THIS
    // GUARD, measured on real emitted OOXML rather than argued. A footer's
    // reference type being right does not mean the footer is READ.
    const draft = await pack({ signedAt: null });

    // 1 — `titlePage: true` + no `first` footer = page 1 renders NO footer.
    //     On a one-page draft, that is the whole document.
    expect(draft.titlePg, 'titlePg unmarks page 1 while `default` still reads correct').toBe(false);

    // 2 — even/odd headers = the `default` footer stops applying to EVEN pages.
    //     `document.xml` is byte-unchanged; the switch lives in settings.xml,
    //     which nothing here used to read.
    expect(draft.evenAndOddHeaders, 'even/odd would bare pages 2 and 4').toBe(false);

    // 3 — the run can be made INVISIBLE with `<w:t>` byte-identical: `vanish`,
    //     a white fill, a 2pt size. `visibleText()` reads what the XML says,
    //     never what renders.
    const [xml] = draft.footerXml;
    expect(xml, 'a vanished run is not a marking').not.toMatch(/<w:vanish/);
    expect(xml, 'the muted grey the in-body block uses').toContain('666666');
    expect(xml, 'half-points: 18 = 9pt, legible').toContain('w:sz w:val="18"');

    // 4 — footers attach PER SECTION, so an appended section is unmarked in
    //     full while the first section's reference set is untouched. One
    //     section is the contract; a second one must fail HERE and be handled
    //     deliberately rather than render quietly.
    expect(draft.sectionCount, 'a second section would be entirely unmarked').toBe(1);
  });

  it('UNSIGNED standard: the draft marking is in a referenced section footer', async () => {
    const { footerTexts, footerReferenceTypes, documentText } = await pack({ signedAt: null });

    expect(footerTexts, 'exactly one footer part').toHaveLength(1);
    // EXACT, not toContain — the in-body 'Not yet signed.' is a substring of this.
    expect(footerTexts[0]).toBe(DRAFT_FOOTER_LINE);
    // ⚠️ `default` EXACTLY. `first` without `w:titlePg` marks no page at all.
    expect(
      footerReferenceTypes,
      'only a DEFAULT footer reference renders on every page'
    ).toEqual(['default']);

    // NON-VACUITY: the same call really did build a document.
    expect(documentText).toContain(BODY_MARKER);
  });

  it('UNSIGNED form-only: marked too — a draft is a draft on anyone’s paper (#117a)', async () => {
    const { footerTexts, footerReferenceTypes } = await pack({
      signedAt: null,
      formOnly: true,
      formTitle: 'Operative Note',
    });

    expect(
      footerTexts,
      'form-only is chrome-free for FINAL documents ONLY — #117(a) overrides #117(c) while unsigned'
    ).toHaveLength(1);
    expect(footerTexts[0]).toBe(DRAFT_FOOTER_LINE);
    expect(footerReferenceTypes).toEqual(['default']);
  });

  it('SIGNED standard: the attestation, from the SAME source as the in-body block (#117b)', async () => {
    const { footerTexts, footerReferenceTypes, documentText } = await pack({
      signedAt: SIGNED_AT,
    });

    const expected = signedAttestationLine('Dr Test', SIGNED_AT);
    expect(footerTexts).toHaveLength(1);
    expect(footerTexts[0]).toBe(expected);
    expect(footerReferenceTypes).toEqual(['default']);

    // ⚠️ ONE TRUTH. Two call sites composing this independently is how a
    // document ends up disagreeing with itself; the body must carry the
    // byte-identical string, not merely a similar one.
    expect(documentText, 'the in-body block and the footer are one string')
      .toContain(expected);

    // And the draft marking must be nowhere on a signed record.
    expect(footerTexts[0]).not.toBe(DRAFT_FOOTER_LINE);
  });

  it('SIGNED form-only: NO QuillMD chrome — the form’s own field IS the attestation (#117c)', async () => {
    const { footerTexts, footerReferenceTypes, documentText } = await pack({
      signedAt: SIGNED_AT,
      formOnly: true,
      formTitle: 'Operative Note',
    });

    // ⚠️ THE SIDE THAT WAS ALREADY CORRECT. It is asserted so that a future
    // edit "completing the matrix" cannot quietly stamp QuillMD chrome onto a
    // finished document on the doctor's own paper.
    expect(footerTexts, 'signed form-only carries no QuillMD footer').toHaveLength(0);
    expect(footerReferenceTypes, 'and nothing references one').toEqual([]);

    // NON-VACUITY: it is a real document, and specifically NOT the standard one.
    expect(documentText).toContain(BODY_MARKER);
    expect(
      documentText,
      'the standard attestation must not appear in the body either'
    ).not.toContain(signedAttestationLine('Dr Test', SIGNED_AT));
  });

  it('the four cells are DISTINCT — a builder ignoring its inputs cannot pass', async () => {
    // ⚠️ NON-VACUITY FOR THE MATRIX ITSELF. Each arm above is individually
    // satisfiable by a builder that emits one fixed footer forever; what makes
    // them a matrix is that the cells DIFFER.
    const cells = await Promise.all([
      pack({ signedAt: null }),
      pack({ signedAt: null, formOnly: true, formTitle: 'Operative Note' }),
      pack({ signedAt: SIGNED_AT }),
      pack({ signedAt: SIGNED_AT, formOnly: true, formTitle: 'Operative Note' }),
    ]);

    expect(cells.map((c) => c.footerTexts.length)).toEqual([1, 1, 1, 0]);
    expect(cells.map((c) => c.footerReferenceTypes)).toEqual([
      ['default'],
      ['default'],
      ['default'],
      [],
    ]);
    expect(cells.map((c) => c.footerTexts[0] ?? null)).toEqual([
      DRAFT_FOOTER_LINE,
      DRAFT_FOOTER_LINE,
      signedAttestationLine('Dr Test', SIGNED_AT),
      null,
    ]);
    // The signed and unsigned strings are genuinely different documents.
    expect(DRAFT_FOOTER_LINE).not.toBe(signedAttestationLine('Dr Test', SIGNED_AT));
  });
});
