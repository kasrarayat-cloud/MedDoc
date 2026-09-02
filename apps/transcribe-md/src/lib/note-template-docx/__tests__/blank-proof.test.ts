// ============================================================================
// BLANK verification mode — a blank is PROVEN against the doctor's own canvas.
// ----------------------------------------------------------------------------
// A field the bridge honestly left blank used to emit no proof entry at all
// (`if (patches.length === 0) continue`). The certification gate requires one
// entry per expected field, so every legitimately blank field silently had
// none and certification could never close.
//
// A blank now emits an entry, and the verifier checks it the strict way: the
// rendered bytes at that binding must be BYTE-IDENTICAL to the SOURCE
// template's bytes at the same binding. Not "is it empty", not "does a null
// hash match" — is it still, byte for byte, the unfilled canvas the doctor
// uploaded ("Choose an item.", the empty cell).
//
// The filled path is untouched: filled proofs must still be exactly the
// patched set, and every pre-existing renderer/verifier test passes unchanged.
// ============================================================================

import { describe, expect, it } from 'vitest';

import { FieldResolutionSchema, type FieldResolution, type TemplateDocIR } from '../../template-twin/ir';
import type { TemplateTwinValidationResult } from '../../template-twin/ir';
import { renderTemplateDocx } from '../renderer';
import { verifyRenderedTemplateDocx, TemplateDocxRenderError } from '../roundtrip-verify';
import { buildSyntheticDocx } from './synthetic-docx';

const VALIDATION: TemplateTwinValidationResult = {
  valid: true,
  issues: [],
  checkedAt: '2026-01-01T00:00:00.000Z',
  validatorVersion: 'template-field-validator/1.0.0',
};

