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
import { renderTemplateDocx } from '../renderer';
import { buildSyntheticDocx, syntheticOpc } from './synthetic-docx';

const VALIDATION: TemplateTwinValidationResult = {
  valid: true,
  issues: [],
  checkedAt: '2026-07-15T20:00:00.000Z',
  validatorVersion: 'template-field-validator/1.0.0',
};

function unresolved(
  field: TemplateField,
  status: 'not_mentioned' | 'ambiguous' | 'conflict' = 'not_mentioned',
): FieldResolution {
  return FieldResolutionSchema.parse({
    fieldId: field.fieldId,
    status,
    value: null,
    sourceFactIds: status === 'not_mentioned' ? [] : [`ttfact_${'c'.repeat(24)}`],
    evidenceAnchorIds: status === 'not_mentioned' ? [] : ['synthetic-conflict-anchor'],
    selectedOptionOrdinal: null,
    reasonCode: `synthetic_${status}`,
    clinicianReviewed: false,
  });
}

function resolvedCheckbox(
  field: TemplateField,
  value: boolean,
  status: 'supported' | 'explicitly_denied' = value
    ? 'supported'
    : 'explicitly_denied',
): FieldResolution {
  return FieldResolutionSchema.parse({
    fieldId: field.fieldId,
    status,
    value,
    sourceFactIds: [`ttfact_${(value ? 'a' : 'b').repeat(24)}`],
    evidenceAnchorIds: [
      value ? 'synthetic-affirmed-anchor' : 'synthetic-denied-anchor',
    ],
    selectedOptionOrdinal: null,
    reasonCode: value ? 'synthetic_affirmed' : 'synthetic_explicit_denial',
    clinicianReviewed: false,
  });
}

function allUnresolved(
  ir: TemplateDocIR,
  checkboxStatus: 'not_mentioned' | 'ambiguous' | 'conflict' = 'not_mentioned',
): FieldResolution[] {
  return ir.fields.map((field) =>
    field.kind === 'checkbox'
      ? unresolved(field, checkboxStatus)
      : unresolved(field),
  );
}

function xmlFrom(document: Uint8Array): string {
  return inspectDocxPackage(document).zip.entries
    .get('word/document.xml')!
    .bytes.toString('utf8');
}

function contentControlById(xml: string, id: string): string {
  const identity = xml.indexOf(`<w:id w:val="${id}"`);
  if (identity < 0) throw new Error('Synthetic control missing');
  const start = xml.lastIndexOf('<w:sdt>', identity);
  const end = xml.indexOf('</w:sdt>', identity);
  if (start < 0 || end < 0) throw new Error('Synthetic control malformed');
  return xml.slice(start, end + '</w:sdt>'.length);
}

function paragraphContaining(xml: string, needle: string): string {
  const identity = xml.indexOf(needle);
  if (identity < 0) throw new Error('Synthetic legacy field missing');
  const start = xml.lastIndexOf('<w:p>', identity);
  const end = xml.indexOf('</w:p>', identity);
  if (start < 0 || end < 0) throw new Error('Synthetic legacy field malformed');
  return xml.slice(start, end + '</w:p>'.length);
}

