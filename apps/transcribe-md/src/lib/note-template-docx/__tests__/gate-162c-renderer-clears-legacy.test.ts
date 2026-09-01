// ============================================================================
// #162(c) — THE RENDERER CLEARS A LEGACY FORM FIELD'S RESULT.
// ----------------------------------------------------------------------------
// ⚠️ THE DIVISION OF LABOUR, IN ONE LINE: the VERIFIER proves
// intent-conformance (the output is byte-identical to what the writer meant to
// leave); THESE TESTS prove intent-CORRECTNESS (what the writer meant to leave
// is actually empty). Together they cover the harm. Byte-equality alone cannot
// catch a writer's own failure to clear, because the expectation would carry
// the same mistake — so that half is proved here, at the writer.
//
// These began as throwaway probes for a harm an adversarial pass constructed:
// a FORMTEXT whose result still carried `WARFARIN 5 MG DAILY` after being
// rendered with a null resolution. In THIS renderer both shapes clear
// correctly, so there was no refusal to assert and no arm was written claiming
// one. Pinning the passing behaviour is the honest residue: cheap, and it reds
// the day a change stops clearing.
//
// ⚠️ IT USES ITS OWN DOCUMENT, NOT THE SHARED FIXTURE. Widening
// `synthetic-docx`'s default broke SEVEN tests that pin its field counts. A
// probe does not belong in a fixture other suites depend on.
// ============================================================================
import { describe, expect, it } from 'vitest';

import { FieldResolutionSchema, type TemplateTwinValidationResult } from '../../template-twin/ir';
import { renderTemplateDocx } from '../renderer';
import { buildSyntheticDocx } from './synthetic-docx';

const VALIDATION: TemplateTwinValidationResult = {
  valid: true,
  issues: [],
  checkedAt: '2026-01-01T00:00:00.000Z',
  validatorVersion: 'template-field-validator/1.0.0',
};

const STALE = 'WARFARIN 5 MG DAILY';
/** Sits AFTER a nested field's `end` and BEFORE the outer field's `end`. */
const TAIL = 'CLOPIDOGREL 75 MG DAILY';

/**
 * The outer FORMTEXT's result contains a COMPLETE nested field (` PAGE `), and
 * a stale run after it. The nested field's `end` is the first `end` the walk
 * meets; only the depth count keeps it from closing the outer field there — and
 * if it did close there, `TAIL` would never be cleared.
 */
function nestedLegacyDoc(): string {
  const begin =
    `<w:r><w:fldChar w:fldCharType="begin"><w:ffData>` +
    `<w:name w:val="Legacy anticoagulant"/><w:enabled/>` +
    `<w:textInput><w:default w:val="${STALE}"/></w:textInput>` +
    `</w:ffData></w:fldChar></w:r><w:r><w:instrText> FORMTEXT </w:instrText></w:r>`;
  const nested =
    `<w:r><w:fldChar w:fldCharType="begin"/></w:r>` +
    `<w:r><w:instrText> PAGE </w:instrText></w:r>` +
    `<w:r><w:fldChar w:fldCharType="separate"/></w:r>` +
    `<w:r><w:t>1</w:t></w:r>` +
    `<w:r><w:fldChar w:fldCharType="end"/></w:r>`;
  const result =
    `<w:r><w:fldChar w:fldCharType="separate"/></w:r>` +
    `<w:r><w:t>${STALE}</w:t></w:r>` +
    nested +
    `<w:r><w:t>${TAIL}</w:t></w:r>` +
    `<w:r><w:fldChar w:fldCharType="end"/></w:r>`;
  return (
    `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>` +
    `<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">` +
    `<w:body><w:p>${begin}${result}</w:p></w:body></w:document>`
  );
}

/** A legacy FORMTEXT carrying a stale result, in one paragraph or across two. */
function legacyDoc(spanParagraphs: boolean): string {
  const begin =
    `<w:r><w:fldChar w:fldCharType="begin"><w:ffData>` +
    `<w:name w:val="Legacy anticoagulant"/><w:enabled/>` +
    `<w:textInput><w:default w:val="${STALE}"/></w:textInput>` +
    `</w:ffData></w:fldChar></w:r><w:r><w:instrText> FORMTEXT </w:instrText></w:r>`;
  const result =
    `<w:r><w:fldChar w:fldCharType="separate"/></w:r>` +
    `<w:r><w:t>${STALE}</w:t></w:r>` +
    `<w:r><w:fldChar w:fldCharType="end"/></w:r>`;
  const body = spanParagraphs
    ? `<w:p>${begin}</w:p><w:p>${result}</w:p>`
    : `<w:p>${begin}${result}</w:p>`;
  return (
    `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>` +
    `<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">` +
    `<w:body>${body}</w:body></w:document>`
  );
}

