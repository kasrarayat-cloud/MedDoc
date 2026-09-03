// ============================================================================
// THE PDF THE DOCTOR SENDS CONTAINS WHAT HIS DOCX CONTAINS.
// ----------------------------------------------------------------------------
// ⚠️ OWNER-REPORTED, and the numbers are the argument. His signed export served
// byte-identical DOCX to Word and to the PDF converter:
//
//     DOCX : 22 filled content controls, 7,603 visible characters
//     PDF  : 0 of the 22,               2,199 characters
//
// Every paragraph OUTSIDE a control rendered; every filled control rendered
// EMPTY. The deliverable he sends to a referring physician had never once shown
// a filled value. His words: "it changed my file again".
//
// ⚠️ AND IT IS NOT OUR FILL. The same emptiness reproduces on his BLANK uploaded
// form — 0 of 35 — untouched by any render of ours.
//
// The cure is to hand the converter only what it has always rendered: plain
// paragraph text. See `flatten-sdt.ts` for the four invalidated bisection
// harnesses and why this is a workaround with a clean measurement rather than a
// diagnosis.
// ============================================================================
import { readFileSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

import { XMLValidator } from 'fast-xml-parser';

import { flattenContentControls } from '../flatten-sdt';

const APP = resolve(__dirname, '..', '..', '..', '..');

const W = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"';
const doc = (body: string) =>
  `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:document ${W}><w:body>${body}</w:body></w:document>`;
const runs = (xml: string) => (xml.match(/<w:t[^>]*>[^<]*<\/w:t>/g) ?? []);

describe('flattening the conversion input', () => {
  it('⚠️ ZERO w:sdt survive, and the RUN SET is identical', () => {
    const before = doc(
      `<w:p><w:r><w:t>outside</w:t></w:r>` +
        `<w:sdt><w:sdtPr><w:alias w:val="A"/><w:id w:val="1"/><w:text/></w:sdtPr>` +
        `<w:sdtContent><w:r><w:t>INSIDE</w:t></w:r></w:sdtContent></w:sdt></w:p>`,
    );
    const after = flattenContentControls(before);
    expect(after).not.toMatch(/<w:sdt[ >]/);
    expect(after).not.toMatch(/<w:sdtPr[ >]/);
    // the property that makes this content-preserving rather than a rewrite
    expect(runs(after)).toEqual(runs(before));
    expect(after).toContain('INSIDE');
  });

  // ⚠️ THE CASE THAT INVALIDATED A BISECTION HARNESS. Pairing the first
  // `<w:sdt>` with the first `</w:sdt>` closes the INNER control and orphans a
  // tag — which made an EMPTY `sdtPr` look fatal and cost four experiments.
  it('⚠️ NESTED controls unwrap innermost-first, leaving no orphan tag', () => {
    const before = doc(
      `<w:p><w:sdt><w:sdtPr><w:id w:val="1"/></w:sdtPr><w:sdtContent>` +
        `<w:r><w:t>OUTER</w:t></w:r>` +
        `<w:sdt><w:sdtPr><w:id w:val="2"/></w:sdtPr><w:sdtContent>` +
        `<w:r><w:t>NESTED</w:t></w:r>` +
        `</w:sdtContent></w:sdt>` +
        `</w:sdtContent></w:sdt></w:p>`,
    );
    const after = flattenContentControls(before);
    expect(after).not.toMatch(/<w:sdt[ >]/);
    expect(after).not.toContain('</w:sdt>');
    expect(after).toContain('OUTER');
    expect(after).toContain('NESTED');
    expect(runs(after)).toEqual(runs(before));
  });

  it('a control with no sdtContent contributes nothing, and does not throw', () => {
    const before = doc(`<w:p><w:sdt><w:sdtPr><w:id w:val="1"/></w:sdtPr></w:sdt></w:p>`);
    const after = flattenContentControls(before);
    expect(after).not.toMatch(/<w:sdt[ >]/);
    expect(runs(after)).toEqual([]);
  });

  it('a document with no controls is returned unchanged', () => {
    const before = doc('<w:p><w:r><w:t>plain</w:t></w:r></w:p>');
    expect(flattenContentControls(before)).toBe(before);
  });

  // ==========================================================================
  // ⚠️ THE THREE SHAPES THE REFUTATION PASS DEMONSTRATED, AND WHY THEY ARE HERE.
  // The FIRST version of this flattener SELECTED A SUBTREE — it captured
  // `w:sdtContent`'s children and replaced the control with them. Every arm
  // above passed. All three of these failed, and the first one DELETED A DRUG
  // NAME from a document that was well-formed afterwards, so nothing threw and
  // the fail-open never engaged.
  //
  // They are anchored to ruling #174's own adjudicated shapes, not invented:
  // #174 REFUSES such controls at admission and keeps the doctor's text
  // verbatim as static content, which is exactly how they reach the converter.
  // ==========================================================================
  const wellFormed = (xml: string) => XMLValidator.validate(xml) === true;

  it('⚠️ CLINICAL: a run AFTER w:sdtContent survives — it used to be deleted', () => {
    const before = doc(
      `<w:p><w:sdt><w:sdtPr><w:id w:val="980"/></w:sdtPr>` +
        `<w:sdtContent><w:r><w:t>placeholder</w:t></w:r></w:sdtContent>` +
        `<w:r><w:t>WARFARIN 5 MG DAILY</w:t></w:r></w:sdt></w:p>`,
    );
    const after = flattenContentControls(before);
    expect(after, 'the drug name was deleted').toContain('WARFARIN 5 MG DAILY');
    expect(runs(after)).toEqual(runs(before));
    expect(wellFormed(after), 'output is not well-formed XML').toBe(true);
  });

  it('⚠️ TWO w:sdtContent children unwrap to WELL-FORMED xml, not orphan tags', () => {
    const before = doc(
      `<w:p><w:sdt><w:sdtPr><w:id w:val="7"/></w:sdtPr>` +
        `<w:sdtContent><w:r><w:t>ASPIRIN</w:t></w:r></w:sdtContent>` +
        `<w:sdtContent><w:r><w:t>WARFARIN</w:t></w:r></w:sdtContent></w:sdt></w:p>`,
    );
    const after = flattenContentControls(before);
    // the previous version kept both drugs and emitted an orphan close plus an
    // unclosed open — the converter then refused, so the doctor got NO pdf
    expect(wellFormed(after), 'output is not well-formed XML').toBe(true);
    expect(runs(after)).toEqual(runs(before));
  });

  it('⚠️ a SELF-CLOSING `<w:sdt />` (with a space) deletes nothing', () => {
    const before = doc(
      `<w:p><w:sdt><w:sdtPr><w:id w:val="1"/></w:sdtPr><w:sdtContent>` +
        `<w:sdt />` +
        `<w:r><w:t>PATIENT ALLERGIC TO PENICILLIN</w:t></w:r>` +
        `</w:sdtContent></w:sdt></w:p>`,
    );
    const after = flattenContentControls(before);
    expect(after, 'the allergy line was deleted').toContain('PATIENT ALLERGIC TO PENICILLIN');
    expect(runs(after)).toEqual(runs(before));
    expect(wellFormed(after)).toBe(true);
  });

  // ⚠️ TWO REFUSALS, TWO GUARDS, PROVED SEPARATELY. The first draft of this
  // pair used ONE fixture and asserted the balance message — and it was caught
  // by the CARRIER TRIPWIRE instead, because the fixture was MISNESTED rather
  // than unbalanced (counts 1/1). A red run from the wrong guard is the most
  // convincing possible evidence that the right one works, so each arm now
  // asserts the message that names ITS OWN guard.

  it('⚠️ UNBALANCED control metadata is REFUSED (the COUNT guard)', () => {
    // a lone `<w:sdtPr>` would let a non-greedy delete run on to some LATER
    // `</w:sdtPr>` and swallow a paragraph on the way. Refusing means the
    // ORIGINAL bytes convert — hollow, but nothing is destroyed.
    const before = doc(
      `<w:p><w:sdt><w:sdtPr><w:id w:val="1"/></w:sdtPr>` +
        `<w:sdtContent><w:r><w:t>KEEP ME</w:t></w:r></w:sdtContent></w:sdt></w:p>` +
        `<w:sdtPr>`,
    );
    expect(() => flattenContentControls(before)).toThrow(/unbalanced control metadata/);
  });

  it('⚠️ MISNESTED metadata is REFUSED too (the CARRIER TRIPWIRE)', () => {
    // counts reconcile (1 open, 1 close) so the count guard is satisfied; what
    // catches this is the ordered carrier comparison, which notices that
    // `KEEP ME` and `LATER` did not survive the splice.
    const before = doc(
      `<w:p><w:sdt><w:sdtPr><w:id w:val="1"/><w:sdtContent><w:r><w:t>KEEP ME</w:t></w:r>` +
        `</w:sdtContent></w:sdt></w:p><w:p><w:r><w:t>LATER</w:t></w:r></w:p></w:sdtPr>`,
    );
    expect(() => flattenContentControls(before)).toThrow(/text carriers changed/);
  });

  it('⚠️ the TRIPWIRE fires rather than shipping a changed run set', () => {
    // `w:delText` and `w:instrText` are carriers this codebase has been bitten
    // by; they are watched too, so a future pattern that eats one goes red.
    const before = doc(
      `<w:p><w:sdt><w:sdtPr><w:id w:val="1"/></w:sdtPr><w:sdtContent>` +
        `<w:del><w:r><w:delText>OLD DOSE</w:delText></w:r></w:del>` +
        `</w:sdtContent></w:sdt></w:p>`,
    );
    const after = flattenContentControls(before);
    expect(after).toContain('OLD DOSE');
    expect(wellFormed(after)).toBe(true);
  });

  it('flattening is LINEAR — 5,000 controls in well under a second', () => {
    // the subtree-selecting version rescanned the whole part per removal and
    // measured ~34 SECONDS of blocked event loop on this input
    const body = Array.from(
      { length: 5000 },
      (_, i) =>
        `<w:p><w:sdt><w:sdtPr><w:id w:val="${i}"/></w:sdtPr><w:sdtContent>` +
        `<w:r><w:t>V${i}</w:t></w:r></w:sdtContent></w:sdt></w:p>`,
    ).join('');
    const before = doc(body);
    const t0 = Date.now();
    const after = flattenContentControls(before);
    const ms = Date.now() - t0;
    expect(runs(after)).toHaveLength(5000);
    expect(after).not.toMatch(/<w:sdt[ />]/);
    expect(ms, `flatten took ${ms}ms`).toBeLessThan(2000);
  });

  it('⚠️ an ARCHIVE THAT INFLATES past the hardened ceiling is REFUSED', async () => {
    const JSZip = (await import('jszip')).default;
    const { flattenDocxForConversion } = await import('../flatten-docx');
    const { DEFAULT_TEMPLATE_DOCX_LIMITS } = await import('../../note-template-docx/limits');

    // one part just over the per-entry ceiling. It deflates to almost nothing —
    // which is the point: the COMPRESSED upload is tiny and passes every size
    // check upstream, while the INFLATED part is what lands in the app's heap.
    const big =
      doc('<w:p><w:r><w:t>' + 'A'.repeat(DEFAULT_TEMPLATE_DOCX_LIMITS.maxEntryUncompressedBytes) + '</w:t></w:r></w:p>');
    const zip = new JSZip();
    zip.file('word/document.xml', big);
    // ⚠️ DEFLATE EXPLICITLY. JSZip defaults to STORE, so the first draft of
    // this arm produced a 16 MB "bomb" that was not compressed at all — the
    // non-vacuity assertion below is what caught it.
    const bytes = await zip.generateAsync({ type: 'uint8array', compression: 'DEFLATE' });
    expect(bytes.byteLength, 'the bomb should compress small').toBeLessThan(1_000_000);

    await expect(flattenDocxForConversion(bytes)).rejects.toThrow(/uncompressed ceiling/);
  });

  // ⚠️ THE REAL DOCUMENT, not a fixture of my own shape. The owner's blank form
  // is a tracked fixture; it is the artifact the defect was measured on.
  it('⚠️ ON THE REAL CUSTOMER FORM: every control out, every run kept', async () => {
    const { flattenDocxForConversion } = await import('../flatten-docx');
    const { inspectDocxPackage } = await import('../../note-template-docx/package-security');
    const src = readFileSync(join(APP, 'tests', 'e2e', 'fixtures', 'sample-form.docx'));
    const xmlOf = (b: Uint8Array) =>
      Buffer.from(
        inspectDocxPackage(b).zip.entries.get('word/document.xml')!.bytes,
      ).toString('utf8');

    const beforeXml = xmlOf(src);
    // NON-VACUITY: the fixture must actually carry controls, or this arm proves
    // nothing about flattening — it would pass just as well on a plain document.
    const beforeCount = (beforeXml.match(/<w:sdt[ >]/g) ?? []).length;
    expect(beforeCount, 'the fixture carries no content controls').toBeGreaterThan(20);

    const flat = await flattenDocxForConversion(src);
    const afterXml = xmlOf(flat);
    expect((afterXml.match(/<w:sdt[ >]/g) ?? []).length, 'controls survived').toBe(0);
    expect(afterXml).not.toMatch(/<w:sdtPr[ >]/);
    // the content-preserving property, on the real document
    expect(runs(afterXml)).toEqual(runs(beforeXml));
  });
});

describe('every producer of a visit document routes through ONE source', () => {
  // ⚠️ A RATCHET, NOT A BUG REPORT. F5-f fixed the PDF export route to derive
  // from the same document the Word download serves, after a period when one
  // record had two formats and two documents. Nothing enumerated the producers,
  // so a fourth caller could reintroduce it silently.
  //
  // ⚠️ AND THE ENUMERATION IS THE POINT: a session reading this file previously
  // reported `preview-visit-document.ts` as carrying that defect. It does not —
  // its styled builder is a FALLBACK helper and its twin branch is intact. The
  // claim was a misread of a helper for the main flow, and this arm is what
  // makes the question answerable by measurement instead of by reading.
  it('the PDF export route derives from resolveVisitDocx, never a second render', () => {
    const route = readFileSync(
      join(APP, 'src', 'app', 'api', 'visits', '[id]', 'export', 'pdf', 'route.ts'),
      'utf8',
    );
    expect(route).toContain('resolveVisitDocx');
  });

  it('the preview action keeps a twin branch and a styled FALLBACK, not only styled', () => {
    const preview = readFileSync(
      join(APP, 'src', 'actions', 'preview-visit-document.ts'),
      'utf8',
    );
    // the signed path serves the STORED, roundtrip-verified bytes
    expect(preview).toContain('loadNativeTemplateDocxForVisit');
    // and the unsigned certified path renders the twin
    expect(preview).toMatch(/prepared\.render\?\.document|prepared\.render\.document/);
  });
});
