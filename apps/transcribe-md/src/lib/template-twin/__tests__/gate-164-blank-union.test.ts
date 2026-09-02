// ============================================================================
// #164 — blankProofCount = blank ∪ emptied, KIND-AWARE AND BINDING-AWARE.
// ----------------------------------------------------------------------------
// Two rulings tried to make consult forms certifiable by building new
// verification machinery, and both were falsified — #162(c)'s extra emptiness
// check proved to be decoration behind the structural guards, and #163's
// removal of the clearing regressed worse than what it replaced. #164 changes
// no rendering and adds no check: it changes what CERTIFICATION COUNTS.
//
// ⚠️ THE COUNTING PREDICATE IS TESTED DIRECTLY, not only through a
// database-backed certification run, because a rule reachable only by mutation
// has arms that prove the mutation rather than the rule.
// ============================================================================
import { describe, expect, it } from 'vitest';

import { FieldResolutionSchema, type TemplateTwinValidationResult } from '../ir';
import { countsAsBlankProof, PROVEN_EMPTIABLE_BINDINGS } from '../blank-proof-count';
import { compileTemplateDocx } from '../../note-template-docx/compiler';
import { renderTemplateDocx } from '../../note-template-docx/renderer';
import { buildSyntheticDocx } from '../../note-template-docx/__tests__/synthetic-docx';

const VALIDATION: TemplateTwinValidationResult = {
  valid: true, issues: [], checkedAt: '2026-01-01T00:00:00.000Z',
  validatorVersion: 'template-field-validator/1.0.0',
};

async function renderAllNull() {
  const source = await buildSyntheticDocx();
  const ir = compileTemplateDocx(source);
  const resolutions = ir.fields.map((f) =>
    FieldResolutionSchema.parse({
      fieldId: f.fieldId, status: 'not_mentioned', value: null, sourceFactIds: [],
      evidenceAnchorIds: [], selectedOptionOrdinal: null,
      reasonCode: 'blank_when_unsaid', clinicianReviewed: false,
    }),
  );
  const rendered = await renderTemplateDocx({ source, ir, resolutions, validation: VALIDATION });
  const bindingOf = (id: string) =>
    ir.fields.find((f) => f.fieldId === id)?.rendererBinding.bindingType;
  const kindOf = (id: string) => ir.fields.find((f) => f.fieldId === id)?.kind;
  return { ir, rendered, bindingOf, kindOf };
}