describe('Template Twin checkbox tri-state rendering', () => {
  it.each(['not_mentioned', 'ambiguous', 'conflict'] as const)(
    'preserves a native checked control for unresolved status %s',
    async (status) => {
      const documentXml = syntheticOpc.documentXml
        .replace('w14:checked w14:val="0"', 'w14:checked w14:val="1"')
        .replace('<w:t>☐</w:t>', '<w:t>☒</w:t>');
      const source = await buildSyntheticDocx({ documentXml });
      const ir = compileTemplateDocx(source);
      const rendered = await renderTemplateDocx({
        source,
        ir,
        resolutions: allUnresolved(ir, status),
        validation: VALIDATION,
      });

      expect(contentControlById(xmlFrom(rendered.document), '104')).toBe(
        contentControlById(xmlFrom(source), '104'),
      );
    },
  );

  it('renders native true and physician-certified explicit false distinctly', async () => {
    const source = await buildSyntheticDocx();
    const ir = compileTemplateDocx(source);
    const checkbox = ir.fields.find(
      (field) => field.originalLabel === 'Medication reviewed',
    )!;
    const trueOutput = await renderTemplateDocx({
      source,
      ir,
      resolutions: allUnresolved(ir).map((resolution) =>
        resolution.fieldId === checkbox.fieldId
          ? resolvedCheckbox(checkbox, true)
          : resolution,
      ),
      validation: VALIDATION,
    });
    expect(contentControlById(xmlFrom(trueOutput.document), '104')).toContain(
      'w14:checked w14:val="1"',
    );
    expect(contentControlById(xmlFrom(trueOutput.document), '104')).toContain('☒');

    const checkedSource = await buildSyntheticDocx({
      documentXml: syntheticOpc.documentXml
        .replace('w14:checked w14:val="0"', 'w14:checked w14:val="1"')
        .replace('<w:t>☐</w:t>', '<w:t>☒</w:t>'),
    });
    const checkedIr = compileTemplateDocx(checkedSource);
    const checkedField = checkedIr.fields.find(
      (field) => field.originalLabel === 'Medication reviewed',
    )!;
    const falseOutput = await renderTemplateDocx({
      source: checkedSource,
      ir: checkedIr,
      resolutions: allUnresolved(checkedIr).map((resolution) =>
        resolution.fieldId === checkedField.fieldId
          ? resolvedCheckbox(checkedField, false)
          : resolution,
      ),
      validation: VALIDATION,
    });
    expect(contentControlById(xmlFrom(falseOutput.document), '104')).toContain(
      'w14:checked w14:val="0"',
    );
    expect(contentControlById(xmlFrom(falseOutput.document), '104')).toContain('☐');
  });

  it('preserves an unresolved legacy checkbox and renders only explicit false', async () => {
    const legacy = `<w:p><w:r><w:fldChar w:fldCharType="begin"><w:ffData><w:name w:val="Legacy synthetic consent"/><w:checkBox><w:default w:val="1"/><w:checked w:val="1"/></w:checkBox></w:ffData></w:fldChar></w:r><w:r><w:instrText> FORMCHECKBOX </w:instrText></w:r><w:r><w:fldChar w:fldCharType="separate"/></w:r><w:r><w:t>☒</w:t></w:r><w:r><w:fldChar w:fldCharType="end"/></w:r></w:p>`;
    const source = await buildSyntheticDocx({
      documentXml: syntheticOpc.documentXml.replace('<w:sectPr>', `${legacy}<w:sectPr>`),
    });
    const ir = compileTemplateDocx(source);
    const field = ir.fields.find(
      (candidate) => candidate.originalLabel === 'Legacy synthetic consent',
    )!;
    expect(field.rendererBinding.bindingType).toBe('legacy_form_field');

    const unresolvedOutput = await renderTemplateDocx({
      source,
      ir,
      resolutions: allUnresolved(ir),
      validation: VALIDATION,
    });
    expect(
      paragraphContaining(xmlFrom(unresolvedOutput.document), 'Legacy synthetic consent'),
    ).toBe(paragraphContaining(xmlFrom(source), 'Legacy synthetic consent'));

    const deniedOutput = await renderTemplateDocx({
      source,
      ir,
      resolutions: allUnresolved(ir).map((resolution) =>
        resolution.fieldId === field.fieldId
          ? resolvedCheckbox(field, false)
          : resolution,
      ),
      validation: VALIDATION,
    });
    const deniedParagraph = paragraphContaining(
      xmlFrom(deniedOutput.document),
      'Legacy synthetic consent',
    );
    expect(deniedParagraph).toContain('<w:checked w:val="0"/>');
    expect(deniedParagraph).toContain('<w:t>☐</w:t>');
  });

  it('rejects a tampered false checkbox that is mislabeled as supported', async () => {
    const source = await buildSyntheticDocx();
    const ir = compileTemplateDocx(source);
    const field = ir.fields.find((candidate) => candidate.kind === 'checkbox')!;

    await expect(
      renderTemplateDocx({
        source,
        ir,
        resolutions: allUnresolved(ir).map((resolution) =>
          resolution.fieldId === field.fieldId
            ? resolvedCheckbox(field, false, 'supported')
            : resolution,
        ),
        validation: VALIDATION,
      }),
    ).rejects.toMatchObject({ code: 'FIELD_RESOLUTION_INVALID' });
  });
});
