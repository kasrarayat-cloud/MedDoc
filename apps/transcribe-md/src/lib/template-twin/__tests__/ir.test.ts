import { describe, expect, it } from 'vitest';

import {
  FieldResolutionSchema,
  TEMPLATE_TWIN_COMPILER_VERSION,
  TEMPLATE_TWIN_IR_SCHEMA_VERSION,
  TemplateDocIRSchema,
  templateTwinCounts,
  type TemplateDocIR,
} from '../ir';

const SHA = 'a'.repeat(64);
const FIELD_ID = `ttf_${'b'.repeat(24)}`;

function validIr(): TemplateDocIR {
  return {
    irSchemaVersion: TEMPLATE_TWIN_IR_SCHEMA_VERSION,
    compilerVersion: TEMPLATE_TWIN_COMPILER_VERSION,
    source: {
      sha256: SHA,
      sizeBytes: 1024,
      mimeType:
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    },
    parts: [
      {
        partName: '[Content_Types].xml',
        contentType: 'application/xml',
        kind: 'other',
        sha256: SHA,
        staticSha256: SHA,
        relationshipCount: 0,
      },
      {
        partName: '_rels/.rels',
        contentType: 'application/vnd.openxmlformats-package.relationships+xml',
        kind: 'relationships',
        sha256: SHA,
        staticSha256: SHA,
        relationshipCount: 1,
      },
      {
        partName: 'word/document.xml',
        contentType:
          'application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml',
        kind: 'document',
        sha256: SHA,
        staticSha256: SHA,
        relationshipCount: 0,
      },
    ],
    nodes: [
      {
        nodeId: `ttn_${'c'.repeat(20)}`,
        partName: 'word/document.xml',
        path: '/document/body/sdt[0]',
        displayOrder: 0,
        kind: 'single_select',
        fieldId: FIELD_ID,
        tableId: null,
        staticTextSha256: null,
        bookmarkNames: [],
      },
    ],
    fields: [
      {
        fieldId: FIELD_ID,
        kind: 'single_select',
        originalLabel: 'Synthetic status',
        labelSource: 'alias',
        displayOrder: 0,
        detectionStatus: 'recognized',
        allowedOptions: [
          { ordinal: 0, displayText: 'Absent', value: 'absent' },
          { ordinal: 1, displayText: 'Present', value: 'present' },
        ],
        rendererBinding: {
          partName: 'word/document.xml',
          bindingType: 'content_control',
          path: '/document/body/sdt[0]',
          canonicalPath: '/document/body/sdt[0]',
          ordinal: 0,
          sdtId: '101',
          tag: 'synthetic_status',
          alias: 'Synthetic status',
          legacyName: null,
          tableIndex: null,
          rowIndex: null,
          cellIndex: null,
          repeatAncestorPath: null,
          canonicalRepeatAncestorPath: null,
          sourceControlSha256: SHA,
          sourceBindingIdentitySha256: SHA,
          certifiedBindingSha256: SHA,
          originalContentSha256: SHA,
        },
        required: false,
        unknownPolicy: 'blank',
        clinicallyMaterial: true,
        criticality: 'routine',
        tableId: null,
        rowPrototype: false,
      },
    ],
    tables: [],
    unsupported: [],
    structureSha256: SHA,
    staticContentSha256: SHA,
    stats: {
      totalFields: 1,
      dropdowns: 1,
      comboBoxes: 0,
      checkboxes: 0,
      dateControls: 0,
      tables: 0,
      repeatingTables: 0,
      headers: 0,
      footers: 0,
      unsupported: 0,
      blockingUnsupported: 0,
    },
  };
}

describe('TemplateDocIRSchema', () => {
  it('accepts a versioned deterministic field binding', () => {
    expect(TemplateDocIRSchema.parse(validIr()).fields[0].fieldId).toBe(
      FIELD_ID,
    );
  });

  it('rejects select fields that lost their native options', () => {
    const ir = validIr();
    ir.fields[0].allowedOptions = [];
    expect(TemplateDocIRSchema.safeParse(ir).success).toBe(false);
  });

  it('rejects duplicate stable field identifiers', () => {
    const ir = validIr();
    ir.fields.push({ ...ir.fields[0], displayOrder: 1 });
    expect(TemplateDocIRSchema.safeParse(ir).success).toBe(false);
  });

  it('rejects the tab-only table profile on a non-table binding', () => {
    const ir = validIr();
    ir.fields[0]!.rendererBinding.bindingProfile =
      'TAB_ONLY_BLANK_TABLE_CELL_V1';

    expect(TemplateDocIRSchema.safeParse(ir).success).toBe(false);
  });
});

describe('evidence contract', () => {
  it.each(['supported', 'approved_practice_default'] as const)(
    'requires facts and anchors for every populated %s value',
    (status) => {
      const result = FieldResolutionSchema.safeParse({
        fieldId: FIELD_ID,
        status,
        value: 'Present',
        sourceFactIds: [],
        evidenceAnchorIds: [],
        selectedOptionOrdinal: 1,
        reasonCode: 'exact_option_evidence',
        clinicianReviewed: false,
      });
      expect(result.success).toBe(false);
    },
  );
  it('counts critical unresolved fields independently of filled values', () => {
    const fields = [
      FieldResolutionSchema.parse({
        fieldId: FIELD_ID,
        status: 'conflict',
        value: null,
        sourceFactIds: [],
        evidenceAnchorIds: [],
        selectedOptionOrdinal: null,
        reasonCode: 'conflicting_evidence',
        clinicianReviewed: false,
      }),
    ];
    const definitions = validIr().fields.map((field) => ({
      ...field,
      criticality: 'allergy' as const,
    }));
    expect(templateTwinCounts(fields, definitions)).toEqual({
      filled: 0,
      needsReview: 1,
      notMentioned: 0,
      conflicts: 1,
      criticalUnresolved: 1,
    });
  });
});
