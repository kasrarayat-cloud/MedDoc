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
import { readbackTemplateDocxOutput } from '../output-readback';
import { renderTemplateDocx } from '../renderer';
import { buildSyntheticDocx, syntheticOpc } from './synthetic-docx';

const FACT_ID = `ttfact_${'b'.repeat(24)}`;
const VALIDATION: TemplateTwinValidationResult = {
  valid: true,
  issues: [],
  checkedAt: '2026-07-16T00:00:00.000Z',
  validatorVersion: 'template-field-validator/1.0.0',
};

function resolution(
  field: TemplateField,
  value: FieldResolution['value'],
  selectedOptionOrdinal: number | null = null,
): FieldResolution {
  return FieldResolutionSchema.parse({
    fieldId: field.fieldId,
    status: value === null ? 'not_mentioned' : 'supported',
    value,
    sourceFactIds: value === null ? [] : [FACT_ID],
    evidenceAnchorIds: value === null ? [] : ['synthetic-binding-anchor'],
    selectedOptionOrdinal,
    reasonCode: value === null ? 'synthetic_not_mentioned' : 'synthetic_supported',
    clinicianReviewed: false,
  });
}

function resolutionsFor(
  ir: TemplateDocIR,
  values: ReadonlyMap<string, FieldResolution['value']>,
): FieldResolution[] {
  return ir.fields.map((field) => {
    const value = values.get(field.originalLabel) ?? null;
    const option =
      value === null
        ? null
        : field.allowedOptions.find((candidate) => candidate.value === value)
            ?.ordinal ?? null;
    return resolution(field, value, option);
  });
}

async function renderedFixture(
  providedSource?: Buffer,
  values = new Map<string, FieldResolution['value']>([
    ['Assessment narrative', 'Same synthetic assessment'],
  ]),
) {
  const source = providedSource ?? (await buildSyntheticDocx());
  const ir = compileTemplateDocx(source);
  const resolutions = resolutionsFor(ir, values);
  const rendered = await renderTemplateDocx({
    source,
    ir,
    resolutions,
    validation: VALIDATION,
  });
  return { source, ir, resolutions, rendered };
}

async function mutateParts(
  source: Uint8Array,
  mutations: Readonly<Record<string, (xml: string) => string>>,
): Promise<Buffer> {
  const zip = await JSZip.loadAsync(source);
  for (const [partName, mutate] of Object.entries(mutations)) {
    const entry = zip.file(partName);
    if (!entry) throw new Error(`Synthetic part ${partName} is missing.`);
    const before = await entry.async('string');
    const after = mutate(before);
    if (before === after) throw new Error(`Mutation for ${partName} was a no-op.`);
    zip.file(partName, after);
  }
  return zip.generateAsync({ type: 'nodebuffer', compression: 'DEFLATE' });
}

function elementContaining(xml: string, marker: string, element: string): string {
  const markerIndex = xml.indexOf(marker);
  const start = xml.lastIndexOf(`<w:${element}>`, markerIndex);
  const end = xml.indexOf(`</w:${element}>`, markerIndex);
  if (markerIndex < 0 || start < 0 || end < 0) {
    throw new Error(`Synthetic ${element} containing ${marker} is missing.`);
  }
  return xml.slice(start, end + `</w:${element}>`.length);
}

function expectReadbackMismatch(
  fixture: Awaited<ReturnType<typeof renderedFixture>>,
  output: Uint8Array,
): void {
  expect(() =>
    readbackTemplateDocxOutput({
      source: fixture.source,
      output,
      ir: fixture.ir,
      resolutions: fixture.resolutions,
    }),
  ).toThrowError(expect.objectContaining({ code: 'ROUNDTRIP_FIELD_MISMATCH' }));
}

