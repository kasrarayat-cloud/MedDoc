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
import { buildSyntheticDocx, syntheticOpc } from './synthetic-docx';

const VALIDATION: TemplateTwinValidationResult = {
  valid: true,
  issues: [],
  checkedAt: '2026-01-01T00:00:00.000Z',
  validatorVersion: 'template-field-validator/1.0.0',
};

/**
 * Every visible carrier the four falsified instruments failed to enumerate.
 *
 * ⚠️ THIS LIST MUST MATCH THE ONE `docs/backlog/renderer-legacy-clearing.md`
 * NAMES, AND IT DID NOT. The adversarial pass caught `w:object` present in the
 * prose and absent here, under this very comment claiming "every". An
 * enumeration that does not reconcile with its own stated list is exactly the
 * defect this whole arc keeps paying for — so the count is asserted below
 * rather than trusted.
 */
const CARRIERS: ReadonlyArray<readonly [string, string, string]> = [
  ['w:sym', '<w:r><w:sym w:font="Wingdings" w:char="F0FE"/></w:r>', 'w:sym'],
  ['w:pict', '<w:r><w:pict><v:shape id="s1"/></w:pict></w:r>', 'w:pict'],
  ['w:drawing', '<w:r><w:drawing><wp:inline/></w:drawing></w:r>', 'w:drawing'],
  ['w:object', '<w:r><w:object><v:shape id="o1"/></w:object></w:r>', 'w:object'],
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

async function renderAllNull(documentXml: string, stylesXml?: string) {
  // `extraEntries` is applied after the defaults, so this overrides
  // `word/styles.xml` — which is where a paragraph's numbering can live.
  const source = await buildSyntheticDocx({
    documentXml,
    ...(stylesXml ? { extraEntries: { 'word/styles.xml': stylesXml } } : {}),
  });
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
  // ⚠️ THE REAL KIND, FROM THE COMPILED IR — not a stub. `kindOf` fails CLOSED
  // on `undefined`, so a stub would make every arm below refuse for a reason
  // that has nothing to do with what it is testing.
  const kindOf = (fieldId: string) =>
    ir.fields.find((f) => f.fieldId === fieldId)?.kind as string | undefined;
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
    kindOf,
  };
}

