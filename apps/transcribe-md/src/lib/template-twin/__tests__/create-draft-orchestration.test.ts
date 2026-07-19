import { createHash } from 'node:crypto';

import { beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  modelComplete: vi.fn(),
  findSystemTemplate: vi.fn(),
  noteTemplateCreate: vi.fn(),
  sourceArtifactCreate: vi.fn(),
  compiledVersionCreate: vi.fn(),
  transaction: vi.fn(),
  ledgerUpdate: vi.fn(),
  ledgerFind: vi.fn(),
  outboxCreate: vi.fn(),
  finalRollout: vi.fn(),
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
    templateTwinObjectLedger: {
      updateMany: mocks.ledgerUpdate,
      findUnique: mocks.ledgerFind,
    },
    templateTwinAuditOutbox: { create: mocks.outboxCreate },
  };
  const prisma = {
    noteTemplate: { findFirst: mocks.findSystemTemplate },
    $transaction: mocks.transaction,
  };
  mocks.transaction.mockImplementation(
    async (callback: (client: unknown) => Promise<unknown>) => callback(tx),
  );
  return { default: prisma, prisma };
});

vi.mock('../rollout', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../rollout')>();
  return {
    ...actual,
    lockTemplateTwinRolloutForFinalClaim: mocks.finalRollout,
  };
});

import { createTemplateTwinDraft } from '../create-draft';
import type { TemplateTwinArtifactStore } from '../storage';
import { buildTemplateTwinIntegrationFixture } from './integration-fixture';
import { buildSyntheticDocx } from '../../note-template-docx/__tests__/synthetic-docx';

const ACTOR = {
  userId: 'doctor-synthetic-1',
  userEmail: 'doctor@synthetic.test',
  practiceId: 'practice-synthetic-1',
  rolloutToken: {
    practiceId: 'practice-synthetic-1',
    globalGeneration: BigInt(3),
    practiceGeneration: BigInt(7),
  },
};

