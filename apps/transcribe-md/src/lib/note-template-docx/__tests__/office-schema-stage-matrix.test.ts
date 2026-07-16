import { readFile } from 'node:fs/promises';
import path from 'node:path';

import { describe, expect, it } from 'vitest';

const matrixPath = path.resolve(
  process.cwd(),
  '../../docs/qa/template-twin-office-schema-error-matrix.json',
);

interface SchemaMatrix {
  matrixContract: string;
  stageSummary: Array<{
    stage: string;
    errors?: number;
    physicalErrors?: number;
    result: string;
  }>;
  classificationSummary: Record<string, number>;
  policy: string;
  errors: Array<{
    findingId: string;
    stage: string;
    officeTargets: string[];
    ooxmlPart: string;
    namespaceAwareXPath: string;
    schemaRule: { validatorId: string; constraint: string };
    elementQName: string;
    attributeQName: string;
    firstIntroducedBy: string;
    sourceStageError: boolean;
    rendererStageError: boolean;
    requiredFixOrClassification: string;
  }>;
}

async function loadMatrix(): Promise<SchemaMatrix> {
  return JSON.parse(await readFile(matrixPath, 'utf8')) as SchemaMatrix;
}

describe('Template Twin Office schema-stage evidence', () => {
  it('proves source and immutable renderer packages were valid before Office', async () => {
    const matrix = await loadMatrix();

    expect(matrix.matrixContract).toBe(
      'template-twin-office-schema-stage-matrix/1.0.0',
    );
    expect(matrix.stageSummary).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          stage: 'synthetic_source_before_rendering',
          errors: 0,
          result: 'PASS',
        }),
        expect.objectContaining({
          stage: 'quillmd_rendered_before_libreoffice',
          errors: 0,
          result: 'PASS',
        }),
      ]),
    );
  });

  it('classifies every physical schema error at its first-introduction stage', async () => {
    const matrix = await loadMatrix();
    const officeStage = matrix.stageSummary.find(
      (stage) => stage.stage === 'libreoffice_saved',
    );

    expect(officeStage).toMatchObject({
      physicalErrors: 42,
      result: 'CLASSIFIED_EXTERNAL_TOOL_FAILURE_PENDING_WORD',
    });
    expect(matrix.classificationSummary).toEqual({
      FONT_CHARACTER_SET_EXTENSION: 20,
      LOGICAL_ALIGNMENT_ENUM: 19,
      TABLE_ROW_ON_OFF_LEXICAL_VALUE: 3,
    });
    expect(matrix.errors).toHaveLength(42);
    expect(new Set(matrix.errors.map((error) => error.findingId)).size).toBe(42);

    for (const error of matrix.errors) {
      expect(error.stage).toBe('libreoffice_saved');
      expect(error.officeTargets).toEqual(['Office2013', 'Microsoft365']);
      expect(error.ooxmlPart).toMatch(/^\/word\//);
      expect(error.namespaceAwareXPath).toContain(
        'Q{http://schemas.openxmlformats.org/wordprocessingml/2006/main}',
      );
      expect(error.schemaRule.validatorId).toBe(
        'Sch_AttributeValueDataTypeDetailed',
      );
      expect(error.schemaRule.constraint).toBe('attribute enumeration');
      expect(error.elementQName).toMatch(/^w:/);
      expect(error.attributeQName).toMatch(/^w:/);
      expect(error.firstIntroducedBy).toContain('LibreOffice 25.8.7.3');
      expect(error.sourceStageError).toBe(false);
      expect(error.rendererStageError).toBe(false);
      expect(error.requiredFixOrClassification).not.toHaveLength(0);
    }
  });

  it('forbids using a broad schema allowlist for immutable delivery output', async () => {
    const matrix = await loadMatrix();

    expect(matrix.policy).toContain(
      'Sources and immutable pre-delivery renderer outputs require zero errors.',
    );
    expect(matrix.policy).toContain('can never authorize signing or reimport');
  });
});