describe('#165 rule 1 — the writer clears the whole subtree, so nothing inside survives', () => {
  // ⚠️ THIS IS LENS 1'S ATTACK, TURNED INTO THE GATE. Under #164 every one of
  // these rows produced `emptied` + counts=true with the carrier STILL PRESENT.
  for (const [name, extra, needle] of CARRIERS) {
    it(`a null control containing ${name} renders EMPTY — the carrier is GONE`, async () => {
      const { sourceXml, outputXml, bodyProofs, bindingOf, kindOf, rendered } = await renderAllNull(
        docWith(extra),
      );

      // POSITIVE CONTROL — the carrier really is in the SOURCE, so its absence
      // below is the writer's doing and not the fixture's.
      expect([name, sourceXml.includes(needle)]).toEqual([name, true]);

      // ⚠️ THE PROPERTY #164 NEVER ASSERTED: the output is actually empty.
      expect([name, outputXml.includes(needle)]).toEqual([name, false]);

      // and only THEN may it buy a blank proof.
      // ⚠️ SCOPED TO THE BODY. The fixture package always ships a header
      // control that ALSO earns an `emptied` proof, so `proofs.find` measures
      // whichever comes first. It is the body today — verified — but that is
      // index-dependence, and this file uses `bodyProofs` everywhere else.
      const proof = bodyProofs.find((p) => p.kind === 'emptied');
      expect(proof, `${name}: no emptied proof was produced`).toBeDefined();
      expect(
        countsAsBlankProof(proof as never, { bindingOf, resolvedNull: () => true, kindOf }),
      ).toBe(true);
      expect(rendered.verification.verified).toBe(true);
    });
  }

  it('an emptied proof carries `expectedSpanSha256` — an uncheckable claim is not a proof', async () => {
    const { bodyProofs } = await renderAllNull(docWith(CARRIERS[0][1]));
    const emptied = bodyProofs.filter((p) => p.kind === 'emptied');
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
  it('⚠️ a null SELECTION is NOT emptied — #165 included them, #168 reversed it', async () => {
    // ⚠️ THIS ARM PREVIOUSLY ASSERTED THE OPPOSITE AND STAYED GREEN THROUGH THE
    // REVERSAL, because its `proofs.find(kind === 'emptied')` was UNSCOPED and
    // matched the header control the fixture package always ships. Measured:
    //
    //   word/document.xml  Exam side (single_select)      proof=filled   counts=false
    //   word/header1.xml   Practice display name (narr.)  proof=emptied  counts=true
    //   the arm's find() -> the HEADER field
    //
    // That is the exact hazard this file's own `bodyProofs` comment warns
    // about, in the arm that most needed the scoping — an arm asserting a rule
    // the codebase had already reversed, kept green by measuring a different
    // field in a different part.
    const { bodyProofs, outputXml } = await renderAllNull(
      `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>` +
        `<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">` +
        `<w:body><w:p><w:sdt><w:sdtPr><w:id w:val="901"/><w:alias w:val="Exam side"/>` +
        `<w:dropDownList><w:listItem w:displayText="Left" w:value="L"/>` +
        `<w:listItem w:displayText="Right" w:value="R"/></w:dropDownList>` +
        `</w:sdtPr><w:sdtContent><w:r><w:t>Choose an item.</w:t></w:r>` +
        `</w:sdtContent></w:sdt></w:p></w:body></w:document>`,
    );
    // NON-VACUITY: exactly one BODY field, and it is the selection.
    expect(bodyProofs.length).toBe(1);
    // It still CLEARS — the exclusion is on the count, not the render.
    expect(outputXml.includes('Choose an item.')).toBe(false);
    expect(bodyProofs[0].kind).not.toBe('emptied');
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

// ============================================================================
// WHAT THE ADVERSARIAL PASS FORCED — five defects in the bounded clear itself.
// ----------------------------------------------------------------------------
// Every arm below reds against the version of `sdtBoundedClearPatches` that
// shipped in the first draft of this commit. They are here because the pass
// measured each one, not because they seemed prudent.
// ============================================================================
function sdtDoc(opts: {
  prefix?: string;
  parent?: string;
  content: string;
  extraSdtChild?: string;
  /** Place the control as a sibling of paragraphs (block level) rather than
   *  inside one. This is the shape the formatting regression was measured on —
   *  27 of the customer template's 28 controls are inline, and the page-spill
   *  came from a block-level control in a table cell. */
  block?: boolean;
}): string {
  const p = opts.prefix ?? 'w';
  const inner =
    `<${p}:sdt><${p}:sdtPr><${p}:id ${p}:val="950"/>` +
    `<${p}:alias ${p}:val="Anticoagulation"/><${p}:text/></${p}:sdtPr>` +
    `<${p}:sdtContent>${opts.content}</${p}:sdtContent>` +
    `${opts.extraSdtChild ?? ''}</${p}:sdt>`;
  const body = opts.block
    ? inner
    : opts.parent
      ? `<${p}:p><${p}:${opts.parent}>${inner}</${p}:${opts.parent}></${p}:p>`
      : `<${p}:p>${inner}</${p}:p>`;
  return (
    `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>` +
    `<${p}:document xmlns:${p}="http://schemas.openxmlformats.org/wordprocessingml/2006/main">` +
    `<${p}:body>${body}</${p}:body></${p}:document>`
  );
}

describe('#165 — the bounded clear, after the adversarial pass', () => {
  it('the clear emits ONLY DELETIONS — nothing is written, so no prefix can be wrong', async () => {
    // ⚠️ RETARGETED — THE PREVIOUS ASSERTION WAS VACUOUS AND A LENS PROVED IT.
    // It asserted no `w:`-prefixed element appears in an `x:`-prefixed document.
    // Under v3 nothing is EVER written, so that cannot fail: hardcoding
    // `qualifiedPrefix` to return `'w:'`, and even making it THROW, redded zero
    // arms — the function is not called from this file at all.
    //
    // The honest arm is the property that makes it vacuous, and that property IS
    // falsifiable: every patch this path emits is a DELETION. Reintroduce any
    // writing — a rebuilt run, a synthesised paragraph — and this reds.
    const { outputXml, rendered } = await renderAllNull(
      sdtDoc({ prefix: 'x', content: '<x:r><x:t>Enter anticoagulation</x:t></x:r>' }),
    );
    expect(rendered.verification.verified).toBe(true);
    const emptied = rendered.plan.fields.find((f) => f.kind === 'emptied');
    expect(emptied, 'no emptied proof — the arm would be vacuous').toBeDefined();
    const patches = rendered.plan.parts
      .flatMap((part) => part.patches)
      .filter((patch) => patch.fieldIds.includes(emptied!.fieldId));
    expect(patches.length).toBeGreaterThan(0);
    // THE PROPERTY: every patch is a pure deletion.
    expect(patches.map((patch) => patch.replacement)).toEqual(patches.map(() => ''));
    // and the content really did clear, in the document's own prefix.
    expect(outputXml.includes('Enter anticoagulation')).toBe(false);
    expect(outputXml.includes('<x:t')).toBe(true);
  });

  it('an SDT carrying children beyond sdtPr/sdtContent is REFUSED, not half-cleared', async () => {
    // The bound is the FIRST `w:sdtContent`. A stale run trailing it is inside
    // `w:sdt` and outside that element, so it survived a control proofed
    // `emptied` — the pass rendered WARFARIN out of one.
    const { outputXml, bodyProofs } = await renderAllNull(
      sdtDoc({
        content: '<w:r><w:t>placeholder</w:t></w:r>',
        extraSdtChild: '<w:r><w:t>WARFARIN 5 MG DAILY</w:t></w:r>',
      }),
    );
    // It is NOT claimed empty. (The fallback still blanks the container's text,
    // which is main's long-standing behaviour; what must not happen is an
    // `emptied` proof buying a blank requirement for a control that prints.)
    expect(bodyProofs.map((p) => p.kind)).not.toContain('emptied');
    expect(outputXml.includes('WARFARIN')).toBe(true);
  });

  for (const parent of ['fldSimple', 'moveTo', 'bdo']) {
    it(`a control inside w:${parent} clears by DELETION, with no level to infer`, async () => {
      // ⚠️ RETARGETED — the old assertion (`no <w:p> inside a <w:p>`) was VACUOUS
      // under v3 and a lens proved it: v3 writes no `w:p` at all, so the regex
      // cannot match, and all three survived `sdtBoundedClearPatches` returning
      // `null` unconditionally.
      //
      // These three parents mattered because v2 inferred a block/inline LEVEL
      // from an enumeration that was short by four. v3 infers no level, so the
      // arm now pins that: the content clears, and every patch is a deletion.
      const { outputXml, rendered } = await renderAllNull(
        sdtDoc({ parent, content: '<w:r><w:t>Enter anticoagulation</w:t></w:r>' }),
      );
      expect([parent, outputXml.includes('Enter anticoagulation')]).toEqual([parent, false]);
      const patches = rendered.plan.parts.flatMap((part) => part.patches);
      expect([parent, patches.every((patch) => patch.replacement === '')]).toEqual([parent, true]);
    });
  }

  it('an ALREADY-EMPTY container needs no patch and earns a `blank` proof', async () => {
    // The documented fallback for this case aborted the WHOLE render:
    // `textContainerPatches` found no `w:t` and threw BINDING_NOT_FOUND.
    const { bodyProofs, rendered } = await renderAllNull(sdtDoc({ content: '' }));
    expect(rendered.verification.verified).toBe(true);
    expect(bodyProofs.length).toBe(1);
    expect(bodyProofs[0].kind).toBe('blank');
  });

  it('the emptied field KEEPS its paragraph and run formatting', async () => {
    // Measured through the product's own converter: dropping `w:pPr`/`w:rPr`
    // moved row pitch 10.75pt -> 14.20pt and pushed a 48-row form onto a second
    // page; on the customer's template a doctor typing into an emptied control
    // got the document default instead of Times New Roman.
    const { outputXml } = await renderAllNull(
      sdtDoc({
        block: true,
        content:
          '<w:p><w:pPr><w:jc w:val="center"/><w:spacing w:line="200" w:lineRule="exact"/>' +
          // ⚠️ THE PARAGRAPH-MARK rPr IS THE ONE THAT MATTERS FOR AN EMPTIED
          // FIELD. Under #167 the RUN is deleted, so a run's own `w:rPr` goes
          // with it — correctly, since the run is content. What a doctor typing
          // into the emptied paragraph inherits is `w:pPr/w:rPr`, and that is
          // skeleton, so it survives.
          '<w:rPr><w:rFonts w:ascii="Times New Roman"/><w:sz w:val="14"/></w:rPr></w:pPr>' +
          '<w:r><w:rPr><w:rFonts w:ascii="Courier New"/></w:rPr>' +
          '<w:t>Enter anticoagulation</w:t></w:r></w:p>',
      }),
    );
    const inner = outputXml.slice(
      outputXml.indexOf('<w:sdtContent>'),
      outputXml.indexOf('</w:sdtContent>'),
    );
    expect(inner.includes('Enter anticoagulation')).toBe(false);
    // THE PROPERTIES SURVIVE — the field is empty, not restyled.
    expect([
      inner.includes('w:jc'),
      inner.includes('w:lineRule="exact"'),
      inner.includes('Times New Roman'),
      inner.includes('w:sz w:val="14"'),
    ]).toEqual([true, true, true, true]);
    // ⚠️ #168 — THE RUN SHELL AND ITS `w:rPr` NOW SURVIVE. An empty run with
    // properties prints nothing and is what a doctor typing into the cleared
    // control inherits. What must be gone is the run's CONTENT.
    expect([inner.includes('<w:r>'), inner.includes('Courier New')]).toEqual([true, true]);
    expect(inner.includes('<w:t>Enter anticoagulation</w:t>')).toBe(false);
  });

  it('an INLINE emptied field KEEPS its run shell and properties — #168', async () => {
    // ⚠️ RETARGETED TWICE, AND THE SECOND TIME RESTORES A CAPABILITY.
    // v2 rebuilt an empty run carrying the source `w:rPr`. v3 deleted the run
    // outright, which cost `w:rPr` on all 28 controls of the real template
    // (307 -> 279) — a measured delta against base on the majority path, since
    // 27 of 28 controls are inline. #168 keeps the run SHELL and its properties
    // and deletes every other child, so the field is empty AND a doctor typing
    // into it inherits what the template author specified.
    const { outputXml, bodyProofs } = await renderAllNull(
      sdtDoc({
        content:
          '<w:r><w:rPr><w:rFonts w:ascii="Times New Roman"/><w:sz w:val="22"/>' +
          '<w:b/></w:rPr><w:t>Enter anticoagulation</w:t><w:sym w:font="Wingdings" w:char="F0FE"/></w:r>',
      }),
    );
    const inner = outputXml.slice(
      outputXml.indexOf('<w:sdtContent>'),
      outputXml.indexOf('</w:sdtContent>'),
    );
    // CONTENT gone — including a non-`w:t` carrier inside the very run we keep.
    expect([inner.includes('Enter anticoagulation'), inner.includes('w:sym')])
      .toEqual([false, false]);
    // PROPERTIES kept.
    expect([
      inner.includes('<w:r>'),
      inner.includes('Times New Roman'),
      inner.includes('w:sz w:val="22"'),
      inner.includes('<w:b/>'),
    ]).toEqual([true, true, true, true]);
    expect(bodyProofs[0]?.kind).toBe('emptied');
  });

  it('a control WRAPPING A TABLE keeps the grid and empties the cells', async () => {
    // Replacing a `w:tbl` with an empty paragraph deleted borders, columns and
    // rows: an empty bordered results table became nothing.
    const { outputXml, bodyProofs } = await renderAllNull(
      sdtDoc({
        block: true,
        content:
          '<w:tbl><w:tblPr><w:tblBorders><w:top w:val="single"/></w:tblBorders></w:tblPr>' +
          '<w:tr><w:tc><w:p><w:r><w:t>Diameter</w:t></w:r></w:p></w:tc></w:tr></w:tbl>',
      }),
    );
    // ⚠️ #167 KEEPS THE STRUCTURE AND EMPTIES IT, where v2 flattened the grid
    // away entirely and an earlier version refused the shape. `w:tbl`, `w:tr`,
    // `w:tc` and their properties are skeleton; the cell's runs are not.
    expect([
      outputXml.includes('<w:tbl>'),
      outputXml.includes('w:tblBorders'),
      outputXml.includes('<w:tr>'),
      outputXml.includes('<w:tc>'),
    ]).toEqual([true, true, true, true]);
    expect(outputXml.includes('Diameter')).toBe(false);
    expect(bodyProofs.map((p) => p.kind)).toContain('emptied');
  });

  it('`w:sectPr` inside the cleared paragraph survives, because it lives in w:pPr', async () => {
    const { outputXml } = await renderAllNull(
      sdtDoc({
        block: true,
        content:
          '<w:p><w:pPr><w:sectPr><w:pgSz w:w="12240" w:h="15840"/>' +
          '<w:pgMar w:left="1440"/></w:sectPr></w:pPr>' +
          '<w:r><w:t>Enter anticoagulation</w:t></w:r></w:p>',
      }),
    );
    expect([outputXml.includes('w:sectPr'), outputXml.includes('w:pgSz')]).toEqual([true, true]);
  });
});

// ============================================================================
// RULE 2's BYTE COMPARISON IS LOAD-BEARING — decided by composition, not by
// assertion, after an adversarial lens argued it was decoration.
// ----------------------------------------------------------------------------
// The lens was RIGHT that deleting the check reds nothing in the suite, and
// WRONG about why. Its structural argument was that the only way an emptied
// span can diverge from its expectation is a foreign patch inside it — which
// means nested bindings, which die earlier as PATCH_OVERLAP.
//
// But a SAME-FIELD patch touching the span AFTER the expectation is computed
// diverges too, and nothing else sees it: `PATCH_OVERLAP` does not fire (one
// fieldId, non-overlapping ranges), and the whole-part equality PASSES, because
// it compares the output against `applyApprovedXmlPatches(source, proof.patches)`
// and the stray patch is IN that list. The two guards watch different things:
//
//   whole-part equality — "is the output what the recorded PATCH LIST produces?"
//   this check          — "does the recorded EXPECTATION describe the output?"
//
// They can only disagree when the patch list and the expectation disagree,
// which is exactly the renderer-bug class: a future change that touches an
// emptied field's span without re-deriving its expectation.
//
// MEASURED by mutation, injecting a stray same-field patch after the
// expectation was taken:
//
//   span check | whole-part | divergence | result
//   -----------|------------|------------|--------------------------
//   ON         | ON         | yes        | ROUNDTRIP_FIELD_MISMATCH
//   OFF        | ON         | yes        | NO THROW  <- it ships
//   OFF        | OFF        | yes        | NO THROW
//   ON         | ON         | no         | NO THROW  (control)
//
// The arms below reach the same guarantee without mutating production code, by
// re-running the verifier over a plan whose expectation has been corrupted.
// ============================================================================
describe('#165 rule 2 — the expectation must describe the output', () => {
  async function renderedWithPlan() {
    const documentXml = sdtDoc({ content: '<w:r><w:t>Enter anticoagulation</w:t></w:r>' });
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
    return { source, ir, rendered };
  }

  it('re-verifying an untouched render passes — the control', async () => {
    const { source, ir, rendered } = await renderedWithPlan();
    const { verifyRenderedTemplateDocx } = await import('../roundtrip-verify');
    const again = verifyRenderedTemplateDocx({
      source,
      output: rendered.document,
      ir,
      plan: rendered.plan,
    });
    expect(again.verified).toBe(true);
    // NON-VACUITY: there really is an emptied proof carrying an expectation.
    const emptied = rendered.plan.fields.filter((f) => f.kind === 'emptied');
    expect(emptied.length).toBeGreaterThan(0);
  });

  for (const [label, corrupt] of [
    ['a WRONG expectation', (f: Record<string, unknown>) => ({ ...f, expectedSpanSha256: 'b'.repeat(64) })],
    ['a MISSING expectation', (f: Record<string, unknown>) => {
      const { expectedSpanSha256: _gone, ...rest } = f;
      return rest;
    }],
  ] as const) {
    it(`${label} is REFUSED, and nothing else catches it`, async () => {
      const { source, ir, rendered } = await renderedWithPlan();
      const { verifyRenderedTemplateDocx } = await import('../roundtrip-verify');
      const plan = {
        parts: rendered.plan.parts,
        fields: rendered.plan.fields.map((f) =>
          f.kind === 'emptied' ? corrupt(f as unknown as Record<string, unknown>) : f,
        ),
      };
      let code = 'NO THROW';
      try {
        verifyRenderedTemplateDocx({ source, output: rendered.document, ir, plan: plan as never });
      } catch (error) {
        code = (error as { code?: string }).code ?? String(error);
      }
      // ⚠️ THE CODE IS ASSERTED BY NAME. "It threw" would be satisfied by the
      // whole-part equality (STATIC_INVARIANCE_FAILED), which is precisely the
      // guard this arm must NOT be laundered by — canon 62.
      expect([label, code]).toEqual([label, 'ROUNDTRIP_FIELD_MISMATCH']);
    });
  }
});

describe('#165 — "already empty" is not "cleared"', () => {
  it('a DATE control with empty content and a fullDate to strip is NOT `emptied`', async () => {
    // ⚠️ `[]` IS TRUTHY. `sdtBoundedClearPatches` returns `[]` for "already
    // empty, nothing to do" and `null` for "cannot bound this, fall back" — and
    // the comment said they were "treated differently" while all three call
    // sites took the same branch. So a field where NO clearing write happened
    // was labelled `emptied`, falsifying the invariant three files rely on:
    // "the renderer refuses to label anything `emptied` unless it actually
    // performed the whole-subtree replacement."
    const { bodyProofs, rendered } = await renderAllNull(
      `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>` +
        `<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">` +
        `<w:body><w:p><w:sdt><w:sdtPr><w:id w:val="970"/><w:alias w:val="Encounter date"/>` +
        `<w:date w:fullDate="2026-01-01T00:00:00Z"><w:dateFormat w:val="yyyy-MM-dd"/></w:date>` +
        `</w:sdtPr><w:sdtContent></w:sdtContent></w:sdt></w:p></w:body></w:document>`,
    );
    expect(rendered.verification.verified).toBe(true);
    expect(bodyProofs.length).toBe(1);
    // It IS patched — the `w:fullDate` attribute is stripped — so it is not
    // `blank` either. What it must not be is `emptied`, because nothing cleared.
    expect(bodyProofs[0].kind).not.toBe('emptied');
  });
});

// ============================================================================
// #167 RULE 1 v3 — STRUCTURE-KEEP. The six shapes two passes broke v2 on, plus
// the two the ruling named as the reason the mechanism must be a KEEP-list.
// ============================================================================
describe('#167 — structure survives, content does not', () => {
  it('a SECOND w:sdtContent is emptied too — v2 matched by NAME and let it through', async () => {
    const { outputXml, bodyProofs } = await renderAllNull(
      `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>` +
        `<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">` +
        `<w:body><w:p><w:sdt><w:sdtPr><w:id w:val="980"/>` +
        `<w:alias w:val="Anticoagulation"/><w:text/></w:sdtPr>` +
        `<w:sdtContent><w:r><w:t>placeholder</w:t></w:r></w:sdtContent>` +
        `<w:sdtContent><w:r><w:t>WARFARIN 5 MG DAILY</w:t></w:r></w:sdtContent>` +
        `</w:sdt></w:p></w:body></w:document>`,
    );
    // v2 proofed this `emptied` while the drug name printed.
    expect(outputXml.includes('WARFARIN')).toBe(false);
    expect(outputXml.includes('placeholder')).toBe(false);
    expect(bodyProofs[0]?.kind).toBe('emptied');
  });

  it('w:sectPr on the LAST paragraph survives — where it conventionally sits', async () => {
    const { outputXml } = await renderAllNull(
      sdtDoc({
        block: true,
        content:
          '<w:p><w:r><w:t>first</w:t></w:r></w:p>' +
          '<w:p><w:pPr><w:sectPr><w:pgSz w:w="15840" w:h="12240"/>' +
          '<w:pgMar w:left="360"/></w:sectPr></w:pPr>' +
          '<w:r><w:t>second</w:t></w:r></w:p>',
      }),
    );
    // v2 rebuilt only the FIRST paragraph, so a landscape section became portrait.
    expect([
      outputXml.includes('w:sectPr'),
      outputXml.includes('w:w="15840"'),
      outputXml.includes('first'),
      outputXml.includes('second'),
    ]).toEqual([true, true, false, false]);
  });

  it('MULTI-PARAGRAPH content keeps every paragraph', async () => {
    const { outputXml } = await renderAllNull(
      sdtDoc({
        block: true,
        content:
          '<w:p><w:r><w:t>one</w:t></w:r></w:p>' +
          '<w:p><w:r><w:t>two</w:t></w:r></w:p>' +
          '<w:p><w:r><w:t>three</w:t></w:r></w:p>',
      }),
    );
    const inner = outputXml.slice(
      outputXml.indexOf('<w:sdtContent>'),
      outputXml.indexOf('</w:sdtContent>'),
    );
    // v2 collapsed three paragraphs to one and moved a signature block 164pt.
    expect((inner.match(/<w:p>/g) ?? []).length).toBe(3);
    expect([inner.includes('one'), inner.includes('two'), inner.includes('three')])
      .toEqual([false, false, false]);
  });

  it('a NAMESPACE declared on the content paragraph survives — nothing is rewritten', async () => {
    const { outputXml, rendered } = await renderAllNull(
      `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>` +
        `<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">` +
        `<w:body><w:sdt><w:sdtPr><w:id w:val="981"/>` +
        `<w:alias w:val="Anticoagulation"/><w:text/></w:sdtPr><w:sdtContent>` +
        `<w:p xmlns:zz="urn:example:zz"><w:pPr><w:jc w:val="center"/></w:pPr>` +
        `<w:r><w:t>Enter anticoagulation</w:t></w:r></w:p>` +
        `</w:sdtContent></w:sdt></w:body></w:document>`,
    );
    // v2 re-emitted a bare `<w:p>`, dropping the declaration and producing a
    // part that failed namespace parsing and that LibreOffice refused with 400.
    expect(outputXml.includes('xmlns:zz')).toBe(true);
    expect(rendered.verification.verified).toBe(true);
  });

  it('OMML is deleted — the named counterexample to "delete the runs"', async () => {
    // `m:oMath` prints mathematics and is not a `w:r`. A delete-the-runs rule
    // leaves an equation standing in a field proofed blank; a keep-list does
    // not, because OMML is simply not skeleton.
    const { sourceXml, outputXml, bodyProofs } = await renderAllNull(
      sdtDoc({
        block: true,
        content:
          '<w:p><m:oMathPara xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math">' +
          '<m:oMath><m:r><m:t>INR 3.5</m:t></m:r></m:oMath></m:oMathPara>' +
          '<w:r><w:t>Enter anticoagulation</w:t></w:r></w:p>',
      }),
    );
    expect(sourceXml.includes('m:oMath')).toBe(true);
    expect([outputXml.includes('m:oMath'), outputXml.includes('INR 3.5')]).toEqual([false, false]);
    expect(bodyProofs[0]?.kind).toBe('emptied');
  });

  it('w:fldSimple is deleted — an empty simple field can be RECOMPUTED', async () => {
    // Leaving the wrapper behind is not inert: the PDF engine may recompute it
    // from `w:instr` and print a value nobody wrote.
    const { sourceXml, outputXml } = await renderAllNull(
      sdtDoc({
        content:
          '<w:fldSimple w:instr=" DOCPROPERTY Patient "><w:r><w:t>J. DOE</w:t></w:r></w:fldSimple>' +
          '<w:r><w:t>Enter anticoagulation</w:t></w:r>',
      }),
    );
    expect(sourceXml.includes('w:fldSimple')).toBe(true);
    expect([outputXml.includes('w:fldSimple'), outputXml.includes('DOCPROPERTY')])
      .toEqual([false, false]);
  });

  it('bare CHARACTER DATA inside the control REFUSES THE RENDER — base parity', async () => {
    // A walk cannot see raw text, and an element count reads it as "already
    // empty" — v2 measured a control holding this earning a `blank` proof while
    // printing, turning a refusal into a false blank: fail-closed -> fail-open.
    //
    // v3 refuses the shape, which falls back to text patching, which finds no
    // `w:t` and aborts. ⚠️ THAT IS EXACTLY WHAT `6220e0ea` DID — measured,
    // BINDING_NOT_FOUND — so this restores base behaviour rather than inventing
    // a new refusal. The input is schema-invalid; Word will not author it.
    const documentXml =
      `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>` +
      `<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">` +
      `<w:body><w:p><w:sdt><w:sdtPr><w:id w:val="982"/>` +
      `<w:alias w:val="Anticoagulation"/><w:text/></w:sdtPr>` +
      `<w:sdtContent>WARFARIN 5 MG DAILY</w:sdtContent></w:sdt></w:p></w:body></w:document>`;
    let code = 'NO THROW';
    try {
      await renderAllNull(documentXml);
    } catch (error) {
      code = (error as { code?: string }).code ?? String(error);
    }
    // ⚠️ ASSERTED BY NAME. "It threw" would be satisfied by any of the
    // renderer's other refusals, several of which this fixture could plausibly
    // trip — and the point is that the field is never CLAIMED empty.
    expect(code).toBe('BINDING_NOT_FOUND');
  });
});

// ============================================================================
// #167 — the five defects the v3 pass found IN v3, all measured before fixing.
// ============================================================================
describe('#167 — structure the clear must not destroy', () => {
  const cellDoc = (inner: string, trExtra = '') =>
    `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>` +
    `<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" ` +
    `xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006" ` +
    `xmlns:w14="http://schemas.microsoft.com/office/word/2010/wordml"><w:body>` +
    `<w:sdt><w:sdtPr><w:id w:val="991"/><w:alias w:val="Findings"/><w:text/></w:sdtPr>` +
    `<w:sdtContent><w:tbl><w:tblPr><w:tblBorders><w:top w:val="single"/></w:tblBorders></w:tblPr>` +
    `<w:tblGrid><w:gridCol w:w="2000"/></w:tblGrid><w:tr>${trExtra}` +
    `<w:tc><w:tcPr><w:tcW w:w="2000" w:type="dxa"/></w:tcPr>${inner}</w:tc></w:tr>` +
    `</w:tbl></w:sdtContent></w:sdt></w:body></w:document>`;

  it('a block-level mc:AlternateContent is RECURSED — the cell keeps a paragraph', async () => {
    // Deleting the wrapper whole took the cell's ONLY paragraph with it and left
    // `<w:tc><w:tcPr/></w:tc>` — `CT_Tc` requires a block-level child, so that is
    // the "Word found unreadable content" shape. Measured before the fix.
    const { outputXml } = await renderAllNull(
      cellDoc(
        '<mc:AlternateContent><mc:Choice Requires="w14">' +
          '<w:p><w:r><w:t>PSV 340</w:t></w:r></w:p></mc:Choice></mc:AlternateContent>',
      ),
    );
    const cell = /<w:tc>[\s\S]*?<\/w:tc>/.exec(outputXml)?.[0] ?? '';
    expect(cell.includes('PSV 340')).toBe(false);
    // THE PROPERTY: the cell still holds a block-level child.
    expect(cell.includes('<w:p>')).toBe(true);
  });

  it('w:tblPrEx survives — per-row borders are properties, not content', async () => {
    const { outputXml } = await renderAllNull(
      cellDoc(
        '<w:p><w:r><w:t>PSV 340</w:t></w:r></w:p>',
        '<w:tblPrEx><w:tblBorders><w:top w:val="single" w:sz="8"/></w:tblBorders></w:tblPrEx>',
      ),
    );
    expect([outputXml.includes('tblPrEx'), outputXml.includes('PSV 340')]).toEqual([true, false]);
  });

  it('a NESTED control’s showingPlcHdr is removed too, not just the outer one', async () => {
    // The exception was applied only to `control.children.find(sdtPr)`, so an
    // inner control kept its flag AND its docPart inside a span proofed
    // `emptied` — the same hazard, one level down, with blank credit attached.
    const { outputXml, bodyProofs } = await renderAllNull(
      `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>` +
        `<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">` +
        `<w:body><w:p><w:sdt><w:sdtPr><w:id w:val="992"/><w:alias w:val="Outer"/><w:text/></w:sdtPr>` +
        // ⚠️ THE INNER CONTROL IS A QUICK-PARTS GALLERY, DELIBERATELY. A nested
        // control the compiler BINDS as its own field makes both fields patch
        // the same span and the render throws PATCH_OVERLAP — pre-existing,
        // identical at `6220e0ea`, and not what this arm is about. A
        // `w:docPartObj` control is not bound, so it is carried as structure and
        // its placeholder flag is the thing under test.
        `<w:sdtContent><w:sdt><w:sdtPr><w:showingPlcHdr/><w:id w:val="993"/>` +
        `<w:alias w:val="Inner"/><w:placeholder><w:docPart w:val="WARFARIN_DEFAULT"/></w:placeholder>` +
        `<w:docPartObj><w:docPartGallery w:val="Quick Parts"/></w:docPartObj>` +
        `</w:sdtPr><w:sdtContent><w:r><w:t>inner text</w:t></w:r></w:sdtContent></w:sdt>` +
        `</w:sdtContent></w:sdt></w:p></w:body></w:document>`,
    );
    expect([outputXml.includes('showingPlcHdr'), outputXml.includes('inner text')])
      .toEqual([false, false]);
    expect(bodyProofs[0]?.kind).toBe('emptied');
  });

  it('showingPlcHdr goes even when the content was ALREADY pure skeleton', async () => {
    // Gating the removal on "something else was deleted" left the flag set on a
    // control whose content held only a `w:p` — a regression against the
    // previous commit, which removed it there.
    const { outputXml } = await renderAllNull(
      sdtDoc({ block: true, content: '<w:p><w:pPr><w:jc w:val="center"/></w:pPr></w:p>' })
        .replace('<w:sdtPr>', '<w:sdtPr><w:showingPlcHdr/>'),
    );
    expect(outputXml.includes('showingPlcHdr')).toBe(false);
  });

  it('an XML COMMENT does not silently disarm the clear', async () => {
    // The character-data refusal is a whole-control veto, and `scanXmlPart`
    // skips comments without registering a child — so their raw bytes landed in
    // the sibling gap and one comment anywhere below the control turned the fix
    // OFF, degrading to pre-fix behaviour with no warning and no distinguishable
    // proof.
    const { outputXml, bodyProofs } = await renderAllNull(
      sdtDoc({
        content: '<!-- a Word comment --><w:r><w:t>Enter anticoagulation</w:t></w:r>',
      }),
    );
    expect(outputXml.includes('Enter anticoagulation')).toBe(false);
    expect(bodyProofs[0]?.kind).toBe('emptied');
  });

  it('a tracked-change INSERTED PARAGRAPH survives as structure', async () => {
    // `w:ins`/`w:del` hold RUNS inline and PARAGRAPHS at block level. Deleting
    // them whole removed a tracked-inserted paragraph entirely; recursing gets
    // both right — the runs go as content, the paragraph stays as structure.
    const { outputXml } = await renderAllNull(
      sdtDoc({
        block: true,
        content:
          '<w:ins w:id="5" w:author="Dr"><w:p><w:r><w:t>inserted finding</w:t></w:r></w:p></w:ins>',
      }),
    );
    expect([outputXml.includes('inserted finding'), outputXml.includes('<w:p>')])
      .toEqual([false, true]);
  });
});

describe('#167 — the two shapes the pass left unarmed', () => {
  it('CHARACTER DATA INTERLEAVED with elements refuses — the guard nothing watched', async () => {
    // ⚠️ THE GUARD WAS LOAD-BEARING AND UNARMED: disabling the sibling-gap check
    // redded 0 of 5610 tests, while the shape it stops restores #164 exactly —
    // measured, `emptied` with the drug name still printing. The existing
    // character-data arm covers only the NO-CHILDREN case, caught by a
    // different (trailing) check.
    const documentXml =
      `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>` +
      `<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">` +
      `<w:body><w:p><w:sdt><w:sdtPr><w:id w:val="994"/>` +
      `<w:alias w:val="Anticoagulation"/><w:text/></w:sdtPr>` +
      `<w:sdtContent>WARFARIN 5 MG DAILY<w:r><w:t>prompt</w:t></w:r></w:sdtContent>` +
      `</w:sdt></w:p></w:body></w:document>`;
    const { outputXml, bodyProofs } = await renderAllNull(documentXml);
    // It still prints — the fallback only blanks `w:t` — but it must NEVER be
    // claimed empty, which is the whole difference.
    expect(outputXml.includes('WARFARIN')).toBe(true);
    expect(bodyProofs.map((p) => p.kind)).not.toContain('emptied');
  });

  it('a RUN smuggled into w:pPr refuses — a property container may not hold one', async () => {
    // ⚠️ CANON 86's CORRECTION, CONFIRMED LIVE AND PREVIOUSLY UNARMED. The
    // keep-list is a claim about the FORMAT; the code copies subtrees verbatim
    // and nothing validates them. Measured: the run survives, prints, and the
    // field is proofed `emptied` with blank credit — #164's shape one layer
    // inside the fix for it.
    const { outputXml, bodyProofs } = await renderAllNull(
      sdtDoc({
        block: true,
        content:
          '<w:p><w:pPr><w:jc w:val="center"/>' +
          '<w:r><w:t>WARFARIN 5 MG DAILY</w:t></w:r></w:pPr>' +
          '<w:r><w:t>Enter anticoagulation</w:t></w:r></w:p>',
      }),
    );
    // ⚠️ THE ESSENTIAL PROPERTY IS THE LABEL, NOT THE TEXT. The refusal falls
    // back to text patching, which happens to blank this run's `w:t` as well —
    // better than required, and NOT what the arm rests on, because that
    // fallback cannot reach a non-`w:t` carrier smuggled the same way.
    expect(bodyProofs.map((p) => p.kind)).not.toContain('emptied');
    expect(outputXml.includes('WARFARIN')).toBe(false);
  });

  it('and a NON-w:t carrier in w:pPr is refused too — where the fallback cannot help', async () => {
    // The sibling arm's fallback blanks `w:t`. This one cannot be rescued that
    // way, so it isolates the refusal itself: a `w:sym` inside `w:pPr` survives
    // whatever we do, and the only correct outcome is to refuse the blank claim.
    const { outputXml, bodyProofs } = await renderAllNull(
      sdtDoc({
        block: true,
        content:
          '<w:p><w:pPr><w:jc w:val="center"/>' +
          '<w:r><w:sym w:font="Wingdings" w:char="F0FE"/></w:r></w:pPr>' +
          '<w:r><w:t>Enter anticoagulation</w:t></w:r></w:p>',
      }),
    );
    expect(outputXml.includes('w:sym')).toBe(true);
    expect(bodyProofs.map((p) => p.kind)).not.toContain('emptied');
  });
});

// ============================================================================
// #168 — FAIL-CLOSED ON THE COUNT, NOT ON THE RENDER.
// ----------------------------------------------------------------------------
// Two kept-list members can still put something on the page. Neither is removed
// — removing either damages the doctor's document BEYOND the field — so the
// clear still happens and the field simply cannot CLAIM blank.
// ============================================================================
describe('#168 — a cleared region that can still render buys no blank credit', () => {
  it('NUMBERING survives and the field cannot claim blank', async () => {
    // `w:numPr` rides inside the kept-whole `w:pPr` and drives a marker from
    // `numbering.xml`. Measured: with `lvlText="ANTICOAGULATED %1."` the
    // exported PDF printed `ANTICOAGULATED 1.` for a field proofed `emptied` —
    // arbitrary template-authored text, not a bullet.
    //
    // ⚠️ NO PARSING OF `lvlText`, AND THAT IS THE POINT: the rule cannot be
    // wrong about which markers are "just" markers, because it never looks.
    const { outputXml, bodyProofs } = await renderAllNull(
      sdtDoc({
        block: true,
        content:
          '<w:p><w:pPr><w:numPr><w:ilvl w:val="0"/><w:numId w:val="7"/></w:numPr></w:pPr>' +
          '<w:r><w:t>Enter anticoagulation</w:t></w:r></w:p>',
      }),
    );
    // The numbering STAYS — removing it renumbers the doctor's list beyond
    // this field, which is damage outside the thing being cleared.
    expect(outputXml.includes('w:numPr')).toBe(true);
    expect(outputXml.includes('Enter anticoagulation')).toBe(false);
    expect(bodyProofs.map((p) => p.kind)).not.toContain('emptied');
  });

  it('a SELECTION clears but earns no blank credit — #165 reversed on measurement', async () => {
    // #165 included selections because they clear identically in the XML —
    // true, and the wrong axis. Measured on the real template: an emptied
    // dropdown makes the PDF engine fall back to `w:listItem[0]`, so
    // "Choose an item." prints while the field buys blank credit. Base prints
    // it too, so this is not a new visual — it is a TRUE statement turned into
    // a FALSE ATTESTATION, which is worse.
    const { outputXml, bodyProofs } = await renderAllNull(
      `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>` +
        `<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">` +
        `<w:body><w:p><w:sdt><w:sdtPr><w:id w:val="995"/><w:alias w:val="Exam side"/>` +
        `<w:dropDownList><w:listItem w:displayText="Choose an item." w:value="X"/>` +
        `<w:listItem w:displayText="Left" w:value="L"/></w:dropDownList></w:sdtPr>` +
        `<w:sdtContent><w:r><w:t>Choose an item.</w:t></w:r></w:sdtContent>` +
        `</w:sdt></w:p></w:body></w:document>`,
    );
    // It IS still cleared — that is what stops a previously SELECTED value
    // printing, and it is why the exclusion is on the COUNT and not the render.
    const inner = outputXml.slice(
      outputXml.indexOf('<w:sdtContent>'),
      outputXml.indexOf('</w:sdtContent>'),
    );
    expect(inner.includes('Choose an item.')).toBe(false);
    // NON-VACUITY: the list definition survives — that is what the engine falls
    // back to, and the reason this may not buy blank credit.
    expect(outputXml.includes('w:listItem')).toBe(true);
    expect(bodyProofs.map((p) => p.kind)).not.toContain('emptied');
  });
});

describe('#168(a) — numbering OUTSIDE the control disqualifies it too', () => {
  it('an INLINE control under a numbered paragraph cannot claim blank', async () => {
    // ⚠️ THE GUARD WAS SCOPED TO THE CONTROL'S INSIDE AND WAS EVADED BY ONE
    // NESTING LEVEL. For an inline control the numbering sits on the `w:pPr` of
    // the paragraph HOLDING it. Measured: two documents printing the identical
    // line — "ANTICOAGULATED 1." — got opposite verdicts, the outside one
    // earning `emptied` AND blank credit.
    //
    // Live on the real template: 4 of its 133 paragraphs carry both `w:numPr`
    // and an inline `w:sdt`, masked only because those controls are dropdowns.
    const { outputXml, bodyProofs } = await renderAllNull(
      `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>` +
        `<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">` +
        `<w:body><w:p>` +
        `<w:pPr><w:numPr><w:ilvl w:val="0"/><w:numId w:val="7"/></w:numPr></w:pPr>` +
        `<w:sdt><w:sdtPr><w:id w:val="996"/><w:alias w:val="Anticoagulation"/><w:text/></w:sdtPr>` +
        `<w:sdtContent><w:r><w:t>Enter anticoagulation</w:t></w:r></w:sdtContent></w:sdt>` +
        `</w:p></w:body></w:document>`,
    );
    // The numbering stays, the content clears — and the field cannot claim blank.
    expect(outputXml.includes('w:numPr')).toBe(true);
    expect(outputXml.includes('Enter anticoagulation')).toBe(false);
    expect(bodyProofs.map((p) => p.kind)).not.toContain('emptied');
  });

  it('a control with NO numbering anywhere still earns its blank credit', async () => {
    // NON-VACUITY for the arm above: the widened search must not disqualify
    // every field. Without this, "not emptied" could be true for any reason.
    const { bodyProofs } = await renderAllNull(
      sdtDoc({ content: '<w:r><w:t>Enter anticoagulation</w:t></w:r>' }),
    );
    expect(bodyProofs.map((p) => p.kind)).toContain('emptied');
  });
});


// ============================================================================
// #170 — THE INERT ALLOWLIST, THE ROUTING, AND THE THREE-STATE SENTINEL.
// ----------------------------------------------------------------------------
// The previous pass found that the guard was consulted by ONE of the three
// bindings that can earn blank credit, and that on the only real customer
// template that binding supplies NONE of it. These arms watch the fix from both
// ends: the bindings that never asked now ask, and a verdict that was never
// computed can no longer masquerade as approval.
// ============================================================================

/**
 * An inline control in a paragraph whose `w:pPr` is exactly `inner`.
 *
 * ⚠️ THE CONTENT IS AN EMPTY RUN SHELL ON PURPOSE, AND THE FIRST DRAFT OF THESE
 * ARMS GOT IT WRONG. With real text inside, an INELIGIBLE control is still
 * cleared, so its proof is `filled` — and `filled` carries no eligibility at
 * all, so every assertion read `undefined` and told us nothing about the guard.
 * An already-skeleton control needs no patch, takes the zero-patch `blank`
 * path, and therefore carries the sentinel EXPLICITLY, which is the thing these
 * arms exist to watch.
 */
const pPrDoc = (inner: string) =>
  `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>` +
  `<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" ` +
  `xmlns:w14="http://schemas.microsoft.com/office/word/2010/wordml">` +
  `<w:body><w:p><w:pPr>${inner}</w:pPr>` +
  `<w:sdt><w:sdtPr><w:id w:val="770"/><w:alias w:val="Impression"/><w:text/></w:sdtPr>` +
  `<w:sdtContent><w:r><w:rPr><w:b/></w:rPr></w:r></w:sdtContent></w:sdt>` +
  `</w:p></w:body></w:document>`;

const stylesWith = (inner: string) =>
  `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>` +
  `<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">` +
  inner + `</w:styles>`;

describe('#170 — the inert allowlist over w:pPr', () => {
  it('the MEASURED inert set is eligible — all seven, exactly as the real template writes them', async () => {
    // ⚠️ THE POSITIVE CONTROL FOR EVERY REFUSAL BELOW. These are the seven
    // direct `w:pPr` children measured on the 52 blank-bearing cells of
    // `WM IOV Template.docx`. If this arm ever reds, the allowlist has stopped
    // matching the artifact it was derived from and 52 real blank credits have
    // silently gone with it.
    const { bodyProofs } = await renderAllNull(
      pPrDoc(
        '<w:widowControl/><w:tabs><w:tab w:val="left" w:pos="720"/></w:tabs>' +
          '<w:autoSpaceDE/><w:autoSpaceDN/><w:adjustRightInd/><w:jc w:val="left"/>' +
          '<w:rPr><w:rFonts w:ascii="Arial"/><w:b/><w:bCs/><w:color w:val="000000"/>' +
          '<w:kern w:val="0"/><w:sz w:val="20"/><w:szCs w:val="20"/>' +
          '<w14:ligatures w14:val="none"/></w:rPr>',
      ),
    );
    expect(bodyProofs[0]?.blankEligible).toBe('eligible');
    expect(bodyProofs[0]?.kind).toBe('blank');
  });

  it('⚠️ AN UNKNOWN pPr CHILD IS INELIGIBLE — an INVENTED element name proves it', async () => {
    // ⚠️ THE ELEMENT IS DELIBERATELY FICTIONAL. Using a real-but-unlisted
    // property (`w:spacing`, say) would leave the arm ambiguous the day
    // somebody argues that property onto the list. `w:zzzNotARealProperty`
    // can never be argued onto it, so this arm tests the RULE — unknown means
    // refuse — rather than one property's membership.
    //
    // This is the whole safety property of #170: the guard does not need to
    // know what a child DOES, only that it was not measured to be inert.
    const { bodyProofs, bindingOf, kindOf } = await renderAllNull(
      pPrDoc('<w:zzzNotARealProperty w:val="1"/>'),
    );
    expect(bodyProofs[0]?.blankEligible).toBe('ineligible');
    // AND THE OUTCOME, not only the flag: the census must actually refuse it.
    expect(
      countsAsBlankProof(bodyProofs[0] as never, {
        bindingOf,
        resolvedNull: () => true,
        kindOf,
      }),
    ).toBe(false);
  });

  it('a run hiding inside w:pPr is refused even though every child name is inert', async () => {
    // The structural backstop that does not depend on the list being right:
    // `w:r` is the universal carrier of printable content and no property block
    // legitimately holds one.
    const { bodyProofs } = await renderAllNull(
      pPrDoc('<w:rPr><w:r><w:t>ANTICOAGULATED</w:t></w:r></w:rPr>'),
    );
    expect(bodyProofs[0]?.blankEligible).toBe('ineligible');
  });

  it('no w:pPr at all is eligible — the shape the owner’s form uses on all 35', async () => {
    const { bodyProofs } = await renderAllNull(
      `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>` +
        `<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">` +
        `<w:body><w:p><w:sdt><w:sdtPr><w:id w:val="771"/><w:alias w:val="Impression"/>` +
        `<w:text/></w:sdtPr><w:sdtContent><w:r><w:t>Enter impression</w:t></w:r>` +
        `</w:sdtContent></w:sdt></w:p></w:body></w:document>`,
    );
    expect(bodyProofs[0]?.blankEligible).toBe('eligible');
  });
});

describe('#170 — the ONE surviving resolution: the inherited default', () => {
  const plainDoc = pPrDoc('<w:jc w:val="left"/>');

  it('⚠️ w:default is ST_OnOff — "1", "true" and "on" ALL disqualify', async () => {
    // ⚠️ THIS IS NOT A MISSED ROUTE, IT IS A RATIFIED ROUTE RE-OPENED BY A
    // RESPELLING. The old code compared the literal `"1"`, so a numbered
    // default style written `w:default="true"` — which `ST_OnOff` explicitly
    // permits (ECMA-376 §22.9.2.7) — granted credit over live numbering.
    for (const spelling of ['1', 'true', 'on', 'TRUE', 'On']) {
      const { bodyProofs } = await renderAllNull(
        plainDoc,
        stylesWith(
          `<w:style w:type="paragraph" w:default="${spelling}" w:styleId="Normal">` +
            `<w:pPr><w:numPr><w:numId w:val="7"/></w:numPr></w:pPr></w:style>`,
        ),
      );
      expect(bodyProofs[0]?.blankEligible, `w:default="${spelling}" granted credit`).toBe(
        'ineligible',
      );
    }
  });

  it('⚠️ an OMITTED or oddly-cased w:type is still a candidate default', async () => {
    // Requiring `w:type === "paragraph"` exactly meant omitting the attribute
    // walked straight past a numbered default. Fail-closed means an unstated
    // type is a type that MIGHT apply.
    for (const attr of ['', ' w:type="Paragraph"', ' w:type="paragraph"']) {
      const { bodyProofs } = await renderAllNull(
        plainDoc,
        stylesWith(
          `<w:style${attr} w:default="1" w:styleId="Normal">` +
            `<w:pPr><w:numPr><w:numId w:val="7"/></w:numPr></w:pPr></w:style>`,
        ),
      );
      expect(bodyProofs[0]?.blankEligible, `w:type "${attr}" granted credit`).toBe(
        'ineligible',
      );
    }
    // ⚠️ #171 R4 — THE NON-VACUITY CONTROL CHANGED WITH THE RULE, AND THE OLD
    // ONE IS KEPT BELOW AS THE REVERSAL IT IS. It used to assert that a
    // NON-paragraph default does not disqualify. That filter was one-sided in
    // the opposite direction from the ST_OnOff widening two lines above it: a
    // `w:type="table"` default carrying `w:pPr/w:numPr` applies to paragraphs
    // in cells of tables naming no style, and was skipped. There is no type
    // filter now — ANY default carrying numbering disqualifies.
    const { bodyProofs: tableDefault } = await renderAllNull(
      plainDoc,
      stylesWith(
        `<w:style w:type="table" w:default="1" w:styleId="TableGrid">` +
          `<w:pPr><w:numPr><w:numId w:val="7"/></w:numPr></w:pPr></w:style>`,
      ),
    );
    expect(tableDefault[0]?.blankEligible, 'a default TABLE style was skipped').toBe(
      'ineligible',
    );
    // NON-VACUITY, RE-AIMED: a default style carrying NO numbering must still
    // grant credit, or the arm above would pass with the guard refusing
    // everything — which is the other way to be wrong.
    const { bodyProofs } = await renderAllNull(
      plainDoc,
      stylesWith(`<w:style w:type="paragraph" w:default="1" w:styleId="Normal"/>`),
    );
    expect(bodyProofs[0]?.blankEligible).toBe('eligible');
  });

  it('⚠️ #171 R1 — a DEFAULT style carrying w:basedOn is UNRESOLVED, and we do not walk it', async () => {
    // ⚠️ #170 DELETED THE `w:pStyle` CHAIN WALK AND LEFT THE DEFAULT STYLE'S
    // CHAIN LIVE. The pass measured `Normal basedOn <numbered>` returning
    // `emptied` + eligible + COUNTED over live numbering, on a paragraph with no
    // `w:pPr` at all — the shape `paragraphIsInert` calls the cleanest possible
    // answer.
    //
    // The fix is a REFUSAL, not a walk: walking here would reinstate exactly the
    // surface #170 deleted, one level up. #171 permits refusing-instead-of-
    // walking as a fix class precisely so this cannot become a chain resolver.
    const numbered = await renderAllNull(
      plainDoc,
      stylesWith(
        `<w:style w:type="paragraph" w:default="1" w:styleId="Normal">` +
          `<w:basedOn w:val="ListPara"/></w:style>` +
          `<w:style w:type="paragraph" w:styleId="ListPara">` +
          `<w:pPr><w:numPr><w:numId w:val="7"/></w:numPr></w:pPr></w:style>`,
      ),
    );
    expect(
      numbered.bodyProofs[0]?.blankEligible,
      'a default style inheriting numbering bought credit',
    ).toBe('ineligible');

    // ⚠️ AND THE ACCEPTED COST, ARMED SO IT CANNOT BE QUIETLY "FIXED" BY A WALK.
    // A default style based on a perfectly innocent one is ALSO ineligible: the
    // rule refuses what it cannot resolve without walking, and a future reader
    // who repairs this by resolving the parent has reinstated the surface.
    //
    // COST MEASURED BEFORE RULING: `WM IOV Template.docx`'s `Normal` carries no
    // `basedOn`, and Word's built-in `Normal` is the root of the chain by
    // construction — zero on both real artifacts.
    const innocent = await renderAllNull(
      plainDoc,
      stylesWith(
        `<w:style w:type="paragraph" w:default="1" w:styleId="Normal">` +
          `<w:basedOn w:val="Body"/></w:style>` +
          `<w:style w:type="paragraph" w:styleId="Body"><w:name w:val="Body"/></w:style>`,
      ),
    );
    expect(innocent.bodyProofs[0]?.blankEligible).toBe('ineligible');

    // NON-VACUITY: the SAME default style WITHOUT `basedOn` still grants credit,
    // so the two arms above measure the attribute and not the fixture.
    const control = await renderAllNull(
      plainDoc,
      stylesWith(`<w:style w:type="paragraph" w:default="1" w:styleId="Normal"/>`),
    );
    expect(control.bodyProofs[0]?.blankEligible).toBe('eligible');
  });

  it('⚠️ w:docDefaults/w:pPrDefault numbering disqualifies — no style names it', async () => {
    // The seventh route. It is invisible to every style-id lookup because no
    // style is involved: numbering is set for the whole document at the
    // defaults level, and a paragraph naming no style inherits it.
    const { bodyProofs } = await renderAllNull(
      plainDoc,
      stylesWith(
        `<w:docDefaults><w:pPrDefault><w:pPr>` +
          `<w:numPr><w:ilvl w:val="0"/><w:numId w:val="7"/></w:numPr>` +
          `</w:pPr></w:pPrDefault></w:docDefaults>` +
          `<w:style w:type="paragraph" w:default="1" w:styleId="Normal"/>`,
      ),
    );
    expect(bodyProofs[0]?.blankEligible).toBe('ineligible');
  });

  it('⚠️ duplicate defaults do NOT resolve last-wins — ANY numbered default disqualifies', async () => {
    // The old scanner overwrote `defaultId` as it went, so the verdict depended
    // on DOCUMENT ORDER alone and granted credit in half the orderings.
    const numbered =
      `<w:style w:type="paragraph" w:default="1" w:styleId="A">` +
      `<w:pPr><w:numPr><w:numId w:val="7"/></w:numPr></w:pPr></w:style>`;
    const clear = `<w:style w:type="paragraph" w:default="1" w:styleId="B"/>`;
    for (const [label, xml] of [
      ['numbered FIRST', numbered + clear],
      ['numbered LAST', clear + numbered],
    ] as const) {
      const { bodyProofs } = await renderAllNull(plainDoc, stylesWith(xml));
      expect(bodyProofs[0]?.blankEligible, label).toBe('ineligible');
    }
  });

  it('⚠️ an ABSENT styles.xml is INELIGIBLE — the branch nobody could reach before', async () => {
    // ⚠️ THE UNDISCLOSED HALF. The previous arm disclosed that an UNPARSEABLE
    // styles.xml is refused one layer earlier by package inspection, and
    // honestly said the `catch` had no demonstrated caller. It never mentioned
    // the ABSENT case — and the fixture builder wrote the part unconditionally,
    // so no arm in this file could reach it. It is reachable now.
    // ⚠️ THE CONTENT-TYPES DECLARATION GOES WITH THE PART. Removing the part
    // alone leaves `[Content_Types].xml` declaring an override for a file that
    // is not there, and the package layer correctly rejects THAT instead —
    // which would have made this arm pass for the wrong reason.
    const source = await buildSyntheticDocx({
      documentXml: plainDoc,
      contentTypes: syntheticOpc.contentTypes.replace(
        /\s*<Override PartName="\/word\/styles\.xml"[^>]*\/>/,
        '',
      ),
      // ⚠️ AND THE RELATIONSHIP TOO — THREE DECLARATIONS POINT AT ONE PART.
      // A `.docx` names `word/styles.xml` in the content types, in
      // `document.xml.rels`, AND by its presence in the zip. Each omission the
      // package layer catches first would have made this arm green for a reason
      // that has nothing to do with the guard.
      documentRelationships: syntheticOpc.documentRelationships.replace(
        /\s*<Relationship Id="rIdStyles"[^>]*\/>/,
        '',
      ),
      omitEntries: ['word/styles.xml'],
    });
    const { compileTemplateDocx } = await import('../compiler');
    const ir = compileTemplateDocx(source);
    const rendered = await renderTemplateDocx({
      source,
      ir,
      resolutions: ir.fields.map((field) =>
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
      ),
      validation: VALIDATION,
    });
    const body = rendered.verification.fields.filter(
      (p) => p.partName === 'word/document.xml',
    );
    expect(body.length).toBeGreaterThan(0);
    for (const proof of body) {
      expect(
        (proof as { blankEligible?: string }).blankEligible,
        'an unresolvable style table granted credit',
      ).toBe('ineligible');
    }
  });
});

describe('#171 — the quantifier and the third state, OBSERVED leaving the renderer', () => {
  // ⚠️ BOTH ARMS EXIST BECAUSE A MUTATION MATRIX OF TEN FOUND NOTHING AND A
  // SECOND MATRIX FOUND THESE. Mine tested the fixes wholesale; these are the
  // quantifier and the never-observed-value shapes, which is what actually
  // ships. Neither property had an arm, and both are load-bearing claims made
  // in this file's own comments.

  it('⚠️ EVERY paragraph in scope is asked — a two-paragraph control with ONE numbered', async () => {
    // ⚠️ THE ALL-QUANTIFIER HAD NO ARM. Replacing `every` with
    // `length === 0 || some` redded 0 of 757, because — instrumented — 2 171 of
    // 2 174 calls in the whole suite had exactly ONE paragraph in scope. A
    // universal claim tested only on singletons is not tested.
    //
    // This fixture is the smallest thing that distinguishes them: a block-level
    // control holding two paragraphs, the FIRST inert and the SECOND numbered.
    // Under `some`, the first paragraph alone would grant credit.
    const { bodyProofs } = await renderAllNull(
      sdtDoc({
        block: true,
        content:
          '<w:p><w:pPr><w:jc w:val="left"/></w:pPr><w:r><w:rPr><w:b/></w:rPr></w:r></w:p>' +
          '<w:p><w:pPr><w:numPr><w:ilvl w:val="0"/><w:numId w:val="7"/></w:numPr></w:pPr>' +
          '<w:r><w:rPr><w:b/></w:rPr></w:r></w:p>',
      }),
    );
    expect(bodyProofs[0]?.blankEligible, 'a numbered SECOND paragraph bought credit').toBe(
      'ineligible',
    );
  });

  it('⚠️ `unevaluated` is OBSERVED coming out of the renderer, and does not count', async () => {
    // ⚠️ THE THIRD STATE HAD NEVER BEEN SEEN. Instrumented across all 62 files:
    // 1 160 `eligible`, 20 `ineligible`, ZERO `unevaluated` — and flipping all
    // five `'unevaluated'` literals to `'eligible'` redded 0 of 757. The only
    // arm naming the value fed hand-built objects to the READ path, which says
    // nothing about the WRITE path ever producing one.
    //
    // A block-level control whose content is already empty gives the guard an
    // EMPTY paragraph set. `[].every(...)` is `true`, so that used to yield
    // `eligible` — a guard that examined nothing reporting approval, the exact
    // defect the third state exists to abolish, one layer inside the fix.
    const { bodyProofs, bindingOf, kindOf } = await renderAllNull(
      sdtDoc({ block: true, content: '' }),
    );
    expect(bodyProofs.length, 'fixture produced no body proof').toBeGreaterThan(0);
    expect(bodyProofs[0]?.blankEligible).toBe('unevaluated');
    // AND THE OUTCOME: an unevaluated verdict must not buy credit.
    expect(
      countsAsBlankProof(bodyProofs[0] as never, {
        bindingOf,
        resolvedNull: () => true,
        kindOf,
      }),
    ).toBe(false);
  });
});

describe('#171 — table_cell and legacy LEFT THE SLICE, and the limit is pinned', () => {
  // ⚠️ THIS BLOCK PINS AN ACCEPTED LIMIT, NOT A GUARANTEE, AND SAYS SO LOUDLY.
  //
  // #170 routed these two bindings through the paragraph guard. The pass then
  // showed the guard was answering the wrong question for them: NOTHING CLEARS
  // a cell or a legacy result — `tableCellPatches` and `legacyFieldPatches`
  // rewrite `w:t` only — so "could a list marker print?" is beside the point
  // when the region may still hold a glyph, a drawing or a picture untouched.
  // And legacy's guard judged the paragraph holding `begin`, one paragraph of a
  // span this codebase says cannot be bounded by walking.
  //
  // #171 deletes that guard code rather than improving it. Both bindings keep
  // `main`'s behaviour verbatim — the unpatched `blank` path, no `emptied`, no
  // NEW credit — and the `eligible ≠ empty` limit, which PREDATES this arc, is
  // filed with its cure named (`w:tc` is a bounded container, so structure-keep
  // applies to it later).
  //
  // ⚠️ THE ARMS BELOW ASSERT THE LIMIT ITSELF. That is deliberate: a limit
  // recorded only in prose decays, and one recorded in a test reds the day
  // somebody changes it in either direction — closing it (good, and it should
  // come with its own slice) or widening it (bad, and nothing else would say).

  const NUM = '<w:pPr><w:numPr><w:ilvl w:val="0"/><w:numId w:val="7"/></w:numPr></w:pPr>';
  const tableDoc = (cellPPr: string) =>
    `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>` +
    `<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">` +
    `<w:body><w:tbl><w:tblGrid><w:gridCol w:w="2800"/><w:gridCol w:w="4200"/></w:tblGrid>` +
    `<w:tr>` +
    `<w:tc><w:p><w:r><w:t>Anticoagulation</w:t></w:r></w:p></w:tc>` +
    `<w:tc><w:p>${cellPPr}</w:p></w:tc>` +
    `</w:tr></w:tbl></w:body></w:document>`;

  it('a TABLE CELL keeps main behaviour — it counts, numbered or not, and that is the LIMIT', async () => {
    for (const [label, doc] of [
      ['unnumbered', tableDoc('')],
      ['NUMBERED — the accepted limit', tableDoc(NUM)],
    ] as const) {
      const { bodyProofs, bindingOf, kindOf } = await renderAllNull(doc);
      const cell = bodyProofs.find((p) => bindingOf(String(p.fieldId)) === 'table_cell');
      expect(cell, 'fixture produced no table_cell field').toBeDefined();
      expect(cell?.kind, label).toBe('blank');
      expect(
        countsAsBlankProof(cell as never, { bindingOf, resolvedNull: () => true, kindOf }),
        label,
      ).toBe(true);
    }
  });

  it('a LEGACY form field likewise keeps main behaviour, numbered or not', async () => {
    const legacyDoc = (pPr: string) =>
      `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>` +
      `<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">` +
      `<w:body><w:p>${pPr}` +
      `<w:r><w:fldChar w:fldCharType="begin"><w:ffData>` +
      `<w:name w:val="Anticoagulation"/><w:enabled/><w:textInput/>` +
      `</w:ffData></w:fldChar></w:r>` +
      `<w:r><w:instrText> FORMTEXT </w:instrText></w:r>` +
      `<w:r><w:fldChar w:fldCharType="separate"/></w:r>` +
      `<w:r><w:fldChar w:fldCharType="end"/></w:r>` +
      `</w:p></w:body></w:document>`;
    for (const [label, doc] of [
      ['unnumbered', legacyDoc('')],
      ['NUMBERED — the accepted limit', legacyDoc(NUM)],
    ] as const) {
      const { bodyProofs, bindingOf, kindOf } = await renderAllNull(doc);
      const legacy = bodyProofs.find(
        (p) => bindingOf(String(p.fieldId)) === 'legacy_form_field',
      );
      expect(legacy, 'fixture produced no legacy field').toBeDefined();
      expect(
        countsAsBlankProof(legacy as never, { bindingOf, resolvedNull: () => true, kindOf }),
        label,
      ).toBe(true);
    }
  });

  it('neither binding ever earns an `emptied` proof — that half is unchanged', async () => {
    // The half that was never in question and stays pinned: no bounded clear
    // exists for either, so neither can claim the byte-verified label.
    const { bodyProofs, bindingOf } = await renderAllNull(tableDoc(''));
    for (const p of bodyProofs) {
      if (bindingOf(String(p.fieldId)) === 'table_cell') expect(p.kind).not.toBe('emptied');
    }
  });
});

describe('#170 — the DATE and SELECTION branches, each on its own merit', () => {
  it('a DATE control with NO w:fullDate, already skeleton, in a numbered paragraph', async () => {
    // ⚠️ THE SHAPE THE PREVIOUS PASS FOUND UNARMED. The existing date arm uses
    // `w:fullDate="…"`, which forces a state patch, so the zero-patch branch
    // was unreachable from it — hardcoding that branch's eligibility redded
    // nothing. With no `w:fullDate` and skeleton content there is no patch at
    // all, and the field takes the `blank` path where the credit is decided.
    const { bodyProofs, bindingOf, kindOf } = await renderAllNull(
      `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>` +
        `<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">` +
        `<w:body><w:p><w:pPr><w:numPr><w:numId w:val="7"/></w:numPr></w:pPr>` +
        `<w:sdt><w:sdtPr><w:id w:val="772"/><w:alias w:val="Procedure date"/>` +
        `<w:date><w:dateFormat w:val="yyyy-MM-dd"/></w:date></w:sdtPr>` +
        `<w:sdtContent><w:r><w:rPr><w:b/></w:rPr></w:r></w:sdtContent></w:sdt>` +
        `</w:p></w:body></w:document>`,
    );
    expect(bodyProofs[0]?.kind).toBe('blank');
    expect(bodyProofs[0]?.blankEligible).toBe('ineligible');
    expect(
      countsAsBlankProof(bodyProofs[0] as never, {
        bindingOf,
        resolvedNull: () => true,
        kindOf,
      }),
    ).toBe(false);
  });

  it('a SELECTION is ineligible on its OWN merit, not by the read-path kind check', async () => {
    // ⚠️ TWO GUARDS OVERLAP HERE AND ONLY ONE IS BEING PROVED — canon 62.
    // `countsAsBlankProof` refuses selections by KIND, so a census-level
    // assertion passes whether or not the renderer decided anything. This arm
    // reads the renderer's OWN verdict on the proof, which the kind check
    // cannot supply.
    const { bodyProofs } = await renderAllNull(
      `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>` +
        `<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">` +
        `<w:body><w:p><w:sdt><w:sdtPr><w:id w:val="773"/><w:alias w:val="Side"/>` +
        `<w:dropDownList><w:listItem w:displayText="Left" w:value="L"/>` +
        `<w:listItem w:displayText="Right" w:value="R"/></w:dropDownList></w:sdtPr>` +
        `<w:sdtContent><w:r><w:rPr><w:b/></w:rPr></w:r></w:sdtContent></w:sdt>` +
        `</w:p></w:body></w:document>`,
    );
    // The paragraph is perfectly inert, so ONLY the selection rule can refuse it.
    expect(bodyProofs[0]?.blankEligible).toBe('ineligible');
  });
});

describe('#170 — a `pStyle` is INELIGIBLE outright, and the style walk is gone', () => {
  const styledDoc = (pPrInner: string, styles: string) => ({
    documentXml:
      `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>` +
      `<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">` +
      `<w:body><w:sdt><w:sdtPr><w:id w:val="997"/><w:alias w:val="Anticoagulation"/>` +
      `<w:text/></w:sdtPr><w:sdtContent>` +
      `<w:p><w:pPr>${pPrInner}</w:pPr><w:r><w:t>Enter anticoagulation</w:t></w:r></w:p>` +
      `</w:sdtContent></w:sdt></w:body></w:document>`,
    stylesXml:
      `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>` +
      `<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">` +
      styles + `</w:styles>`,
  });

  it('numbering carried by w:pStyle disqualifies the field — the region has no w:numPr at all', async () => {
    // ⚠️ MEASURED TO PDF: the cleared region contained only
    // `<w:pStyle w:val="ListParagraph"/>`, the guard found no `w:numPr`, and the
    // field printed `ANTICOAGULATED 1.` while proofed `emptied` with blank
    // credit. The numbering lived entirely in `styles.xml`.
    const { documentXml, stylesXml } = styledDoc(
      '<w:pStyle w:val="ListParagraph"/>',
      `<w:style w:type="paragraph" w:styleId="ListParagraph"><w:pPr>` +
        `<w:numPr><w:ilvl w:val="0"/><w:numId w:val="7"/></w:numPr></w:pPr></w:style>`,
    );
    const { bodyProofs, outputXml } = await renderAllNull(documentXml, stylesXml);
    expect(outputXml.includes('Enter anticoagulation')).toBe(false);
    expect(bodyProofs.map((p) => p.kind)).not.toContain('emptied');
  });

  it('a style based on a numbered style is caught — and NOT by walking basedOn', async () => {
    // ⚠️ THIS ARM SURVIVES #170 WITH ITS MECHANISM DELETED, WHICH IS THE POINT.
    // It used to prove that `basedOn` was resolved transitively. There is no
    // transitive resolution any more: `w:pStyle` is simply not an inert
    // property, so the paragraph is ineligible without anybody looking up a
    // style id. The OUTCOME is identical and the attack surface is gone.
    const { documentXml, stylesXml } = styledDoc(
      '<w:pStyle w:val="ClinicalList"/>',
      `<w:style w:type="paragraph" w:styleId="ListParagraph"><w:pPr>` +
        `<w:numPr><w:numId w:val="7"/></w:numPr></w:pPr></w:style>` +
        `<w:style w:type="paragraph" w:styleId="ClinicalList">` +
        `<w:basedOn w:val="ListParagraph"/></w:style>`,
    );
    const { bodyProofs } = await renderAllNull(documentXml, stylesXml);
    expect(bodyProofs.map((p) => p.kind)).not.toContain('emptied');
  });

  it('⚠️ AND A `pStyle` NAMING A PERFECTLY INNOCENT STYLE IS ALSO INELIGIBLE', async () => {
    // ⚠️ THE ACCEPTED COST, ARMED SO IT CANNOT BE QUIETLY "FIXED". This style
    // carries no numbering whatsoever, and the field still earns nothing. That
    // is the deal #170 makes: one field's credit in exchange for deleting an
    // entire resolution surface that was falsified six times. A future reader
    // who "repairs" this by looking the style up has reinstated the surface.
    const { documentXml, stylesXml } = styledDoc(
      '<w:pStyle w:val="BodyText"/>',
      `<w:style w:type="paragraph" w:styleId="BodyText"><w:name w:val="Body Text"/></w:style>`,
    );
    const { bodyProofs } = await renderAllNull(documentXml, stylesXml);
    expect(bodyProofs.map((p) => p.kind)).not.toContain('emptied');
  });

  it('⚠️ REVERSED BY #170 — `numId="0"` no longer buys an exemption', async () => {
    // ⚠️ THIS ARM ASSERTED THE OPPOSITE UNTIL #170, AND THE REVERSAL IS
    // DELIBERATE. `numId="0"` really is Word's documented "no list", and the
    // old arm was correct about the XML. It was the LAST PLACE IN THIS GUARD
    // WHERE A JUDGEMENT LIVED — a rule that had to be right about what a
    // numbering value means — and every previous judgement in this guard was
    // eventually falsified. #170 pays one field's credit to have none left.
    //
    // `w:numPr` is not on the inert list. No exception, no value inspected.
    const { documentXml, stylesXml } = styledDoc(
      '<w:numPr><w:ilvl w:val="0"/><w:numId w:val="0"/></w:numPr>',
      '<w:style w:type="paragraph" w:styleId="Normal"/>',
    );
    const { bodyProofs } = await renderAllNull(documentXml, stylesXml);
    expect(bodyProofs.map((p) => p.kind)).not.toContain('emptied');
  });

  it('⚠️ REVERSED BY #170 — `w:pPrChange` is INELIGIBLE, though it renders nothing', async () => {
    // ⚠️ ALSO REVERSED, AND ALSO ON PURPOSE. `w:pPrChange` genuinely records
    // former properties for revision tracking and renders nothing — the old arm
    // was right, and honouring it required a walk up from each `w:numPr` to ask
    // whether it was historical. That walk was a JUDGEMENT, and its absence
    // from the sibling style-scanner was itself a finding in the last pass.
    //
    // #170 keeps no such walk. An unknown `pPr` child is ineligible, and
    // `pPrChange` is simply not on the list.
    const { documentXml, stylesXml } = styledDoc(
      '<w:pPrChange w:id="9" w:author="Dr"><w:pPr>' +
        '<w:numPr><w:numId w:val="7"/></w:numPr></w:pPr></w:pPrChange>',
      '<w:style w:type="paragraph" w:styleId="Normal"/>',
    );
    const { bodyProofs } = await renderAllNull(documentXml, stylesXml);
    expect(bodyProofs.map((p) => p.kind)).not.toContain('emptied');
  });
});

describe('#168(a) — the DATE branch carries the eligibility check too', () => {
  it('a numbered DATE control cannot claim blank', async () => {
    // ⚠️ THE `date` BRANCH'S `blankEligible` WAS UNPROVED: deleting
    // ` && cleared.blankEligible` there redded 0 of 57 arms, while the other two
    // sites each redded one. It is load-bearing, not dead — this is its arm.
    const { bodyProofs } = await renderAllNull(
      `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>` +
        `<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">` +
        `<w:body><w:sdt><w:sdtPr><w:id w:val="998"/><w:alias w:val="Encounter date"/>` +
        `<w:date w:fullDate="2026-01-01T00:00:00Z"><w:dateFormat w:val="yyyy-MM-dd"/></w:date>` +
        `</w:sdtPr><w:sdtContent>` +
        `<w:p><w:pPr><w:numPr><w:numId w:val="7"/></w:numPr></w:pPr>` +
        `<w:r><w:t>2026-01-01</w:t></w:r></w:p>` +
        `</w:sdtContent></w:sdt></w:body></w:document>`,
    );
    expect(bodyProofs.map((p) => p.kind)).not.toContain('emptied');
  });
});

describe('#168(a) — the numbering decision reaches the `blank` label too', () => {
  const numberedDoc = (content: string, styles?: string) => ({
    documentXml:
      `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>` +
      `<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">` +
      `<w:body><w:p>` +
      `<w:pPr><w:numPr><w:ilvl w:val="0"/><w:numId w:val="7"/></w:numPr></w:pPr>` +
      `<w:sdt><w:sdtPr><w:id w:val="999"/><w:alias w:val="Anticoagulation"/><w:text/></w:sdtPr>` +
      `<w:sdtContent>${content}</w:sdtContent></w:sdt>` +
      `</w:p></w:body></w:document>`,
    stylesXml: styles,
  });

  it('a numbered control whose content needs NO patch is not `blank` either', async () => {
    // ⚠️ THE ELIGIBILITY WAS COMPUTED AND THROWN AWAY. A control whose content
    // is already skeleton produces ZERO patches, and the zero-patch branch
    // pushed `blank` unconditionally — so two documents printing the identical
    // list marker got opposite verdicts, and the one that needed no work got
    // the credit:
    //
    //   run WITH a w:t      -> patches -> `filled`, refused (correct)
    //   run ALREADY empty   -> none    -> `blank`,  CREDIT  (the defect)
    //
    // The second is the first's own output. Both lenses found this
    // independently, and the read path cannot rescue it: the stored proof
    // carries no numbering signal, so this is the only place it can be decided.
    const { documentXml } = numberedDoc('<w:r><w:rPr><w:b/></w:rPr></w:r>');
    const { bodyProofs, bindingOf, kindOf } = await renderAllNull(documentXml);
    expect(bodyProofs.length).toBe(1);
    // ⚠️ THE LABEL STAYS `blank`, AND THE CREDIT IS WHAT MUST BE FALSE.
    // Emitting `filled` here to deny credit broke the verifier: `filled` joins
    // the PATCHED set, which must equal the proof set exactly, and this field
    // has no patches. `blank` is the honest label for an unpatched field; the
    // ineligibility rides beside it and the COUNT is where it bites.
    expect(bodyProofs[0].kind).toBe('blank');
    // #170 — three-state. `ineligible` is a decision; `unevaluated` would mean
    // no guard ran, and both refuse. This arm needs the DECISION.
    expect(bodyProofs[0].blankEligible).toBe('ineligible');
    expect(
      countsAsBlankProof(bodyProofs[0] as never, {
        bindingOf,
        resolvedNull: () => true,
        kindOf,
      }),
    ).toBe(false);
  });

  it('an UNnumbered control whose content needs no patch IS still `blank`', async () => {
    // NON-VACUITY for the arm above: the zero-patch path must still produce a
    // real `blank` proof, or "not blank" would hold for any reason at all.
    const { bodyProofs, bindingOf, kindOf } = await renderAllNull(
      sdtDoc({ content: '<w:r><w:rPr><w:b/></w:rPr></w:r>' }),
    );
    expect(bodyProofs[0]?.kind).toBe('blank');
    // ⚠️ #170 — AN EXPLICIT `eligible`, NEVER AN ABSENCE. Under the old boolean
    // this asserted `toBeUndefined()`, i.e. yes-encoded-as-absence — the exact
    // encoding that let two whole bindings go unguarded while looking approved.
    expect(bodyProofs[0]?.blankEligible).toBe('eligible');
    expect(
      countsAsBlankProof(bodyProofs[0] as never, {
        bindingOf,
        resolvedNull: () => true,
        kindOf,
      }),
    ).toBe(true);
  });

  it('numbering on the DEFAULT paragraph style reaches a paragraph that names none', async () => {
    // ⚠️ AN IMPLICIT EDGE THE `basedOn` CLOSURE DOES NOT CARRY. A paragraph with
    // no `w:pStyle` inherits `w:default="1"`. Measured: identical `styles.xml`
    // and identical PDF, but the paragraph NAMING the numbered style was
    // refused while the one naming nothing earned `emptied` and counted.
    const { documentXml } = numberedDoc('<w:r><w:t>Enter anticoagulation</w:t></w:r>');
    const plain = documentXml.replace(
      '<w:pPr><w:numPr><w:ilvl w:val="0"/><w:numId w:val="7"/></w:numPr></w:pPr>',
      '',
    );
    const styles =
      `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>` +
      `<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">` +
      `<w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:pPr>` +
      `<w:numPr><w:numId w:val="7"/></w:numPr></w:pPr></w:style></w:styles>`;
    const { bodyProofs } = await renderAllNull(plain, styles);
    expect(bodyProofs.map((p) => p.kind)).not.toContain('emptied');
  });

  it('⚠️ REVERSED by #169 — an ilvl with NO numId is INELIGIBLE, not exempt', async () => {
    // This arm previously asserted the opposite, and #169 reverses it on the
    // asymmetry rather than on new evidence about what prints:
    //
    //   a false REFUSAL costs ONE field its credit, and certification needs
    //   only one blank — the owner's form has 35 eligible;
    //   a false GRANT attests "renders blank" over printed prose in a signed
    //   clinical note.
    //
    // A `w:numPr` with only an `ilvl` was measured as printing nothing, and
    // "measured as harmless on the engine I could drive" is exactly the kind of
    // guess this guard stopped making. The one exclusion that survives is
    // `numId="0"` — Word's documented "no list", deterministic.
    //
    // ⚠️ AND THE COST IS REAL, NOT NOTIONAL: this is Word's built-in `Subtitle`,
    // byte-identical in both tracked customer templates. Neither applies it to
    // a control-bearing paragraph today, so nothing loses credit now — but the
    // trade is accepted knowingly, not by accident.
    const styles =
      `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>` +
      `<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">` +
      `<w:style w:type="paragraph" w:styleId="Subtitle"><w:pPr>` +
      `<w:numPr><w:ilvl w:val="1"/></w:numPr></w:pPr></w:style></w:styles>`;
    const { bodyProofs } = await renderAllNull(
      sdtDoc({
        block: true,
        content:
          '<w:p><w:pPr><w:pStyle w:val="Subtitle"/></w:pPr>' +
          '<w:r><w:t>Enter anticoagulation</w:t></w:r></w:p>',
      }),
      styles,
    );
    expect(bodyProofs.map((p) => p.kind)).not.toContain('emptied');
  });

  it('an UNKNOWN pStyle is INELIGIBLE — inability to resolve is not proof of absence', async () => {
    // #169's core: the guard answers "can I PROVE there is no numbering?", so a
    // style that is not in the table is disqualifying rather than ignorable.
    const styles =
      `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>` +
      `<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">` +
      `<w:style w:type="paragraph" w:styleId="Normal"/></w:styles>`;
    const { bodyProofs } = await renderAllNull(
      sdtDoc({
        block: true,
        content:
          '<w:p><w:pPr><w:pStyle w:val="NotInTheTable"/></w:pPr>' +
          '<w:r><w:t>Enter anticoagulation</w:t></w:r></w:p>',
      }),
      styles,
    );
    expect(bodyProofs.map((p) => p.kind)).not.toContain('emptied');
  });

  it('a basedOn pointing at a MISSING style is INELIGIBLE', async () => {
    const styles =
      `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>` +
      `<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">` +
      `<w:style w:type="paragraph" w:styleId="Body">` +
      `<w:basedOn w:val="Vanished"/></w:style></w:styles>`;
    const { bodyProofs } = await renderAllNull(
      sdtDoc({
        block: true,
        content:
          '<w:p><w:pPr><w:pStyle w:val="Body"/></w:pPr>' +
          '<w:r><w:t>Enter anticoagulation</w:t></w:r></w:p>',
      }),
      styles,
    );
    expect(bodyProofs.map((p) => p.kind)).not.toContain('emptied');
  });

  it('a basedOn CYCLE is INELIGIBLE rather than spinning', async () => {
    const styles =
      `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>` +
      `<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">` +
      `<w:style w:type="paragraph" w:styleId="A"><w:basedOn w:val="B"/></w:style>` +
      `<w:style w:type="paragraph" w:styleId="B"><w:basedOn w:val="A"/></w:style></w:styles>`;
    const { bodyProofs } = await renderAllNull(
      sdtDoc({
        block: true,
        content:
          '<w:p><w:pPr><w:pStyle w:val="A"/></w:pPr>' +
          '<w:r><w:t>Enter anticoagulation</w:t></w:r></w:p>',
      }),
      styles,
    );
    expect(bodyProofs.map((p) => p.kind)).not.toContain('emptied');
  });

  it('an UNPARSEABLE styles.xml refuses the whole render, one layer earlier', async () => {
    // ⚠️ THE ARM MEASURES WHAT ACTUALLY HAPPENS, NOT WHAT I EXPECTED.
    // `numberedStyleIds` has a `catch` that returns `readable: false`, which
    // under #169 makes every field ineligible — but the package inspection
    // rejects a malformed part FIRST, with `XML_INVALID`, so the render never
    // reaches it. That is strictly more fail-closed than ineligibility.
    //
    // ⚠️ HONEST LIMIT, STATED RATHER THAN CLAIMED: I could not construct an
    // input that reaches that `catch`, so the branch is defence-in-depth
    // against a future change in which the package layer stops validating this
    // part — not a path with a demonstrated caller. It is left in place and
    // labelled, rather than described as a guard that has been exercised.
    let code = 'NO THROW';
    try {
      await renderAllNull(
        sdtDoc({ content: '<w:r><w:t>Enter anticoagulation</w:t></w:r>' }),
        '<w:styles><w:style w:styleId="Broken"',
      );
    } catch (error) {
      code = (error as { code?: string }).code ?? String(error);
    }
    expect(code).toBe('XML_INVALID');
  });

  it('⚠️ REVERSED BY #170 — a `pStyle` is ineligible whatever the style says', async () => {
    // ⚠️ THIS ARM ONCE PROVED THE `numId="0"` EXCLUSION IN THE STYLE SCANNER —
    // the half nobody had armed until #169. #170 deletes the scanner and the
    // exclusion together: the paragraph names a `w:pStyle`, and that alone is
    // disqualifying, so the style's contents are never consulted.
    //
    // Kept rather than deleted because a reversed arm records that the old
    // behaviour was deliberate and is now deliberately gone. A deleted arm just
    // looks like coverage nobody wrote.
    const styles =
      `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>` +
      `<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">` +
      `<w:style w:type="paragraph" w:styleId="ListParagraph"><w:pPr>` +
      `<w:numPr><w:ilvl w:val="0"/><w:numId w:val="0"/></w:numPr></w:pPr></w:style></w:styles>`;
    const { bodyProofs } = await renderAllNull(
      sdtDoc({
        block: true,
        content:
          '<w:p><w:pPr><w:pStyle w:val="ListParagraph"/></w:pPr>' +
          '<w:r><w:t>Enter anticoagulation</w:t></w:r></w:p>',
      }),
      styles,
    );
    expect(bodyProofs.map((p) => p.kind)).not.toContain('emptied');
  });
});
