// ============================================================================
// RULING #313 · G4 — THE COMPILER'S `soleParagraphControl`, AND ITS IDENTITY.
// ----------------------------------------------------------------------------
// WHAT WOULD MAKE THIS FAIL, stated before it was made to fail:
//  · flag a control that shares its paragraph with text, another control, a
//    legacy field, a glyph, or a wrapper -> an arm below reads `true` where it
//    must read absent;
//  · emit `false` instead of omitting the key -> the "absent, not false" arm;
//  · hash the property -> `structureSha256` moves and the stored-IR render arm
//    throws SOURCE_IR_MISMATCH (the #191 orphaning, measured at 10 of 10).
// Every refusal arm has a positive twin that differs only in the discriminator.
// ============================================================================
import { describe, expect, it } from 'vitest';

import { compileTemplateDocx, fieldForStructuralIdentity } from '../compiler';
import { renderTemplateDocx } from '../renderer';
import { canonicalSha256 } from '../../template-twin/canonical';
import { TemplateDocIRSchema, TemplateFieldSchema } from '../../template-twin/ir';
import {
  bullets,
  compiledForm,
  ctl,
  heading,
  mappingsFor,
  para,
  resolveAll,
  text,
  withoutSoleParagraphControl,
} from '../../template-twin/__tests__/helpers-313';
import { validateTemplateTwin } from '../../template-twin/validation';

async function bodyFields(body: string[]) {
  const { ir } = await compiledForm(body);
  return ir.fields.filter((field) => field.rendererBinding.partName === 'word/document.xml');
}

const LEGACY_FIELD =
  '<w:r><w:fldChar w:fldCharType="begin"><w:ffData><w:name w:val="Legacy"/><w:textInput/></w:ffData></w:fldChar></w:r>' +
  '<w:r><w:instrText xml:space="preserve"> FORMTEXT </w:instrText></w:r><w:r><w:fldChar w:fldCharType="end"/></w:r>';

