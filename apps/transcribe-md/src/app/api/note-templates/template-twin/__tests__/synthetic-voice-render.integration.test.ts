import { createHash } from 'node:crypto';

import { beforeAll, beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  legacyAudit: vi.fn(),
  completeEntities: vi.fn(),
  createStore: vi.fn(),
  findTemplate: vi.fn(),
  findCompiled: vi.fn(),
  rateLimitOr429: vi.fn(),
  requireDoctorSession: vi.fn(),
  transcribe: vi.fn(),
  transaction: vi.fn(),
  updateCompiled: vi.fn(),
  ledgerUpdate: vi.fn(),
  ledgerFind: vi.fn(),
  outboxCreate: vi.fn(),
  finalRollout: vi.fn(),
}));

vi.mock('next/server', () => {
  class FakeNextResponse {
    status: number;
    headers: Headers;
    private readonly payload: unknown;

    constructor(
      payload: unknown,
      init?: { status?: number; headers?: Record<string, string> },
    ) {
      this.payload = payload;
      this.status = init?.status ?? 200;
      this.headers = new Headers(init?.headers);
    }

    async json() {
      return this.payload;
    }

    static json(
      payload: unknown,
      init?: { status?: number; headers?: Record<string, string> },
    ) {
      return new FakeNextResponse(payload, init);
    }
  }
  return { NextResponse: FakeNextResponse };
});

vi.mock('@meddoc/ai', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@meddoc/ai')>();
  return {
    ...actual,
    transcribe: mocks.transcribe,
    modelClient: { ...actual.modelClient, complete: mocks.completeEntities },
  };
});

vi.mock('@meddoc/db', () => ({
  default: {
    noteTemplate: { findFirst: mocks.findTemplate },
    $transaction: mocks.transaction,
  },
}));

vi.mock('@/lib/auth', () => ({
  AuthError: class AuthError extends Error {
    constructor(
      public readonly code: 'UNAUTHENTICATED' | 'FORBIDDEN',
      message: string,
    ) {
      super(message);
    }
  },
  requireDoctorSession: mocks.requireDoctorSession,
}));

vi.mock('@/lib/rate-limit', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/lib/rate-limit')>();
  return { ...actual, rateLimitOr429: mocks.rateLimitOr429 };
});

vi.mock('@/lib/audit', () => ({ logAudit: mocks.legacyAudit }));

vi.mock('@/lib/template-twin/storage', async (importOriginal) => {
  const actual = await importOriginal<
    typeof import('@/lib/template-twin/storage')
  >();
  return {
    ...actual,
    createTemplateTwinArtifactStore: mocks.createStore,
  };
});

vi.mock('@/lib/template-twin/rollout', async (importOriginal) => {
  const actual = await importOriginal<
    typeof import('@/lib/template-twin/rollout')
  >();
  return {
    ...actual,
    lockTemplateTwinRolloutForFinalClaim: mocks.finalRollout,
  };
});

import { inspectDocxPackage } from '@/lib/note-template-docx';
import { templateTwinFieldIntentsSha256 } from '@/lib/template-twin/field-intent';
import { templateTwinMappingsSha256 } from '@/lib/template-twin/mapping-hash';
import {
  TEMPLATE_TWIN_SOURCE_PROVENANCE_GATE_CODE,
  templateTwinSourcePhiScanEvidenceSha256,
} from '@/lib/template-twin/source-phi-evidence';
import type { TemplateTwinArtifactStore } from '@/lib/template-twin/storage';
import {
  buildTemplateTwinIntegrationFixture,
  SYNTHETIC_CONTEXT,
  SYNTHETIC_ENTITIES,
} from '@/lib/template-twin/__tests__/integration-fixture';

import { POST } from '../[id]/synthetic-test-voice/route';

const SESSION = {
  templateTwinRolloutToken: {
    practiceId: 'practice-synthetic-route-render',
    globalGeneration: BigInt(4),
    practiceGeneration: BigInt(9),
  },
  user: {
    id: 'doctor-synthetic-route-render',
    email: 'route-render-doctor@synthetic.test',
    practiceId: 'practice-synthetic-route-render',
  },
};
const TEMPLATE_ID = 'template-synthetic-route-render';
const COMPILED_ID = 'compiled-synthetic-route-render';
const SOURCE_KEY =
  'practices/practice-synthetic-route-render/template-twin/sources/lineage-synthetic/v1/source.docx';
