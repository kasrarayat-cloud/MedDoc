// ============================================================================
// R1.4 — the paper the export is drawn on, asserted on the bytes.
// (It read "the two generators draw the SAME paper" until ruling #113 left one.)
// ----------------------------------------------------------------------------
// C2-b pinned the PAGE (US Letter, both units). This pins what is drawn ON it.
//
// ⚠️ EVERY DIVERGENCE BELOW WAS SHIPPING, AND ALL OF THEM WERE INVISIBLE TO THE
// CHECK THAT LOOKED LIKE IT COVERED THEM. The Gate B parity clause compares
// section-heading STRINGS pulled through `helpers/exportText.ts`, which strips
// XML tags and reads the PDF with a text extractor. "DIAGNOSES" and "DIAGNOSES"
// match whether one is 11pt over nothing and the other is 12pt over a hairline.
//
//   role              PDF                  DOCX                  status
//   ---------------   ------------------   -------------------   -----------
//   section size      12pt                 22 half-pt = 11pt     was SPLIT
//   section rule      200pt hairline       none at all           was SPLIT
//   section tracking  1.2pt                20 = 1.0pt            was SPLIT
//   title rule        drawn                none at all           was SPLIT
//   metadata layout   n side-by-side       n side-by-side        was SHARED,
//                                                                 both wrong
//
// The preview a doctor reads is a LibreOffice render OF THE DOCX. So a split
// here is not "the Word file looks a bit different" — it is the preview and the
// download disagreeing, which SPEC.md:200 forbids outright.
//
// ⚠️ FLAG-INDEPENDENT, like its C2-b sibling. Both generators run with
// `NEXT_PUBLIC_SKIN_ROUNDS` off; this ships to every doctor today.
// ============================================================================

import { readFileSync } from 'node:fs';

import JSZip from 'jszip';
import { describe, expect, it } from 'vitest';

import { generateVisitDocx } from '../docx-generator';
import {
  TYPE_PT,
  RULE_PT,
  LOCKUP_PT,
  SECTION_MARK,
  SECTION_TRACKING_PT,
  EMPTY_VALUE,
  EXPORT_COLOR,
  META_LABEL_COL_PT,
  CONTENT_WIDTH_PT,
  toHalfPt,
  toTwip,
  toEighthPt,
  bareHex,
} from '../export-page';
import type { VisitExportData } from '../visit-export';

function fixture(overrides: Partial<VisitExportData> = {}): VisitExportData {
  return {
    visitId: 'v_r1_paper',
    patientName: 'Paper Fixture',
    specialty: 'Primary Care',
    chiefComplaint: 'Cough',
    status: 'SIGNED',
    createdAt: new Date('2026-08-01T00:00:00Z'),
    signedAt: new Date('2026-08-01T00:00:00Z'),
    clinicianName: 'Dr. Ada Lovelace',
    clinicianEmail: 'ada@example.test',
    soapText:
      'Subjective\nCough for three days.\n\nObjective\nChest clear.\n\nAssessment\nViral URI.\n\nPlan\nRest.',
    icdCodes: [
      {
        code: 'J06.9',
        description: 'Acute URI, unspecified',
        evidence_quote: 'Cough for three days.',
        confidence: 0.9,
      },
    ],
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
    ...overrides,
  };
}

async function docxXml(data = fixture()): Promise<string> {
  const buf = await generateVisitDocx(data);
  const zip = await JSZip.loadAsync(buf);
  return zip.file('word/document.xml')!.async('string');
}


/**
 * The enclosing `<w:p>` for a piece of text.
 *
 * ⚠️ Anchored on `'<w:p '` and `'<w:p>'`, never on the bare `'<w:p'` — that
 * prefix is a substring of `<w:pPr>` and `<w:pBdr>`, so a bare match silently
 * returns a slice that STARTS INSIDE the paragraph's own properties. Found by
 * writing it the wrong way first: the title slice began at `<w:pBdr>`.
 * `Math.max` because either form may be the nearer one.
 */