describe('#164 — the blank proof is a counting rule', () => {
  it('a null NARRATIVE content control is proofed `emptied`, and the render still verifies', async () => {
    const { rendered, bindingOf, kindOf } = await renderAllNull();
    const emptied = rendered.verification.fields.filter((p) => p.kind === 'emptied');
    expect(emptied.length, 'fixture produced no emptied proof — the arm would be vacuous')
      .toBeGreaterThan(0);
    for (const p of emptied) {
      expect(bindingOf(p.fieldId)).toBe('content_control');
      expect(['checkbox', 'single_select', 'multi_select']).not.toContain(kindOf(p.fieldId));
    }
    // ⚠️ `emptied` IS patched, so it must survive the SAME round-trip equality a
    // fill does. If it had been filed with the blanks it would skip that.
    expect(rendered.verification.verified).toBe(true);
  });

  it('⚠️ a null CHECKBOX and a null SELECTION are NOT emptied — they render a mark', async () => {
    // A checkbox renders a glyph either way; a selection that renders anything
    // asserts a choice (#157(d) rule 2). Neither is "empty", so neither may buy
    // a blank proof. Without this arm the rule could quietly widen to any null.
    const { rendered, kindOf } = await renderAllNull();
    const excluded = rendered.verification.fields.filter((p) =>
      ['checkbox', 'single_select', 'multi_select'].includes(kindOf(p.fieldId) ?? ''),
    );
    expect(excluded.length, 'fixture has no checkbox/selection — the arm would be vacuous')
      .toBeGreaterThan(0);
    expect(excluded.every((p) => p.kind !== 'emptied')).toBe(true);
  });

  it('an UNPATCHED field is still `blank` — source-byte-identity is untouched', async () => {
    const { rendered } = await renderAllNull();
    expect(rendered.verification.fields.some((p) => p.kind === 'blank')).toBe(true);
  });

  // ══ THE COUNTING RULE ITSELF ═══════════════════════════════════════════════

  it('blank counts, regardless of binding', () => {
    expect(countsAsBlankProof({ kind: 'blank', fieldId: 'x' }, () => 'legacy_form_field')).toBe(true);
    expect(countsAsBlankProof({ kind: 'blank', fieldId: 'x' }, () => 'table_cell')).toBe(true);
  });

  it('a content-control `emptied` counts', () => {
    expect(countsAsBlankProof({ kind: 'emptied', fieldId: 'x' }, () => 'content_control')).toBe(true);
  });

  it('⚠️ A LEGACY `emptied` DOES NOT COUNT — the fail-closed arm', () => {
    // Legacy clearing has two MEASURED defects: a paragraph-spanning result is
    // not cleared, and non-`w:t` content is never cleared. Both are filed as the
    // renderer slice with reproduced fixtures. Until that lands, a legacy
    // `emptied` must not buy a blank — and this is the arm that reds if someone
    // adds `legacy_form_field` to the proven set without doing the work.
    expect(countsAsBlankProof({ kind: 'emptied', fieldId: 'x' }, () => 'legacy_form_field')).toBe(false);
    expect(PROVEN_EMPTIABLE_BINDINGS.has('legacy_form_field')).toBe(false);
    expect(PROVEN_EMPTIABLE_BINDINGS.has('table_cell')).toBe(false);
  });

  it('fails closed on an unknown or absent binding', () => {
    expect(countsAsBlankProof({ kind: 'emptied', fieldId: 'x' }, () => undefined)).toBe(false);
    expect(countsAsBlankProof({ kind: 'emptied' }, () => 'content_control')).toBe(false);
    expect(countsAsBlankProof({ kind: 'filled', fieldId: 'x' }, () => 'content_control')).toBe(false);
  });

  it('⚠️ the union is what makes the owner\'s form satisfiable — measured, not assumed', async () => {
    // MEASURED on production compiled version 87223c49: 35 fields, ALL
    // content_control, ALL emptiable kinds (30 narrative_text + 5 number, zero
    // checkbox/selection). Before #164 every null was `filled`, so
    // blankProofCount was 0 and certification could not close. This arm pins the
    // mechanism on the fixture: the union is strictly larger than `blank` alone.
    const { rendered, bindingOf } = await renderAllNull();
    const blankOnly = rendered.verification.fields.filter((p) => p.kind === 'blank').length;
    const union = rendered.verification.fields.filter((p) =>
      countsAsBlankProof(p, (id) => bindingOf(id)),
    ).length;
    expect(union).toBeGreaterThan(blankOnly);
  });
});

// ══ THE RENDERER SLICE — FILED, WITH THE REPRODUCTIONS KEPT ══════════════════
//
// ⚠️ #164 rule 1 keeps main's clearing behaviour, and records its two known
// defects rather than deleting the evidence for them. Both were REPRODUCED
// during the #163 adversarial pass, against real documents. They are `it.todo`
// so they are never a red test on main and never a lost repro — the fixtures
// that demonstrate them live in the item, and these lines are the pointer.
describe('renderer slice — legacy clearing defects (FILED, see docs/backlog/renderer-legacy-clearing.md)', () => {
  it.todo(
    'a paragraph-spanning legacy FORMTEXT result is NOT cleared — reproduced: ' +
      'SOURCE has the stale value, OUTPUT has it too, verified:true',
  );
  it.todo(
    'non-w:t content in a cleared region survives — reproduced: a w:sym tick ' +
      'and a w:pict image both print after a null render',
  );
});