const DOCX_MIME =
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document' as const;
const SOURCE_VERSION_ID = 'provider-source-version-synthetic';
const SOURCE_ETAG = 'provider-source-etag-synthetic';
const OUTPUT_VERSION_ID = 'provider-output-version-synthetic';
const OUTPUT_ETAG = 'provider-output-etag-synthetic';
const SOURCE_PRIVACY_SCAN_EVIDENCE = {
  profileVersion: 'template-twin-source-phi-safe-alpha-v1' as const,
  provider: 'anthropic' as const,
  model: 'synthetic-privacy-model-v1',
  scannedAt: '2026-07-15T12:00:00.000Z',
  scannedPartCount: 8,
  approvedStaticAssetPolicySha256: 'a'.repeat(64),
  approvedStaticAssetCount: 0,
  approvedStaticAssetUsedCount: 0,
  approvedStaticAssetUsageSha256: 'b'.repeat(64),
};
const EMPTY_FIELD_INTENTS_SHA256 = templateTwinFieldIntentsSha256([]);

type Fixture = Awaited<ReturnType<typeof buildTemplateTwinIntegrationFixture>>;

interface PersistedSyntheticProof {
  latestSyntheticTestManifest: unknown | null;
  latestTestMappingsSha256: string | null;
  latestTestFieldIntentsSha256: string | null;
  latestTestOutputObjectKey: string | null;
  latestTestOutputVersionId: string | null;
  latestTestOutputEtag: string | null;
  latestTestOutputSha256: string | null;
  latestTestStaticContentSha256: string | null;
  latestTestRoundTrip: unknown | null;
  latestTestVerifiedAt: Date | null;
}

let fixture: Fixture;
let sourceSha256: string;
let mappingRows: Array<{
  id: string;
  fieldId: string;
  intentDecisions: [];
  mapping: {
    clinicalConcept: string | null;
    expectedDataType: string;
    polarityBehavior: string;
    temporality: string | null;
    laterality: string | null;
    unitPolicy: string | null;
    approvedSynonyms: string[];
    required: boolean;
    blankPolicy: string;
    unknownPolicy: string;
    practiceDefault: string | null;
    mappingStatus: 'CERTIFIED';
  };
}>;
let proof: PersistedSyntheticProof;
let outputs: Map<string, Buffer>;
let sourcePrivacyScanEvidence: unknown;

function sha256(bytes: Uint8Array): string {
  return createHash('sha256').update(bytes).digest('hex');
}

/** A complete 46-byte PCM WAV containing one zero-valued sample. The route
 * exercises the real server-side magic-byte check before the provider seam. */
function tinySyntheticWav(): Buffer {
  const wav = Buffer.alloc(46);
  wav.write('RIFF', 0, 'ascii');
  wav.writeUInt32LE(38, 4);
  wav.write('WAVE', 8, 'ascii');
  wav.write('fmt ', 12, 'ascii');
  wav.writeUInt32LE(16, 16);
  wav.writeUInt16LE(1, 20);
  wav.writeUInt16LE(1, 22);
  wav.writeUInt32LE(8_000, 24);
  wav.writeUInt32LE(16_000, 28);
  wav.writeUInt16LE(2, 32);
  wav.writeUInt16LE(16, 34);
  wav.write('data', 36, 'ascii');
  wav.writeUInt32LE(2, 40);
  wav.writeInt16LE(0, 44);
  return wav;
}

