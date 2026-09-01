// ============================================================================
// RULING #162(c) — EMPTINESS IS BYTE-EQUALITY AGAINST THE WRITER'S OWN
// EXPECTATION, NEVER PARSING.
// ----------------------------------------------------------------------------
// Two earlier instruments for this invariant failed, each a layer deeper, and
// BOTH tried to read the document: "does the control contain no `w:t`" (which
// never looked at the right span for a legacy field, and enumerated the VISIBLE
// element kinds — a list that grows forever), then a locus table plus an inert
// allowlist (whose attribute regex read a field the scanner never populates, so
// every empty legacy field hard-failed the render). The second pass filed 29
// and 29 survived.
//
// So this instrument reads nothing. The renderer records the binding span AS IT
// MEANT TO LEAVE IT — the source span with that field's own patches applied,
// hashed with the renderer's own `applyApprovedXmlPatches`. Verification is one
// comparison.
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

async function setupAllBlank() {
  const source = await buildSyntheticDocx();
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
  return { source, ir, resolutions, validation: VALIDATION };
}

describe('#162(c) — emptiness is one byte comparison', () => {
  it('CORRECT EMPTIES PASS — the false-refusal direction, on the kinds this fixture covers', async () => {
    // ⚠️ THE FALSE-REFUSAL DIRECTION, AND IT IS WHY THE ALLOWLIST DIED. Its
    // predecessor refused a correctly-emptied `<w:t></w:t>` because `t` was not
    // on a hand-kept list. A correct empty must pass BY CONSTRUCTION, or the
    // gate becomes a certification denial-of-service for legitimate templates.
    const input = await setupAllBlank();
    const rendered = await renderTemplateDocx(input);
    expect(rendered.verification.verified).toBe(true);
    expect(rendered.verification.fieldCheck).toBe('verified');

    const emptied = rendered.verification.fields.filter((p) => p.kind === 'emptied');
    // NON-VACUITY — and it names the population, so a fixture that stopped
    // producing emptied proofs reds here rather than passing on an empty set.
    expect(emptied.length).toBeGreaterThan(0);

    // Every emptied proof carries the writer's expectation. A proof without one
    // is unverifiable, and the verifier refuses it — assert it is always there.
    for (const p of emptied) {
      expect([p.fieldId, typeof (p as { expectedSha256?: string }).expectedSha256]).toEqual([
        p.fieldId,
        'string',
      ]);
    }

    // ⚠️ HONEST COVERAGE, MEASURED AND NAMED RATHER THAN CLAIMED. This arm
    // first asserted "more than one binding kind" and RED at 1 — the shared
    // fixture's emptied proofs are all `content_control`. The assertion is
    // corrected to what is true, and the gap is stated: `table_cell`,
    // `repeating_row` and `legacy_form_field` are NOT exercised here.
    //
    // I briefly widened the shared fixture to cover them and it broke SEVEN
    // other tests that pin its field counts — a probe does not belong in a
    // fixture other suites depend on. Widening it properly is its own change.
    const kinds = [
      ...new Set(
        input.ir.fields
          .filter((f) => emptied.some((p) => p.fieldId === f.fieldId))
          .map((f) => f.rendererBinding.bindingType),
      ),
    ].sort();
    // Pinned by NAME so a change in coverage — up or down — reds this arm
    // instead of silently altering what the gate is about.
    expect(kinds).toEqual(['content_control']);
  });

  it('⚠️ A SPAN THAT DIVERGES FROM THE WRITER\'S EXPECTATION IS REFUSED', async () => {
    // The check's whole content: if the output's binding span is not what the
    // writer meant to leave, refuse. Stale content, a `w:sym`, another field's
    // patch bleeding in and outright tampering all look identical here — which
    // is the point of not parsing.
    const input = await setupAllBlank();
    const rendered = await renderTemplateDocx(input);
    const emptied = rendered.verification.fields.find((p) => p.kind === 'emptied');
    expect(emptied, 'fixture must produce an emptied proof').toBeDefined();

    const { verifyRenderedTemplateDocx } = await import('../roundtrip-verify');
    // Re-verify the REAL render with ONE proof's expectation corrupted. Nothing
    // else changes, so nothing else can object: this isolates the comparison.
    expect(() =>
      verifyRenderedTemplateDocx({
        source: input.source,
        output: rendered.document,
        ir: input.ir,
        plan: {
          parts: [],
          fields: rendered.verification.fields.map((p) =>
            p.fieldId === emptied!.fieldId
              ? { ...p, expectedSha256: 'f'.repeat(64) }
              : p,
          ),
        },
      } as never),
    ).toThrow();
  });
});
