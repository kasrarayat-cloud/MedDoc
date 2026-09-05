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
