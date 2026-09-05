// ============================================================================
// #191 — A KEPT DEFAULT SURVIVES THE RENDER. THE ONE ARM THAT WATCHES THE
// DELIVERY.
// ----------------------------------------------------------------------------
// ⚠️ THIS FILE EXISTS BECAUSE A MUTATION PROVED NOTHING WATCHED IT. Reverting
// `renderer.ts`'s clear condition to `resolution.value === null` alone -- which
// is the ENTIRE delivery of `keep`, and the exact defect the adversarial pass
// found -- redded ZERO arms across the whole suite. A one-line change carrying
// a ruling's whole product, unwatched, is how the status shipped inert the
// first time.
//
// The discriminator is a REAL RENDER of a REAL scaffolded control, both ways:
// `default_kept` must leave the doctor's sentence standing; `not_mentioned`
// must clear it. An arm that asserted only the first would pass just as well if
// the renderer had stopped clearing ANYTHING.
// ============================================================================

import { describe, expect, it } from 'vitest';

import { FieldResolutionSchema, type FieldResolution, type TemplateDocIR } from '../../template-twin/ir';
import type { TemplateTwinValidationResult } from '../../template-twin/ir';
import { renderTemplateDocx } from '../renderer';
import { buildSyntheticDocx } from './synthetic-docx';

const VALIDATION: TemplateTwinValidationResult = {
  valid: true,
  issues: [],
  checkedAt: '2026-01-01T00:00:00.000Z',
  validatorVersion: 'template-field-validator/1.0.0',
};

const SENTENCE = 'The patient denies chest pain, palpitations and syncope.';

/** One SCAFFOLDED control: real prose, and NO `w:showingPlcHdr`. */
const DOC = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>
<w:p><w:sdt>
  <w:sdtPr><w:alias w:val="Cardiovascular ROS"/><w:id w:val="401"/><w:text/></w:sdtPr>
  <w:sdtContent><w:r><w:t>${SENTENCE}</w:t></w:r></w:sdtContent>
