import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

import { describe, expect, it } from 'vitest';

import {
  FieldResolutionSchema,
  type FieldResolution,
  type TemplateField,
} from '../../template-twin/ir';
import { compileTemplateDocx } from '../compiler';
import { inspectDocxPackage } from '../package-security';
import { renderTemplateDocx } from '../renderer';
import {
  WORDPROCESSINGML_NAMESPACE,
  expandedXmlVisits,
  parseOrderedXml,
} from '../xml';

const EXISTING_FIXTURE = resolve(
  process.cwd(),
  process.cwd().endsWith('/apps/transcribe-md')
    ? '../../WM IOV Template.docx'
    : 'WM IOV Template.docx',
);

describe('existing WM IOV Template.docx read-only compatibility audit', () => {
  it(
    'recognizes its placeholder controls without copying or committing another document',
    async () => {
      const source = readFileSync(EXISTING_FIXTURE);
      const inspected = inspectDocxPackage(source);
      let placeholderControls = 0;
      for (const partName of [
        inspected.mainPartName,
        ...inspected.headerPartNames,
        ...inspected.footerPartNames,
      ]) {
        const entry = inspected.zip.entries.get(partName)!;
        placeholderControls += expandedXmlVisits(
          parseOrderedXml(entry.bytes, inspected.limits),
        ).filter(
          (visit) =>
            visit.namespaceUri === WORDPROCESSINGML_NAMESPACE &&
            visit.localName === 'showingPlcHdr',
        ).length;
      }
      const ir = compileTemplateDocx(source);

      expect(placeholderControls).toBe(28);
      expect(ir.fields.length).toBe(28);
      expect(ir.stats).toMatchObject({
        dropdowns: 28,
        comboBoxes: 0,
        checkboxes: 0,
        dateControls: 0,
        tables: 1,
        repeatingTables: 0,
        headers: 2,
        footers: 0,
        unsupported: 59,
        blockingUnsupported: 59,
      });
      expect([...new Set(ir.unsupported.map((item) => item.code))].sort()).toEqual([
        'UNBOUND_COMPLEX_TABLE_CELL',
        'UNBOUND_ORDINARY_PLACEHOLDER',
      ]);
      expect(
        ir.unsupported.filter(
          (item) => item.code === 'UNBOUND_COMPLEX_TABLE_CELL',
        ),
      ).toHaveLength(52);
      expect(
        ir.unsupported.filter(
          (item) => item.code === 'UNBOUND_ORDINARY_PLACEHOLDER',
        ),
      ).toHaveLength(7);

      const resolutions = ir.fields.map(fixtureResolution);
      const rendered = await renderTemplateDocx({
        source,
        ir,
        resolutions,
        validation: {
          valid: true,
          issues: [],
          checkedAt: '2026-07-15T00:00:00.000Z',
          validatorVersion: 'template-field-validator/1.0.0',
        },
      });
      let renderedPlaceholders = 0;
      const output = inspectDocxPackage(rendered.document);
      for (const partName of [
        output.mainPartName,
        ...output.headerPartNames,
        ...output.footerPartNames,
      ]) {
        renderedPlaceholders += expandedXmlVisits(
          parseOrderedXml(output.zip.entries.get(partName)!.bytes, output.limits),
        ).filter(
          (visit) =>
            visit.namespaceUri === WORDPROCESSINGML_NAMESPACE &&
            visit.localName === 'showingPlcHdr',
        ).length;
      }
      expect(renderedPlaceholders).toBe(0);
      expect(rendered.verification.fields).toHaveLength(ir.fields.length);
      expect(rendered.verification.staticRegionCheck).toBe('verified');
    },
  );
});

const FIXTURE_FACT = `ttfact_${'d'.repeat(24)}`;

function fixtureResolution(field: TemplateField): FieldResolution {
  let value: FieldResolution['value'];
  let selectedOptionOrdinal: number | null = null;
  switch (field.kind) {
    case 'single_select':
      value = field.allowedOptions[0]!.value;
      selectedOptionOrdinal = field.allowedOptions[0]!.ordinal;
      break;
    case 'multi_select':
      value = [field.allowedOptions[0]!.value];
      break;
    case 'checkbox':
      value = true;
      break;
    case 'date':
      value = '2026-07-15';
      break;
    case 'number':
      value = 1;
      break;
    case 'measurement':
      value = '1 synthetic-unit';
      break;
    case 'narrative_text':
      value = 'Synthetic QA value';
      break;
  }
  return FieldResolutionSchema.parse({
    fieldId: field.fieldId,
    status: 'supported',
    value,
    sourceFactIds: [FIXTURE_FACT],
    evidenceAnchorIds: ['synthetic-wm-fixture-anchor'],
    selectedOptionOrdinal,
    reasonCode: 'synthetic_fixture_evidence',
    clinicianReviewed: false,
  });
}
