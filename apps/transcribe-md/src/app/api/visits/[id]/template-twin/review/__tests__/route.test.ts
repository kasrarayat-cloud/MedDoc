import { beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  acknowledgeReview: vi.fn(),
  rateLimit: vi.fn(),
  requireDoctorSession: vi.fn(),
  sameOrigin: vi.fn(),
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
  requireDoctorSession: mocks.requireDoctorSession,
}));

vi.mock('@/lib/rate-limit', () => ({
  RATE_LIMITS: { VISIT_OPS: { bucket: 'test', windows: [] } },
  rateLimitOr429: mocks.rateLimit,
}));

vi.mock('@/lib/template-twin/request-security', () => ({
  isSameOriginTemplateTwinMutation: mocks.sameOrigin,
}));

vi.mock('@/lib/template-twin/review-acknowledgement', () => ({
  TemplateTwinReviewAcknowledgementError:
    class TemplateTwinReviewAcknowledgementError extends Error {
      constructor(
        public readonly code: string,
        message: string,
      ) {
        super(message);
      }
    },
  acknowledgeTemplateTwinReview: mocks.acknowledgeReview,
}));

vi.mock('@/lib/template-twin/rollout', () => ({
  TemplateTwinRolloutError: class TemplateTwinRolloutError extends Error {
    constructor(
      public readonly code: string,
      message: string,
    ) {
      super(message);
    }
  },
}));

import { AuthError } from '@/lib/auth';
import {
  TemplateTwinReviewAcknowledgementError,
} from '@/lib/template-twin/review-acknowledgement';
import { TemplateTwinRolloutError } from '@/lib/template-twin/rollout';

import { POST } from '../route';

const MANIFEST_SHA256 = 'a'.repeat(64);
const SESSION = {
  user: {
    id: 'doctor-review-route',
    email: 'doctor-review-route@synthetic.test',
    practiceId: 'practice-review-route',
  },
};
const ACKNOWLEDGEMENT = {
  expectedManifestVersion: 7,
  expectedManifestSha256: MANIFEST_SHA256,
};

function jsonRequest(body: unknown): Request {
  return {
    headers: new Headers({
      origin: 'https://app.synthetic.test',
      host: 'app.synthetic.test',
    }),
    json: async () => body,
  } as unknown as Request;
}

function call(request: Request = jsonRequest(ACKNOWLEDGEMENT)) {
  return POST(request, {
    params: Promise.resolve({ id: 'visit-review-route' }),
  });
}

beforeEach(() => {
  vi.clearAllMocks();
  mocks.sameOrigin.mockReturnValue(true);
  mocks.requireDoctorSession.mockResolvedValue(SESSION);
  mocks.rateLimit.mockReturnValue(null);
  mocks.acknowledgeReview.mockResolvedValue({
    fillManifestId: 'fill-review-route',
    manifestVersion: 7,
    reviewedAt: '2026-07-15T12:00:00.000Z',
  });
});

describe('visit Template Twin whole-manifest review route', () => {
  it('rejects cross-origin requests before authentication or service work', async () => {
    mocks.sameOrigin.mockReturnValue(false);

    const response = await call();

    expect(response.status).toBe(403);
    expect(mocks.requireDoctorSession).not.toHaveBeenCalled();
    expect(mocks.acknowledgeReview).not.toHaveBeenCalled();
    expect(response.headers.get('Cache-Control')).toBe('no-store, private');
  });

  it('returns 400 for malformed JSON without calling the review service', async () => {
    const response = await call({
      headers: jsonRequest({}).headers,
      json: async () => {
        throw new SyntaxError('synthetic malformed JSON');
      },
    } as unknown as Request);

    expect(response.status).toBe(400);
    expect(await response.json()).toEqual({
      ok: false,
      error: 'The review confirmation body is not valid JSON.',
    });
    expect(mocks.acknowledgeReview).not.toHaveBeenCalled();
  });

  it.each([
    ['missing hash', { expectedManifestVersion: 7 }],
    [
      'uppercase hash',
      { ...ACKNOWLEDGEMENT, expectedManifestSha256: 'A'.repeat(64) },
    ],
    [
      'unexpected property',
      { ...ACKNOWLEDGEMENT, unexpected: true },
    ],
  ])('returns 400 for an invalid %s acknowledgement schema', async (_label, body) => {
    const response = await call(jsonRequest(body));

    expect(response.status).toBe(400);
    expect(mocks.acknowledgeReview).not.toHaveBeenCalled();
  });

  it('forwards the exact manifest version, hash, visit, and tenant actor', async () => {
    const response = await call();

    expect(response.status).toBe(200);
    expect(mocks.acknowledgeReview).toHaveBeenCalledWith({
      visitId: 'visit-review-route',
      expectedManifestVersion: 7,
      expectedManifestSha256: MANIFEST_SHA256,
      actor: {
        userId: SESSION.user.id,
        userEmail: SESSION.user.email,
        practiceId: SESSION.user.practiceId,
      },
    });
    expect(await response.json()).toEqual({
      ok: true,
      result: expect.objectContaining({ manifestVersion: 7 }),
    });
  });

  it.each([
    ['UNAUTHENTICATED', 401],
    ['FORBIDDEN', 403],
  ] as const)('maps %s authentication failures to %i', async (code, status) => {
    mocks.requireDoctorSession.mockRejectedValue(
      new AuthError(code, 'Synthetic authentication failure.'),
    );

    const response = await call();

    expect(response.status).toBe(status);
    expect(mocks.acknowledgeReview).not.toHaveBeenCalled();
  });

  it('returns a rate-limit response before parsing or service work', async () => {
    const blocked = {
      status: 429,
      headers: new Headers({ 'Retry-After': '30' }),
      json: async () => ({ error: 'rate limited' }),
    };
    mocks.rateLimit.mockReturnValue(blocked);

    const response = await call();

    expect(response).toBe(blocked);
    expect(mocks.acknowledgeReview).not.toHaveBeenCalled();
  });

  it('maps a disabled rollout to a fail-closed 403', async () => {
    mocks.acknowledgeReview.mockRejectedValue(
      new TemplateTwinRolloutError(
        'TEMPLATE_TWIN_PRACTICE_DISABLED',
        'Template Twin is not enabled for this practice.',
      ),
    );

    const response = await call();

    expect(response.status).toBe(403);
    expect(await response.json()).toMatchObject({
      code: 'TEMPLATE_TWIN_PRACTICE_DISABLED',
    });
  });

  it.each([
    ['NOT_FOUND', 404],
    ['NOT_READY', 422],
    ['MANIFEST_INVALID', 422],
    ['SOAP_BINDING_STALE', 409],
    ['OPTIMISTIC_CONFLICT', 409],
  ] as const)('maps service error %s to HTTP %i', async (code, status) => {
    mocks.acknowledgeReview.mockRejectedValue(
      new TemplateTwinReviewAcknowledgementError(
        code,
        'Synthetic fail-closed review error.',
      ),
    );

    const response = await call();

    expect(response.status).toBe(status);
    expect(await response.json()).toEqual({
      ok: false,
      error: 'Synthetic fail-closed review error.',
      code,
    });
  });

  it('fails closed with 503 when the durable audit transaction fails', async () => {
    mocks.acknowledgeReview.mockRejectedValue(
      new Error('synthetic outbox write failure'),
    );

    const response = await call();

    expect(response.status).toBe(503);
    expect(await response.json()).toEqual({
      ok: false,
      error:
        'Review was not confirmed because its durable audit record could not be saved.',
    });
  });
});