function paragraphAround(xml: string, text: string): string | null {
  const at = xml.indexOf(text);
  if (at === -1) return null;
  const start = Math.max(xml.lastIndexOf('<w:p ', at), xml.lastIndexOf('<w:p>', at));
  const end = xml.indexOf('</w:p>', at);
  return start === -1 || end === -1 ? null : xml.slice(start, end + 6);
}

/** The paragraph XML for a named section heading, run properties included. */
function headingParagraph(xml: string, name: string): string | null {
  // Word splits a run at will, so the mark and the name can land in separate
  // <w:t>s. Anchor on the NAME and take the enclosing <w:p>.
  const at = xml.indexOf(name.toUpperCase());
  if (at === -1) return null;
  const start = xml.lastIndexOf('<w:p ', at) >= 0 ? xml.lastIndexOf('<w:p ', at) : xml.lastIndexOf('<w:p>', at);
  const end = xml.indexOf('</w:p>', at);
  return start === -1 || end === -1 ? null : xml.slice(start, end + 6);
}

// ⚠️ `PDF_SRC` STOOD HERE. `pdf-generator.ts` was retired by ruling #113, and
// with it every "the two generators agree" assertion in this file.
//
// R1.4's job was to stop ONE paper drifting into TWO. That is now structural
// rather than tested: there is one builder, the PDF download is LibreOffice's
// render of its bytes, and two renderers cannot disagree when there is one.
// What survives — and is still load-bearing — is every assertion that pins the
// DOCX's OWN typography to the shared `export-page.ts` tokens, because those
// are what the single paper is drawn with.
const DOCX_SRC = readFileSync('src/lib/docx-generator.ts', 'utf8');


describe('R1.4 — the harness reads real artifacts', () => {
  it('POSITIVE CONTROL — both generators produce a document with content', async () => {
    // Without this every "the bytes say X" assertion below could be passing on
    // an empty string, which is the vacuity this project has shipped twice.
    const xml = await docxXml();
    expect(xml.length, 'the DOCX document.xml is empty').toBeGreaterThan(2000);
    expect(xml).toContain('DIAGNOSES');
  });

  it('NEGATIVE CONTROL — the heading locator returns null for a heading that is not there', async () => {
    const xml = await docxXml();
    expect(
      headingParagraph(xml, 'NOT-A-SECTION-IN-THIS-DOCUMENT'),
      'the locator found a paragraph for a heading that does not exist, so ' +
        'every assertion built on it is meaningless',
    ).toBeNull();
    expect(headingParagraph(xml, 'Diagnoses')).not.toBeNull();
  });
});

describe('R1.4 — section headings take the shared type tokens', () => {
  it('the DOCX heading is 12pt — it was 11pt while the PDF drew 12pt', async () => {
    const p = headingParagraph(await docxXml(), 'Diagnoses')!;
    const sz = Number(p.match(/<w:sz w:val="(\d+)"/)?.[1] ?? NaN);
    expect(sz, `heading run size, in half-points; paragraph was:\n${p}`).toBe(
      toHalfPt(TYPE_PT.sectionHead),
    );
    expect(sz, 'still the old literal — 22 half-points is 11pt').not.toBe(22);
  });

  it('⚠️ the DOCX heading HAS A RULE — it had none at all', async () => {
    const p = headingParagraph(await docxXml(), 'Diagnoses')!;
    expect(
      p,
      'no <w:pBdr> on the section heading. Word has no line primitive, so a ' +
        'paragraph bottom border is the rule — without it the preview shows a ' +
        'bare heading where the downloaded PDF shows one over a hairline',
    ).toMatch(/<w:pBdr>/);
    const bottom = p.match(/<w:bottom\b[^>]*\/>/)?.[0] ?? '';
    expect(bottom, `bottom border element; paragraph:\n${p}`).toContain(
      `w:sz="${toEighthPt(RULE_PT)}"`,
    );
    expect(bottom.toUpperCase()).toContain(bareHex(EXPORT_COLOR.rule));
  });

  it('the document carries the section mark, and it is a glyph the fonts have', async () => {
    expect(await docxXml()).toContain(SECTION_MARK);
    // Guarded at the source too: the two marks a designer reaches for first
    // (▪ U+25AA, ■ U+25A0) are absent from all four Charter faces and would
    // ship as tofu. Verified with fontkit against the TTFs in fonts/.
    expect(SECTION_MARK).toBe('§');
  });

  it('the tracking agrees — 1.2pt in points, 24 in twentieths of one', async () => {
    const p = headingParagraph(await docxXml(), 'Diagnoses')!;
    expect(p).toContain(`<w:spacing w:val="${toTwip(SECTION_TRACKING_PT)}"/>`);
    expect(toTwip(SECTION_TRACKING_PT)).toBe(24);
  });
});

