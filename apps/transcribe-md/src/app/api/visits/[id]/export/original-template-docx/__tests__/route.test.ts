import { beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  auth: vi.fn(),
  freshDoctor: vi.fn(),
  findFirst: vi.fn(),
  assess: vi.fn(),
  readOutputArtifact: vi.fn(),
  logAudit: vi.fn(),
  logDelivery: vi.fn(),
  logWarn: vi.fn(),
}));

vi.mock('next/server', () => {
  class FakeNextResponse {
    status: number;
    headers = new Map<string, string>();
    body: unknown;

    constructor(
      body: unknown,
      init?: { status?: number; headers?: Record<string, string> },
    ) {
      this.body = body;
      this.status = init?.status ?? 200;
      for (const [key, value] of Object.entries(init?.headers ?? {})) {
        this.headers.set(key, value);
      }
    }

    async json() {
      return this.body;
    }

    static json(body: unknown, init?: { status?: number }) {
      return new FakeNextResponse(body, init);
    }
  }
  return { NextResponse: FakeNextResponse };
});

vi.mock('@meddoc/db', () => ({
  default: { transcribeVisit: { findFirst: mocks.findFirst } },
}));
vi.mock('@meddoc/ai', () => ({ redactPhi: (value: unknown) => value }));
vi.mock('@/lib/nextauth', () => ({ auth: mocks.auth }));
vi.mock('@/lib/auth', () => ({
  AuthError: class AuthError extends Error {
    constructor(
      public readonly code: 'UNAUTHENTICATED' | 'FORBIDDEN',
      message: string,
    ) {
      super(message);
    }
  },
  requireFreshDoctorIdentity: mocks.freshDoctor,
}));
vi.mock('@/lib/audit', () => ({ logAudit: mocks.logAudit }));
vi.mock('@/lib/deliveries', () => ({ logDelivery: mocks.logDelivery }));
vi.mock('@/lib/log', () => ({
  log: { warn: mocks.logWarn, info: vi.fn(), error: vi.fn() },
}));
vi.mock('@/lib/template-twin/signing-gate', () => ({
  TEMPLATE_TWIN_SIGNING_VISIT_SELECT: {},
  assessTemplateTwinSigning: mocks.assess,
}));
vi.mock('@/lib/template-twin/storage/artifact-store', () => ({
  createTemplateTwinArtifactStore: () => ({
    readOutputArtifact: mocks.readOutputArtifact,
  }),
  TemplateTwinArtifactIntegrityError: class extends Error {},
  TemplateTwinStorageUnavailableError: class extends Error {},
}));
vi.mock('@/lib/template-twin/storage/ownership', () => ({
  TemplateTwinArtifactNotFoundError: class extends Error {},
}));

import type { NextRequest } from 'next/server';
import { AuthError } from '@/lib/auth';

import { GET } from '../route';

const VISIT_ID = 'visit-1';
const DOCUMENT = Buffer.from('synthetic-template-twin-docx');

function call() {
  return GET({} as NextRequest, {
    params: Promise.resolve({ id: VISIT_ID }),
  });
}

beforeEach(() => {
  vi.clearAllMocks();
  mocks.auth.mockResolvedValue({
    user: { id: 'doctor-1', practiceId: 'practice-stale-jwt' },
  });
  mocks.freshDoctor.mockResolvedValue({
    role: 'DOCTOR',
    practiceId: 'practice-1',
  });
  mocks.findFirst.mockResolvedValue({
    id: VISIT_ID,
    status: 'SIGNED',
    noteTemplateId: 'template-1',
    noteTemplateVersion: 1,
    noteTemplate: { templateKind: 'template_twin_docx' },
    templateTwinFill: {
      outputObjectKey: 'tenant-output-key',
      outputSha256: 'a'.repeat(64),
      outputSizeBytes: DOCUMENT.byteLength,
    },
  });
  mocks.assess.mockReturnValue({
    applies: true,
    ready: true,
    blockerCodes: [],
    compiledVersionId: 'compiled-1',
    fillManifestId: 'fill-1',
    claim: {
      id: 'fill-1',
      manifestVersion: 1,
      manifestSha256: 'b'.repeat(64),
      outputSha256: 'a'.repeat(64),
      updatedAt: new Date('2026-07-15T12:00:00.000Z'),
    },
  });
  mocks.readOutputArtifact.mockResolvedValue(DOCUMENT);
});

describe('Original Template DOCX delivery', () => {
  it('requires an authenticated tenant-scoped physician', async () => {
    mocks.auth.mockResolvedValue(null);

    const response = await call();

    expect(response.status).toBe(401);
    expect(mocks.freshDoctor).not.toHaveBeenCalled();
    expect(mocks.findFirst).not.toHaveBeenCalled();
    expect(mocks.readOutputArtifact).not.toHaveBeenCalled();
  });

  it.each(['STAFF', 'ADMIN'] as const)(
    'rejects a fresh %s role before visit or object lookup',
    async (role) => {
      mocks.freshDoctor.mockRejectedValue(
        new AuthError('FORBIDDEN', `Synthetic ${role} is not a physician.`),
      );

      const response = await call();

      expect(response.status).toBe(403);
      expect(mocks.findFirst).not.toHaveBeenCalled();
      expect(mocks.readOutputArtifact).not.toHaveBeenCalled();
    },
  );

  it('returns 404 when the owned signed visit cannot be found', async () => {
    mocks.findFirst.mockResolvedValue(null);

    const response = await call();

    expect(response.status).toBe(404);
    expect(mocks.readOutputArtifact).not.toHaveBeenCalled();
  });

  it('refuses an unverified manifest without reading object storage', async () => {
    mocks.assess.mockReturnValue({
      applies: true,
      ready: false,
      blockerCodes: ['ROUND_TRIP_UNVERIFIED'],
      compiledVersionId: 'compiled-1',
      fillManifestId: 'fill-1',
      claim: null,
    });

    const response = await call();

    expect(response.status).toBe(409);
    expect((await response.json()).code).toBe(
      'TEMPLATE_TWIN_OUTPUT_UNVERIFIED',
    );
    expect(mocks.readOutputArtifact).not.toHaveBeenCalled();
    expect(mocks.logAudit).toHaveBeenCalledWith(
      expect.objectContaining({
        action: 'EXPORT_TEMPLATE_TWIN_DOCX_DOWNLOADED',
        success: false,
        errorCode: 'TEMPLATE_TWIN_OUTPUT_UNVERIFIED',
      }),
    );
  });

  it('streams only storage-verified bytes with private download headers', async () => {
    const response = await call();

    expect(response.status).toBe(200);
    expect(response.body).toEqual(DOCUMENT);
    expect(response.headers.get('Content-Type')).toBe(
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    );
    expect(response.headers.get('Cache-Control')).toBe('no-store, private');
    expect(response.headers.get('X-Content-Type-Options')).toBe('nosniff');
    expect(mocks.readOutputArtifact).toHaveBeenCalledWith({
      practiceId: 'practice-1',
      objectKey: 'tenant-output-key',
      expectedSha256: 'a'.repeat(64),
      expectedSizeBytes: DOCUMENT.byteLength,
    });
    expect(mocks.logDelivery).toHaveBeenCalledWith({
      visitId: VISIT_ID,
      channel: 'docx_original_template',
      sizeBytes: DOCUMENT.byteLength,
    });
    expect(mocks.logAudit).toHaveBeenCalledWith(
      expect.objectContaining({
        action: 'EXPORT_TEMPLATE_TWIN_DOCX_DOWNLOADED',
      }),
    );
  });
});