describe('#313 compiler — which controls are alone in their paragraph', () => {
  it('POSITIVE: a control that IS the paragraph is flagged `true`', async () => {
    const [field] = await bodyFields([para(ctl('Plan', 'plan', 1))]);
    expect(field!.soleParagraphControl).toBe(true);
  });

  it('text outside the control ("Right leg: [control]") — ABSENT, not false', async () => {
    const [field] = await bodyFields([para(text('Right leg: '), ctl('Impression', 'imp', 1))]);
    // ⚠️ THE KEY IS OMITTED. `false` would make every non-sole field of every
    // form compile differently from before this property existed.
    expect('soleParagraphControl' in field!).toBe(false);
  });

  it('TWIN: whitespace-only text outside still reads as nothing — flagged', async () => {
    const [field] = await bodyFields([para(text('   '), ctl('Impression', 'imp', 1))]);
    expect(field!.soleParagraphControl).toBe(true);
  });

  it('two controls in one paragraph (the ROS shape) — neither is flagged', async () => {
    const fields = await bodyFields([para(ctl('A', 'a', 1), text(' '), ctl('B', 'b', 2))]);
    expect(fields).toHaveLength(2);
    expect(fields.every((field) => !('soleParagraphControl' in field))).toBe(true);
  });

  // ⚠️ AN EMPTY SECOND CONTROL — the battery found "exactly one control" masked
  // by the outside-text test whenever the second control carries scaffold
  // text. A control with NO content contributes no text, so only the count
  // refuses this paragraph.
  it('two controls in one paragraph, the second EMPTY — still neither is flagged', async () => {
    const empty =
      '<w:sdt><w:sdtPr><w:alias w:val="B"/><w:tag w:val="b"/><w:id w:val="2"/><w:text/></w:sdtPr>' +
      '<w:sdtContent></w:sdtContent></w:sdt>';
    const fields = await bodyFields([para(ctl('A', 'a', 1), empty)]);
    expect(fields).toHaveLength(2);
    expect(fields.every((field) => !('soleParagraphControl' in field))).toBe(true);
  });

  it('TWIN: that same empty control ALONE in its paragraph is flagged', async () => {
    const empty =
      '<w:sdt><w:sdtPr><w:alias w:val="B"/><w:tag w:val="b"/><w:id w:val="2"/><w:text/></w:sdtPr>' +
      '<w:sdtContent></w:sdtContent></w:sdt>';
    const [field] = await bodyFields([para(empty)]);
    expect(field!.soleParagraphControl).toBe(true);
  });

  // ⚠️ A WRAPPER THAT IS NOT ON THE FORBIDDEN LIST — the battery found the
  // direct-child test masked by the hyperlink case (hyperlink IS forbidden,
  // and the control's own text leaked into "outside"). `w:dir` is neither, and
  // an empty control adds no text, so only the direct-child test refuses it.
  it('an EMPTY control inside a bidi `w:dir` wrapper is not a direct child — refused', async () => {
    const empty =
      '<w:sdt><w:sdtPr><w:alias w:val="B"/><w:tag w:val="b"/><w:id w:val="2"/><w:text/></w:sdtPr>' +
      '<w:sdtContent></w:sdtContent></w:sdt>';
    const [field] = await bodyFields([para(`<w:dir w:val="rtl">${empty}</w:dir>`)]);
    expect(field).toBeDefined();
    expect('soleParagraphControl' in field!).toBe(false);
  });

  it('a legacy form field in the same paragraph refuses the flag', async () => {
    const fields = await bodyFields([para(ctl('Plan', 'plan', 1), LEGACY_FIELD)]);
    const control = fields.find((field) => field.rendererBinding.bindingType === 'content_control');
    expect(control).toBeDefined();
    expect('soleParagraphControl' in control!).toBe(false);
  });

  // ⚠️ MEASURED: the compiler admits a legacy form field INSIDE a control's
  // own content as a SECOND field. That paragraph holds two fillables, so the
  // control is not alone in it — and nothing outside the control shows it.
  it('a legacy form field INSIDE the control\'s own content refuses the flag', async () => {
    const control =
      '<w:sdt><w:sdtPr><w:alias w:val="L"/><w:tag w:val="l"/><w:id w:val="7"/><w:text/></w:sdtPr><w:sdtContent>' +
      '<w:r><w:fldChar w:fldCharType="begin"><w:ffData><w:name w:val="x"/><w:textInput/></w:ffData></w:fldChar></w:r>' +
      '<w:r><w:fldChar w:fldCharType="end"/></w:r></w:sdtContent></w:sdt>';
    const fields = await bodyFields([para(control)]);
    expect(fields.length).toBeGreaterThanOrEqual(2);
    expect(fields.every((field) => !('soleParagraphControl' in field))).toBe(true);
  });

  // ⚠️ MEASURED: a control inside a BLOCK-level control's paragraph is admitted
  // as its own field. It lives inside another control's content, so it is not
  // a bullet of the document — the paragraph belongs to the outer control.
  it('a control nested inside a block-level control\'s content is never flagged', async () => {
    const block =
      '<w:sdt><w:sdtPr><w:alias w:val="Block"/><w:tag w:val="block"/><w:id w:val="8"/></w:sdtPr>' +
      `<w:sdtContent>${para(ctl('Inner', 'inner', 9))}</w:sdtContent></w:sdt>`;
    const fields = await bodyFields([block]);
    const inner = fields.find((field) => field.originalLabel === 'Inner');
    expect(inner).toBeDefined();
    expect('soleParagraphControl' in inner!).toBe(false);
    // twin: the same control NOT nested is flagged
    const [plain] = await bodyFields([para(ctl('Inner', 'inner', 9))]);
    expect(plain!.soleParagraphControl).toBe(true);
  });

  it('a control wrapped in a hyperlink is not a DIRECT child — refused', async () => {
    const [field] = await bodyFields([para(`<w:hyperlink w:anchor="x">${ctl('Plan', 'plan', 1)}</w:hyperlink>`)]);
    expect(field).toBeDefined();
    expect('soleParagraphControl' in field!).toBe(false);
  });

  it('a symbol glyph outside the control (no `w:t` text) — refused', async () => {
    const [field] = await bodyFields([
      para('<w:r><w:sym w:font="Symbol" w:char="F0B7"/></w:r>', ctl('Plan', 'plan', 1)),
    ]);
    expect('soleParagraphControl' in field!).toBe(false);
  });

  it('TWIN: paragraph properties and bookmarks around the control are not content — flagged', async () => {
    const [field] = await bodyFields([
      para(
        '<w:pPr><w:spacing w:after="0"/></w:pPr><w:bookmarkStart w:id="9" w:name="b"/>',
        ctl('Plan', 'plan', 1),
        '<w:bookmarkEnd w:id="9"/>',
      ),
    ]);
    expect(field!.soleParagraphControl).toBe(true);
  });

  it('a heading paragraph is a static node and consumes a display number', async () => {
    const fields = await bodyFields([...bullets('Plan', 'plan', 2, 1), heading('Break'), ...bullets('Plan', 'plan', 1, 3)]);
    expect(fields.map((field) => field.displayOrder)).toEqual([0, 1, 3]);
    expect(fields.every((field) => field.soleParagraphControl === true)).toBe(true);
  });
});

