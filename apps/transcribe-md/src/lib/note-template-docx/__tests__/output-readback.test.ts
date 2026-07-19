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
import { buildSyntheticDocx, syntheticOpc } from './synthetic-docx';

const FACT = `ttfact_${'c'.repeat(24)}`;
const VALIDATION: TemplateTwinValidationResult = {
  valid: true,
  issues: [],
  checkedAt: '2026-07-15T00:00:00.000Z',
  validatorVersion: 'template-field-validator/1.0.0',
};

function resolved(
  field: TemplateField,
  value: FieldResolution['value'],
  option: number | null = null,
): FieldResolution {
  return FieldResolutionSchema.parse({
    fieldId: field.fieldId,
    status: value === null ? 'not_mentioned' : 'supported',
    value,
    sourceFactIds: value === null ? [] : [FACT],
    evidenceAnchorIds: value === null ? [] : ['synthetic-anchor'],
    selectedOptionOrdinal: option,
    reasonCode:
      value === null ? 'synthetic_not_mentioned' : 'synthetic_evidence',
    clinicianReviewed: false,
  });
}

function allResolutions(ir: TemplateDocIR): FieldResolution[] {
  return ir.fields.map((field) => {
    const values: Record<string, [FieldResolution['value'], number | null]> = {
      'Exam side': ['R', 1],
      'Encounter category': ['follow_up', 1],
      'Assessment narrative': ['Synthetic assessment', null],
      'Encounter date': ['2026-07-15', null],
      'Medication reviewed': [true, null],
      'Legacy severity': ['Moderate', 1],
      'Finding value': ['Synthetic finding', null],
      'Practice display name': ['Synthetic Clinic', null],
    };
    const selected = values[field.originalLabel] ?? [null, null];
    return resolved(field, selected[0], selected[1]);
  });
}

async function renderFixture(providedSource?: Buffer) {
  const source = providedSource ?? (await buildSyntheticDocx());
  const ir = compileTemplateDocx(source);
  const resolutions = allResolutions(ir);
  const rendered = await renderTemplateDocx({
    source,
    ir,
    resolutions,
    validation: VALIDATION,
  });
  return { source, ir, resolutions, rendered };
}

async function replacePart(
  source: Uint8Array,
  partName: string,
  replace: (xml: string) => string,
): Promise<Buffer> {
  const zip = await JSZip.loadAsync(source);
  const entry = zip.file(partName);
  if (!entry) throw new Error('Synthetic part missing');
  const before = await entry.async('string');
  const after = replace(before);
  if (after === before) throw new Error('Synthetic mutation did not apply');
  zip.file(partName, after);
  return zip.generateAsync({ type: 'nodebuffer', compression: 'DEFLATE' });
}