describe('R1.4 — the title lockup', () => {
  it('the DOCX title carries the rule the PDF has always drawn', async () => {
    const xml = await docxXml();
    const at = xml.indexOf('Ada Lovelace');
    expect(at, 'the clinician title is not in the document').toBeGreaterThan(-1);
    const start = xml.lastIndexOf('<w:p ', at) >= 0 ? xml.lastIndexOf('<w:p ', at) : xml.lastIndexOf('<w:p>', at);
    const para = xml.slice(start, xml.indexOf('</w:p>', at) + 6);
    expect(para, `title paragraph:\n${para}`).toMatch(/<w:pBdr>/);
  });

  // ⚠️ THIS READ `the lockup gaps are absolute points on BOTH sides` AND
  // ASSERTED ONE GAP, AGAINST THE SOURCE TEXT, ON A SIDE THAT NO LONGER EXISTS.
  //
  // Three separate defects, all invisible while it was green:
  //
  //  1. `BOTH sides` is a FOSSIL. Ruling #113 retired `pdf-generator.ts`; the
  //     PDF is now LibreOffice's render of these very bytes. There is one side.
  //  2. It asserted `ruleToBody` and left `eyebrowToTitle` and `titleToRule`
  //     — both live, at `docx-generator.ts:168` and `:191` — unguarded.
  //  3. ⚠️ IT PINNED A SPELLING, NOT A PROPERTY — it asserted the SOURCE TEXT
  //     of `docx-generator.ts` contained `toTwip(LOCKUP_PT.ruleToBody)`.
  //     Extracting that call into a named const — an improvement — reddens it,
  //     while any change that leaves the call site spelled the same but emits
  //     different bytes stays green. It failed for improvements and passed for
  //     regressions, which is the wrong way round.
  //
  // What is load-bearing is that each gap REACHES the rendered document, and
  // reaches it BY DERIVATION FROM THE TOKEN. `pdfkit`'s `moveDown(n)` was
  // n × the CURRENT line height, so the same call drew a different gap
  // depending on the font size in effect; the Word file has always used fixed
  // units. That is the property, and it is pinned against the bytes.
  //
  // ⚠️ WHAT THIS DELIBERATELY DOES NOT CLAIM, BECAUSE THE FIRST MUTATION
  // CAUGHT ME ASSERTING IT: it cannot detect a change to a token's VALUE.
  // The expectation is computed from the same `LOCKUP_PT` the generator reads,
  // so both sides move together and `eyebrowToTitle: 3 -> 5` stays green. That
  // is correct — the value is a design decision, not an invariant — but it
  // means the discriminating mutation is BREAKING THE DERIVATION (hard-coding
  // a literal in the generator), never editing the token. Proved that way.
  it('every lockup gap reaches the document as an absolute measure', async () => {
    const xml = await docxXml();

    // Word's unit differs per attribute, and that is not a slip: paragraph
    // spacing is twentieths of a point, a border's `space` is whole points.
    const eyebrow = paragraphAround(xml, 'QUILLMD');
    expect(eyebrow, 'the wordmark paragraph is not in the document').not.toBeNull();
    expect(eyebrow!).toContain(`<w:spacing w:after="${toTwip(LOCKUP_PT.eyebrowToTitle)}"/>`);

    const title = paragraphAround(xml, 'Ada Lovelace');
    expect(title, 'the title paragraph is not in the document').not.toBeNull();
    expect(title!).toContain(`w:space="${LOCKUP_PT.titleToRule}"`);
    expect(title!).toContain(`<w:spacing w:after="${toTwip(LOCKUP_PT.ruleToBody)}"/>`);
  });

  it('the three lockup gaps are positive and distinct — the guard cannot go vacuous', () => {
    // A zero gap would still render an attribute, and two equal gaps would let
    // one paragraph's value satisfy the other's assertion if the anchoring
    // ever slipped. Both are stated here rather than assumed.
    const gaps = [LOCKUP_PT.eyebrowToTitle, LOCKUP_PT.titleToRule, LOCKUP_PT.ruleToBody];
    for (const gap of gaps) expect(gap).toBeGreaterThan(0);
    expect(new Set(gaps).size).toBe(gaps.length);
  });
});