describe('certified output-derived field identity and path binding', () => {
  it('rejects an SDT moved with the same ID, alias, and value to another paragraph', async () => {
    const fixture = await renderedFixture();
    const tampered = await mutateParts(fixture.rendered.document, {
      'word/document.xml': (xml) => {
        const control = elementContaining(xml, 'w:id w:val="102"', 'sdt');
        return xml
          .replace(control, '')
          .replace('<w:sectPr>', `<w:p>${control}</w:p><w:sectPr>`);
      },
    });
    expectReadbackMismatch(fixture, tampered);
  });

  it('rejects an SDT reordered across a differently named sibling in the same parent', async () => {
    const fixture = await renderedFixture();
    const tampered = await mutateParts(fixture.rendered.document, {
      'word/document.xml': (xml) => {
        const paragraph = elementContaining(xml, 'w:id w:val="100"', 'p');
        const control = elementContaining(paragraph, 'w:id w:val="100"', 'sdt');
        const reordered = paragraph
          .replace(control, '')
          .replace('<w:p>', `<w:p>${control}`);
        return xml.replace(paragraph, reordered);
      },
    });
    expectReadbackMismatch(fixture, tampered);
  });

  it('rejects an SDT moved with unchanged identity and value into another table cell', async () => {
    const fixture = await renderedFixture();
    const tampered = await mutateParts(fixture.rendered.document, {
      'word/document.xml': (xml) => {
        const control = elementContaining(xml, 'w:id w:val="102"', 'sdt');
        return xml
          .replace(control, '')
          .replace('<w:tc><w:p/></w:tc>', `<w:tc><w:p>${control}</w:p></w:tc>`);
      },
    });
    expectReadbackMismatch(fixture, tampered);
  });

  it.each([
    ['word/header1.xml', '</w:hdr>'],
    ['word/footer1.xml', '</w:ftr>'],
  ])('rejects an SDT moved between the body and %s', async (targetPart, closingTag) => {
    const fixture = await renderedFixture();
    let movedControl = '';
    const tampered = await mutateParts(fixture.rendered.document, {
      'word/document.xml': (xml) => {
        movedControl = elementContaining(xml, 'w:id w:val="102"', 'sdt');
        return xml.replace(movedControl, '');
      },
      [targetPart]: (xml) => xml.replace(closingTag, `<w:p>${movedControl}</w:p>${closingTag}`),
    });
    expectReadbackMismatch(fixture, tampered);
  });

  it('rejects two same-valued fields swapped while retaining native IDs', async () => {
    const secondControl =
      '<w:p><w:sdt><w:sdtPr><w:id w:val="109"/><w:alias w:val="Second assessment narrative"/><w:text/></w:sdtPr><w:sdtContent><w:r><w:t>Enter second assessment</w:t></w:r></w:sdtContent></w:sdt></w:p>';
    const source = await buildSyntheticDocx({
      documentXml: syntheticOpc.documentXml.replace(
        '<w:sectPr>',
        `${secondControl}<w:sectPr>`,
      ),
    });
    const fixture = await renderedFixture(
      source,
      new Map([
        ['Assessment narrative', 'Same synthetic assessment'],
        ['Second assessment narrative', 'Same synthetic assessment'],
      ]),
    );
    const tampered = await mutateParts(fixture.rendered.document, {
      'word/document.xml': (xml) => {
        const first = elementContaining(xml, 'w:id w:val="102"', 'sdt');
        const second = elementContaining(xml, 'w:id w:val="109"', 'sdt');
        return xml
          .replace(first, '__FIRST_SYNTHETIC_CONTROL__')
          .replace(second, first)
          .replace('__FIRST_SYNTHETIC_CONTROL__', second);
      },
    });
    expectReadbackMismatch(fixture, tampered);
  });

  it('rejects a duplicate stable field occurrence at another path', async () => {
    const fixture = await renderedFixture();
    const tampered = await mutateParts(fixture.rendered.document, {
      'word/document.xml': (xml) => {
        const control = elementContaining(xml, 'w:id w:val="102"', 'sdt');
        return xml.replace('<w:sectPr>', `<w:p>${control}</w:p><w:sectPr>`);
      },
    });
    expectReadbackMismatch(fixture, tampered);
  });

  it('rejects a moved legacy field even when its legacy name is retained', async () => {
    const fixture = await renderedFixture();
    const tampered = await mutateParts(fixture.rendered.document, {
      'word/document.xml': (xml) => {
        const paragraph = elementContaining(xml, 'w:val="Legacy severity"', 'p');
        return xml
          .replace(paragraph, '')
          .replace('<w:sectPr>', `${paragraph}<w:sectPr>`);
      },
    });
    expectReadbackMismatch(fixture, tampered);
  });

  it('rejects an IR whose certified binding ordinal alone was changed', async () => {
    const fixture = await renderedFixture();
    const target = fixture.ir.fields.find(
      (field) => field.originalLabel === 'Assessment narrative',
    )!;
    const tamperedIr: TemplateDocIR = {
      ...fixture.ir,
      fields: fixture.ir.fields.map((field) =>
        field.fieldId === target.fieldId
          ? {
              ...field,
              rendererBinding: {
                ...field.rendererBinding,
                ordinal: field.rendererBinding.ordinal + 1,
              },
            }
          : field,
      ),
    };
    expect(() =>
      readbackTemplateDocxOutput({
        source: fixture.source,
        output: fixture.rendered.document,
        ir: tamperedIr,
        resolutions: fixture.resolutions,
      }),
    ).toThrowError(expect.objectContaining({ code: 'ROUNDTRIP_FIELD_MISMATCH' }));
  });

  it('accepts an unchanged rendered document with one output-derived proof per field', async () => {
    const fixture = await renderedFixture();
    const proofs = readbackTemplateDocxOutput({
      source: fixture.source,
      output: fixture.rendered.document,
      ir: fixture.ir,
      resolutions: fixture.resolutions,
    });
    expect(proofs).toHaveLength(fixture.ir.fields.length);
    expect(
      proofs.every(
        (proof) =>
          proof.bindingEvidence?.status === 'verified' &&
          proof.bindingEvidence.certifiedFingerprintSha256 ===
            proof.bindingEvidence.outputFingerprintSha256,
      ),
    ).toBe(true);
  });

  it('accepts a legitimate value change while preserving certified path identity', async () => {
    const source = await buildSyntheticDocx();
    const first = await renderedFixture(
      source,
      new Map([['Assessment narrative', 'First synthetic assessment']]),
    );
    const second = await renderedFixture(
      source,
      new Map([['Assessment narrative', 'Second synthetic assessment']]),
    );
    const fieldId = first.ir.fields.find(
      (field) => field.originalLabel === 'Assessment narrative',
    )!.fieldId;
    const firstProof = first.rendered.verification.fields.find(
      (field) => field.fieldId === fieldId,
    )!;
    const secondProof = second.rendered.verification.fields.find(
      (field) => field.fieldId === fieldId,
    )!;
    expect(secondProof.bindingEvidence).toEqual(firstProof.bindingEvidence);
    expect(secondProof.valueSha256).not.toBe(firstProof.valueSha256);
  });
});
