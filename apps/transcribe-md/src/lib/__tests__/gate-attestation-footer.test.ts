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
  for (const name of Object.keys(zip.files).sort()) {
    if (!/^word\/footer\d*\.xml$/.test(name)) continue;
    footerTexts.push(visibleText(await zip.file(name)!.async('string')));
  }

  const documentXml = await zip.file('word/document.xml')!.async('string');
  // ⚠️ SCOPED TO `w:sectPr`. A footerReference is only a reference where the
  // section properties are; matching the whole document would count one
  // sitting anywhere.
  const sectPr = documentXml.slice(documentXml.indexOf('<w:sectPr'));
  return {
    footerTexts,
    // ⚠️ THE ARM THAT SEPARATES "the part exists" FROM "every page shows it".
    footerReferenceTypes: [
      ...sectPr.matchAll(/<w:footerReference[^>]*w:type="([^"]+)"/g),
    ].map((m) => m[1]),
    documentText: visibleText(documentXml),
  };
}

/** Everything a reader sees, runs concatenated. */
function visibleText(xml: string): string {
  return [...xml.matchAll(/<w:t[^>]*>([\s\S]*?)<\/w:t>/g)].map((m) => m[1]).join('');
}

describe('RULING #117 — the attestation footer', () => {
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
