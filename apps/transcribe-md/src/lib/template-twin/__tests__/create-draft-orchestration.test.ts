import { createHash } from 'node:crypto';

import { beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  modelComplete: vi.fn(),
  findSystemTemplate: vi.fn(),
  noteTemplateCreate: vi.fn(),
  sourceArtifactCreate: vi.fn(),
  quarantineArtifactCreate: vi.fn(),
  quarantineArtifactUpdateMany: vi.fn(),
  compiledVersionCreate: vi.fn(),
  transaction: vi.fn(),
  ledgerUpdate: vi.fn(),
  ledgerFind: vi.fn(),
  outboxCreate: vi.fn(),
  finalRollout: vi.fn(),
  currentPhysician: vi.fn(),
}));

vi.mock('@meddoc/ai', () => ({
  delimiterSystemSuffix: () => '',
  getTemplateTwinSyntheticQaProviderContext: () => null,
  wrapAsData: (value: string) => ({
    wrapped: value,
    injectionAttemptDetected: false,
  }),
  modelClient: { complete: mocks.modelComplete },
}));

vi.mock('../provider-ownership', () => ({
  requireTemplateTwinProviderOwnershipContext: vi.fn(),
  runTemplateTwinOwnedModelComplete: vi.fn(
    async (input: {
      args: unknown;
      client: { complete(args: unknown): Promise<unknown> };
    }) => input.client.complete(input.args),
  ),
  runWithTemplateTwinProviderOwnershipContext: vi.fn(
    async (_context: unknown, callback: () => Promise<unknown>) => callback(),
  ),
  buildTemplateTwinProviderOwnershipReceipt: vi.fn(() => ({
    evidence: {
      contractVersion: 'template-twin-provider-ownership-receipt-v2',
      practiceId: 'practice-synthetic-1',
      actorUserId: 'doctor-synthetic-1',
      providerMode: 'LIVE',
      executions: [],
    },
    sha256: 'c'.repeat(64),
  })),
}));

