import { createHash } from 'node:crypto';

import { beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  modelComplete: vi.fn(),
  findSystemTemplate: vi.fn(),
  noteTemplateCreate: vi.fn(),
  sourceArtifactCreate: vi.fn(),
  compiledVersionCreate: vi.fn(),
  quarantineCreate: vi.fn(),
  transaction: vi.fn(),
  logAudit: vi.fn(),
}));

vi.mock('@meddoc/ai', () => ({
  delimiterSystemSuffix: () => '',
  wrapAsData: (value: string) => ({
    wrapped: value,
    injectionAttemptDetected: false,
  }),
  modelClient: { complete: mocks.modelComplete },
}));

vi.mock('@meddoc/db', () => {
  const tx = {
    noteTemplate: { create: mocks.noteTemplateCreate },
    templateTwinSourceArtifact: { create: mocks.sourceArtifactCreate },
    templateTwinCompiledVersion: { create: mocks.compiledVersionCreate },
  };
  const prisma = {
    noteTemplate: { findFirst: mocks.findSystemTemplate },
    templateTwinSourceArtifact: { create: mocks.quarantineCreate },
    $transaction: mocks.transaction,
  };
  mocks.transaction.mockImplementation(
    async (callback: (client: unknown) => Promise<unknown>) => callback(tx),
  );
  return { default: prisma, prisma };
});

vi.mock('@/lib/audit', () => ({ logAudit: mocks.logAudit }));

import { createTemplateTwinDraft } from '../create-draft';
import type { TemplateTwinArtifactStore } from '../storage';
import { buildTemplateTwinIntegrationFixture } from './integration-fixture';

beforeEach(() => {
  vi.clearAllMocks();
  mocks.transaction.mockImplementation(
    async (callback: (client: unknown) => Promise<unknown>) =>
      callback({
        noteTemplate: { create: mocks.noteTemplateCreate },
        templateTwinSourceArtifact: { create: mocks.sourceArtifactCreate },
        templateTwinCompiledVersion: { create: mocks.compiledVersionCreate },
      }),
  );
  mocks.findSystemTemplate.mockResolvedValue({
    sections: [{ key: 'subjective', label: 'Subjective', order: 1 }],
    styleProfile: { tone: 'concise' },
    specialtyBaseline: null,
  });
  mocks.noteTemplateCreate.mockResolvedValue({ id: 'template-synthetic-1' });
  mocks.sourceArtifactCreate.mockResolvedValue({ id: 'source-synthetic-1' });
  mocks.compiledVersionCreate.mockResolvedValue({ id: 'compiled-synthetic-1' });
  mocks.logAudit.mockResolvedValue(undefined);
});

describe('Template Twin upload/compile proposal orchestration', () => {
  it('uses the shared model boundary, immutable storage, and one Prisma transaction', async () => {
    const fixture = await buildTemplateTwinIntegrationFixture();
    mocks.modelComplete.mockImplementation(
      async (request: { purpose: string }) => {
        if (request.purpose === 'tm_template_phi_scan') {
          return { phiFields: [], anyUncertain: false };
        }
        if (request.purpose === 'tm_template_parse') {
          return {
            mappings: fixture.mappings.map((mapping) => ({
              ...mapping,
              status: 'recognized',
              practiceDefault: null,
            })),
          };
        }
        throw new Error('Unexpected synthetic model purpose');
      },
    );

    const digest = createHash('sha256').update(fixture.source).digest('hex');
    const storeSourceArtifact = vi.fn().mockResolvedValue({
      bucket: 'synthetic-template-artifacts',
      objectKey: `practices/practice-synthetic-1/template-twin/sources/lineage/v1/artifact/${digest}.docx`,
      sha256: digest,
      mimeType:
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
      sizeBytes: fixture.source.byteLength,
      created: true,
    });
    const storage = { storeSourceArtifact } as unknown as TemplateTwinArtifactStore;

    const result = await createTemplateTwinDraft({
      source: fixture.source,
      actor: {
        userId: 'doctor-synthetic-1',
        userEmail: 'doctor@synthetic.test',
        practiceId: 'practice-synthetic-1',
      },
      storage,
    });

    expect(result).toMatchObject({
      sourceSha256: digest,
      compilerVersion: fixture.ir.compilerVersion,
      fieldCount: fixture.ir.fields.length,
      blockingUnsupportedCount: 0,
      usedFallbackMappings: false,
    });
    expect(mocks.modelComplete).toHaveBeenCalledTimes(2);
    expect(mocks.modelComplete.mock.calls.map((call) => call[0].purpose)).toEqual([
      'tm_template_phi_scan',
      'tm_template_parse',
    ]);
    expect(storeSourceArtifact).toHaveBeenCalledWith(
      expect.objectContaining({
        practiceId: 'practice-synthetic-1',
        templateVersion: 1,
        bytes: fixture.source,
      }),
    );
    expect(mocks.transaction).toHaveBeenCalledTimes(1);
    expect(mocks.noteTemplateCreate).toHaveBeenCalledWith({
      data: expect.objectContaining({
        doctorId: 'doctor-synthetic-1',
        templateKind: 'template_twin_docx',
        status: 'draft',
        version: 1,
      }),
    });
    expect(mocks.sourceArtifactCreate).toHaveBeenCalledWith({
      data: expect.objectContaining({
        practiceId: 'practice-synthetic-1',
        objectKey: expect.stringContaining('/template-twin/sources/'),
        sha256: digest,
        validationStatus: 'accepted',
      }),
    });
    const compiledData = mocks.compiledVersionCreate.mock.calls[0]![0].data;
    expect(compiledData).toEqual(
      expect.objectContaining({
        compilerVersion: fixture.ir.compilerVersion,
        compiledDocumentIr: fixture.ir,
        certificationStatus: 'NEEDS_CONFIRMATION',
        blockingUnsupportedCount: 0,
      }),
    );
    expect(compiledData.fields.create).toHaveLength(fixture.ir.fields.length);
    expect(
      compiledData.fields.create.every(
        (field: { mapping: { create: { practiceDefault: unknown } } }) =>
          field.mapping.create.practiceDefault === null,
      ),
    ).toBe(true);
    expect(mocks.logAudit).toHaveBeenCalledTimes(2);
    expect(JSON.stringify(mocks.logAudit.mock.calls)).not.toContain(
      'synthetic wrist discomfort',
    );
  });
});
