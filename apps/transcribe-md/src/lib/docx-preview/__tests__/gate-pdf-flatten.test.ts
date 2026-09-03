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
    // the count the caller uses to tell `applied` from `not_needed`
    expect(flat.controlsRemoved).toBe(beforeCount);
    const afterXml = xmlOf(flat.docx);
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