describe('independent Template Twin DOCX output readback', () => {
  it('derives a proof for every rendered, unresolved, and unsupported IR field', async () => {
    const fixture = await renderFixture();
    expect(fixture.rendered.verification.fields).toHaveLength(
      fixture.ir.fields.length,
    );
    expect(
      fixture.rendered.verification.fields.find(
        (proof) =>
          proof.fieldId ===
          fixture.ir.fields.find(
            (field) => field.originalLabel === 'Assessment narrative',
          )?.fieldId,
      )?.disposition,
    ).toBe('rendered');
    expect(
      fixture.rendered.verification.fields.some(
        (proof) => proof.disposition === 'unresolved_blank',
      ),
    ).toBe(true);
    expect(
      fixture.rendered.verification.fields.some(
        (proof) => proof.disposition === 'preserved_unsupported',
      ),
    ).toBe(true);
  });

  it.each([
    ['native dropdown display', 'word/document.xml', '>Right<', '>Left<'],
    ['combo display', 'word/document.xml', '>Follow-up<', '>Initial<'],
    [
      'combo stored value',
      'word/document.xml',
      '</w:comboBox>',
      '<w:lastValue w:val="initial"/></w:comboBox>',
    ],
    [
      'narrative text',
      'word/document.xml',
      'Synthetic assessment',
      'Tampered assessment',
    ],
    ['date display', 'word/document.xml', '>2026-07-15<', '>2026-07-14<'],
    [
      'native checkbox state',
      'word/document.xml',
      'w14:checked w14:val="1"',
      'w14:checked w14:val="0"',
    ],
    [
      'legacy dropdown state',
      'word/document.xml',
      '<w:result w:val="1"/>',
      '<w:result w:val="2"/>',
    ],
    [
      'table cell',
      'word/document.xml',
      'Synthetic finding',
      'Tampered finding',
    ],
    ['header text', 'word/header1.xml', 'Synthetic Clinic', 'Tampered Clinic'],
  ])(
    'detects post-render tampering of %s',
    async (_name, part, before, after) => {
      const fixture = await renderFixture();
      const tampered = await replacePart(
        fixture.rendered.document,
        part,
        (xml) => xml.replace(before, after),
      );
      expect(() =>
        readbackTemplateDocxOutput({
          source: fixture.source,
          output: tampered,
          ir: fixture.ir,
          resolutions: fixture.resolutions,
        }),
      ).toThrowError(
        expect.objectContaining({ code: 'ROUNDTRIP_FIELD_MISMATCH' }),
      );
    },
  );

  it('detects duplicated stable control identities and unexpected occurrences', async () => {
    const fixture = await renderFixture();
    const xml = inspectDocxPackage(fixture.rendered.document)
      .zip.entries.get('word/document.xml')!
      .bytes.toString('utf8');
    const start = xml.indexOf('<w:sdt><w:sdtPr><w:id w:val="100"');
    const end = xml.indexOf('</w:sdt>', start) + '</w:sdt>'.length;
    const duplicated = await replacePart(
      fixture.rendered.document,
      'word/document.xml',
      (value) =>
        value.replace('<w:sectPr>', `${value.slice(start, end)}<w:sectPr>`),
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

  it('detects an appended Word SDT even when it lacks sdtPr identity metadata', async () => {
    const fixture = await renderFixture();
    const malformed =
      '<w:p><w:sdt><w:sdtContent><w:r><w:t>Synthetic unexpected control</w:t></w:r></w:sdtContent></w:sdt></w:p>';
    const tampered = await replacePart(
      fixture.rendered.document,
      'word/document.xml',
      (xml) => xml.replace('<w:sectPr>', `${malformed}<w:sectPr>`),
    );

    expect(() =>
      readbackTemplateDocxOutput({
        source: fixture.source,
        output: tampered,
        ir: fixture.ir,
        resolutions: fixture.resolutions,
      }),
    ).toThrowError(
      expect.objectContaining({ code: 'ROUNDTRIP_FIELD_MISMATCH' }),
    );
  });

  it('detects an appended malformed legacy form field with no supported ffData control', async () => {
    const fixture = await renderFixture();
    const malformed =
      '<w:p><w:r><w:fldChar w:fldCharType="begin"><w:ffData/></w:fldChar></w:r><w:r><w:instrText> FORMTEXT </w:instrText></w:r><w:r><w:fldChar w:fldCharType="end"/></w:r></w:p>';
    const tampered = await replacePart(
      fixture.rendered.document,
      'word/document.xml',
      (xml) => xml.replace('<w:sectPr>', `${malformed}<w:sectPr>`),
    );

    expect(() =>
      readbackTemplateDocxOutput({
        source: fixture.source,
        output: tampered,
        ir: fixture.ir,
        resolutions: fixture.resolutions,
      }),
    ).toThrowError(expect.objectContaining({ code: 'XML_INVALID' }));
  });

  it('preserves harmless complex Word fields but detects appended field markers', async () => {
    const harmlessField =
      '<w:p><w:r><w:fldChar w:fldCharType="begin"/></w:r><w:r><w:instrText> PAGE </w:instrText></w:r><w:r><w:fldChar w:fldCharType="separate"/></w:r><w:r><w:t>1</w:t></w:r><w:r><w:fldChar w:fldCharType="end"/></w:r></w:p>';
    const source = await buildSyntheticDocx({
      documentXml: syntheticOpc.documentXml.replace(
        '<w:sectPr>',
        `${harmlessField}<w:sectPr>`,
      ),
    });
    const fixture = await renderFixture(source);

    expect(() =>
      readbackTemplateDocxOutput({
        source: fixture.source,
        output: fixture.rendered.document,
        ir: fixture.ir,
        resolutions: fixture.resolutions,
      }),
    ).not.toThrow();

    const tampered = await replacePart(
      fixture.rendered.document,
      'word/document.xml',
      (xml) => xml.replace('<w:sectPr>', `${harmlessField}<w:sectPr>`),
    );
    expect(() =>
      readbackTemplateDocxOutput({
        source: fixture.source,
        output: tampered,
        ir: fixture.ir,
        resolutions: fixture.resolutions,
      }),
    ).toThrowError(
      expect.objectContaining({ code: 'ROUNDTRIP_FIELD_MISMATCH' }),
    );
  });

  it('clears Word placeholder state and PlaceholderText style only when populated', async () => {
    const documentXml = syntheticOpc.documentXml
      .replace(
        '<w:id w:val="102"/><w:alias w:val="Assessment narrative"/><w:text/>',
        '<w:id w:val="102"/><w:alias w:val="Assessment narrative"/><w:showingPlcHdr/><w:text/>',
      )
      .replace(
        '<w:t>Enter assessment</w:t>',
        '<w:rPr><w:rStyle w:val="PlaceholderText"/></w:rPr><w:t>Enter assessment</w:t>',
      )
      .replace(
        '<w:id w:val="108"/><w:alias w:val="Data-bound synthetic value"/><w:text/>',
        '<w:id w:val="108"/><w:alias w:val="Data-bound synthetic value"/><w:showingPlcHdr/><w:text/>',
      );
    const fixture = await renderFixture(
      await buildSyntheticDocx({ documentXml }),
    );
    const output = inspectDocxPackage(fixture.rendered.document)
      .zip.entries.get('word/document.xml')!
      .bytes.toString('utf8');
    const populated = controlById(output, '102');
    const unresolved = controlById(output, '108');
    expect(populated).not.toContain('showingPlcHdr');
    expect(populated).not.toContain('PlaceholderText');
    expect(unresolved).toContain('showingPlcHdr');
  });

  it('rejects placeholder metadata reintroduced after population', async () => {
    const fixture = await renderFixture();
    const tampered = await replacePart(
      fixture.rendered.document,
      'word/document.xml',
      (xml) =>
        xml.replace(
          '<w:id w:val="102"/><w:alias w:val="Assessment narrative"/>',
          '<w:id w:val="102"/><w:alias w:val="Assessment narrative"/><w:showingPlcHdr/>',
        ),
    );
    expect(() =>
      readbackTemplateDocxOutput({
        source: fixture.source,
        output: tampered,
        ir: fixture.ir,
        resolutions: fixture.resolutions,
      }),
    ).toThrowError(
      expect.objectContaining({ code: 'ROUNDTRIP_FIELD_MISMATCH' }),
    );
  });

  it('independently reads exact multi-select option values from displayed output', async () => {
    const source = await buildSyntheticDocx();
    const compiled = compileTemplateDocx(source);
    const field = compiled.fields.find(
      (candidate) => candidate.originalLabel === 'Assessment narrative',
    )!;
    const ir = {
      ...compiled,
      fields: compiled.fields.map((candidate) =>
        candidate.fieldId === field.fieldId
          ? {
              ...candidate,
              kind: 'multi_select' as const,
              allowedOptions: [
                { ordinal: 0, displayText: 'Alpha', value: 'alpha' },
                { ordinal: 1, displayText: 'Beta', value: 'beta' },
              ],
            }
          : { ...candidate, detectionStatus: 'unsupported' as const },
      ),
    } satisfies TemplateDocIR;
    const output = await replacePart(source, 'word/document.xml', (xml) =>
      xml.replace('Enter assessment', 'Alpha; Beta'),
    );
    const resolutions = ir.fields.map((candidate) =>
      candidate.fieldId === field.fieldId
        ? resolved(candidate, ['alpha', 'beta'])
        : resolved(candidate, null),
    );
    const proofs = readbackTemplateDocxOutput({
      source,
      output,
      ir,
      resolutions,
    });
    expect(
      proofs.find((proof) => proof.fieldId === field.fieldId),
    ).toMatchObject({
      disposition: 'rendered',
      occurrences: 1,
    });
  });

  it.each([
    ['number', '7', 7, '8'],
    [
      'measurement',
      '120 synthetic-unit',
      '120 synthetic-unit',
      '121 synthetic-unit',
    ],
  ] as const)(
    'independently derives and detects tampering of %s values',
    async (kind, display, expected, tamperedDisplay) => {
      const source = await buildSyntheticDocx();
      const compiled = compileTemplateDocx(source);
      const field = compiled.fields.find(
        (candidate) => candidate.originalLabel === 'Assessment narrative',
      )!;
      const ir = {
        ...compiled,
        fields: compiled.fields.map((candidate) =>
          candidate.fieldId === field.fieldId
            ? { ...candidate, kind }
            : { ...candidate, detectionStatus: 'unsupported' as const },
        ),
      } satisfies TemplateDocIR;
      const output = await replacePart(source, 'word/document.xml', (xml) =>
        xml.replace('Enter assessment', display),
      );
      const resolutions = ir.fields.map((candidate) =>
        candidate.fieldId === field.fieldId
          ? resolved(candidate, expected)
          : resolved(candidate, null),
      );
      expect(
        readbackTemplateDocxOutput({ source, output, ir, resolutions }).find(
          (proof) => proof.fieldId === field.fieldId,
        )?.disposition,
      ).toBe('rendered');

      const tampered = await replacePart(output, 'word/document.xml', (xml) =>
        xml.replace(display, tamperedDisplay),
      );
      expect(() =>
        readbackTemplateDocxOutput({
          source,
          output: tampered,
          ir,
          resolutions,
        }),
      ).toThrowError(
        expect.objectContaining({ code: 'ROUNDTRIP_FIELD_MISMATCH' }),
      );
    },
  );

  it('certification-blocks DrawingML compatibility text inside a plain Word control', async () => {
    const documentXml = syntheticOpc.documentXml.replace(
      '<w:r><w:t>Enter assessment</w:t></w:r>',
      '<w:r><w:t>Enter assessment</w:t></w:r><w:r><w:drawing><a:graphic xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"><a:t>Static drawing label</a:t></a:graphic></w:drawing></w:r>',
    );
    const ir = compileTemplateDocx(await buildSyntheticDocx({ documentXml }));
    expect(
      ir.fields.find((field) => field.originalLabel === 'Assessment narrative')
        ?.detectionStatus,
    ).toBe('unsupported');
    expect(ir.unsupported).toContainEqual(
      expect.objectContaining({
        code: 'CONTENT_CONTROL_TEXT_SHAPE_UNSUPPORTED',
        blocksCertification: true,
      }),
    );
  });
});

function controlById(xml: string, id: string): string {
  const marker = xml.indexOf(`<w:id w:val="${id}"`);
  const start = xml.lastIndexOf('<w:sdt>', marker);
  const end = xml.indexOf('</w:sdt>', marker);
  return xml.slice(start, end + '</w:sdt>'.length);
}
