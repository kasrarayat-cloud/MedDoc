// ============================================================================
// RULING #165 — THE WRITER IS CORRECT BY CONSTRUCTION; THE PROOF IS OURS.
// ----------------------------------------------------------------------------
// ⚠️ WHY THIS FILE REPLACES #164's GATE, STATED AS A MEASUREMENT.
//
// #164 asserted that a null-valued field was labelled `emptied` and that the
// label counted. Three independent adversarial lenses broke it with the same
// input, and the author reproduced it: a `narrative_text` content control
// holding a Wingdings tick beside its prompt was proofed `emptied`, verified,
// and BOUGHT THE CERTIFICATION BLANK REQUIREMENT — while still printing the
// tick. The gate flipped BLOCKED -> PASS on a field that renders a mark.
//
// #164's arms could not see it because every one of them asserted on a LABEL
// (kind, binding) and none asserted that anything had been CLEARED. This file
// asserts the output.
//
// THE TWO HALVES, and neither is sufficient alone:
//   1. WRITER — a null replaces the control's whole `w:sdtContent` subtree.
//      The boundary is the document's own element, so no carrier list exists to
//      be incomplete. That is what the four falsified instruments all lacked.
//   2. PROOF  — byte-equality against what the writer recorded it would leave.
//      On its own this is WRITER-BLIND (it would happily certify a writer that
//      left a glyph behind); half 1 is what makes it sufficient.
// ============================================================================
import { describe, expect, it } from 'vitest';

import { FieldResolutionSchema, type TemplateTwinValidationResult } from '../../template-twin/ir';
import { countsAsBlankProof } from '../../template-twin/blank-proof-count';
import { renderTemplateDocx } from '../renderer';
import { buildSyntheticDocx } from './synthetic-docx';

const VALIDATION: TemplateTwinValidationResult = {
  valid: true,
  issues: [],
  checkedAt: '2026-01-01T00:00:00.000Z',
  validatorVersion: 'template-field-validator/1.0.0',
};

/** Every visible carrier the four falsified instruments failed to enumerate. */
const CARRIERS: ReadonlyArray<readonly [string, string, string]> = [
  ['w:sym', '<w:r><w:sym w:font="Wingdings" w:char="F0FE"/></w:r>', 'w:sym'],
  ['w:pict', '<w:r><w:pict><v:shape id="s1"/></w:pict></w:r>', 'w:pict'],
  ['w:drawing', '<w:r><w:drawing><wp:inline/></w:drawing></w:r>', 'w:drawing'],
  ['w:delText', '<w:r><w:delText>WARFARIN 5 MG DAILY</w:delText></w:r>', 'WARFARIN'],
  [
    'w:instrText',
    '<w:r><w:instrText> QUOTE "WARFARIN 5 MG DAILY" </w:instrText></w:r>',
    'QUOTE',
  ],
];

function docWith(extra: string, opts: { placeholder?: boolean } = {}): string {
  const plc = opts.placeholder ? '<w:showingPlcHdr/>' : '';
  return (
    `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>` +
    `<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" ` +
    `xmlns:w14="http://schemas.microsoft.com/office/word/2010/wordml" ` +
    `xmlns:v="urn:schemas-microsoft-com:vml" ` +
    `xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing">` +
    `<w:body><w:p>` +
    `<w:sdt><w:sdtPr>${plc}<w:id w:val="900"/>` +
    `<w:alias w:val="Anticoagulation"/><w:tag w:val="anticoag"/><w:text/></w:sdtPr>` +
    `<w:sdtContent><w:r><w:t>Enter anticoagulation</w:t></w:r>${extra}</w:sdtContent>` +
    `</w:sdt></w:p></w:body></w:document>`
  );
}

async function renderAllNull(documentXml: string) {
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
  // ⚠️ UNZIP. A .docx is a ZIP; reading the buffer as text measures COMPRESSION.
  const { inspectDocxPackage } = await import('../package-security');
  const read = (buf: Buffer | Uint8Array) =>
    Buffer.from(
      inspectDocxPackage(buf).zip.entries.get('word/document.xml')!.bytes,
    ).toString('utf8');
  const bindingOf = (fieldId: string) =>
    ir.fields.find((f) => f.fieldId === fieldId)?.rendererBinding.bindingType as
      | string
      | undefined;
  return {
    ir,
    rendered,
    sourceXml: read(source),
    outputXml: read(rendered.document),
    proofs: (rendered.verification.fields ?? []) as unknown as Array<Record<string, unknown>>,
    // ⚠️ SCOPED TO THE BODY ON PURPOSE. `buildSyntheticDocx` always ships a
    // header carrying its OWN narrative content control, which correctly
    // clears and correctly earns its own `emptied` proof. A global
    // "no proof anywhere is emptied" assertion therefore measures the HEADER,
    // not the field under test — it failed twice here before being scoped.
    bodyProofs: (
      (rendered.verification.fields ?? []) as unknown as Array<Record<string, unknown>>
    ).filter((p) => p.partName === 'word/document.xml'),
    bindingOf,
  };
}

