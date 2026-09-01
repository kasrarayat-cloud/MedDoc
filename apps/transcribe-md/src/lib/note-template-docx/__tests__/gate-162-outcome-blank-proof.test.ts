// ============================================================================
// RULING #162 — THE BLANK PROOF IS OUTCOME-BASED.
// ----------------------------------------------------------------------------
// The invariant has always been "unfilled fields render genuinely blank". The
// old proxy asked "did the renderer produce ZERO PATCHES?" — a fact about a
// CODE PATH, and it never once looked at the OUTPUT. On a form whose fields are
// content controls a blank field is still patched (to empty), so no field could
// earn `kind: 'blank'` and `blankVerification` was UNSATISFIABLE BY
// CONSTRUCTION. Measured on the owner's live GI consult form: 20 fields null in
// the manifest, ALL 35 round-trip entries `filled`, blankProofCount 0.
//
// The gate now counts `blank` UNION `emptied`, and `emptied` is proven by
// reading the rendered control and requiring ZERO characters. A requirement is
// ADDED; none is removed.
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

describe('#162 — the blank proof is proven in the OUTPUT, not inferred', () => {
  it('a PATCHED null field earns an `emptied` proof — the class the old proxy could not see', async () => {
    const input = await setupAllBlank();
    const rendered = await renderTemplateDocx(input);
    const proofs = rendered.verification.fields;

    const emptied = proofs.filter((p) => p.kind === 'emptied');
    // NON-VACUITY — if the fixture produced none, every row below would hold
    // trivially and this arm would be measuring nothing.
    expect(emptied.length).toBeGreaterThan(0);
    expect(rendered.verification.verified).toBe(true);
    expect(rendered.verification.fieldCheck).toBe('verified');

    // ⚠️ THE GATE'S OWN PREDICATE, RE-STATED THROUGH THE DATA rather than by
    // grepping the source: this arm fails if certification stops counting the
    // union. Text presence is not membership.
    const blankProofCount = proofs.filter(
      (p) => p.kind === 'blank' || p.kind === 'emptied',
    ).length;
    expect(blankProofCount).toBeGreaterThan(0);
  });

  it('⚠️ EVERY `emptied` CONTROL IS ACTUALLY EMPTY IN THE RENDERED BYTES', async () => {
    // The claim is about the ARTIFACT, so it is checked against the artifact —
    // not against the resolution that produced it. This is the row that makes
    // `emptied` a proof rather than a relabelling.
    const input = await setupAllBlank();
    const rendered = await renderTemplateDocx(input);
    const emptied = rendered.verification.fields.filter((p) => p.kind === 'emptied');
    expect(emptied.length).toBeGreaterThan(0);

    const { inspectDocxPackage } = await import('../package-security');
    const pkg = inspectDocxPackage(rendered.document);
    const { scanXmlPart } = await import('../roundtrip-verify');
    for (const proof of emptied) {
      const entry = pkg.zip.entries.get(proof.partName);
      expect(entry, `part ${proof.partName} must exist`).toBeDefined();
      const scanned = scanXmlPart(entry!.bytes);
      const span = scanned.byPath.get(proof.bindingPath);
      expect(span, `binding ${proof.bindingPath} must resolve`).toBeDefined();
      const xml = scanned.text.slice(span!.start, span!.end);
      const text = [...xml.matchAll(/<w:t(?:\s[^>]*)?>([\s\S]*?)<\/w:t>/g)]
        .map((m) => m[1]!)
        .join('');
      expect([proof.fieldId, text]).toEqual([proof.fieldId, '']);
    }
  });

  it('a CHECKBOX is never `emptied` — unchecked is a rendered STATE, not an absence', async () => {
    // ⚠️ THIS ARM EXISTS BECAUSE I GOT IT WRONG. The first implementation keyed
    // `emptied` on the VALUE alone, and a null checkbox still renders the `☐`
    // glyph — real content — so the verifier read text where it had been
    // promised none. Seven existing arms went red, including `blank-proof`'s
    // own CANARY. The suite caught it; this row keeps it caught.
    const input = await setupAllBlank();
    const checkbox = input.ir.fields.find((f) => f.kind === 'checkbox');
    if (!checkbox) {
      // Recorded rather than silently skipped: the property is asserted at the
      // classifier instead, and the fixture's shape is the reason.
      expect(input.ir.fields.every((f) => f.kind !== 'checkbox')).toBe(true);
      return;
    }
    const rendered = await renderTemplateDocx(input);
    const mine = rendered.verification.fields.find((p) => p.fieldId === checkbox.fieldId);
    expect([checkbox.fieldId, mine?.kind]).not.toEqual([checkbox.fieldId, 'emptied']);
  });

  it('⚠️ a FILLED control claimed `emptied` is REFUSED — and see the honest limit below', async () => {
    // ⚠️ HONEST LIMIT, RECORDED RATHER THAN OVERCLAIMED — AND IT IS THE SAME
    // ONE `blank-proof`'s CANARY records about its own byte comparison.
    //
    // MEASURED, twice: deleting the output-bytes emptiness check in
    // `roundtrip-verify` leaves this arm — and the entire suite — GREEN. The
    // refusal below therefore comes from the STRUCTURAL guards that run first,
    // not from that check. Claiming this arm isolates it would be canon 62
    // exactly: an overlapping guard laundering an unproved one.
    //
    // WHAT IS PROVED, and it is the direction the ruling names first: a
    // renderer that JUNK-FILLS a blank is REFUSED — mutating
    // `textContainerPatches(… '' …)` to write text reds SIX arms. And the
    // checkbox exclusion is load-bearing: calling a null checkbox `emptied`
    // reds SEVEN. The emptiness check itself is DEFENCE IN DEPTH behind those,
    // and constructing a case that reaches it with the structural guards
    // satisfied is not expressible in this fixture.
    //
    // So this arm asserts what it can: the mislabelled claim is refused.
    const source = await buildSyntheticDocx();
    const { compileTemplateDocx } = await import('../compiler');
    const { verifyRenderedTemplateDocx } = await import('../roundtrip-verify');
    const { TemplateDocxRenderError } = await import('../errors');
    const ir = compileTemplateDocx(source);

    const target = ir.fields.find(
      (f) => f.kind === 'single_select' && !f.rowPrototype && f.allowedOptions.length > 0,
    )!;
    const resolutions = ir.fields.map((field) =>
      FieldResolutionSchema.parse(
        field.fieldId === target.fieldId
          ? {
              fieldId: field.fieldId,
              status: 'supported',
              value: target.allowedOptions[0]!.value,
              // The evidence rails are REAL and the schema enforces them: a
              // populated value must cite a fact and an anchor. Satisfied here
              // rather than bypassed — the arm is about the blank proof, and it
              // must not buy its setup by weakening something else.
              sourceFactIds: ['ttfact_' + 'a'.repeat(24)],
              evidenceAnchorIds: ['anchor-1'],
              selectedOptionOrdinal: target.allowedOptions[0]!.ordinal,
              reasonCode: 'direct_evidence_supported',
              clinicianReviewed: false,
            }
          : {
              fieldId: field.fieldId,
              status: 'not_mentioned',
              value: null,
              sourceFactIds: [],
              evidenceAnchorIds: [],
              selectedOptionOrdinal: null,
              reasonCode: 'blank_when_unsaid',
              clinicianReviewed: false,
            },
      ),
    );

    const rendered = await renderTemplateDocx({ source, ir, resolutions, validation: VALIDATION });
    const filledProof = rendered.verification.fields.find(
      (p) => p.kind === 'filled' && p.fieldId === target.fieldId,
    );
    // NON-VACUITY — if nothing rendered filled there is no isolation to run.
    expect(filledProof, 'fixture rendered no filled field; isolation cannot run').toBeDefined();

    expect(() =>
      verifyRenderedTemplateDocx({
        source,
        output: rendered.document,
        ir,
        plan: {
          ...rendered.plan,
          fields: rendered.verification.fields.map((p) =>
            p.fieldId === target.fieldId ? { ...p, kind: 'emptied' as const } : p,
          ),
        },
      }),
    ).toThrow(TemplateDocxRenderError);
  });
});
