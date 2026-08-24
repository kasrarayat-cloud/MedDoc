// ============================================================================
// F24-S5 ITEM A — THE COMPILED IR IS STABLE, AND THAT IS A CLINICAL INVARIANT
// ----------------------------------------------------------------------------
// `renderer.ts:assertSourceMatchesIr` RE-COMPILES the immutable source document
// on EVERY fill and refuses unless the result matches the STORED IR — by
// `structureSha256` and by `canonicalSha256(fields)`. That check is what makes a
// certified twin trustworthy: nobody can swap the source under a certification.
//
// Its cost is the invariant this file guards:
//
//   > **ANY change to what the compiler PERSISTS orphans every template already
//   > compiled. Not a subset — all of them. And `compilerVersion` is not a
//   > sufficient signal, because it does not have to move.**
//
// ============================================================================
// ⚠️ THIS IS NOT HYPOTHETICAL. IT SHIPPED TO `main` AND ITEM A CAUGHT IT.
// ----------------------------------------------------------------------------
// `f340c589` (the F24-S5 rebuild) assigned `withoutPlaceholderOptions(...)`
// directly into `allowedOptions`, so Word's "Choose an item." furniture never
// reached the IR. Measured on the QA stack by driving the real fill:
//
//   · 10 of 10 CERTIFIED twins began failing SOURCE_IR_MISMATCH
//   · options 153 -> 125 — exactly 28, one per single-select content control
//   · BOTH legs fired from ONE cause: structureSha256 is
//     canonicalSha256({fields, tables, nodes, unsupported})
//   · compilerVersion stayed `template-docx-compiler/1.0.0` and said nothing
//
// Production's only certified twin carries the identical 80 fields / 153 options
// / 28 placeholders, so it would have stopped filling the moment that deployed.
// Every recompute path degrades SILENTLY to the styled export, and a signature
// freezes a NULL pointer — permanently, for that record.
//
// ⚠️ AND THE FEATURE IT SHIPPED WITH WAS ITS OWN TRIGGER: a clinician's
// form-control correction moves `overridesSha256`, which is exactly what forces
// the recompute that then refuses. The door would still have answered `ok`.
//
// THE FIX, and what these arms pin: the placeholder is excluded WHERE IT IS
// READ — the door, the overlay, and the list offered to the model — never where
// it is STORED.
//
// ⚠️ WHY NO UNIT TEST COULD HAVE CAUGHT IT BEFORE. Every other twin proof
// compiles its fixture fresh, so the IR and the recompile come from the SAME
// compiler and agree by construction. The universe those proofs never contain
// is *an artifact compiled by yesterday's compiler* — and production is made
// entirely of those. That is why the arms below assert the compiler's OUTPUT
// SHAPE directly rather than round-tripping it.
// ============================================================================
import { readFileSync } from 'node:fs';
import path from 'node:path';

import { describe, expect, it } from 'vitest';

import { compileTemplateDocx } from '../../note-template-docx/compiler';
import {
  isWordPlaceholderOption,
  withoutPlaceholderOptions,
} from '../../note-template-docx/placeholder-option';
import { listEditableFormControls } from '../editable-controls';
import type { TemplateDocIR } from '../ir';

const REPO_ROOT = path.resolve(process.cwd(), '../..');
/** The sanctioned BLANK customer form — AGENTS.md, "Tracked fixtures". */
const WM_IOV_PATH = path.join(REPO_ROOT, 'WM IOV Template.docx');

function realForm() {
  return compileTemplateDocx(new Uint8Array(readFileSync(WM_IOV_PATH)));
}