describe('#165 rule 1 — the writer clears the whole subtree, so nothing inside survives', () => {
  // ⚠️ THIS IS LENS 1'S ATTACK, TURNED INTO THE GATE. Under #164 every one of
  // these rows produced `emptied` + counts=true with the carrier STILL PRESENT.
  for (const [name, extra, needle] of CARRIERS) {
    it(`a null control containing ${name} renders EMPTY — the carrier is GONE`, async () => {
      const { sourceXml, outputXml, proofs, bindingOf, rendered } = await renderAllNull(
        docWith(extra),
      );

      // POSITIVE CONTROL — the carrier really is in the SOURCE, so its absence
      // below is the writer's doing and not the fixture's.
      expect([name, sourceXml.includes(needle)]).toEqual([name, true]);

      // ⚠️ THE PROPERTY #164 NEVER ASSERTED: the output is actually empty.
      expect([name, outputXml.includes(needle)]).toEqual([name, false]);

      // and only THEN may it buy a blank proof.
      const proof = proofs.find((p) => p.kind === 'emptied');
      expect(proof, `${name}: no emptied proof was produced`).toBeDefined();
      expect(countsAsBlankProof(proof as never, bindingOf)).toBe(true);
      expect(rendered.verification.verified).toBe(true);
    });
  }

  it('an emptied proof carries `expectedSpanSha256` — an uncheckable claim is not a proof', async () => {
    const { proofs } = await renderAllNull(docWith(CARRIERS[0][1]));
    const emptied = proofs.filter((p) => p.kind === 'emptied');
    expect(emptied.length).toBeGreaterThan(0);
    for (const p of emptied) {
      expect(typeof p.expectedSpanSha256, JSON.stringify(p)).toBe('string');
      expect((p.expectedSpanSha256 as string).length).toBe(64);
    }
  });

  it('`w:showingPlcHdr` is removed with the content, so Word cannot re-show the prompt', async () => {
    const { sourceXml, outputXml } = await renderAllNull(
      docWith('', { placeholder: true }),
    );
    expect(sourceXml.includes('showingPlcHdr')).toBe(true);
    expect(outputXml.includes('showingPlcHdr')).toBe(false);
  });
});

describe('#165 — the replacement matches the control LEVEL, read from its parent', () => {
  // ⚠️ THESE TWO ARMS EXIST BECAUSE THE FIRST VERSION INFERRED THE LEVEL FROM
  // THE CONTENT. That has a silent hole: an already-empty BLOCK-level
  // `w:sdtContent` has no children, so a child scan calls it inline and writes
  // a bare `w:r` between two paragraphs — invalid OOXML. The parent always
  // knows, so the parent is what decides.
  const blockDoc = (inner: string) =>
    `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>` +
    `<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">` +
    `<w:body>` +
    `<w:sdt><w:sdtPr><w:id w:val="910"/><w:alias w:val="Assessment"/><w:text/></w:sdtPr>` +
    `<w:sdtContent>${inner}</w:sdtContent></w:sdt>` +
    `</w:body></w:document>`;

  it('a BLOCK-level control clears to a PARAGRAPH, never a bare run', async () => {
    const { outputXml, bodyProofs } = await renderAllNull(
      blockDoc('<w:p><w:r><w:t>Enter assessment</w:t></w:r></w:p>'),
    );
    const inner = outputXml.slice(
      outputXml.indexOf('<w:sdtContent>'),
      outputXml.indexOf('</w:sdtContent>'),
    );
    expect(inner.includes('Enter assessment')).toBe(false);
    // THE PROPERTY: a block container must still hold a paragraph.
    expect([inner.includes('<w:p>'), inner.startsWith('<w:sdtContent><w:r>')]).toEqual([
      true,
      false,
    ]);
    expect(bodyProofs[0]?.kind).toBe('emptied');
  });

  it('an ALREADY-EMPTY block-level control does not gain a bare run', async () => {
    const { outputXml } = await renderAllNull(blockDoc(''));
    const inner = outputXml.slice(
      outputXml.indexOf('<w:sdtContent>'),
      outputXml.indexOf('</w:sdtContent>'),
    );
    // A child scan would have written `<w:r>` straight into the body here.
    expect(inner.startsWith('<w:sdtContent><w:r>')).toBe(false);
  });
});