function syntheticVoiceRequest(): {
  audio: Buffer;
  mappingsSha256: string;
  request: Request;
} {
  const audio = tinySyntheticWav();
  const browserAudio = new Uint8Array(audio.byteLength);
  browserAudio.set(audio);
  const mappingsSha256 = templateTwinMappingsSha256(fixture.mappings);
  const boundary = '----template-twin-synthetic-route-render';
  const multipart = Buffer.concat([
    Buffer.from(
      `--${boundary}\r\nContent-Disposition: form-data; name="audio"; filename="synthetic-one-sample.wav"\r\nContent-Type: audio/wav\r\n\r\n`,
      'utf8',
    ),
    Buffer.from(browserAudio),
    Buffer.from(
      `\r\n--${boundary}\r\nContent-Disposition: form-data; name="expectedMappingsSha256"\r\n\r\n${mappingsSha256}` +
        `\r\n--${boundary}\r\nContent-Disposition: form-data; name="expectedFieldIntentsSha256"\r\n\r\n${EMPTY_FIELD_INTENTS_SHA256}` +
        `\r\n--${boundary}--\r\n`,
      'utf8',
    ),
  ]);
  const request = new Request(
    `https://app.synthetic.test/api/note-templates/template-twin/${TEMPLATE_ID}/synthetic-test-voice`,
    {
      method: 'POST',
      headers: {
        origin: 'https://app.synthetic.test',
        'sec-fetch-site': 'same-origin',
        'content-type': `multipart/form-data; boundary=${boundary}`,
      },
      body: multipart,
    },
  );
  return {
    audio,
    mappingsSha256,
    request,
  };
}

function sourceArtifactRow(privacyScanEvidence = sourcePrivacyScanEvidence) {
  return {
    practiceId: SESSION.user.practiceId,
    objectKey: SOURCE_KEY,
    objectVersionId: SOURCE_VERSION_ID,
    objectEtag: SOURCE_ETAG,
    sha256: sourceSha256,
    sizeBytes: fixture.source.byteLength,
    mimeType: DOCX_MIME,
    validationStatus: 'accepted',
    privacyScanEvidence,
  };
}

function compiledTransactionRow(privacyScanEvidence = sourcePrivacyScanEvidence) {
  return {
    certificationStatus: 'DRAFT',
    sourceArtifact: sourceArtifactRow(privacyScanEvidence),
    fields: mappingRows,
  };
}

function templateRow() {
  return {
    id: TEMPLATE_ID,
    lineageId: 'lineage-synthetic-route-render',
    version: 1,
    name: 'Synthetic route renderer template',
    encounterType: null,
    status: 'draft',
    templateTwinSyntheticQaAdmissions: [],
    templateTwinCompiledVersion: {
      id: COMPILED_ID,
      compilerVersion: fixture.ir.compilerVersion,
      compiledAt: new Date('2026-07-15T12:00:00.000Z'),
      compiledDocumentIr: fixture.ir,
      certificationStatus: 'DRAFT',
      latestTestMappingsSha256: proof.latestTestMappingsSha256,
      latestTestFieldIntentsSha256: proof.latestTestFieldIntentsSha256,
      latestSyntheticTestManifest: proof.latestSyntheticTestManifest,
      latestTestOutputObjectKey: proof.latestTestOutputObjectKey,
      latestTestOutputVersionId: proof.latestTestOutputVersionId,
      latestTestOutputEtag: proof.latestTestOutputEtag,
      latestTestOutputSha256: proof.latestTestOutputSha256,
      latestTestStaticContentSha256: proof.latestTestStaticContentSha256,
      latestTestVerifiedAt: proof.latestTestVerifiedAt,
      latestTestRoundTrip: proof.latestTestRoundTrip,
      sourceArtifact: sourceArtifactRow(),
      fields: mappingRows,
    },
  };
}

function inMemoryStorage(): TemplateTwinArtifactStore {
  return {
    bucket: 'synthetic-memory-only',
    storeQuarantineArtifact: vi.fn(),
    readQuarantineArtifact: vi.fn(),
    storeCandidateArtifact: vi.fn(),
    readCandidateArtifact: vi.fn(),
    storeSourceArtifact: vi.fn(),
    readSourceArtifact: vi.fn(async (input) => {
      expect(input).toEqual({
        practiceId: SESSION.user.practiceId,
        objectKey: SOURCE_KEY,
        expectedObjectVersionId: SOURCE_VERSION_ID,
        expectedObjectEtag: SOURCE_ETAG,
        expectedSha256: sourceSha256,
        expectedSizeBytes: fixture.source.byteLength,
      });
      return Buffer.from(fixture.source);
    }),
    readOutputArtifact: vi.fn(async (input) => {
      const document = outputs.get(input.objectKey);
      if (!document) throw new Error('Synthetic in-memory output not found.');
      return Buffer.from(document);
    }),
    storeOutputArtifact: vi.fn(async (input) => {
      const document = Buffer.from(input.bytes);
      const outputSha256 = sha256(document);
      const objectKey = `practices/${input.practiceId}/template-twin/outputs/${input.visitId}/${input.manifestSha256}/${outputSha256}.docx`;
      outputs.set(objectKey, document);
      return {
        bucket: 'synthetic-memory-only',
        objectKey,
        objectVersionId: OUTPUT_VERSION_ID,
        objectEtag: OUTPUT_ETAG,
        sha256: outputSha256,
        mimeType: DOCX_MIME,
        sizeBytes: document.byteLength,
        created: true,
      };
    }),
  };
}