/** Every field unfilled — the "doctor said nothing about any of this" case. */
function allBlank(ir: TemplateDocIR): FieldResolution[] {
  return ir.fields.map((field) =>
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
}

async function setupAllBlank() {
  const source = await buildSyntheticDocx();
  const { compileTemplateDocx } = await import('../compiler');
  const ir = compileTemplateDocx(source);
  return { source, ir, resolutions: allBlank(ir), validation: VALIDATION };
}

describe('blank verification mode', () => {
  it('emits a blank proof for every unfilled field, and verifies', async () => {
    const input = await setupAllBlank();
    const rendered = await renderTemplateDocx(input);

    const proofs = rendered.verification.fields;
    const blanks = proofs.filter((p) => p.kind === 'blank');
    // The point: unfilled fields now HAVE entries. (Repeating-row rendering
    // emits its own proofs, so this is "at least one blank", not "all".)
    expect(blanks.length).toBeGreaterThan(0);
    expect(rendered.verification.verified).toBe(true);
    expect(rendered.verification.fieldCheck).toBe('verified');
  });

  it('a blank entry carries occurrences > 0, so the gate stays untouched', async () => {
    const input = await setupAllBlank();
    const rendered = await renderTemplateDocx(input);
    // certification-lifecycle requires `expected.occurrences > 0`. We satisfy
    // it rather than relaxing it: a blank still has one verified binding site.
    expect(rendered.verification.fields.every((p) => p.occurrences > 0)).toBe(true);
  });

  it('CANARY: claiming a field is blank when the render CHANGED it throws', async () => {
    // Render normally (a field gets filled), then submit a plan asserting that
    // field was blank. Verification must reject it.
    //
    // HONEST NOTE ON WHAT CATCHES THIS: the rejection comes from the structural
    // checks that run first (a patched part with no declared part-proof trips
    // static invariance). The per-binding BYTE comparison added for blank mode
    // is defence-in-depth BEHIND those, and removing it does not make this test
    // pass — verified by mutation. Constructing a case that isolates the byte
    // check alone needs a blank whose span encloses another field's patch, which
    // this fixture cannot express. Recorded rather than overclaimed.
    const source = await buildSyntheticDocx();
    const { compileTemplateDocx } = await import('../compiler');
    const ir = compileTemplateDocx(source);

    const target = ir.fields.find(
      (f) => f.kind === 'single_select' && !f.rowPrototype && f.allowedOptions.length > 0,
    )!;
    const filled = ir.fields.map((field) =>
      field.fieldId === target.fieldId
        ? FieldResolutionSchema.parse({
            fieldId: field.fieldId,
            status: 'supported',
            value: target.allowedOptions[0]!.value,
            sourceFactIds: [`ttfact_${'a'.repeat(24)}`],
            evidenceAnchorIds: ['synthetic-anchor-a'],
            selectedOptionOrdinal: 0,
            reasonCode: 'synthetic_direct_evidence',
            clinicianReviewed: false,
          })
        : FieldResolutionSchema.parse({
            fieldId: field.fieldId,
            status: 'not_mentioned',
            value: null,
            sourceFactIds: [],
            evidenceAnchorIds: [],
            selectedOptionOrdinal: null,
            reasonCode: 'synthetic_not_mentioned',
            clinicianReviewed: false,
          }),
    );
    const rendered = await renderTemplateDocx({
      source,
      ir,
      resolutions: filled,
      validation: VALIDATION,
    });

    const changed = rendered.verification.fields.find(
      (p) => p.kind === 'filled' && p.fieldId === target.fieldId,
    );
    // If the fixture filled nothing there is no canary to run — fail loudly
    // rather than pass vacuously.
    expect(changed, 'fixture rendered no filled field; canary cannot run').toBeDefined();

    expect(() =>
      verifyRenderedTemplateDocx({
        source,
        output: rendered.document,
        ir,
        plan: {
          // No patches declared, and the changed field asserted as blank.
          parts: [],
          fields: [{ ...changed!, kind: 'blank' as const }],
        },
      }),
    ).toThrow(TemplateDocxRenderError);
  });

  // ⚠️ REWRITTEN FROM A SOURCE-TEXT REGEX TO A BEHAVIOURAL ASSERTION — canon 72,
  // caught red-handed on its own terms.
  //
  // This arm used to assert `/patches\.length === 0[\s\S]{0,1800}fieldProofs\.push/`
  // against `renderer.ts` as TEXT. Ruling #170 added explanatory comments in
  // that window, the distance grew past 1800 characters, and the gate went RED
  // FOR A CHANGE THAT ALTERED NO BEHAVIOUR AT ALL. That is the exact tell canon
  // 72 names: *if somebody IMPROVED this code, would my gate fail?* — here, yes,
  // and the "fix" it invites is widening the window, which weakens the gate a
  // little more every time somebody writes a comment.
  //
  // The property it was reaching for is not a spelling, it is an OUTCOME: a
  // field the encounter did not mention must still produce a proof entry. That
  // is assertable directly, and it cannot be defeated by formatting.
  it('MUTATION: the renderer must not go back to skipping unfilled fields', async () => {
    const input = await setupAllBlank();
    const rendered = await renderTemplateDocx(input);
    const proofs = rendered.verification.fields;
    // ⚠️ THE ASSERTION IS CHOSEN TO BE EXACTLY WHAT THE REGRESSION BREAKS.
    // `if (patches.length === 0) continue;` removes the proof from every field
    // that needed no write — which, on an all-unfilled render, is precisely the
    // unfilled ones. So the count of unfilled proofs goes to ZERO under the
    // mutation and is non-zero otherwise.
    //
    // ⚠️ AND IT IS DELIBERATELY NOT "one proof per IR field". Measured: this
    // fixture has 11 fields and 10 proofs, because a content control nested in
    // a repeating row is accounted for by `renderRepeatingRows` separately.
    // That is pre-existing and correct; an arm asserting 11 would red on a
    // truth it had simply never checked.
    expect(
      proofs.filter((p) => p.kind === 'blank' || p.kind === 'emptied').length,
      'the renderer skips unfilled fields again — every honestly-blank field ' +
        'loses its proof entry and certification can never close',
    ).toBeGreaterThan(0);
  });
});
