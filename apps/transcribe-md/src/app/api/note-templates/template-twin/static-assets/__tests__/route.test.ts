// @vitest-environment node

import { beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  requireAdmin: vi.fn(),
  readiness: vi.fn(),
  inspect: vi.fn(),
  approve: vi.fn(),
  reject: vi.fn(),
  revoke: vi.fn(),
  list: vi.fn(),
  rateLimit: vi.fn(),
  stagingRequested: vi.fn(),
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

vi.mock('@/lib/auth', () => ({
  AuthError: class AuthError extends Error {
    constructor(
      public readonly code: 'UNAUTHENTICATED' | 'FORBIDDEN',
      message: string,
    ) {
      super(message);
    }
  },
}));
vi.mock('@/lib/rate-limit', () => ({
  RATE_LIMITS: { SETTINGS: { bucket: 'synthetic-settings' } },
  rateLimitOr429: mocks.rateLimit,
}));
vi.mock('@/lib/template-twin/static-asset-admin', () => ({
  requireTemplateTwinStaticAssetAdmin: mocks.requireAdmin,
}));
vi.mock('@/lib/template-twin/static-asset-ocr', () => ({
  configuredTemplateTwinLocalOcr: mocks.readiness,
}));
vi.mock('@/lib/template-twin/staging-qa-gate', () => ({
  isTemplateTwinStagingQaRequested: mocks.stagingRequested,
}));
vi.mock('@/lib/template-twin/static-assets', () => ({
  TemplateTwinStaticAssetError: class TemplateTwinStaticAssetError extends Error {
    constructor(public readonly code: string, message: string) {
      super(message);
    }
  },
  inspectTemplateTwinStaticAssetForReview: mocks.inspect,
  approveTemplateTwinStaticAsset: mocks.approve,
  rejectTemplateTwinStaticAsset: mocks.reject,
  revokeTemplateTwinStaticAsset: mocks.revoke,
  listTemplateTwinStaticAssetsForPractice: mocks.list,
}));

import { AuthError } from '@/lib/auth';
import { GET, POST } from '../route';

const ACTOR = {
  userId: 'admin_synthetic',
  userEmail: 'admin@synthetic.test',
  practiceId: 'practice_synthetic',
  role: 'ADMIN',
  rolloutToken: {
    practiceId: 'practice_synthetic',
    globalGeneration: BigInt(1),
    practiceGeneration: BigInt(1),
  },
};
const PREVIEW_RECEIPT =
  '123e4567-e89b-42d3-a456-426614174000.' + 'A'.repeat(43);
const OCR = { scan: vi.fn() };
const READY = {
  ready: true,
  code: 'TT_STATIC_ASSET_LOCAL_OCR_READY',
  message: 'Bounded local image-text inspection is available.',
  engineVersion: 'tesseract/5.3.0',
  ocr: OCR,
};
const ENDPOINT =
  'https://app.synthetic.test/api/note-templates/template-twin/static-assets';

function formRequest(form: FormData, headers?: Record<string, string>): Request {
  return new Request(ENDPOINT, {
    method: 'POST',
    headers: {
      origin: 'https://app.synthetic.test',
      'sec-fetch-site': 'same-origin',
      ...headers,
    },
    body: form,
  });
}

function imageForm(action: 'inspect' | 'approve' | 'reject'): FormData {
  const form = new FormData();
  form.set('action', action);
  form.set(
    'file',
    new File(
      [
        Buffer.from(
          'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4nGOor6//DwAFewJ94ITM6gAAAABJRU5ErkJggg==',
          'base64',
        ),
      ],
      'synthetic-logo.png',
      { type: 'image/png' },
    ),
  );
  return form;
}

beforeEach(() => {
  vi.clearAllMocks();
  mocks.requireAdmin.mockResolvedValue(ACTOR);
  mocks.stagingRequested.mockReturnValue(false);
  mocks.readiness.mockResolvedValue(READY);
  mocks.rateLimit.mockReturnValue(null);
  mocks.inspect.mockResolvedValue({
    evidence: { sha256: 'a'.repeat(64), mimeType: 'image/png' },
    previewBytes: Uint8Array.from([1, 2, 3, 4]),
    previewReviewReceipt: PREVIEW_RECEIPT,
    previewReviewExpiresAtIso: '2026-07-16T00:15:00.000Z',
  });
  mocks.approve.mockResolvedValue({
    sha256: 'a'.repeat(64),
    assetId: 'asset_synthetic',
    decisionId: 'decision_synthetic',
  });
  mocks.reject.mockResolvedValue(undefined);
  mocks.revoke.mockResolvedValue(undefined);
  mocks.list.mockResolvedValue([
    {
      sha256: 'a'.repeat(64),
      status: 'APPROVED',
      mimeType: 'image/png',
      width: 320,
      height: 80,
      sizeBytes: 2048,
      scannerVersion: 'template-twin-static-png/1.0.0',
      ocrEngineVersion: 'synthetic-local-ocr/1.0',
      decisionVersion: 1,
      createdAtIso: '2026-07-16T00:00:00.000Z',
      updatedAtIso: '2026-07-16T00:00:00.000Z',
    },
  ]);
});

describe('Template Twin static-image management route', () => {
  it('returns a non-revealing 404 before arbitrary media reaches any service in synthetic-only mode', async () => {
    mocks.stagingRequested.mockReturnValue(true);

    const getResponse = await GET();
    const postResponse = await POST(formRequest(imageForm('inspect')));

    expect(getResponse.status).toBe(404);
    expect(postResponse.status).toBe(404);
    expect(await getResponse.json()).toEqual({ ok: false, error: 'not found' });
    expect(await postResponse.json()).toEqual({ ok: false, error: 'not found' });
    expect(mocks.requireAdmin).not.toHaveBeenCalled();
    expect(mocks.readiness).not.toHaveBeenCalled();
    expect(mocks.rateLimit).not.toHaveBeenCalled();
    expect(mocks.inspect).not.toHaveBeenCalled();
    expect(mocks.approve).not.toHaveBeenCalled();
    expect(mocks.reject).not.toHaveBeenCalled();
    expect(mocks.revoke).not.toHaveBeenCalled();
    expect(mocks.list).not.toHaveBeenCalled();
  });

  it('rejects cross-site mutations before authentication or body parsing', async () => {
    const form = imageForm('inspect');
    const request = new Request(ENDPOINT, {
      method: 'POST',
      headers: {
        origin: 'https://attacker.synthetic.test',
        'sec-fetch-site': 'cross-site',
      },
      body: form,
    });
    const response = await POST(request);
    expect(response.status).toBe(403);
    expect(mocks.requireAdmin).not.toHaveBeenCalled();
    expect(mocks.inspect).not.toHaveBeenCalled();
  });

  it('requires fresh practice-admin authorization before readiness is disclosed', async () => {
    mocks.requireAdmin.mockRejectedValue(
      new AuthError('FORBIDDEN', 'Synthetic non-admin.'),
    );
    const response = await GET();
    expect(response.status).toBe(403);
    expect(mocks.readiness).not.toHaveBeenCalled();
  });

  it('reports missing local OCR as an explicit blocking readiness state', async () => {
    mocks.readiness.mockResolvedValue({
      ready: false,
      code: 'TT_STATIC_ASSET_LOCAL_OCR_NOT_CONFIGURED',
      message: 'Synthetic OCR is not configured.',
    });
    const response = await GET();
    expect(response.status).toBe(200);
    expect(await response.json()).toMatchObject({
      ok: true,
      readiness: {
        ready: false,
        code: 'TT_STATIC_ASSET_LOCAL_OCR_NOT_CONFIGURED',
      },
      imageBytesSentToExternalProviders: false,
      extractedTextPrivacyScanProvider: 'anthropic',
      assets: [expect.objectContaining({ status: 'APPROVED' })],
    });
    expect(mocks.list).toHaveBeenCalledWith({ actor: ACTOR });
  });

  it('blocks image inspection when local OCR is unavailable', async () => {
    mocks.readiness.mockResolvedValue({
      ready: false,
      code: 'TT_STATIC_ASSET_LOCAL_OCR_UNAVAILABLE',
      message: 'Synthetic OCR unavailable.',
    });
    const response = await POST(formRequest(imageForm('inspect')));
    expect(response.status).toBe(503);
    expect(mocks.inspect).not.toHaveBeenCalled();
  });

  it('returns only an admin-scoped safe preview after bounded inspection', async () => {
    const response = await POST(formRequest(imageForm('inspect')));
    expect(response.status).toBe(200);
    expect(mocks.inspect).toHaveBeenCalledWith({
      bytes: expect.any(Uint8Array),
      claimedMimeType: 'image/png',
      actor: ACTOR,
      ocr: OCR,
    });
    expect(await response.json()).toMatchObject({
      ok: true,
      status: 'needs_attestation',
      previewDataUrl: 'data:image/png;base64,AQIDBA==',
      previewReviewReceipt: PREVIEW_RECEIPT,
    });
    expect(response.headers.get('cache-control')).toContain('no-store');
  });

  it('binds approval to the reviewed digest and explicit attestation', async () => {
    const form = imageForm('approve');
    form.set('expectedSha256', 'a'.repeat(64));
    form.set('reason', 'Reusable synthetic practice logo.');
    form.set('previewReviewReceipt', PREVIEW_RECEIPT);
    form.set('attestedReusableBlankAsset', 'true');
    const response = await POST(formRequest(form));
    expect(response.status).toBe(201);
    expect(mocks.approve).toHaveBeenCalledWith(
      expect.objectContaining({
        actor: ACTOR,
        ocr: OCR,
        expectedSha256: 'a'.repeat(64),
        previewReviewReceipt: PREVIEW_RECEIPT,
        attestedReusableBlankAsset: true,
      }),
    );
  });

  it('blocks direct approval without the single-use preview proof', async () => {
    const form = imageForm('approve');
    form.set('expectedSha256', 'a'.repeat(64));
    form.set('reason', 'Reusable synthetic practice logo.');
    form.set('attestedReusableBlankAsset', 'true');
    const response = await POST(formRequest(form));
    expect(response.status).toBe(409);
    expect(await response.json()).toMatchObject({
      code: 'TT_STATIC_ASSET_PREVIEW_RECEIPT_INVALID',
    });
    expect(mocks.approve).not.toHaveBeenCalled();
  });

  it('permits explicit revocation even when OCR is unavailable', async () => {
    mocks.readiness.mockResolvedValue({
      ready: false,
      code: 'TT_STATIC_ASSET_LOCAL_OCR_UNAVAILABLE',
      message: 'Synthetic OCR unavailable.',
    });
    const form = new FormData();
    form.set('action', 'revoke');
    form.set('sha256', 'a'.repeat(64));
    form.set('reason', 'Retire the synthetic reusable logo.');
    const response = await POST(formRequest(form));
    expect(response.status).toBe(200);
    expect(mocks.revoke).toHaveBeenCalledWith({
      practiceId: ACTOR.practiceId,
      sha256: 'a'.repeat(64),
      reason: 'Retire the synthetic reusable logo.',
      actor: ACTOR,
    });
  });

  it('rejects declared and actual multipart overflow before image inspection', async () => {
    const declared = await POST(
      formRequest(imageForm('inspect'), {
        'content-length': String(5 * 1024 * 1024 + 64 * 1024 + 1),
      }),
    );
    expect(declared.status).toBe(413);

    const oversized = new FormData();
    oversized.set('action', 'inspect');
    oversized.set(
      'file',
      new File(
        [Buffer.alloc(5 * 1024 * 1024 + 128 * 1024)],
        'oversized-synthetic.png',
        { type: 'image/png' },
      ),
    );
    const actual = await POST(formRequest(oversized));
    expect(actual.status).toBe(413);
    expect(mocks.inspect).not.toHaveBeenCalled();
  });
});