describe('F24-S5 ITEM A — the compiled IR is stable across the placeholder change', () => {
  it('POSITIVE CONTROL: the instrument discriminates before any count is read', () => {
    const ir = realForm();
    // Non-vacuity: a form that compiled to nothing would satisfy every arm
    // below while checking nothing at all.
    expect(ir.fields.length).toBe(80);
    expect(isWordPlaceholderOption('Choose an item.')).toBe(true);
    expect(isWordPlaceholderOption('Bilateral Screening')).toBe(false);
  });

  // ── THE ARM THAT REDDENS IF ANYBODY RE-STRIPS AT COMPILE TIME ────────────
  it('⚠️ PERSISTS Word’s placeholder in allowedOptions — 153 options, 28 of them furniture', () => {
    const ir = realForm();
    const all = ir.fields.flatMap((f) => f.allowedOptions ?? []);
    const placeholders = all.filter((o) => isWordPlaceholderOption(o.displayText));

    // The exact figures the live certified twins carry, on QA and in
    // production — both measured 2026-08-24, both 80 / 153 / 28. If this arm
    // moves, EVERY already-compiled twin has just been orphaned.
    expect(all.length).toBe(153);
    expect(placeholders.length).toBe(28);

    // And the shape, so a future compiler cannot satisfy the counts by a
    // different route: one placeholder per single-select, always at ordinal 0.
    const withOptions = ir.fields.filter((f) => (f.allowedOptions?.length ?? 0) > 0);
    expect(withOptions.length).toBe(28);
    expect(placeholders.every((o) => o.ordinal === 0)).toBe(true);
  });

  it('leaves every surviving ordinal at the document’s own index', () => {
    const ir = realForm();
    for (const f of ir.fields) {
      const opts = f.allowedOptions ?? [];
      // Contiguous from 0 — i.e. nothing has been removed and renumbered.
      // Ruling #145: a stored ordinal outlives a recompile, so renumbering
      // silently re-points it at its NEIGHBOUR, which RESOLVES, so the
      // fail-closed decline never fires.
      opts.forEach((o, i) => expect(o.ordinal).toBe(i));
    }
  });

  // ── THE VALIDATION REFINEMENT IS NOT LOST ────────────────────────────────
  it('still judges option validity on the SELECTABLE set, not the stored one', () => {
    const ir = realForm();
    // Every one of the 28 keeps at least one REAL option once the furniture is
    // discounted — which is the property `SELECT_OPTIONS_INVALID` turns on. A
    // control whose only entry were the placeholder would compile to an empty
    // selectable set and be refused instead of becoming a field.
    const selects = ir.fields.filter((f) => (f.allowedOptions?.length ?? 0) > 0);
    for (const f of selects) {
      expect(withoutPlaceholderOptions(f.allowedOptions).length).toBeGreaterThan(0);
    }
    // …and no compiled field is left holding ONLY furniture.
    expect(
      selects.filter((f) => withoutPlaceholderOptions(f.allowedOptions).length === 0),
    ).toHaveLength(0);
  });

  // ── THE READER FILTERS FOR ITSELF ────────────────────────────────────────
  it('⚠️ never OFFERS the placeholder to the model, though the IR stores it', () => {
    const ir = realForm() as unknown as TemplateDocIR;
    const controls = listEditableFormControls(ir);

    // The list the model addresses by ordinal.
    expect(controls.length).toBe(28);
    const offered = controls.flatMap((c) => c.options);
    expect(offered.filter((o) => isWordPlaceholderOption(o))).toHaveLength(0);
    // 153 stored − 28 furniture = 125 offered. The partition reconciles.
    expect(offered.length).toBe(125);
  });

  it('⚠️ the ORDINALS are unchanged by the reader’s filter — a shift is a wrong-control write', () => {
    const ir = realForm() as unknown as TemplateDocIR;
    const controls = listEditableFormControls(ir);

    // 1..28, contiguous, in document order. `ordinal` is the ONLY address the
    // model may name, and the prompt tells the doctor to count occurrences down
    // their own form — so an off-by-one here writes a real value into a
    // neighbouring control and reports success.
    expect(controls.map((c) => c.ordinal)).toEqual(
      Array.from({ length: 28 }, (_, i) => i + 1),
    );
    const order = controls.map((c) => c.fieldId);
    const byDisplayOrder = ir.fields
      .filter((f) => f.rendererBinding.bindingType === 'content_control')
      .filter((f) => withoutPlaceholderOptions(f.allowedOptions).length > 0)
      .slice()
      .sort((a, b) => a.displayOrder - b.displayOrder)
      .map((f) => f.fieldId);
    expect(order).toEqual(byDisplayOrder);
  });
});