beforeEach(() => {
  vi.clearAllMocks();
  mocks.finalRollout.mockResolvedValue({
    allowed: true,
    token: ACTOR.rolloutToken,
  });
  mocks.transaction.mockImplementation(
    async (callback: (client: unknown) => Promise<unknown>) =>
      callback({
        noteTemplate: { create: mocks.noteTemplateCreate },
        templateTwinSourceArtifact: { create: mocks.sourceArtifactCreate },
        templateTwinCompiledVersion: { create: mocks.compiledVersionCreate },
        templateTwinObjectLedger: {
          updateMany: mocks.ledgerUpdate,
          findUnique: mocks.ledgerFind,
        },
        templateTwinAuditOutbox: { create: mocks.outboxCreate },
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
  mocks.outboxCreate.mockResolvedValue({ id: 'outbox-synthetic-1' });
  mocks.ledgerUpdate.mockResolvedValue({ count: 1 });
  mocks.ledgerFind.mockResolvedValue(null);
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
      objectVersionId: 'provider-source-version-synthetic',
      objectEtag: 'provider-source-etag-synthetic',
      sha256: digest,
      mimeType:
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
      sizeBytes: fixture.source.byteLength,
      created: true,
    });
    const storage = { storeSourceArtifact } as unknown as TemplateTwinArtifactStore;

    const result = await createTemplateTwinDraft({
      source: fixture.source,
      identity: {
        name: 'Synthetic orthopedic intake',
        encounterType: 'Orthopedic initial visit',
        versionDescription: 'Initial synthetic QA version',
      },
      actor: ACTOR,
      providerVisitId: 'template-twin-staging-upload-visit:synthetic',
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
    expect(mocks.modelComplete.mock.calls.map((call) => call[0].visitId)).toEqual([
      'template-twin-staging-upload-visit:synthetic',
      'template-twin-staging-upload-visit:synthetic',
    ]);
    expect(storeSourceArtifact).toHaveBeenCalledWith(
      expect.objectContaining({
        practiceId: 'practice-synthetic-1',
        templateVersion: 1,
        bytes: fixture.source,
      }),
    );
    expect(mocks.transaction).toHaveBeenCalledTimes(1);
    expect(mocks.transaction).toHaveBeenCalledWith(expect.any(Function), {
      isolationLevel: 'ReadCommitted',
    });
    expect(mocks.noteTemplateCreate).toHaveBeenCalledWith({
      data: expect.objectContaining({
        doctorId: 'doctor-synthetic-1',
        templateKind: 'template_twin_docx',
        status: 'draft',
        version: 1,
        name: 'Synthetic orthopedic intake',
        encounterType: 'Orthopedic initial visit',
        versionDescription: 'Initial synthetic QA version',
      }),
    });
    expect(mocks.sourceArtifactCreate).toHaveBeenCalledWith({
      data: expect.objectContaining({
        practiceId: 'practice-synthetic-1',
        objectKey: expect.stringContaining('/template-twin/sources/'),
        objectVersionId: 'provider-source-version-synthetic',
        objectEtag: 'provider-source-etag-synthetic',
        sha256: digest,
        validationStatus: 'accepted',
        privacyScanEvidence: expect.objectContaining({
          profileVersion: 'template-twin-source-phi-safe-alpha-v1',
          approvedStaticAssetCount: 0,
          approvedStaticAssetUsedCount: 0,
        }),
      }),
    });
    expect(mocks.ledgerUpdate).toHaveBeenCalledWith(
      expect.objectContaining({
        data: expect.objectContaining({
          state: 'CLAIMED',
          claimType: 'source_artifact',
        }),
      }),
    );
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
    expect(mocks.outboxCreate).toHaveBeenCalledTimes(2);
    expect(mocks.outboxCreate).toHaveBeenCalledWith({
      data: expect.objectContaining({
        action: 'TEMPLATE_TWIN_SOURCE_UPLOADED',
        targetId: expect.any(String),
        status: 'PENDING',
      }),
    });
    expect(mocks.outboxCreate).toHaveBeenCalledWith({
      data: expect.objectContaining({
        action: 'TEMPLATE_TWIN_COMPILED',
        targetId: expect.any(String),
        status: 'PENDING',
      }),
    });
    expect(JSON.stringify(mocks.outboxCreate.mock.calls)).not.toContain(
      'synthetic wrist discomfort',
    );
  });

  it('leaves uploaded bytes unclaimed when rollout changes before the draft claim', async () => {
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
      objectKey: `practices/${ACTOR.practiceId}/template-twin/sources/lineage/v1/artifact/${digest}.docx`,
      objectVersionId: 'provider-source-version-stale-synthetic',
      objectEtag: 'provider-source-etag-stale-synthetic',
      sha256: digest,
      mimeType:
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
      sizeBytes: fixture.source.byteLength,
      created: true,
    });
    mocks.finalRollout.mockResolvedValueOnce({
      allowed: false,
      code: 'TEMPLATE_TWIN_PRACTICE_GENERATION_STALE',
      reason: 'Synthetic practice generation changed.',
      currentToken: {
        practiceId: ACTOR.practiceId,
        globalGeneration: BigInt(3),
        practiceGeneration: BigInt(8),
      },
    });

    await expect(
      createTemplateTwinDraft({
        source: fixture.source,
        identity: {
          name: 'Synthetic stale rollout intake',
          encounterType: 'Synthetic initial visit',
          versionDescription: 'Synthetic stale rollout proof',
        },
        actor: ACTOR,
        storage: { storeSourceArtifact } as unknown as TemplateTwinArtifactStore,
      }),
    ).rejects.toMatchObject({
      code: 'ROLLOUT_CHANGED',
      message: expect.stringContaining(
        'TEMPLATE_TWIN_PRACTICE_GENERATION_STALE',
      ),
    });
    expect(storeSourceArtifact).toHaveBeenCalledTimes(1);
    expect(mocks.noteTemplateCreate).not.toHaveBeenCalled();
    expect(mocks.compiledVersionCreate).not.toHaveBeenCalled();
    expect(mocks.ledgerUpdate).not.toHaveBeenCalled();
    expect(mocks.outboxCreate).not.toHaveBeenCalled();
  });

  it('fails the upload transaction when its durable audit event cannot be enqueued', async () => {
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
    const storage = {
      storeSourceArtifact: vi.fn().mockResolvedValue({
        bucket: 'synthetic-template-artifacts',
        objectKey: `practices/practice-synthetic-1/template-twin/sources/lineage/v1/artifact/${digest}.docx`,
        objectVersionId: 'provider-source-version-synthetic',
        objectEtag: 'provider-source-etag-synthetic',
        sha256: digest,
        mimeType:
          'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        sizeBytes: fixture.source.byteLength,
        created: true,
      }),
    } as unknown as TemplateTwinArtifactStore;
    mocks.outboxCreate.mockRejectedValueOnce(
      new Error('synthetic audit outbox unavailable'),
    );

    await expect(
      createTemplateTwinDraft({
        source: fixture.source,
        identity: {
          name: 'Synthetic orthopedic intake',
          encounterType: 'Orthopedic initial visit',
          versionDescription: 'Initial synthetic QA version',
        },
        actor: ACTOR,
        storage,
      }),
    ).rejects.toMatchObject({ code: 'PERSISTENCE_FAILED' });

    expect(mocks.transaction).toHaveBeenCalledTimes(1);
    expect(mocks.outboxCreate).toHaveBeenCalledTimes(1);
  });

  it('fails closed when a rejected DOCX cannot atomically record its quarantine event', async () => {
    mocks.outboxCreate.mockRejectedValueOnce(
      new Error('synthetic quarantine audit unavailable'),
    );

    await expect(
      createTemplateTwinDraft({
        source: Buffer.from('synthetic invalid DOCX package', 'utf8'),
        identity: {
          name: 'Synthetic rejected intake',
          encounterType: 'Synthetic initial visit',
          versionDescription: 'Synthetic rejected QA version',
        },
        actor: ACTOR,
      }),
    ).rejects.toMatchObject({ code: 'PERSISTENCE_FAILED' });

    expect(mocks.sourceArtifactCreate).toHaveBeenCalledWith({
      data: expect.objectContaining({
        validationStatus: 'quarantined',
        objectKey: null,
      }),
      select: { id: true },
    });
    expect(mocks.outboxCreate).toHaveBeenCalledWith({
      data: expect.objectContaining({
        action: 'TEMPLATE_TWIN_QUARANTINED',
        status: 'PENDING',
        metadata: expect.objectContaining({
          gateOutcome: 'blocked',
        }),
      }),
    });
  });

  it('durably records a digest-only quarantine when the required PHI scan is unavailable', async () => {
    const fixture = await buildTemplateTwinIntegrationFixture();
    mocks.modelComplete.mockRejectedValueOnce(
      new Error('synthetic privacy provider unavailable'),
    );

    await expect(
      createTemplateTwinDraft({
        source: fixture.source,
        identity: {
          name: 'Synthetic privacy-blocked intake',
          encounterType: 'Synthetic initial visit',
          versionDescription: 'Synthetic privacy gate outage case',
        },
        actor: ACTOR,
      }),
    ).rejects.toMatchObject({ code: 'TEMPLATE_TWIN_PHI_SCAN_UNAVAILABLE' });

    expect(mocks.sourceArtifactCreate).toHaveBeenCalledWith({
      data: expect.objectContaining({
        objectKey: null,
        validationStatus: 'quarantined',
        rejectionCodes: ['TEMPLATE_TWIN_PHI_SCAN_UNAVAILABLE'],
        sha256: expect.stringMatching(/^[a-f0-9]{64}$/),
      }),
      select: { id: true },
    });
    expect(mocks.outboxCreate).toHaveBeenCalledWith({
      data: expect.objectContaining({
        action: 'TEMPLATE_TWIN_QUARANTINED',
        status: 'PENDING',
        metadata: expect.objectContaining({
          rejectionCode: 'TEMPLATE_TWIN_PHI_SCAN_UNAVAILABLE',
          gateOutcome: 'blocked',
        }),
      }),
    });
  });

  it('durably records a distinct quarantine when package content cannot be privacy-scanned', async () => {
    const source = await buildSyntheticDocx({
      extraEntries: { 'customXml/item1.xml': '<root>synthetic only</root>' },
    });

    await expect(
      createTemplateTwinDraft({
        source,
        identity: {
          name: 'Synthetic unsupported package',
          encounterType: 'Synthetic initial visit',
          versionDescription: 'Synthetic unscannable package case',
        },
        actor: ACTOR,
      }),
    ).rejects.toMatchObject({
      code: 'TEMPLATE_TWIN_SOURCE_PRIVACY_UNSUPPORTED',
    });

    expect(mocks.sourceArtifactCreate).toHaveBeenCalledWith({
      data: expect.objectContaining({
        objectKey: null,
        validationStatus: 'quarantined',
        rejectionCodes: ['TEMPLATE_TWIN_SOURCE_PRIVACY_UNSUPPORTED'],
      }),
      select: { id: true },
    });
    expect(mocks.outboxCreate).toHaveBeenCalledWith({
      data: expect.objectContaining({
        action: 'TEMPLATE_TWIN_QUARANTINED',
        metadata: expect.objectContaining({
          rejectionCode: 'TEMPLATE_TWIN_SOURCE_PRIVACY_UNSUPPORTED',
          gateOutcome: 'blocked',
        }),
      }),
    });
  });
});