describe('#165 — what the writer does decides the label, not a list of kinds', () => {
  it('a null SELECTION is emptied and counts — #164 excluded it on a FALSE premise', async () => {
    // #164's comment claimed a selection "renders anything, so it asserts a
    // choice". Measured: a null single_select clears to empty exactly like a
    // narrative control. The 28 WM_IOV dropdowns are the target population.
    const { proofs, bindingOf, outputXml } = await renderAllNull(
      `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>` +
        `<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">` +
        `<w:body><w:p><w:sdt><w:sdtPr><w:id w:val="901"/><w:alias w:val="Exam side"/>` +
        `<w:dropDownList><w:listItem w:displayText="Left" w:value="L"/>` +
        `<w:listItem w:displayText="Right" w:value="R"/></w:dropDownList>` +
        `</w:sdtPr><w:sdtContent><w:r><w:t>Choose an item.</w:t></w:r>` +
        `</w:sdtContent></w:sdt></w:p></w:body></w:document>`,
    );
    const proof = proofs.find((p) => p.kind === 'emptied');
    expect(proof, 'a null selection produced no emptied proof').toBeDefined();
    expect(countsAsBlankProof(proof as never, bindingOf)).toBe(true);
    expect(outputXml.includes('Choose an item.')).toBe(false);
  });

  it('a null CHECKBOX is NOT emptied — both its states PRINT', async () => {
    // Not a policy choice and not a kind list: we deliberately WRITE the
    // unchecked glyph, so there is no clearing to prove. The exclusion falls
    // out of the write itself.
    const { bodyProofs, outputXml } = await renderAllNull(
      `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>` +
        `<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" ` +
        `xmlns:w14="http://schemas.microsoft.com/office/word/2010/wordml">` +
        `<w:body><w:p><w:sdt><w:sdtPr><w:id w:val="902"/><w:alias w:val="Medication reviewed"/>` +
        `<w14:checkbox><w14:checked w14:val="0"/><w14:checkedState w14:val="2612"/>` +
        `<w14:uncheckedState w14:val="2610"/></w14:checkbox></w:sdtPr>` +
        `<w:sdtContent><w:r><w:t>☐</w:t></w:r></w:sdtContent></w:sdt></w:p></w:body></w:document>`,
    );
    // NON-VACUITY FIRST: the fixture really did compile ONE body field.
    expect(bodyProofs.length).toBe(1);
    expect(bodyProofs[0].kind).toBe('filled');
    // and it really did render a mark, which is WHY it is excluded.
    expect(outputXml.includes('☐')).toBe(true);
  });
});

describe('#165 — bindings with no bounded container earn nothing', () => {
  it('a LEGACY form field is never emptied — its result has no enclosing element', async () => {
    const { bodyProofs, ir } = await renderAllNull(
      `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>` +
        `<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">` +
        `<w:body><w:p>` +
        `<w:r><w:fldChar w:fldCharType="begin"><w:ffData><w:name w:val="Legacy anticoagulant"/>` +
        `<w:textInput><w:default w:val="WARFARIN 5 MG DAILY"/></w:textInput></w:ffData></w:fldChar></w:r>` +
        `<w:r><w:instrText> FORMTEXT </w:instrText></w:r>` +
        `<w:r><w:fldChar w:fldCharType="separate"/></w:r>` +
        `<w:r><w:t>WARFARIN 5 MG DAILY</w:t></w:r>` +
        `<w:r><w:fldChar w:fldCharType="end"/></w:r>` +
        `</w:p></w:body></w:document>`,
    );
    // NON-VACUITY: the fixture really does compile a legacy binding.
    expect(
      ir.fields.filter((f) => f.rendererBinding.bindingType === 'legacy_form_field').length,
    ).toBeGreaterThan(0);
    expect(bodyProofs.length).toBe(1);
    expect(bodyProofs[0].kind).not.toBe('emptied');
  });
});

// ── FILED, NOT DELETED — ruling #164 rule 1, carried forward by #165 ─────────
// The reproductions live in `docs/backlog/renderer-legacy-clearing.md`. Never a
// red test on `main`, never a deleted repro.
describe('renderer slice — legacy clearing (FILED, docs/backlog/renderer-legacy-clearing.md)', () => {
  it.todo(
    'a paragraph-spanning legacy FORMTEXT result is NOT cleared — reproduced: SOURCE true -> OUTPUT true',
  );
  it.todo(
    'non-w:t content in a cleared LEGACY region survives — the whole-subtree cure needs a real container first',
  );
});
