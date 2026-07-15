import { createHash } from 'node:crypto';

import { beforeAll, beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  audit: vi.fn(),
  completeEntities: vi.fn(),
  createStore: vi.fn(),
  findTemplate: vi.fn(),
  findCompiled: vi.fn(),
  rateLimitOr429: vi.fn(),
  requireDoctorSession: vi.fn(),
  transcribe: vi.fn(),
  transaction: vi.fn(),
  updateCompiled: vi.fn(),
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

vi.mock('@/lib/audit', () => ({ logAudit: mocks.audit }));

vi.mock('@/lib/template-twin/storage', async (importOriginal) => {
  const actual = await importOriginal<
    typeof import('@/lib/template-twin/storage')
  >();
  return {
    ...actual,
    createTemplateTwinArtifactStore: mocks.createStore,
  };
});

import { inspectDocxPackage } from '@/lib/note-template-docx';
import { templateTwinMappingsSha256 } from '@/lib/template-twin/mapping-hash';
import type { TemplateTwinArtifactStore } from '@/lib/template-twin/storage';
import {
  buildTemplateTwinIntegrationFixture,
  SYNTHETIC_CONTEXT,
  SYNTHETIC_ENTITIES,
} from '@/lib/template-twin/__tests__/integration-fixture';

import { POST } from '../[id]/synthetic-test-voice/route';

const SESSION = {
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

type Fixture = Awaited<ReturnType<typeof buildTemplateTwinIntegrationFixture>>;

interface PersistedSyntheticProof {
  latestSyntheticTestManifest: unknown | null;
  latestTestMappingsSha256: string | null;
  latestTestOutputObjectKey: string | null;
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

function templateRow() {
  return {
    id: TEMPLATE_ID,
    lineageId: 'lineage-synthetic-route-render',
    version: 1,
    name: 'Synthetic route renderer template',
    encounterType: null,
    status: 'draft',
    templateTwinCompiledVersion: {
      id: COMPILED_ID,
      compilerVersion: fixture.ir.compilerVersion,
      compiledAt: new Date('2026-07-15T12:00:00.000Z'),
      compiledDocumentIr: fixture.ir,
      certificationStatus: 'DRAFT',
      latestTestMappingsSha256: proof.latestTestMappingsSha256,
      latestTestOutputSha256: proof.latestTestOutputSha256,
      latestTestVerifiedAt: proof.latestTestVerifiedAt,
      latestTestRoundTrip: proof.latestTestRoundTrip,
      sourceArtifact: {
        practiceId: SESSION.user.practiceId,
        objectKey: SOURCE_KEY,
        sha256: sourceSha256,
        sizeBytes: fixture.source.byteLength,
        mimeType: DOCX_MIME,
        validationStatus: 'accepted',
      },
      fields: mappingRows,
    },
  };
}

function inMemoryStorage(): TemplateTwinArtifactStore {
  return {
    bucket: 'synthetic-memory-only',
    storeSourceArtifact: vi.fn(),
    readSourceArtifact: vi.fn(async (input) => {
      expect(input).toEqual({
        practiceId: SESSION.user.practiceId,
        objectKey: SOURCE_KEY,
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
        sha256: outputSha256,
        mimeType: DOCX_MIME,
        sizeBytes: document.byteLength,
        created: true,
      };
    }),
  };
}

beforeAll(async () => {
  fixture = await buildTemplateTwinIntegrationFixture();
  sourceSha256 = sha256(fixture.source);
  mappingRows = fixture.mappings.map((mapping, index) => ({
    id: `field-definition-synthetic-${index + 1}`,
    fieldId: mapping.fieldId,
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
  proof = {
    latestSyntheticTestManifest: null,
    latestTestMappingsSha256: null,
    latestTestOutputObjectKey: null,
    latestTestOutputSha256: null,
    latestTestStaticContentSha256: null,
    latestTestRoundTrip: null,
    latestTestVerifiedAt: null,
  };
  mocks.requireDoctorSession.mockResolvedValue(SESSION);
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
  mocks.findCompiled.mockImplementation(async () => ({
    certificationStatus: 'DRAFT',
    fields: mappingRows,
  }));
  mocks.updateCompiled.mockImplementation(
    async (input: { data: Partial<PersistedSyntheticProof> }) => {
      Object.assign(proof, input.data);
      return { id: COMPILED_ID };
    },
  );
  mocks.transaction.mockImplementation(
    async (operation: (tx: unknown) => Promise<unknown>) =>
      operation({
        templateTwinCompiledVersion: {
          findUnique: mocks.findCompiled,
          update: mocks.updateCompiled,
        },
      }),
  );
});

describe('Template Twin synthetic voice route to exact original DOCX', () => {
  it('persists a verified proof after real projection, resolution, validation, rendering, and round-trip checks', async () => {
    const audio = tinySyntheticWav();
    const browserAudio = new Uint8Array(audio.byteLength);
    browserAudio.set(audio);
    const mappingsSha256 = templateTwinMappingsSha256(fixture.mappings);
    const form = new FormData();
    form.set(
      'audio',
      new File([browserAudio], 'synthetic-one-sample.wav', {
        type: 'audio/wav',
      }),
    );
    form.set('expectedMappingsSha256', mappingsSha256);
    const request = {
      url: `https://app.quillmd.test/api/note-templates/template-twin/${TEMPLATE_ID}/synthetic-test-voice`,
      headers: new Headers({
          origin: 'https://app.quillmd.test',
          'sec-fetch-site': 'same-origin',
      }),
      formData: async () => form,
    } as unknown as Request;

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
    });
    expect(proof.latestSyntheticTestManifest).toMatchObject({
      validation: { valid: true },
      counts: { filled: fixture.ir.fields.length, needsReview: 0 },
    });

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
    expect(mocks.audit).toHaveBeenCalledWith(
      expect.objectContaining({
        action: 'TEMPLATE_TWIN_SYNTHETIC_TESTED',
        metadata: expect.objectContaining({
          outputSha256: proof.latestTestOutputSha256,
          verified: true,
          inputMode: 'dictation',
        }),
      }),
    );
  });
});