function syntheticTransactionClient() {
  return {
    templateTwinCompiledVersion: {
      findUnique: mocks.findCompiled,
      update: mocks.updateCompiled,
    },
    templateTwinObjectLedger: {
      updateMany: mocks.ledgerUpdate,
      findUnique: mocks.ledgerFind,
    },
    templateTwinAuditOutbox: { create: mocks.outboxCreate },
  };
}

beforeAll(async () => {
  fixture = await buildTemplateTwinIntegrationFixture();
  sourceSha256 = sha256(fixture.source);
  mappingRows = fixture.mappings.map((mapping, index) => ({
    id: `field-definition-synthetic-${index + 1}`,
    fieldId: mapping.fieldId,
    intentDecisions: [],
    mapping: {
      clinicalConcept: mapping.clinicalConcept,
      expectedDataType: mapping.expectedDataType,
      polarityBehavior: mapping.polarityBehavior,
      temporality: mapping.temporality,
      laterality: mapping.laterality,
      unitPolicy: mapping.unitPolicy,
      approvedSynonyms: [...mapping.approvedSynonyms],
      required: mapping.required,
      blankPolicy: mapping.blankPolicy,
      unknownPolicy: mapping.unknownPolicy,
      practiceDefault: mapping.practiceDefault,
      mappingStatus: 'CERTIFIED',
    },
  }));
});

beforeEach(() => {
  vi.clearAllMocks();
  outputs = new Map();
  sourcePrivacyScanEvidence = SOURCE_PRIVACY_SCAN_EVIDENCE;
  proof = {
    latestSyntheticTestManifest: null,
    latestTestMappingsSha256: null,
    latestTestFieldIntentsSha256: null,
    latestTestOutputObjectKey: null,
    latestTestOutputVersionId: null,
    latestTestOutputEtag: null,
    latestTestOutputSha256: null,
    latestTestStaticContentSha256: null,
    latestTestRoundTrip: null,
    latestTestVerifiedAt: null,
  };
  mocks.requireDoctorSession.mockResolvedValue(SESSION);
  mocks.finalRollout.mockResolvedValue({
    allowed: true,
    token: SESSION.templateTwinRolloutToken,
  });
  mocks.rateLimitOr429.mockReturnValue(null);
  mocks.transcribe.mockResolvedValue({ transcript: SYNTHETIC_CONTEXT });
  mocks.completeEntities.mockImplementation(
    async (request: { purpose: string }) =>
      request.purpose === 'tm_template_synthetic_phi_scan'
        ? {
            directIdentifierClasses: [],
            appearsExplicitlySynthetic: true,
            anyUncertain: false,
          }
        : SYNTHETIC_ENTITIES,
  );
  mocks.createStore.mockReturnValue(inMemoryStorage());
  mocks.findTemplate.mockImplementation(async () => templateRow());
  mocks.findCompiled.mockImplementation(async () => compiledTransactionRow());
  mocks.updateCompiled.mockImplementation(
    async (input: { data: Partial<PersistedSyntheticProof> }) => {
      Object.assign(proof, input.data);
      return { id: COMPILED_ID };
    },
  );
  mocks.ledgerUpdate.mockResolvedValue({ count: 1 });
  mocks.ledgerFind.mockResolvedValue(null);
  mocks.outboxCreate.mockResolvedValue({ id: 'synthetic-proof-audit' });
  mocks.transaction.mockImplementation(
    async (operation: (tx: unknown) => Promise<unknown>) => {
      const proofBeforeTransaction = { ...proof };
      try {
        return await operation(syntheticTransactionClient());
      } catch (error) {
        proof = proofBeforeTransaction;
        throw error;
      }
    },
  );
});