async function renderAllBlank(documentXml: string) {
  const source = await buildSyntheticDocx({ documentXml });
  const { compileTemplateDocx } = await import('../compiler');
  const ir = compileTemplateDocx(source);
  const resolutions = ir.fields.map((field) =>
    FieldResolutionSchema.parse({
      fieldId: field.fieldId,
      status: 'not_mentioned',
      value: null,
      sourceFactIds: [],
      evidenceAnchorIds: [],
      selectedOptionOrdinal: null,
      reasonCode: 'blank_when_unsaid',
      clinicianReviewed: false,
    }),
  );
  const rendered = await renderTemplateDocx({ source, ir, resolutions, validation: VALIDATION });
  // ⚠️ UNZIP. A .docx is a ZIP, so reading the buffer as text measures
  // COMPRESSION, not content — my first probe did exactly that and reported a
  // stale value absent when it had never looked at the XML at all. The
  // positive control below is what caught it.
  const { inspectDocxPackage } = await import('../package-security');
  const pkg = inspectDocxPackage(rendered.document);
  const entry = pkg.zip.entries.get('word/document.xml');
  if (!entry) throw new Error('word/document.xml missing from the rendered package');
  const text = Buffer.from(entry.bytes).toString('utf8');
  return { ir, rendered, text };
}

describe('#162(c) — the renderer clears a legacy result (intent-correctness)', () => {
  for (const spanParagraphs of [false, true]) {
    const shape = spanParagraphs ? 'SPANNING TWO PARAGRAPHS' : 'in one paragraph';

    it(`clears a stale FORMTEXT result ${shape}`, async () => {
      const { ir, rendered, text } = await renderAllBlank(legacyDoc(spanParagraphs));

      // NON-VACUITY FIRST — if the document compiled no legacy field this arm
      // would pass while measuring nothing, which is the shape this programme
      // keeps paying for.
      const legacy = ir.fields.filter(
        (f) => f.rendererBinding.bindingType === 'legacy_form_field',
      );
      expect(legacy.length).toBeGreaterThan(0);

      // POSITIVE CONTROL — the stale value really is in the SOURCE, so its
      // absence below is the renderer's doing and not the fixture's.
      const src = await buildSyntheticDocx({ documentXml: legacyDoc(spanParagraphs) });
      const { inspectDocxPackage } = await import('../package-security');
      const srcXml = Buffer.from(
        inspectDocxPackage(src).zip.entries.get('word/document.xml')!.bytes,
      ).toString('utf8');
      expect(srcXml.includes(STALE)).toBe(true);

      // ⚠️ THE PROPERTY: a field the encounter did not mention must not carry
      // the template's stale default into a document somebody signs.
      expect([shape, text.includes(STALE)]).toEqual([shape, false]);
      expect(rendered.verification.verified).toBe(true);
    });
  }

  // ⚠️ THE SCOPE-ERROR ARM. Widening the walk from one paragraph to the part
  // root makes every `w:fldChar` in the document visible to it, so the DEPTH
  // COUNT is now the only thing standing between the outer field and a nested
  // field's `end`. Take the first `end` instead of the matching one and the
  // window closes early: `TAIL` — which really is inside the outer result — is
  // never cleared and the stale drug reaches the rendered page.
  //
  // ⚠️ AND IT IS ASSERTED AS AN ORDERED PAIR AGAINST THE NESTED VALUE, so the
  // arm cannot pass by clearing everything blindly: `1` inside the nested field
  // is inside the outer result too, and must go with it.
  it('a nested field does not close the outer one — the tail is still cleared', async () => {
    const documentXml = nestedLegacyDoc();
    const { ir, rendered, text } = await renderAllBlank(documentXml);

    const legacy = ir.fields.filter(
      (f) => f.rendererBinding.bindingType === 'legacy_form_field',
    );
    expect(legacy.length).toBeGreaterThan(0);

    // POSITIVE CONTROL — both values are in the SOURCE.
    const { inspectDocxPackage } = await import('../package-security');
    const srcXml = Buffer.from(
      inspectDocxPackage(await buildSyntheticDocx({ documentXml })).zip.entries.get(
        'word/document.xml',
      )!.bytes,
    ).toString('utf8');
    expect([srcXml.includes(STALE), srcXml.includes(TAIL)]).toEqual([true, true]);

    expect([text.includes(STALE), text.includes(TAIL)]).toEqual([false, false]);
    expect(rendered.verification.verified).toBe(true);
  });
});