</w:sdt></w:p>
</w:body></w:document>`;

function resolutionsWith(ir: TemplateDocIR, status: string, reason: string): FieldResolution[] {
  return ir.fields.map((field) =>
    FieldResolutionSchema.parse({
      fieldId: field.fieldId,
      status,
      value: null,
      // a kept default must cite the facts it evaluated; a not-mentioned must not
      sourceFactIds: status === 'default_kept' ? [`ttfact_${'a'.repeat(24)}`] : [],
      evidenceAnchorIds: status === 'default_kept' ? ['anchor-a'] : [],
      selectedOptionOrdinal: null,
      reasonCode: reason,
      clinicianReviewed: false,
    }),
  );
}

async function renderAs(status: string, reason: string) {
  const source = await buildSyntheticDocx({ documentXml: DOC });
  const { compileTemplateDocx } = await import('../compiler');
  const ir = compileTemplateDocx(source);
  const rendered = await renderTemplateDocx({
    source,
    ir,
    resolutions: resolutionsWith(ir, status, reason),
    validation: VALIDATION,
  });
  const JSZip = (await import('jszip')).default;
  const xml = await (await JSZip.loadAsync(rendered.document)).file('word/document.xml')!.async('string');
  return { ir, xml, rendered };
}

describe('#191 — a kept default survives the render', () => {
  it('the fixture IS a scaffold, per the compiler — otherwise everything below is vacuous', async () => {
    const source = await buildSyntheticDocx({ documentXml: DOC });
    const { compileTemplateDocx } = await import('../compiler');
    const ir = compileTemplateDocx(source);
    // ⚠️ FOUND BY ALIAS, NOT BY INDEX. The synthetic package's header carries
    // a control of its own, so `fields[0]` is not the one under test and an
    // index would have silently measured the wrong control.
    const target = ir.fields.find((f) => f.originalLabel === 'Cardiovascular ROS');
    expect(target, 'the scaffolded control must be compiled').toBeDefined();
    expect(target!.scaffolded).toBe(true);
    // and the header's control is NOT a scaffold — the discriminator works
    // the synthetic header's control is a scaffold too — both are, which is
    // correct: neither declares a placeholder and both carry text.
    expect(ir.fields.filter((f) => f.scaffolded === true).length).toBeGreaterThanOrEqual(1);
  });

  it("⚠️ A DECLARED `keep` LEAVES THE DOCTOR'S SENTENCE STANDING", async () => {
    // #192's delivery. The status reaches this field only because the mapping
    // DECLARED `unmentionedPolicy: 'keep'` -- never because anything inspected
    // the control's content.
    const { xml } = await renderAs('default_kept', 'default_kept_uncontradicted');
    expect(xml).toContain(SENTENCE);
  });

  it('⚠️ AND THE COUNTEREXAMPLE IS PINNED — a prompt with no placeholder flag', async () => {
    // The specific document shape that refuted the discriminator. If a future
    // predicate can tell this from clinical prose, this arm is where it gets
    // proved -- not on a real customer template nobody can regression-test.
    const PROMPT = 'Enter assessment';
    const doc = DOC.replace(SENTENCE, PROMPT);
    const source = await buildSyntheticDocx({ documentXml: doc });
    const { compileTemplateDocx } = await import('../compiler');
    const ir = compileTemplateDocx(source);
    const target = ir.fields.find((f) => f.originalLabel === 'Cardiovascular ROS')!;
    // it declares NO placeholder, so the document-declared signal cannot see it
    expect(doc).not.toContain('showingPlcHdr');
    // and the compiler therefore calls it a scaffold — which is the finding
    expect(target.scaffolded).toBe(true);
  });

  it('⚠️ AND `not_mentioned` STILL CLEARS IT — the other half of the discriminator', async () => {
    // Without this, an arm asserting only survival would pass just as happily
    // if the renderer had stopped clearing anything at all.
    const { xml } = await renderAs('not_mentioned', 'fact_not_mentioned');
    expect(xml).not.toContain(SENTENCE);
  });
});

describe('#192 — A STORED IR MUST NOT ORPHAN', () => {
  it('⚠️ AN IR COMPILED BEFORE `scaffolded`/`scaffoldText` EXISTED STILL RENDERS', async () => {
    // ⚠️ THE ARM THAT WAS MISSING, AND ITS ABSENCE COST THE 10-OF-10 HARM ONCE
    // ALREADY. `assertSourceMatchesIr` recompiles the immutable source on EVERY
    // fill and compares it against the STORED IR. Stripping the derived fields
    // from `structureSha256` was correct and INSUFFICIENT: that function also
    // performs an INDEPENDENT raw comparison over the field arrays, which the
    // strip never reached. Measured before the fix -- structure hash EQUAL,
    // fields hash NOT equal, `SOURCE_IR_MISMATCH` -- and `native-export.ts`
    // catches that and returns the generic STYLED export, so a doctor silently
    // loses their own form with a `console.warn` as the only trace.
    //
    // ⚠️ AND THE GUARD THAT EXISTED WATCHED THE WRONG SET: it asserted the strip
    // was present in `structureSha256`, which was true and blind to the other
    // comparison. This arm watches the OUTCOME -- does a stored IR still render
    // -- which no rewording of a source assertion can fake.
    const source = await buildSyntheticDocx();
    const { compileTemplateDocx } = await import('../compiler');
    const head = compileTemplateDocx(source);

    // exactly what sits in `template_twin_compiled_versions.compiledDocumentIr`
    // today: identical, minus the two keys that did not exist when it was written
    const stored = JSON.parse(JSON.stringify(head)) as typeof head;
    (stored as { fields: unknown[] }).fields = head.fields.map((f) => {
      const { scaffolded: _a, scaffoldText: _b, ...rest } = f;
      return rest;
    });

    // non-vacuity: the stored shape really is missing them
    expect(head.fields.some((f) => f.scaffolded !== undefined)).toBe(true);
    expect(
      (stored.fields as ReadonlyArray<{ scaffolded?: boolean }>).every(
        (f) => f.scaffolded === undefined,
      ),
    ).toBe(true);

    await expect(
      renderTemplateDocx({
        source,
        ir: stored,
        resolutions: stored.fields.map((f) =>
          FieldResolutionSchema.parse({
            fieldId: f.fieldId, status: 'not_mentioned', value: null,
            sourceFactIds: [], evidenceAnchorIds: [], selectedOptionOrdinal: null,
            reasonCode: 'fact_not_mentioned', clinicianReviewed: false,
          }),
        ),
        validation: VALIDATION,
      }),
    ).resolves.toBeDefined();
  });
});

describe('#192 — A DECLARED KEEP IS HONOURED FOR EVERY KIND', () => {
  // ⚠️ THIS ARM EXISTS BECAUSE ITS ABSENCE WAS THE DEFECT. The keep guard was
  // first placed AFTER the `checkbox`, `date` and `single_select` branches, all
  // of which write unconditionally — so a DECLARED keep was silently ignored for
  // those three kinds while the resolution still said `default_kept`. Measured
  // by the adversarial pass: a date control lost `Date of procedure: 12 March
  // 2026`; a select was overwritten. Every arm at the time built a
  // `narrative_text`, so 5740 tests could not see it.
  const KINDS = [
    ['date', '<w:date w:fullDate="2026-03-12T00:00:00Z"/>', 'Date of procedure: 12 March 2026'],
    ['select', '<w:dropDownList><w:listItem w:displayText="Normal" w:value="N"/></w:dropDownList>', 'Normal'],
    ['text', '<w:text/>', 'The patient denies chest pain.'],
  ] as const;

  it.each(KINDS)('a declared keep survives on a %s control', async (_kind, pr, text) => {
    const doc = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>
<w:p><w:sdt><w:sdtPr><w:alias w:val="Kept"/><w:id w:val="777"/>${pr}</w:sdtPr>
<w:sdtContent><w:r><w:t>${text}</w:t></w:r></w:sdtContent></w:sdt></w:p></w:body></w:document>`;
    const source = await buildSyntheticDocx({ documentXml: doc });
    const { compileTemplateDocx } = await import('../compiler');
    const ir = compileTemplateDocx(source);
    const rendered = await renderTemplateDocx({
      source, ir,
      resolutions: ir.fields.map((f) =>
        FieldResolutionSchema.parse({
          fieldId: f.fieldId, status: 'default_kept', value: null,
          sourceFactIds: [`ttfact_${'a'.repeat(24)}`], evidenceAnchorIds: ['anchor-a'],
          selectedOptionOrdinal: null, reasonCode: 'default_kept_uncontradicted',
          clinicianReviewed: false,
        }),
      ),
      validation: VALIDATION,
    });
    const JSZip = (await import('jszip')).default;
    const xml = await (await JSZip.loadAsync(rendered.document))
      .file('word/document.xml')!.async('string');
    expect(xml).toContain(text);
  });
});
