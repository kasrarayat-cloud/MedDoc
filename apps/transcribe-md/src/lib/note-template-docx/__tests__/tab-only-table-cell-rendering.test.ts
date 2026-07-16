import JSZip from 'jszip';
import { describe, expect, it } from 'vitest';

import {
  FieldResolutionSchema,
  type FieldResolution,
  type TemplateDocIR,
  type TemplateField,
  type TemplateTwinValidationResult,
} from '../../template-twin/ir';
import { compileTemplateDocx } from '../compiler';
import { inspectDocxPackage } from '../package-security';
import { readbackTemplateDocxOutput } from '../output-readback';
import { renderTemplateDocx } from '../renderer';
import { buildSyntheticDocx } from './synthetic-docx';

const FACT_ID = `ttfact_${'d'.repeat(24)}`;
const VALIDATION: TemplateTwinValidationResult = {
  valid: true,
  issues: [],
  checkedAt: '2026-07-16T00:00:00.000Z',
  validatorVersion: 'template-field-validator/1.0.0',
};
const TAB_STOP_PROPERTIES =
  '<w:pPr><w:widowControl/><w:tabs><w:tab w:val="left" w:pos="2520"/></w:tabs><w:autoSpaceDE/><w:autoSpaceDN/><w:adjustRightInd/><w:jc w:val="left"/><w:rPr><w:rFonts w:ascii="Calibri"/><w:sz w:val="20"/></w:rPr></w:pPr>';
const STATIC_HEADER =
  '<?xml version="1.0" encoding="UTF-8"?><w:hdr xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:p><w:r><w:t>Synthetic static header</w:t></w:r></w:p></w:hdr>';

function documentXml(
  targetCell = `<w:tc><w:p>${TAB_STOP_PROPERTIES}</w:p></w:tc>`,
): string {
  return `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"
  xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <w:body>
    <w:p><w:r><w:t>Synthetic immutable title</w:t></w:r></w:p>
    <w:tbl>
      <w:tblPr><w:tblW w:w="0" w:type="auto"/></w:tblPr>
      <w:tblGrid><w:gridCol w:w="2200"/><w:gridCol w:w="5000"/></w:tblGrid>
      <w:tr>
        <w:tc><w:p><w:r><w:t>Plan item</w:t></w:r></w:p></w:tc>
        ${targetCell}
      </w:tr>
    </w:tbl>
    <w:sectPr><w:headerReference w:type="default" r:id="rIdHeader"/><w:footerReference w:type="default" r:id="rIdFooter"/></w:sectPr>
  </w:body>
</w:document>`;
}

async function sourceDocx(targetCell?: string): Promise<Buffer> {
  return buildSourceDocx(documentXml(targetCell));
}

async function buildSourceDocx(document: string): Promise<Buffer> {
  return buildSyntheticDocx({
    documentXml: document,
    extraEntries: {
      'word/header1.xml': STATIC_HEADER,
    },
  });
}

function fieldResolution(
  field: TemplateField,
  value: string | null,
): FieldResolution {
  return FieldResolutionSchema.parse({
    fieldId: field.fieldId,
    status: value === null ? 'not_mentioned' : 'supported',
    value,
    sourceFactIds: value === null ? [] : [FACT_ID],
    evidenceAnchorIds: value === null ? [] : ['synthetic-tab-cell-anchor'],
    selectedOptionOrdinal: null,
    reasonCode:
      value === null ? 'synthetic_not_mentioned' : 'synthetic_supported',
    clinicianReviewed: false,
  });
}

function exactField(ir: TemplateDocIR): TemplateField {
  expect(ir.unsupported).toEqual([]);
  expect(ir.fields).toHaveLength(1);
  const field = ir.fields[0]!;
  expect(field).toMatchObject({
    originalLabel: 'Plan item',
    labelSource: 'left_cell',
    detectionStatus: 'needs_confirmation',
    rendererBinding: {
      bindingType: 'table_cell',
      bindingProfile: 'TAB_ONLY_BLANK_TABLE_CELL_V1',
      partName: 'word/document.xml',
      tableIndex: 0,
      rowIndex: 0,
      cellIndex: 1,
    },
  });
  return field;
}