describe('R1.4 — metadata is a two-column key-value grid', () => {
  it('label and value take the shared type tokens, not literals', async () => {
    const xml = await docxXml();
    const at = xml.indexOf('CHIEF COMPLAINT');
    expect(at, 'the chief-complaint label is missing from the metadata').toBeGreaterThan(-1);
    const cell = xml.slice(at - 600, at + 900);
    expect(cell).toContain(`<w:sz w:val="${toHalfPt(TYPE_PT.fieldLabel)}"/>`);
    expect(cell).toContain(`<w:sz w:val="${toHalfPt(TYPE_PT.fieldValue)}"/>`);
  });

  it('the columns are a POINT width shared with the PDF, not a percentage', async () => {
    const xml = await docxXml();
    expect(xml).toContain(`w:w="${toTwip(META_LABEL_COL_PT)}"`);
    expect(xml).toContain(`w:w="${toTwip(CONTENT_WIDTH_PT - META_LABEL_COL_PT)}"`);
    // A percentage width is a different measure on a different page size — and
    // this document's page size was A4-by-accident until C2-b caught it.
  });

  it('⚠️ an empty value is a MUTED em-dash — not blank, and never a bullet', async () => {
    const data = fixture({
      headerFields: [
        { label: 'Surgeon', value: 'Dr. Ada Lovelace' },
        { label: 'Date of surgery', value: '   ' },
      ],
    } as Partial<VisitExportData>);
    const xml = await docxXml(data);

    expect(xml, 'the DOCX dropped the em-dash for the blank field').toContain(EMPTY_VALUE);

    // Muted: the absence of a value must not read with a value's weight.
    const at = xml.indexOf(EMPTY_VALUE);
    const run = xml.slice(Math.max(0, at - 400), at + 40);
    expect(run.toUpperCase(), `run around the em-dash:\n${run}`).toContain(
      bareHex(EXPORT_COLOR.textMuted),
    );

    // "No literal bullets" — the metadata grid is a grid. A bullet here would
    // mean the header block fell back to the list rendering.
    const metaSlice = xml.slice(0, xml.indexOf('CLINICAL NOTE') + 1 || 4000);
    expect(metaSlice, 'a literal bullet appears in the metadata block').not.toContain('•');
  });

  it('the grid is one row PER FIELD — it used to narrow itself as it grew', async () => {
    const four = await docxXml();
    // Patient, Visit date, Chief complaint, Status = 4 rows in the first table.
    const firstTable = four.slice(four.indexOf('<w:tbl>'), four.indexOf('</w:tbl>'));
    const rows = (firstTable.match(/<w:tr\b/g) ?? []).length;
    expect(
      rows,
      'the metadata table is not one row per field. The old layout put all ' +
        'four side by side at contentWidth/4, so a long chief complaint ' +
        'wrapped to three lines while its neighbours sat on one',
    ).toBe(4);
  });
});

describe('R1.4 — a custom template is not this item', () => {
  it('the form-only branch still renders', async () => {
    const data = fixture({ formOnly: true, formTitle: 'WM IOV' });
    const xml = await docxXml(data);
    expect(xml).toContain('WM IOV');
    // form-only suppresses the injected heading — that contract is unchanged.
    expect(xml).not.toContain('CLINICAL NOTE');
  });

  it("the doctor's OWN bytes never reach these generators", () => {
    // `pdf-native` and `template-twin` short-circuit upstream. If either ever
    // imported a generator, a restyle here would repaint a doctor's own form.
    for (const mod of ['pdf-native', 'template-twin']) {
      expect(DOCX_SRC, `docx-generator imports ${mod}`).not.toContain(mod);
    }
  });
});
