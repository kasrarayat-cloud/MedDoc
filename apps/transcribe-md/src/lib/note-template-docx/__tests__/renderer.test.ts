import { describe, expect, it } from 'vitest';

import {
  FieldResolutionSchema,
  type FieldResolution,
  type TemplateDocIR,
  type TemplateField,
  type TemplateTwinValidationResult,
} from '../../template-twin/ir';
import { inspectDocxPackage } from '../package-security';
import {
  renderTemplateDocx,
  type RenderTemplateDocxInput,
} from '../renderer';
import {
  buildSyntheticDocx,
  syntheticOpc,
} from './synthetic-docx';

const FACT_A = `ttfact_${'a'.repeat(24)}`;
const FACT_B = `ttfact_${'b'.repeat(24)}`;
const VALIDATION: TemplateTwinValidationResult = {
  valid: true,
  issues: [],
  checkedAt: '2026-01-01T00:00:00.000Z',
  validatorVersion: 'template-field-validator/1.0.0',
};

function resolution(
  field: TemplateField,
  value: FieldResolution['value'],
  selectedOptionOrdinal: number | null = null,
): FieldResolution {
  if (value === null) {
    return FieldResolutionSchema.parse({
      fieldId: field.fieldId,
      status: 'not_mentioned',
      value: null,
      sourceFactIds: [],
      evidenceAnchorIds: [],
      selectedOptionOrdinal: null,
      reasonCode: 'synthetic_not_mentioned',
      clinicianReviewed: false,
    });
  }
  return FieldResolutionSchema.parse({
    fieldId: field.fieldId,
    status: 'supported',
    value,
    sourceFactIds: [FACT_A, FACT_B],
    evidenceAnchorIds: ['synthetic-anchor-a', 'synthetic-anchor-b'],
    selectedOptionOrdinal,
    reasonCode: 'synthetic_direct_evidence',
    clinicianReviewed: false,
  });
}

function resolutionsFor(ir: TemplateDocIR): FieldResolution[] {
  return ir.fields.map((field) => {
    switch (field.originalLabel) {
      case 'Exam side':
        return resolution(field, 'R', 1);
      case 'Encounter category':
        return resolution(field, 'follow_up', 1);
      case 'Assessment narrative':
        return resolution(field, 'Synthetic assessment line one.\nLine two.');
      case 'Encounter date':
        return resolution(field, '2026-02-03');
      case 'Medication reviewed':
        return resolution(field, true);
      case 'Legacy severity':
        return resolution(field, 'Moderate', 1);
      case 'Finding value':
        return resolution(field, 'Synthetic supported finding');
      case 'Repeat finding':
        return resolution(field, null);
      case 'Practice display name':
        return resolution(field, 'Synthetic Clinic');
      case 'Data-bound synthetic value':
        return resolution(field, null);
      case 'Additional finding':
        return resolution(field, null);
      case 'Blood pressure':
        return resolution(field, '120/80 synthetic');
      default:
        throw new Error(`Unhandled synthetic field label: ${field.originalLabel}`);
    }
  });
}

function contentControlById(xml: string, id: string): string {
  const identity = xml.indexOf(`<w:id w:val="${id}"`);
  if (identity < 0) throw new Error('Synthetic control missing');
  const start = xml.lastIndexOf('<w:sdt>', identity);
  const end = xml.indexOf('</w:sdt>', identity);
  if (start < 0 || end < 0) throw new Error('Synthetic control malformed');
  return xml.slice(start, end + '</w:sdt>'.length);
}

async function setup(source?: Buffer): Promise<RenderTemplateDocxInput> {
  const sourceBytes = source ?? (await buildSyntheticDocx());
  const { compileTemplateDocx } = await import('../compiler');
  const ir = compileTemplateDocx(sourceBytes);
  return {
    source: sourceBytes,
    ir,
    resolutions: resolutionsFor(ir),
    validation: VALIDATION,
  };
}