async function render(value: string | null) {
  const source = await sourceDocx();
  const ir = compileTemplateDocx(source);
  const field = exactField(ir);
  const resolutions = [fieldResolution(field, value)];
  const rendered = await renderTemplateDocx({
    source,
    ir,
    resolutions,
    validation: VALIDATION,
  });
  return { source, ir, field, resolutions, rendered };
}

async function replaceDocumentXml(
  bytes: Uint8Array,
  mutate: (xml: string) => string,
): Promise<Buffer> {
  const zip = await JSZip.loadAsync(bytes);
  const entry = zip.file('word/document.xml');
  if (!entry) throw new Error('Synthetic document part is missing.');
  const before = await entry.async('string');
  const after = mutate(before);
  if (after === before) throw new Error('Synthetic mutation was a no-op.');
  zip.file('word/document.xml', after);
  return zip.generateAsync({ type: 'nodebuffer', compression: 'DEFLATE' });
}

describe('TAB_ONLY_BLANK_TABLE_CELL_V1 rendering and strict readback', () => {
  it('preserves the certified paragraph tab-stop properties and fills only the exact cell', async () => {
    const fixture = await render('Use brace <only> & review — 左');
    const xml = inspectDocxPackage(fixture.rendered.document)
      .zip.entries.get('word/document.xml')!
      .bytes.toString('utf8');

    expect(xml).toContain(TAB_STOP_PROPERTIES);
    expect(xml).toContain(
      `${TAB_STOP_PROPERTIES}<w:r><w:t>Use brace &lt;only&gt; &amp; review — 左</w:t></w:r>`,
    );
    expect(fixture.rendered.verification).toMatchObject({
      verified: true,
      packageCheck: 'verified',
      fieldCheck: 'verified',
      staticRegionCheck: 'verified',
    });
    expect(fixture.rendered.verification.fields).toEqual([
      expect.objectContaining({
        fieldId: fixture.field.fieldId,
        disposition: 'rendered',
        occurrences: 1,
        bindingEvidence: expect.objectContaining({
          status: 'verified',
          outputBindingProfile: 'TAB_ONLY_BLANK_TABLE_CELL_V1',
          outputTableLocation: { tableIndex: 0, rowIndex: 0, cellIndex: 1 },
        }),
      }),
    ]);
  });

  it('leaves an unresolved blank cell and its paragraph properties unchanged with explicit proof', async () => {
    const fixture = await render(null);
    const sourceXml = inspectDocxPackage(fixture.source)
      .zip.entries.get('word/document.xml')!
      .bytes.toString('utf8');
    const outputXml = inspectDocxPackage(fixture.rendered.document)
      .zip.entries.get('word/document.xml')!
      .bytes.toString('utf8');

    expect(outputXml).toBe(sourceXml);
    expect(fixture.rendered.verification.fields).toEqual([
      expect.objectContaining({
        fieldId: fixture.field.fieldId,
        disposition: 'unresolved_blank',
        occurrences: 1,
      }),
    ]);
  });

  it('retains exact path identity for a maximum approved value and emits layout review', async () => {
    const maximum = 'x'.repeat(32_767);
    const fixture = await render(maximum);
    expect(fixture.rendered.verification.warningCodes).toContain(
      'LAYOUT_OVERFLOW_REVIEW_RECOMMENDED',
    );
    expect(
      fixture.rendered.verification.fields[0]?.bindingEvidence,
    ).toMatchObject({
      status: 'verified',
      outputCanonicalPath: fixture.field.rendererBinding.canonicalPath,
    });
  });

  it('preserves boundary whitespace with the one required XML space attribute', async () => {
    const fixture = await render('  synthetic reviewed value  ');
    const xml = inspectDocxPackage(fixture.rendered.document)
      .zip.entries.get('word/document.xml')!
      .bytes.toString('utf8');

    expect(xml).toContain(
      '<w:t xml:space="preserve">  synthetic reviewed value  </w:t>',
    );
    expect(fixture.rendered.verification.verified).toBe(true);
  });

  it('rejects a value above the approved field length before package mutation', async () => {
    await expect(render('x'.repeat(32_768))).rejects.toMatchObject({
      code: 'FIELD_VALUE_TOO_LARGE',
    });
  });

  it('rejects a certified binding ordinal changed after compilation', async () => {
    const source = await sourceDocx();
    const ir = structuredClone(compileTemplateDocx(source));
    ir.fields[0]!.rendererBinding.ordinal += 1;

    await expect(
      renderTemplateDocx({
        source,
        ir,
        resolutions: [fieldResolution(ir.fields[0]!, null)],
        validation: VALIDATION,
      }),
    ).rejects.toMatchObject({ code: 'SOURCE_IR_MISMATCH' });
  });

  it('keeps an unchanged pre-profile 1.1 alpha template renderable', async () => {
    const source = await sourceDocx('<w:tc><w:p/></w:tc>');
    const current = compileTemplateDocx(source);
    const oldIr = {
      ...current,
      compilerVersion: 'template-docx-compiler/1.1.0',
    };
    const rendered = await renderTemplateDocx({
      source,
      ir: oldIr,
      resolutions: oldIr.fields.map((field) => fieldResolution(field, null)),
      validation: VALIDATION,
    });

    expect(rendered.verification.verified).toBe(true);
    expect(rendered.rendererVersion).toBe('template-docx-renderer/1.2.0');
  });

  it('rejects the same populated cell moved to another table row', async () => {
    const fixture = await render('Use synthetic brace');
    const moved = await replaceDocumentXml(fixture.rendered.document, (xml) => {
      const rowStart = xml.indexOf('<w:tr>');
      const rowEnd = xml.indexOf('</w:tr>', rowStart) + '</w:tr>'.length;
      const row = xml.slice(rowStart, rowEnd);
      return xml.replace(
        row,
        `<w:tr><w:tc><w:p/></w:tc><w:tc><w:p/></w:tc></w:tr>${row}`,
      );
    });

    expect(() =>
      readbackTemplateDocxOutput({
        source: fixture.source,
        output: moved,
        ir: fixture.ir,
        resolutions: fixture.resolutions,
      }),
    ).toThrowError(
      expect.objectContaining({ code: 'ROUNDTRIP_FIELD_MISMATCH' }),
    );
  });

  it('rejects a cell substituted at the certified location even when the visible value is retained', async () => {
    const fixture = await render('Use synthetic brace');
    const substituted = await replaceDocumentXml(
      fixture.rendered.document,
      (xml) => xml.replace('w:pos="2520"', 'w:pos="2521"'),
    );

    expect(() =>
      readbackTemplateDocxOutput({
        source: fixture.source,
        output: substituted,
        ir: fixture.ir,
        resolutions: fixture.resolutions,
      }),
    ).toThrowError(
      expect.objectContaining({ code: 'ROUNDTRIP_FIELD_MISMATCH' }),
    );
  });

  it('rejects raw character data injected into immutable paragraph properties', async () => {
    const fixture = await render('Use synthetic brace');
    const altered = await replaceDocumentXml(fixture.rendered.document, (xml) =>
      xml.replace(
        '<w:jc w:val="left"/>',
        '<w:jc w:val="left">SYNTHETIC_INVALID_RAW_TEXT</w:jc>',
      ),
    );

    expect(() =>
      readbackTemplateDocxOutput({
        source: fixture.source,
        output: altered,
        ir: fixture.ir,
        resolutions: fixture.resolutions,
      }),
    ).toThrowError(
      expect.objectContaining({ code: 'ROUNDTRIP_FIELD_MISMATCH' }),
    );
  });

  it.each([
    [
      'a table-cell attribute',
      (xml: string) =>
        xml.replace(
          `<w:tc><w:p>${TAB_STOP_PROPERTIES}`,
          `<w:tc w:rsidR="00A1B2C3"><w:p>${TAB_STOP_PROPERTIES}`,
        ),
    ],
    [
      'a tracked paragraph-deletion identity',
      (xml: string) =>
        xml.replace(
          `<w:tc><w:p>${TAB_STOP_PROPERTIES}`,
          `<w:tc><w:p w:rsidDel="00A1B2C3">${TAB_STOP_PROPERTIES}`,
        ),
    ],
    [
      'a changed paragraph-property revision identity',
      (xml: string) =>
        xml.replace(
          `<w:tc><w:p>${TAB_STOP_PROPERTIES}`,
          `<w:tc><w:p w:rsidRPr="00A1B2C3">${TAB_STOP_PROPERTIES}`,
        ),
    ],
    [
      'a paragraph identity in the Word 2010 namespace',
      (xml: string) =>
        xml
          .replace(
            '<w:document ',
            '<w:document xmlns:w14="http://schemas.microsoft.com/office/word/2010/wordml" ',
          )
          .replace(
            `<w:tc><w:p>${TAB_STOP_PROPERTIES}`,
            `<w:tc><w:p w14:paraId="00A1B2C3">${TAB_STOP_PROPERTIES}`,
          ),
    ],
    [
      'a renderer-created run attribute',
      (xml: string) =>
        xml.replace(
          '<w:r><w:t>Use synthetic brace</w:t></w:r>',
          '<w:r w:rsidRPr="00A1B2C3"><w:t>Use synthetic brace</w:t></w:r>',
        ),
    ],
    [
      'an unnecessary text-preservation attribute',
      (xml: string) =>
        xml.replace(
          '<w:t>Use synthetic brace</w:t>',
          '<w:t xml:space="preserve">Use synthetic brace</w:t>',
        ),
    ],
  ] as const)('rejects %s added after certification', async (_name, mutate) => {
    const fixture = await render('Use synthetic brace');
    const altered = await replaceDocumentXml(fixture.rendered.document, mutate);

    expect(() =>
      readbackTemplateDocxOutput({
        source: fixture.source,
        output: altered,
        ir: fixture.ir,
        resolutions: fixture.resolutions,
      }),
    ).toThrowError(
      expect.objectContaining({ code: 'ROUNDTRIP_FIELD_MISMATCH' }),
    );
  });

  it('rejects a duplicated profiled cell even when its native shape and value are unchanged', async () => {
    const fixture = await render('Use synthetic brace');
    const duplicated = await replaceDocumentXml(
      fixture.rendered.document,
      (xml) => {
        const cell =
          `<w:tc><w:p>${TAB_STOP_PROPERTIES}` +
          '<w:r><w:t>Use synthetic brace</w:t></w:r></w:p></w:tc>';
        return xml.replace(cell, `${cell}${cell}`);
      },
    );

    expect(() =>
      readbackTemplateDocxOutput({
        source: fixture.source,
        output: duplicated,
        ir: fixture.ir,
        resolutions: fixture.resolutions,
      }),
    ).toThrowError(
      expect.objectContaining({ code: 'ROUNDTRIP_FIELD_MISMATCH' }),
    );
  });

  it('rejects two profiled cells swapped between certified row paths', async () => {
    const secondRow = `<w:tr><w:tc><w:p><w:r><w:t>Assessment item</w:t></w:r></w:p></w:tc><w:tc><w:p>${TAB_STOP_PROPERTIES}</w:p></w:tc></w:tr>`;
    const source = await buildSourceDocx(
      documentXml().replace('</w:tbl>', `${secondRow}</w:tbl>`),
    );
    const ir = compileTemplateDocx(source);
    const first = ir.fields.find(
      (field) => field.originalLabel === 'Plan item',
    )!;
    const second = ir.fields.find(
      (field) => field.originalLabel === 'Assessment item',
    )!;
    const resolutions = [
      fieldResolution(first, 'Use synthetic brace'),
      fieldResolution(second, 'Continue synthetic therapy'),
    ];
    const rendered = await renderTemplateDocx({
      source,
      ir,
      resolutions,
      validation: VALIDATION,
    });
    const swapped = await replaceDocumentXml(rendered.document, (xml) =>
      xml
        .replace('Use synthetic brace', '__SYNTHETIC_SWAP__')
        .replace('Continue synthetic therapy', 'Use synthetic brace')
        .replace('__SYNTHETIC_SWAP__', 'Continue synthetic therapy'),
    );

    expect(() =>
      readbackTemplateDocxOutput({ source, output: swapped, ir, resolutions }),
    ).toThrowError(
      expect.objectContaining({ code: 'ROUNDTRIP_FIELD_MISMATCH' }),
    );
  });
});