describe('#313 compiler — the property is OUT of structural identity (#191 precedent)', () => {
  it('`fieldForStructuralIdentity` removes it', async () => {
    const [field] = await bodyFields([para(ctl('Plan', 'plan', 1))]);
    expect(field!.soleParagraphControl).toBe(true);
    const stripped = fieldForStructuralIdentity(field!);
    expect('soleParagraphControl' in stripped).toBe(false);
    expect(Object.keys(stripped).sort()).toEqual(
      Object.keys(field!)
        .filter((key) => !['soleParagraphControl', 'scaffolded', 'scaffoldText'].includes(key))
        .sort(),
    );
  });

  it('`structureSha256` is identical with and without the property', async () => {
    const { ir } = await compiledForm([heading('Plan'), ...bullets('Plan', 'plan', 3, 1)]);
    expect(ir.fields.filter((field) => field.soleParagraphControl === true)).toHaveLength(3);
    const recompute = (fields: typeof ir.fields) =>
      canonicalSha256({
        fields: fields.map(fieldForStructuralIdentity),
        tables: ir.tables,
        nodes: ir.nodes,
        unsupported: ir.unsupported,
      });
    expect(recompute(ir.fields)).toBe(ir.structureSha256);
    expect(recompute(withoutSoleParagraphControl(ir).fields)).toBe(ir.structureSha256);
  });

  it('a STORED IR without the property still renders — `assertSourceMatchesIr` holds', async () => {
    const { source, ir } = await compiledForm([heading('Plan'), ...bullets('Plan', 'plan', 3, 1)]);
    const stored = withoutSoleParagraphControl(ir);
    // Non-vacuity: the fresh compile DOES carry the property, so the renderer's
    // re-compile and this stored IR genuinely differ on it.
    expect(ir.fields.some((field) => field.soleParagraphControl === true)).toBe(true);
    expect(stored.fields.some((field) => 'soleParagraphControl' in field)).toBe(false);
    const mappings = mappingsFor(stored, {});
    const resolutions = resolveAll(stored, mappings, []);
    const validation = validateTemplateTwin({
      fields: stored.fields,
      mappings,
      facts: [],
      resolutions,
      tables: stored.tables,
      unsupported: stored.unsupported,
      allowUncertifiedForSyntheticTest: true,
      now: '2026-09-10T00:00:00.000Z',
    });
    expect(validation.valid).toBe(true);
    const rendered = await renderTemplateDocx({ source, ir: stored, resolutions, validation });
    expect(rendered.verification.verified).toBe(true);
  });

  it('the IR schema accepts the property, and an IR without it', async () => {
    const { ir } = await compiledForm([para(ctl('Plan', 'plan', 1))]);
    expect(TemplateDocIRSchema.safeParse(ir).success).toBe(true);
    expect(TemplateDocIRSchema.safeParse(withoutSoleParagraphControl(ir)).success).toBe(true);
    const field = ir.fields.find((f) => f.soleParagraphControl === true)!;
    expect(TemplateFieldSchema.safeParse({ ...field, soleParagraphControl: 'yes' }).success).toBe(false);
  });

  it('compiling the same bytes twice is byte-identical, property included', async () => {
    const { source, ir } = await compiledForm([heading('Plan'), ...bullets('Plan', 'plan', 2, 1)]);
    expect(canonicalSha256(compileTemplateDocx(new Uint8Array(source)))).toBe(canonicalSha256(ir));
  });
});
