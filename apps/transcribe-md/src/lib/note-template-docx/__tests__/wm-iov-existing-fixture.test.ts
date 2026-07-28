import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

import { describe, expect, it } from 'vitest';

import {
  FieldResolutionSchema,
  type FieldResolution,
  type TemplateField,
} from '../../template-twin/ir';
import { assertTemplateTwinSourcePhiFree } from '../../template-twin/source-phi';
import {
  ORDINARY_PLACEHOLDER_TOKEN_PROFILE,
  TAB_ONLY_BLANK_TABLE_CELL_PROFILE,
  compileTemplateDocx,
} from '../compiler';
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
  it('recognizes its placeholder controls without copying or committing another document', async () => {
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
    expect(ir.fields.length).toBe(87);
    expect(ir.stats).toMatchObject({
      dropdowns: 28,
      comboBoxes: 0,
      checkboxes: 0,
      dateControls: 0,
      tables: 1,
      repeatingTables: 0,
      headers: 2,
      footers: 0,
      unsupported: 0,
      blockingUnsupported: 0,
    });
    expect(ir.unsupported).toEqual([]);
    expect(
      ir.unsupported.filter(
        (item) => item.code === 'UNBOUND_COMPLEX_TABLE_CELL',
      ),
    ).toHaveLength(0);
    const recognizedPlaceholders = ir.fields.filter(
      (field) => field.rendererBinding.bindingType === 'ordinary_placeholder',
    );
    expect(recognizedPlaceholders).toHaveLength(7);
    expect(
      recognizedPlaceholders.every(
        (field) =>
          field.detectionStatus === 'needs_confirmation' &&
          field.rendererBinding.bindingProfile ===
            ORDINARY_PLACEHOLDER_TOKEN_PROFILE &&
          field.rendererBinding.ordinaryPlaceholder?.clinicalMappingStatus ===
            'needs_confirmation',
      ),
    ).toBe(true);

    const admittedTabStopCells = ir.fields.filter(
      (field) => field.rendererBinding.bindingType === 'table_cell',
    );
    expect(admittedTabStopCells).toHaveLength(52);
    expect(
      new Set(
        admittedTabStopCells.map(
          (field) => field.rendererBinding.canonicalPath,
        ),
      ).size,
    ).toBe(52);
    expect(
      admittedTabStopCells.every(
        (field) =>
          field.detectionStatus === 'needs_confirmation' &&
          field.rendererBinding.bindingProfile ===
            TAB_ONLY_BLANK_TABLE_CELL_PROFILE,
      ),
    ).toBe(true);
    expect(80 + recognizedPlaceholders.length).toBe(87);

    const packagePartNames = [...inspected.zip.entries.keys()];
    expect(
      packagePartNames.filter((partName) =>
        partName.startsWith('word/glossary/'),
      ),
    ).toHaveLength(6);
    expect(
      packagePartNames.filter((partName) => partName.startsWith('word/media/')),
    ).toHaveLength(1);
    let providerCalled = false;
    await expect(
      assertTemplateTwinSourcePhiFree({
        source,
        practiceId: 'practice_wm_iov_synthetic_test',
        userId: 'user_wm_iov_synthetic_test',
        client: {
          complete: async () => {
            providerCalled = true;
            throw new Error('The provider must not run for a blocked package.');
          },
        },
      }),
    ).rejects.toMatchObject({
      code: 'TEMPLATE_TWIN_SOURCE_PRIVACY_UNSUPPORTED',
    });
    expect(providerCalled).toBe(false);

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
  }, 60_000);
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