describe('Template Twin exact DOCX renderer', () => {
  it('fills native controls, exact table cells, a legacy field, and headers', async () => {
    const input = await setup();
    const rendered = await renderTemplateDocx(input);
    const sourcePackage = inspectDocxPackage(input.source);
    const outputPackage = inspectDocxPackage(rendered.document);
    const documentXml = outputPackage.zip.entries
      .get('word/document.xml')!
      .bytes.toString('utf8');
    const sourceDocumentXml = sourcePackage.zip.entries
      .get('word/document.xml')!
      .bytes.toString('utf8');
    const headerXml = outputPackage.zip.entries
      .get('word/header1.xml')!
      .bytes.toString('utf8');

    expect(rendered.outputSha256).toMatch(/^[a-f0-9]{64}$/);
    expect(rendered.verification).toMatchObject({
      verified: true,
      packageCheck: 'verified',
      fieldCheck: 'verified',
      staticRegionCheck: 'verified',
      outputSha256: rendered.outputSha256,
    });
    expect(documentXml).toContain('<w:t>Right</w:t>');
    expect(documentXml).toContain('<w:t>Follow-up</w:t>');
    expect(documentXml).toContain('Synthetic assessment line one.');
    expect(documentXml).toContain('<w:br/>');
    expect(documentXml).toContain('Line two.');
    expect(documentXml).toContain('w:fullDate="2026-02-03T00:00:00Z"');
    expect(documentXml).toContain('w14:checked w14:val="1"');
    expect(documentXml).toContain('☒');
    expect(documentXml).toContain('<w:result w:val="1"/>');
    expect(documentXml).toContain('Synthetic supported finding');
    expect(headerXml).toContain('Synthetic Clinic');
    expect(contentControlById(documentXml, '108')).toBe(
      contentControlById(sourceDocumentXml, '108'),
    );

    // Native options and order are immutable; selecting one changes only the
    // displayed result body.
    expect(documentXml.indexOf('w:displayText="Left"')).toBeLessThan(
      documentXml.indexOf('w:displayText="Right"'),
    );
    expect(documentXml.indexOf('w:displayText="Right"')).toBeLessThan(
      documentXml.indexOf('w:displayText="Bilateral"'),
    );

    for (const untouched of [
      '[Content_Types].xml',
      '_rels/.rels',
      'word/_rels/document.xml.rels',
      'word/footer1.xml',
      'word/styles.xml',
      'word/numbering.xml',
    ]) {
      expect(outputPackage.zip.entries.get(untouched)?.bytes).toEqual(
        sourcePackage.zip.entries.get(untouched)?.bytes,
      );
    }
    expect(JSON.stringify(rendered.verification)).not.toContain(
      'Synthetic supported finding',
    );
  });

  it('fills an exact compiler-bound blank table cell without rebuilding the table', async () => {
    const table = `<w:tbl><w:tblGrid><w:gridCol w:w="2800"/><w:gridCol w:w="4200"/></w:tblGrid><w:tr><w:tc><w:p><w:r><w:t>Blood pressure</w:t></w:r></w:p></w:tc><w:tc><w:p/></w:tc></w:tr></w:tbl>`;
    const source = await buildSyntheticDocx({
      documentXml: syntheticOpc.documentXml.replace('<w:sectPr>', `${table}<w:sectPr>`),
    });
    const input = await setup(source);
    const tableField = input.ir.fields.find(
      (field) => field.originalLabel === 'Blood pressure',
    );
    expect(tableField?.rendererBinding.bindingType).toBe('table_cell');

    const rendered = await renderTemplateDocx(input);
    const xml = inspectDocxPackage(rendered.document).zip.entries
      .get('word/document.xml')!
      .bytes.toString('utf8');
    expect(xml).toContain(
      '<w:tc><w:p><w:r><w:t>120/80 synthetic</w:t></w:r></w:p></w:tc>',
    );
    expect(xml).toContain('<w:gridCol w:w="2800"/><w:gridCol w:w="4200"/>');
  });

  it('preserves an embedded header logo and its internal relationship byte-for-byte', async () => {
    const logo = Buffer.from(
      'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Wl2nS8AAAAASUVORK5CYII=',
      'base64',
    );
    const headerWithLogo = `<?xml version="1.0" encoding="UTF-8"?>
<w:hdr xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"
  xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"
  xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
  xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">
  <w:p><w:r><w:drawing><wp:inline><a:graphic><a:graphicData><a:blip r:embed="rIdLogo"/></a:graphicData></a:graphic></wp:inline></w:drawing></w:r></w:p>
  <w:p><w:sdt><w:sdtPr><w:id w:val="201"/><w:alias w:val="Practice display name"/><w:text/></w:sdtPr><w:sdtContent><w:r><w:t>Synthetic Practice</w:t></w:r></w:sdtContent></w:sdt></w:p>
</w:hdr>`;
    const headerRels = `<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rIdLogo" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="media/logo.png"/>
</Relationships>`;
    const source = await buildSyntheticDocx({
      extraEntries: {
        'word/header1.xml': headerWithLogo,
        'word/_rels/header1.xml.rels': headerRels,
        'word/media/logo.png': logo,
      },
    });
    const input = await setup(source);
    const rendered = await renderTemplateDocx(input);
    const before = inspectDocxPackage(source).zip.entries;
    const after = inspectDocxPackage(rendered.document).zip.entries;

    expect(after.get('word/media/logo.png')?.bytes).toEqual(logo);
    expect(after.get('word/media/logo.png')?.bytes).toEqual(
      before.get('word/media/logo.png')?.bytes,
    );
    expect(after.get('word/_rels/header1.xml.rels')?.bytes).toEqual(
      before.get('word/_rels/header1.xml.rels')?.bytes,
    );
    expect(after.get('word/header1.xml')?.bytes.toString('utf8')).toContain(
      'r:embed="rIdLogo"',
    );
    expect(rendered.verification.staticRegionCheck).toBe('verified');
  });

  it('emits a deterministic visual-review warning for a long populated value', async () => {
    const input = await setup();
    const narrative = input.ir.fields.find(
      (field) => field.originalLabel === 'Assessment narrative',
    )!;
    const longValue = 'Synthetic long value '.repeat(40);
    const resolutions = input.resolutions.map((item) =>
      item.fieldId === narrative.fieldId
        ? resolution(narrative, longValue)
        : item,
    );
    const rendered = await renderTemplateDocx({ ...input, resolutions });

    expect(rendered.verification.warningCodes).toContain(
      'LAYOUT_OVERFLOW_REVIEW_RECOMMENDED',
    );
    expect(rendered.verification.verified).toBe(true);
  });

  it('rejects a display-label near match instead of coercing it to a native option value', async () => {
    const input = await setup();
    const examSide = input.ir.fields.find((field) => field.originalLabel === 'Exam side')!;
    const invalid = input.resolutions.map((item) =>
      item.fieldId === examSide.fieldId
        ? resolution(examSide, 'Right', 1)
        : item,
    );
    await expect(
      renderTemplateDocx({ ...input, resolutions: invalid }),
    ).rejects.toMatchObject({
      code: 'FIELD_VALUE_INVALID',
    });
  });

  it('requires a successful independent validation before writing the clone', async () => {
    const input = await setup();
    await expect(
      renderTemplateDocx({
        ...input,
        validation: {
          ...VALIDATION,
          valid: false,
          issues: [
            {
              fieldId: null,
              code: 'SYNTHETIC_BLOCK',
              severity: 'blocking',
              message: 'Synthetic blocking result.',
            },
          ],
        },
      }),
    ).rejects.toMatchObject({
      code: 'VALIDATION_REQUIRED',
    });
  });

  it('fails closed when a safe-alpha blocked repeating structure is populated', async () => {
    const input = await setup();
    const repeat = input.ir.fields.find(
      (field) => field.originalLabel === 'Repeat finding',
    )!;
    const rows = [{
      value: 'Synthetic row 1',
      sourceFactId: FACT_A,
      evidenceAnchorId: 'synthetic-anchor-a',
      optionOrdinal: null,
    }];
    const resolutions = input.resolutions.map((item) =>
      item.fieldId === repeat.fieldId
        ? resolution(repeat, rows)
        : item,
    );

    await expect(
      renderTemplateDocx({ ...input, resolutions }),
    ).rejects.toMatchObject({ code: 'FIELD_VALUE_INVALID' });
  });
});
