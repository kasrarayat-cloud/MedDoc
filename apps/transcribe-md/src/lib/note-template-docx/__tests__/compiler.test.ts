import { describe, expect, it } from 'vitest';

import { TemplateDocIRSchema } from '../../template-twin/ir';
import { compileTemplateDocx } from '..';
import { buildSyntheticDocx, syntheticOpc } from './synthetic-docx';

describe('deterministic Template Twin DOCX compiler', () => {
  it('extracts stable controls and exact native option order from the body, header, and tables', async () => {
    const source = await buildSyntheticDocx();
    const first = compileTemplateDocx(source);
    const second = compileTemplateDocx(source);

    expect(TemplateDocIRSchema.safeParse(first).success).toBe(true);
    expect(second).toEqual(first);
    expect(second.structureSha256).toBe(first.structureSha256);

    const examSide = first.fields.find(
      (field) => field.originalLabel === 'Exam side',
    );
    expect(examSide?.kind).toBe('single_select');
    expect(examSide?.allowedOptions).toEqual([
      { ordinal: 0, displayText: 'Left', value: 'L' },
      { ordinal: 1, displayText: 'Right', value: 'R' },
      { ordinal: 2, displayText: 'Bilateral', value: 'B' },
    ]);
    expect(examSide?.rendererBinding.sdtId).toBe('100');
    expect(examSide?.rendererBinding.tag).toBe('exam_side');

    expect(
      first.fields.find(
        (field) => field.originalLabel === 'Medication reviewed',
      )?.kind,
    ).toBe('checkbox');
    expect(
      first.fields.find((field) => field.originalLabel === 'Encounter date')
        ?.kind,
    ).toBe('date');
    expect(
      first.fields.find((field) => field.originalLabel === 'Legacy severity')
        ?.rendererBinding.bindingType,
    ).toBe('legacy_form_field');
    expect(
      first.fields.find(
        (field) => field.originalLabel === 'Practice display name',
      )?.rendererBinding.partName,
    ).toBe('word/header1.xml');
    expect(
      first.fields.find(
        (field) => field.originalLabel === 'Additional finding',
      ),
    ).toMatchObject({
      labelSource: 'left_cell',
      detectionStatus: 'needs_confirmation',
      rendererBinding: { bindingType: 'table_cell' },
    });
    expect(first.stats.comboBoxes).toBe(1);
    expect(first.stats.headers).toBe(1);
    expect(first.stats.footers).toBe(1);
  });

  it('records merged cells, nested tables, repeat bindings, and immutable renderer locations', async () => {
    const compiled = compileTemplateDocx(await buildSyntheticDocx());
    const outerTable = compiled.tables.find((table) =>
      table.cells.some((cell) => cell.gridSpan === 2),
    );
    const repeatingTable = compiled.tables.find(
      (table) => table.kind === 'repeating_table',
    );
    const repeatField = compiled.fields.find(
      (field) => field.originalLabel === 'Repeat finding',
    );

    expect(outerTable?.gridColumnWidths).toEqual([2800, 4200]);
    expect(
      outerTable?.cells.some(
        (cell) => cell.gridSpan === 2 && cell.verticalMerge === 'restart',
      ),
    ).toBe(true);
    expect(
      outerTable?.cells.some((cell) => cell.verticalMerge === 'continue'),
    ).toBe(true);
    expect(outerTable?.cells.some((cell) => cell.nestedTableCount === 1)).toBe(
      true,
    );
    expect(compiled.tables.length).toBeGreaterThanOrEqual(3);

    expect(repeatingTable?.repeatPrototypeRow).toBe(0);
    expect(repeatField?.rowPrototype).toBe(true);
    expect(repeatField?.detectionStatus).toBe('unsupported');
    expect(repeatField?.rendererBinding.repeatAncestorPath).toBeTruthy();
    expect(repeatField?.tableId).toBe(repeatingTable?.tableId);
    expect(repeatField?.rendererBinding.path).toMatch(/^\/w:document\[0\]/);
    expect(compiled.unsupported).toContainEqual(
      expect.objectContaining({
        code: 'REPEATING_STRUCTURE_UNSUPPORTED_SAFE_ALPHA',
        blocksCertification: true,
      }),
    );
  });

  it('recognizes deterministic visible placeholders but keeps physician confirmation required', async () => {
    const documentXml = syntheticOpc.documentXml.replace(
      '<w:sectPr>',
      '<w:p><w:r><w:t>Synthetic template &lt;&lt;insert patient concern&gt;&gt;</w:t></w:r></w:p><w:sectPr>',
    );
    const compiled = compileTemplateDocx(
      await buildSyntheticDocx({ documentXml }),
    );
    expect(compiled.unsupported).not.toContainEqual(
      expect.objectContaining({ code: 'UNBOUND_ORDINARY_PLACEHOLDER' }),
    );
    expect(compiled.fields).toContainEqual(
      expect.objectContaining({
        detectionStatus: 'needs_confirmation',
        rendererBinding: expect.objectContaining({
          bindingType: 'ordinary_placeholder',
          bindingProfile: 'ORDINARY_PLACEHOLDER_TOKEN_V1',
        }),
      }),
    );
  });

  it('certification-blocks indistinguishable controls without native Word identities', async () => {
    const anonymous =
      '<w:p><w:sdt><w:sdtPr><w:text/></w:sdtPr><w:sdtContent><w:r><w:t>Anonymous placeholder</w:t></w:r></w:sdtContent></w:sdt></w:p>';
    const documentXml = syntheticOpc.documentXml.replace(
      '<w:sectPr>',
      `${anonymous}${anonymous}<w:sectPr>`,
    );
    const compiled = compileTemplateDocx(
      await buildSyntheticDocx({ documentXml }),
    );
    const blockers = compiled.unsupported.filter(
      (item) => item.code === 'AMBIGUOUS_ANONYMOUS_BINDING_IDENTITY',
    );

    expect(blockers).toHaveLength(2);
    expect(blockers.every((item) => item.blocksCertification)).toBe(true);
    expect(
      compiled.fields
        .filter((field) => field.rendererBinding.sdtId === null)
        .filter((field) =>
          blockers.some(
            (blocker) => blocker.path === field.rendererBinding.path,
          ),
        )
        .every((field) => field.detectionStatus === 'unsupported'),
    ).toBe(true);
  });

  it('certification-blocks rich-text and compatibility representations', async () => {
    const richText = `<w:p><w:sdt><w:sdtPr><w:id w:val="901"/><w:alias w:val="Synthetic rich narrative"/></w:sdtPr><w:sdtContent><w:p><w:r><w:rPr><w:b/></w:rPr><w:t>Rich placeholder</w:t></w:r></w:p><w:p><w:r><w:t>Second paragraph</w:t></w:r></w:p></w:sdtContent></w:sdt></w:p>`;
    const alternate = `<mc:AlternateContent xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006"><mc:Choice Requires="w15"><w:p><w:r><w:t>Choice</w:t></w:r></w:p></mc:Choice><mc:Fallback><w:p><w:r><w:t>Fallback</w:t></w:r></w:p></mc:Fallback></mc:AlternateContent>`;
    const documentXml = syntheticOpc.documentXml
      .replace(
        '<w:document ',
        '<w:document xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006" ',
      )
      .replace('<w:sectPr>', `${richText}${alternate}<w:sectPr>`);
    const compiled = compileTemplateDocx(
      await buildSyntheticDocx({ documentXml }),
    );
    expect(
      compiled.fields.find(
        (field) => field.originalLabel === 'Synthetic rich narrative',
      )?.detectionStatus,
    ).toBe('unsupported');
    expect(compiled.unsupported.map((item) => item.code)).toEqual(
      expect.arrayContaining([
        'RICH_TEXT_CONTENT_CONTROL_UNSUPPORTED_SAFE_ALPHA',
        'ALTERNATE_CONTENT_UNSUPPORTED_SAFE_ALPHA',
      ]),
    );
  });

  it('blocks a header plus w15 repeating data row before duplicate IDs can be cloned', async () => {
    const repeating = `<w:sdt><w:sdtPr><w:id w:val="950"/><w:alias w:val="Synthetic repeated medications"/><w15:repeatingSection/></w:sdtPr><w:sdtContent><w:tbl><w:tblGrid><w:gridCol w:w="2000"/><w:gridCol w:w="2000"/></w:tblGrid><w:tr><w:tc><w:p><w:r><w:t>Medication</w:t></w:r></w:p></w:tc><w:tc><w:p><w:r><w:t>Dose</w:t></w:r></w:p></w:tc></w:tr><w:sdt><w:sdtPr><w:id w:val="951"/><w15:repeatingSectionItem/></w:sdtPr><w:sdtContent><w:tr><w:tc><w:p><w:sdt><w:sdtPr><w:id w:val="952"/><w:alias w:val="Synthetic medication"/><w:text/></w:sdtPr><w:sdtContent><w:r><w:t>Medication placeholder</w:t></w:r></w:sdtContent></w:sdt></w:p></w:tc><w:tc><w:p><w:sdt><w:sdtPr><w:id w:val="952"/><w:alias w:val="Synthetic dose"/><w:text/></w:sdtPr><w:sdtContent><w:r><w:t>Dose placeholder</w:t></w:r></w:sdtContent></w:sdt></w:p></w:tc></w:tr></w:sdtContent></w:sdt></w:tbl></w:sdtContent></w:sdt>`;
    const compiled = compileTemplateDocx(
      await buildSyntheticDocx({
        documentXml: syntheticOpc.documentXml.replace(
          '<w:sectPr>',
          `${repeating}<w:sectPr>`,
        ),
      }),
    );
    expect(compiled.unsupported).toContainEqual(
      expect.objectContaining({
        code: 'REPEATING_STRUCTURE_UNSUPPORTED_SAFE_ALPHA',
        blocksCertification: true,
      }),
    );
    const repeatedFields = compiled.fields.filter(
      (field) =>
        field.originalLabel.startsWith('Synthetic medication') ||
        field.originalLabel.startsWith('Synthetic dose'),
    );
    expect(repeatedFields).toHaveLength(2);
    expect(
      repeatedFields.every((field) => field.detectionStatus === 'unsupported'),
    ).toBe(true);
  });

  it('surfaces clinically material unsupported constructs instead of dropping them', async () => {
    const compiled = compileTemplateDocx(await buildSyntheticDocx());
    const dataBound = compiled.fields.find(
      (field) => field.originalLabel === 'Data-bound synthetic value',
    );
    const unsupported = compiled.unsupported.find(
      (item) => item.code === 'DATA_BOUND_CONTENT_CONTROL',
    );

    expect(dataBound?.detectionStatus).toBe('unsupported');
    expect(unsupported).toMatchObject({
      clinicallyMaterial: true,
      blocksCertification: true,
      partName: 'word/document.xml',
    });
    expect(compiled.stats.blockingUnsupported).toBeGreaterThanOrEqual(1);
  });

  it('changes source and binding hashes when the immutable source changes', async () => {
    const original = compileTemplateDocx(await buildSyntheticDocx());
    const changed = compileTemplateDocx(
      await buildSyntheticDocx({
        documentXml: syntheticOpc.documentXml.replace(
          'Synthetic clinical template',
          'Synthetic clinical template revision',
        ),
      }),
    );

    expect(changed.source.sha256).not.toBe(original.source.sha256);
    expect(changed.staticContentSha256).not.toBe(original.staticContentSha256);
    expect(changed.fields[0]?.fieldId).not.toBe(original.fields[0]?.fieldId);
  });

  it('keeps duplicate labels as distinct path-bound fields and bounds long labels', async () => {
    const duplicateLabelXml = syntheticOpc.documentXml.replace(
      'w:alias w:val="Assessment narrative"',
      'w:alias w:val="Exam side"',
    );
    const duplicate = compileTemplateDocx(
      await buildSyntheticDocx({ documentXml: duplicateLabelXml }),
    );
    const sameLabelFields = duplicate.fields.filter(
      (field) => field.originalLabel === 'Exam side',
    );
    expect(sameLabelFields).toHaveLength(2);
    expect(new Set(sameLabelFields.map((field) => field.fieldId)).size).toBe(2);
    expect(
      new Set(sameLabelFields.map((field) => field.rendererBinding.path)).size,
    ).toBe(2);

    const longLabel = 'Synthetic measurement '.repeat(20);
    const longLabelXml = syntheticOpc.documentXml.replace(
      'Assessment narrative',
      longLabel,
    );
    const bounded = compileTemplateDocx(
      await buildSyntheticDocx({ documentXml: longLabelXml }),
    );
    expect(
      bounded.fields.find((field) =>
        field.originalLabel.startsWith('Synthetic'),
      )?.originalLabel,
    ).toHaveLength(240);
  });

  it('masks mutable content-control results from the static-region hash', async () => {
    const original = compileTemplateDocx(await buildSyntheticDocx());
    const changedDisplayValue = compileTemplateDocx(
      await buildSyntheticDocx({
        documentXml: syntheticOpc.documentXml.replace(
          'Choose an item.',
          'Left',
        ),
      }),
    );

    expect(changedDisplayValue.source.sha256).not.toBe(original.source.sha256);
    expect(changedDisplayValue.staticContentSha256).toBe(
      original.staticContentSha256,
    );
  });
});