describe('Template Twin synthetic voice route to exact original DOCX', () => {
  it('persists a verified proof after real projection, resolution, validation, rendering, and round-trip checks', async () => {
    const { audio, mappingsSha256, request } = syntheticVoiceRequest();

    const response = await POST(request, {
      params: Promise.resolve({ id: TEMPLATE_ID }),
    });

    expect(response.status).toBe(200);
    expect(mocks.transcribe).toHaveBeenCalledWith(
      expect.objectContaining({
        audio: expect.any(Buffer),
        mimeType: 'audio/wav',
        allowCrossProviderFallback: false,
      }),
    );
    expect(Buffer.from(mocks.transcribe.mock.calls[0]![0].audio)).toEqual(audio);
    expect(mocks.completeEntities).toHaveBeenCalledWith(
      expect.objectContaining({
        purpose: 'tm_entities',
        provider: 'anthropic',
        visitId: null,
        user: expect.stringContaining(SYNTHETIC_CONTEXT),
      }),
    );

    expect(proof.latestTestMappingsSha256).toBe(mappingsSha256);
    expect(proof.latestTestOutputSha256).toMatch(/^[a-f0-9]{64}$/);
    expect(proof.latestTestOutputObjectKey).toBeTruthy();
    expect(proof.latestTestStaticContentSha256).toBe(
      fixture.ir.staticContentSha256,
    );
    expect(proof.latestTestVerifiedAt).toBeInstanceOf(Date);
    expect(proof.latestTestRoundTrip).toMatchObject({
      verified: true,
      packageCheck: 'verified',
      fieldCheck: 'verified',
      staticRegionCheck: 'verified',
      sourcePrivacyScanEvidenceSha256:
        templateTwinSourcePhiScanEvidenceSha256(
          SOURCE_PRIVACY_SCAN_EVIDENCE,
        ),
    });
    expect(proof.latestSyntheticTestManifest).toMatchObject({
      validation: { valid: true },
      counts: { filled: fixture.ir.fields.length, needsReview: 0 },
    });
    expect(mocks.ledgerUpdate).toHaveBeenCalledWith(
      expect.objectContaining({
        data: expect.objectContaining({
          state: 'CLAIMED',
          claimType: 'compiled_test_output',
          claimId: COMPILED_ID,
        }),
      }),
    );

    const output = outputs.get(proof.latestTestOutputObjectKey!);
    expect(output).toBeDefined();
    expect(sha256(output!)).toBe(proof.latestTestOutputSha256);
    const inspected = inspectDocxPackage(output!);
    const documentXml = inspected.zip.entries
      .get('word/document.xml')!
      .bytes.toString('utf8');
    const headerXml = inspected.zip.entries
      .get('word/header1.xml')!
      .bytes.toString('utf8');
    expect(documentXml).toContain('synthetic wrist discomfort');
    expect(documentXml).toContain('<w:t>Current</w:t>');
    expect(documentXml).toContain('w14:checked w14:val="1"');
    expect(documentXml).toContain('Use synthetic brace');
    expect(headerXml).toContain('Synthetic Clinic Header');

    const body = await response.json();
    expect(body).toMatchObject({
      ok: true,
      workspace: {
        latestSyntheticTest: {
          outputSha256: proof.latestTestOutputSha256,
          mappingsSha256,
          roundTripVerified: true,
        },
      },
    });
    expect(mocks.outboxCreate).toHaveBeenCalledWith({
      data: expect.objectContaining({
        eventKey: expect.stringMatching(
          new RegExp(
            `^template-twin:synthetic-tested:${COMPILED_ID}:[0-9a-f-]{36}$`,
          ),
        ),
        practiceId: SESSION.user.practiceId,
        actorId: SESSION.user.id,
        actorEmailSnapshot: SESSION.user.email,
        action: 'TEMPLATE_TWIN_SYNTHETIC_TESTED',
        targetType: 'TemplateTwinCompiledVersion',
        targetId: COMPILED_ID,
        metadata: expect.objectContaining({
          outputSha256: proof.latestTestOutputSha256,
          verified: true,
          inputMode: 'dictation',
        }),
      }),
    });
    expect(mocks.ledgerUpdate.mock.invocationCallOrder[0]).toBeLessThan(
      mocks.outboxCreate.mock.invocationCallOrder[0]!,
    );
  });

  it('does not persist a synthetic proof when durable audit enqueue fails', async () => {
    mocks.outboxCreate.mockRejectedValue(
      new Error('synthetic audit outbox unavailable'),
    );
    const { request } = syntheticVoiceRequest();

    const response = await POST(request, {
      params: Promise.resolve({ id: TEMPLATE_ID }),
    });

    expect(response.status).toBe(503);
    expect(mocks.updateCompiled).toHaveBeenCalledTimes(1);
    expect(mocks.ledgerUpdate).toHaveBeenCalledTimes(1);
    expect(mocks.outboxCreate).toHaveBeenCalledTimes(1);
    expect(proof).toEqual({
      latestSyntheticTestManifest: null,
      latestTestMappingsSha256: null,
      latestTestFieldIntentsSha256: null,
      latestTestOutputObjectKey: null,
      latestTestOutputVersionId: null,
      latestTestOutputEtag: null,
      latestTestOutputSha256: null,
      latestTestStaticContentSha256: null,
      latestTestRoundTrip: null,
      latestTestVerifiedAt: null,
    });
  });

  it.each([
    {
      name: 'null privacy evidence',
      evidence: null,
    },
    {
      name: 'a legacy privacy profile',
      evidence: {
        ...SOURCE_PRIVACY_SCAN_EVIDENCE,
        profileVersion: 'template-twin-source-phi-legacy-v0',
      },
    },
  ])('blocks source I/O when the source has $name', async ({ evidence }) => {
    sourcePrivacyScanEvidence = evidence;
    const artifactStore = inMemoryStorage();
    mocks.createStore.mockReturnValue(artifactStore);
    const { request } = syntheticVoiceRequest();

    const response = await POST(request, {
      params: Promise.resolve({ id: TEMPLATE_ID }),
    });

    expect(response.status).toBe(422);
    await expect(response.json()).resolves.toMatchObject({
      ok: false,
      error: expect.stringContaining(
        TEMPLATE_TWIN_SOURCE_PROVENANCE_GATE_CODE,
      ),
    });
    expect(artifactStore.readSourceArtifact).not.toHaveBeenCalled();
    expect(artifactStore.storeOutputArtifact).not.toHaveBeenCalled();
    expect(mocks.updateCompiled).not.toHaveBeenCalled();
  });

  it('rejects a valid-looking current profile changed during the synthetic render', async () => {
    const artifactStore = inMemoryStorage();
    mocks.createStore.mockReturnValue(artifactStore);
    mocks.findCompiled.mockResolvedValue(
      compiledTransactionRow({
        ...SOURCE_PRIVACY_SCAN_EVIDENCE,
        model: 'synthetic-tampered-current-profile-v2',
      }),
    );
    const { request } = syntheticVoiceRequest();

    const response = await POST(request, {
      params: Promise.resolve({ id: TEMPLATE_ID }),
    });

    expect(response.status).toBe(422);
    await expect(response.json()).resolves.toMatchObject({
      ok: false,
      error: expect.stringContaining(
        TEMPLATE_TWIN_SOURCE_PROVENANCE_GATE_CODE,
      ),
    });
    expect(artifactStore.readSourceArtifact).toHaveBeenCalledTimes(1);
    expect(artifactStore.storeOutputArtifact).toHaveBeenCalledTimes(1);
    expect(mocks.updateCompiled).not.toHaveBeenCalled();
    expect(proof.latestSyntheticTestManifest).toBeNull();
  });

  it('reuses one idempotency key when the serializable callback is retried', async () => {
    mocks.transaction.mockImplementation(
      async (operation: (tx: unknown) => Promise<unknown>) => {
        const proofBeforeTransaction = { ...proof };
        await operation(syntheticTransactionClient());
        proof = proofBeforeTransaction;
        return operation(syntheticTransactionClient());
      },
    );
    const { request } = syntheticVoiceRequest();

    const response = await POST(request, {
      params: Promise.resolve({ id: TEMPLATE_ID }),
    });

    expect(response.status).toBe(200);
    const eventKeys = mocks.outboxCreate.mock.calls.map(
      (call) => call[0].data.eventKey,
    );
    expect(eventKeys).toHaveLength(2);
    expect(new Set(eventKeys).size).toBe(1);
  });
});