vi.mock('@meddoc/db', () => {
  const tx = {
    noteTemplate: { create: mocks.noteTemplateCreate },
    templateTwinSourceArtifact: { create: mocks.sourceArtifactCreate },
    templateTwinQuarantineArtifact: {
      create: mocks.quarantineArtifactCreate,
      updateMany: mocks.quarantineArtifactUpdateMany,
    },
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
  const actual = (await importOriginal()) as typeof import('../rollout');
  return {
    ...actual,
    lockTemplateTwinRolloutForFinalClaim: mocks.finalRollout,
  };
});

vi.mock('../final-claim-authority', () => ({
  lockAndAssertCurrentTemplateTwinPhysician: mocks.currentPhysician,
}));

import { createTemplateTwinDraft } from '../create-draft';
import { DOCX_TEMPLATE_COMPILER } from '../artifact-compiler';
import {
  TEMPLATE_TWIN_MALWARE_SCAN_PROFILE,
  type TemplateTwinMalwareScanEvidence,
  type TemplateTwinMalwareScanner,
} from '../malware-scan';
import type { TemplateTwinArtifactStore } from '../storage';
import { minimizeTemplateTwinSourceMetadata } from '../source-metadata';
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

function sha256(value: Uint8Array | string): string {
  return createHash('sha256').update(value).digest('hex');
}

function cleanScanner(source: Uint8Array): TemplateTwinMalwareScanner {
  const unsigned = {
    profileVersion: TEMPLATE_TWIN_MALWARE_SCAN_PROFILE,
    scanner: 'clamav-clamd' as const,
    transport: 'unix-domain-socket' as const,
    engineVersion: '1.4.3',
    signatureVersion: '27888',
    sourceSha256: sha256(source),
    sourceSizeBytes: source.byteLength,
    verdict: 'clean' as const,
    threatNameSha256: null,
    scannedAt: '2026-07-19T00:00:00.000Z',
  };
  const evidence: TemplateTwinMalwareScanEvidence = {
    ...unsigned,
    attestationSha256: sha256(JSON.stringify(unsigned)),
  };
  return { scan: vi.fn().mockResolvedValue(evidence) };
}

function syntheticStorage(source: Uint8Array) {
  const rawDigest = sha256(source);
  const storeQuarantineArtifact = vi.fn().mockResolvedValue({
    bucket: 'synthetic-template-artifacts',
    objectKey: `practices/${ACTOR.practiceId}/template-twin/quarantine/lineage/v1/quarantine/${rawDigest}.docx`,
    objectVersionId: 'provider-quarantine-version-synthetic',
    objectEtag: 'provider-quarantine-etag-synthetic',
    sha256: rawDigest,
    mimeType:
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    sizeBytes: source.byteLength,
    created: true,
  });
  const storeSourceArtifact = vi.fn(async (input: { bytes: Uint8Array }) => {
    const admittedDigest = sha256(input.bytes);
    return {
      bucket: 'synthetic-template-artifacts',
      objectKey: `practices/${ACTOR.practiceId}/template-twin/sources/lineage/v1/source/${admittedDigest}.docx`,
      objectVersionId: 'provider-source-version-synthetic',
      objectEtag: 'provider-source-etag-synthetic',
      sha256: admittedDigest,
      mimeType:
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
      sizeBytes: input.bytes.byteLength,
      created: true,
    };
  });
  return {
    value: {
      storeQuarantineArtifact,
      storeSourceArtifact,
    } as unknown as TemplateTwinArtifactStore,
    storeQuarantineArtifact,
    storeSourceArtifact,
  };
}

beforeEach(() => {
  vi.clearAllMocks();
  mocks.finalRollout.mockResolvedValue({
    allowed: true,
    token: ACTOR.rolloutToken,
  });
  mocks.currentPhysician.mockResolvedValue({ email: ACTOR.userEmail });
  mocks.transaction.mockImplementation(
    async (callback: (client: unknown) => Promise<unknown>) =>
      callback({
        noteTemplate: { create: mocks.noteTemplateCreate },
        templateTwinSourceArtifact: { create: mocks.sourceArtifactCreate },
        templateTwinQuarantineArtifact: {
          create: mocks.quarantineArtifactCreate,
          updateMany: mocks.quarantineArtifactUpdateMany,
        },
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
  mocks.quarantineArtifactCreate.mockResolvedValue({
    id: 'quarantine-synthetic-1',
  });
  mocks.quarantineArtifactUpdateMany.mockResolvedValue({ count: 1 });
  mocks.compiledVersionCreate.mockResolvedValue({ id: 'compiled-synthetic-1' });
  mocks.outboxCreate.mockResolvedValue({ id: 'outbox-synthetic-1' });
  mocks.ledgerUpdate.mockResolvedValue({ count: 1 });
  mocks.ledgerFind.mockResolvedValue(null);
});

describe('Template Twin upload/compile proposal orchestration', () => {
  it('quarantines and scans before compiling a metadata-minimized immutable source', async () => {
    const fixture = await buildTemplateTwinIntegrationFixture();
    const minimizedFixture = await minimizeTemplateTwinSourceMetadata(
      fixture.source,
    );
    const admittedIr = DOCX_TEMPLATE_COMPILER.compile(
      minimizedFixture.document,
    );
    mocks.modelComplete.mockImplementation(
      async (request: { purpose: string }) => {
        if (request.purpose === 'tm_template_phi_scan') {
          return { phiFields: [], anyUncertain: false };
        }
        if (request.purpose === 'tm_template_parse') {
          return {
            mappings: fixture.mappings.map((mapping, index) => ({
              ...mapping,
              fieldId: admittedIr.fields[index]!.fieldId,
              status: 'recognized',
              practiceDefault: null,
            })),
          };
        }
        throw new Error('Unexpected synthetic model purpose');
      },
    );

    const rawDigest = sha256(fixture.source);
    const storage = syntheticStorage(fixture.source);

    const result = await createTemplateTwinDraft({
      source: fixture.source,
      identity: {
        name: 'Synthetic orthopedic intake',
        encounterType: 'Orthopedic initial visit',
        versionDescription: 'Initial synthetic QA version',
      },
      actor: ACTOR,
      providerVisitId: 'template-twin-staging-upload-visit:synthetic',
      storage: storage.value,
      malwareScanner: cleanScanner(fixture.source),
    });

    expect(result).toMatchObject({
      sourceSha256: expect.stringMatching(/^[a-f0-9]{64}$/),
      compilerVersion: fixture.ir.compilerVersion,
      fieldCount: fixture.ir.fields.length,
      blockingUnsupportedCount: 0,
      usedFallbackMappings: false,
    });
    expect(result.sourceSha256).not.toBe(rawDigest);
    expect(mocks.modelComplete).toHaveBeenCalledTimes(2);
    expect(
      mocks.modelComplete.mock.calls.map((call) => call[0].purpose),
    ).toEqual(['tm_template_phi_scan', 'tm_template_parse']);
    expect(
      mocks.modelComplete.mock.calls.map((call) => call[0].visitId),
    ).toEqual([
      'template-twin-staging-upload-visit:synthetic',
      'template-twin-staging-upload-visit:synthetic',
    ]);
    expect(storage.storeQuarantineArtifact).toHaveBeenCalledWith(
      expect.objectContaining({
        practiceId: 'practice-synthetic-1',
        lineageVersion: 1,
        bytes: fixture.source,
      }),
    );
    expect(storage.storeSourceArtifact).toHaveBeenCalledWith(
      expect.objectContaining({
        practiceId: 'practice-synthetic-1',
        templateVersion: 1,
        bytes: expect.any(Buffer),
      }),
    );
    expect(storage.storeSourceArtifact.mock.calls[0]![0].bytes).not.toEqual(
      fixture.source,
    );
    expect(mocks.transaction).toHaveBeenCalledTimes(3);
    expect(mocks.transaction).toHaveBeenCalledWith(expect.any(Function), {
      isolationLevel: 'ReadCommitted',
    });
    expect(mocks.currentPhysician).toHaveBeenCalledWith({
      tx: expect.any(Object),
      actor: ACTOR,
    });
    expect(mocks.finalRollout.mock.invocationCallOrder[0]).toBeLessThan(
      mocks.currentPhysician.mock.invocationCallOrder[0]!,
    );
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
        sha256: result.sourceSha256,
        validationStatus: 'accepted',
        quarantineArtifactId: expect.any(String),
        privacyScanEvidence: expect.objectContaining({
          profileVersion: 'template-twin-source-phi-safe-alpha-v1',
          approvedStaticAssetCount: 0,
          approvedStaticAssetUsedCount: 0,
        }),
      }),
    });
    expect(mocks.quarantineArtifactCreate).toHaveBeenCalledWith({
      data: expect.objectContaining({
        status: 'QUARANTINED',
        intakeMode: 'NATIVE_TEMPLATE',
        sha256: rawDigest,
      }),
    });
    expect(mocks.quarantineArtifactUpdateMany).toHaveBeenCalledWith(
      expect.objectContaining({
        data: expect.objectContaining({ status: 'MALWARE_CLEAN' }),
      }),
    );
    expect(mocks.quarantineArtifactUpdateMany).toHaveBeenCalledWith(
      expect.objectContaining({
        data: expect.objectContaining({
          status: 'ADMITTED',
          metadataMinimizationEvidence: expect.objectContaining({
            originalSha256: rawDigest,
            minimizedSha256: result.sourceSha256,
          }),
        }),
      }),
    );
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
        compiledDocumentIr: expect.objectContaining({
          compilerVersion: fixture.ir.compilerVersion,
          structureSha256: admittedIr.structureSha256,
        }),
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
    expect(mocks.outboxCreate).toHaveBeenCalledTimes(5);
    expect(mocks.outboxCreate).toHaveBeenCalledWith({
      data: expect.objectContaining({
        action: 'TEMPLATE_TWIN_QUARANTINED',
        targetId: expect.any(String),
      }),
    });
    expect(mocks.outboxCreate).toHaveBeenCalledWith({
      data: expect.objectContaining({
        action: 'TEMPLATE_TWIN_MALWARE_SCANNED',
        metadata: expect.objectContaining({ verdict: 'clean' }),
      }),
    });
    expect(mocks.outboxCreate).toHaveBeenCalledWith({
      data: expect.objectContaining({
        action: 'TEMPLATE_TWIN_METADATA_MINIMIZED',
      }),
    });
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
    const admittedIr = DOCX_TEMPLATE_COMPILER.compile(
      (await minimizeTemplateTwinSourceMetadata(fixture.source)).document,
    );
    mocks.modelComplete.mockImplementation(
      async (request: { purpose: string }) => {
        if (request.purpose === 'tm_template_phi_scan') {
          return { phiFields: [], anyUncertain: false };
        }
        if (request.purpose === 'tm_template_parse') {
          return {
            mappings: fixture.mappings.map((mapping, index) => ({
              ...mapping,
              fieldId: admittedIr.fields[index]!.fieldId,
              status: 'recognized',
              practiceDefault: null,
            })),
          };
        }
        throw new Error('Unexpected synthetic model purpose');
      },
    );
    const storage = syntheticStorage(fixture.source);
    mocks.finalRollout
      .mockResolvedValueOnce({
        allowed: true,
        token: ACTOR.rolloutToken,
      })
      .mockResolvedValueOnce({
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
        storage: storage.value,
        malwareScanner: cleanScanner(fixture.source),
      }),
    ).rejects.toMatchObject({
      code: 'ROLLOUT_CHANGED',
      message: expect.stringContaining(
        'TEMPLATE_TWIN_PRACTICE_GENERATION_STALE',
      ),
    });
    expect(storage.storeQuarantineArtifact).toHaveBeenCalledTimes(1);
    expect(storage.storeSourceArtifact).toHaveBeenCalledTimes(1);
    expect(mocks.noteTemplateCreate).not.toHaveBeenCalled();
    expect(mocks.compiledVersionCreate).not.toHaveBeenCalled();
    expect(mocks.ledgerUpdate).toHaveBeenCalledTimes(1);
    expect(mocks.ledgerUpdate).toHaveBeenCalledWith(
      expect.objectContaining({
        data: expect.objectContaining({ claimType: 'quarantine_artifact' }),
      }),
    );
    expect(mocks.outboxCreate).toHaveBeenCalledTimes(2);
  });

  it('leaves uploaded bytes unclaimed when physician authority is revoked after provider work', async () => {
    const fixture = await buildTemplateTwinIntegrationFixture();
    const admittedIr = DOCX_TEMPLATE_COMPILER.compile(
      (await minimizeTemplateTwinSourceMetadata(fixture.source)).document,
    );
    mocks.modelComplete.mockImplementation(
      async (request: { purpose: string }) => {
        if (request.purpose === 'tm_template_phi_scan') {
          return { phiFields: [], anyUncertain: false };
        }
        if (request.purpose === 'tm_template_parse') {
          return {
            mappings: fixture.mappings.map((mapping, index) => ({
              ...mapping,
              fieldId: admittedIr.fields[index]!.fieldId,
              status: 'recognized',
              practiceDefault: null,
            })),
          };
        }
        throw new Error('Unexpected synthetic model purpose');
      },
    );
    const storage = syntheticStorage(fixture.source);
    mocks.currentPhysician
      .mockResolvedValueOnce({ email: ACTOR.userEmail })
      .mockRejectedValueOnce(
        new Error('synthetic physician authority revoked'),
      );

    await expect(
      createTemplateTwinDraft({
        source: fixture.source,
        identity: {
          name: 'Synthetic revoked-authority intake',
          encounterType: 'Synthetic initial visit',
          versionDescription: 'Synthetic final authority race proof',
        },
        actor: ACTOR,
        storage: storage.value,
        malwareScanner: cleanScanner(fixture.source),
      }),
    ).rejects.toMatchObject({ code: 'PERSISTENCE_FAILED' });

    expect(mocks.modelComplete).toHaveBeenCalledTimes(2);
    expect(storage.storeSourceArtifact).toHaveBeenCalledTimes(1);
    expect(mocks.finalRollout).toHaveBeenCalledTimes(2);
    expect(mocks.currentPhysician).toHaveBeenCalledTimes(2);
    expect(mocks.finalRollout.mock.invocationCallOrder[1]).toBeLessThan(
      mocks.currentPhysician.mock.invocationCallOrder[1]!,
    );
    expect(mocks.noteTemplateCreate).not.toHaveBeenCalled();
    expect(mocks.sourceArtifactCreate).not.toHaveBeenCalled();
    expect(mocks.compiledVersionCreate).not.toHaveBeenCalled();
    expect(mocks.ledgerUpdate).toHaveBeenCalledTimes(1);
    expect(mocks.ledgerUpdate).toHaveBeenCalledWith(
      expect.objectContaining({
        data: expect.objectContaining({ claimType: 'quarantine_artifact' }),
      }),
    );
  });

  it('fails the upload transaction when its durable audit event cannot be enqueued', async () => {
    const fixture = await buildTemplateTwinIntegrationFixture();
    const admittedIr = DOCX_TEMPLATE_COMPILER.compile(
      (await minimizeTemplateTwinSourceMetadata(fixture.source)).document,
    );
    mocks.modelComplete.mockImplementation(
      async (request: { purpose: string }) => {
        if (request.purpose === 'tm_template_phi_scan') {
          return { phiFields: [], anyUncertain: false };
        }
        if (request.purpose === 'tm_template_parse') {
          return {
            mappings: fixture.mappings.map((mapping, index) => ({
              ...mapping,
              fieldId: admittedIr.fields[index]!.fieldId,
              status: 'recognized',
              practiceDefault: null,
            })),
          };
        }
        throw new Error('Unexpected synthetic model purpose');
      },
    );
    const storage = syntheticStorage(fixture.source);
    mocks.outboxCreate
      .mockResolvedValueOnce({ id: 'outbox-quarantine-synthetic' })
      .mockResolvedValueOnce({ id: 'outbox-scan-synthetic' })
      .mockResolvedValueOnce({ id: 'outbox-metadata-synthetic' })
      .mockRejectedValueOnce(new Error('synthetic audit outbox unavailable'));

    await expect(
      createTemplateTwinDraft({
        source: fixture.source,
        identity: {
          name: 'Synthetic orthopedic intake',
          encounterType: 'Orthopedic initial visit',
          versionDescription: 'Initial synthetic QA version',
        },
        actor: ACTOR,
        storage: storage.value,
        malwareScanner: cleanScanner(fixture.source),
      }),
    ).rejects.toMatchObject({ code: 'PERSISTENCE_FAILED' });

    expect(mocks.transaction).toHaveBeenCalledTimes(3);
    expect(mocks.outboxCreate).toHaveBeenCalledTimes(4);
  });

  it('fails closed when a rejected DOCX cannot atomically record its quarantine event', async () => {
    const source = Buffer.from('synthetic invalid DOCX package', 'utf8');
    const storage = syntheticStorage(source);
    mocks.outboxCreate
      .mockResolvedValueOnce({ id: 'outbox-quarantine-synthetic' })
      .mockResolvedValueOnce({ id: 'outbox-scan-synthetic' })
      .mockRejectedValueOnce(
        new Error('synthetic quarantine audit unavailable'),
      );

    await expect(
      createTemplateTwinDraft({
        source,
        identity: {
          name: 'Synthetic rejected intake',
          encounterType: 'Synthetic initial visit',
          versionDescription: 'Synthetic rejected QA version',
        },
        actor: ACTOR,
        storage: storage.value,
        malwareScanner: cleanScanner(source),
      }),
    ).rejects.toMatchObject({
      code: 'TEMPLATE_TWIN_QUARANTINE_PERSISTENCE_FAILED',
    });

    expect(mocks.quarantineArtifactCreate).toHaveBeenCalledWith({
      data: expect.objectContaining({
        status: 'QUARANTINED',
        objectKey: expect.stringContaining('/template-twin/quarantine/'),
        sha256: sha256(source),
      }),
    });
    expect(mocks.quarantineArtifactUpdateMany).toHaveBeenCalledWith(
      expect.objectContaining({
        data: expect.objectContaining({
          status: 'REJECTED',
          rejectionCodes: ['ZIP_MAGIC_INVALID'],
        }),
      }),
    );
    expect(mocks.outboxCreate).toHaveBeenCalledWith({
      data: expect.objectContaining({
        action: 'TEMPLATE_TWIN_QUARANTINED',
        status: 'PENDING',
        metadata: expect.objectContaining({
          gateOutcome: 'pending_malware_scan',
        }),
      }),
    });
  });

  it('retains the immutable quarantine when the required PHI scan is unavailable', async () => {
    const fixture = await buildTemplateTwinIntegrationFixture();
    const storage = syntheticStorage(fixture.source);
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
        storage: storage.value,
        malwareScanner: cleanScanner(fixture.source),
      }),
    ).rejects.toMatchObject({ code: 'TEMPLATE_TWIN_PHI_SCAN_UNAVAILABLE' });

    expect(mocks.sourceArtifactCreate).not.toHaveBeenCalled();
    expect(mocks.quarantineArtifactCreate).toHaveBeenCalledWith({
      data: expect.objectContaining({
        objectKey: expect.stringContaining('/template-twin/quarantine/'),
        status: 'QUARANTINED',
        sha256: sha256(fixture.source),
      }),
    });
    expect(mocks.quarantineArtifactUpdateMany).toHaveBeenCalledWith(
      expect.objectContaining({
        data: expect.objectContaining({
          status: 'REJECTED',
          rejectionCodes: ['TEMPLATE_TWIN_PHI_SCAN_UNAVAILABLE'],
        }),
      }),
    );
    expect(mocks.outboxCreate).toHaveBeenCalledWith({
      data: expect.objectContaining({
        action: 'TEMPLATE_TWIN_SAFETY_GATE_BLOCKED',
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
    const storage = syntheticStorage(source);

    await expect(
      createTemplateTwinDraft({
        source,
        identity: {
          name: 'Synthetic unsupported package',
          encounterType: 'Synthetic initial visit',
          versionDescription: 'Synthetic unscannable package case',
        },
        actor: ACTOR,
        storage: storage.value,
        malwareScanner: cleanScanner(source),
      }),
    ).rejects.toMatchObject({
      code: 'TEMPLATE_TWIN_SOURCE_PRIVACY_UNSUPPORTED',
    });

    expect(mocks.sourceArtifactCreate).not.toHaveBeenCalled();
    expect(mocks.quarantineArtifactCreate).toHaveBeenCalledWith({
      data: expect.objectContaining({
        objectKey: expect.stringContaining('/template-twin/quarantine/'),
        status: 'QUARANTINED',
        sha256: sha256(source),
      }),
    });
    expect(mocks.quarantineArtifactUpdateMany).toHaveBeenCalledWith(
      expect.objectContaining({
        data: expect.objectContaining({
          status: 'REJECTED',
          rejectionCodes: ['TEMPLATE_TWIN_SOURCE_PRIVACY_UNSUPPORTED'],
        }),
      }),
    );
    expect(mocks.outboxCreate).toHaveBeenCalledWith({
      data: expect.objectContaining({
        action: 'TEMPLATE_TWIN_SAFETY_GATE_BLOCKED',
        metadata: expect.objectContaining({
          rejectionCode: 'TEMPLATE_TWIN_SOURCE_PRIVACY_UNSUPPORTED',
          gateOutcome: 'blocked',
        }),
      }),
    });
  });
});
