import { beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  requireDoctorSession: vi.fn(),
  sameOrigin: vi.fn(),
  reviewField: vi.fn(),
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

vi.mock('@/lib/template-twin/request-security', () => ({
  isSameOriginTemplateTwinMutation: mocks.sameOrigin,
}));

vi.mock('@/lib/template-twin/review-service', () => ({
  TemplateTwinReviewError: class TemplateTwinReviewError extends Error {
    constructor(
      public readonly code: string,
      message: string,
    ) {
      super(message);
    }
  },
  reviewTemplateTwinField: mocks.reviewField,
}));

vi.mock('@/lib/template-twin/storage', () => ({
  TemplateTwinArtifactIntegrityError: class extends Error {},
  TemplateTwinStorageUnavailableError: class extends Error {},
}));

import { AuthError } from '@/lib/auth';
import { TemplateTwinReviewError } from '@/lib/template-twin/review-service';

import { PATCH, POST } from '../route';

const FIELD_ID = `ttf_${'a'.repeat(24)}`;
const SESSION = {
  user: {
    id: 'doctor-synthetic-1',
    email: 'doctor@synthetic.test',
    practiceId: 'practice-synthetic-1',
  },
};
const CORRECTION = {
  expectedManifestVersion: 4,
  fieldId: FIELD_ID,
  value: 'Severe',
  sourceFactIds: [],
  reasonCode: 'selected_exact_option',
  createMappingRule: false,
};

function jsonRequest(body: unknown): Request {
  return {
    headers: new Headers({
      origin: 'https://app.quillmd.test',
      host: 'app.quillmd.test',
    }),
    json: async () => body,
  } as unknown as Request;
}

function call(
  method: typeof PATCH | typeof POST = PATCH,
  body: unknown = CORRECTION,
) {
  return method(jsonRequest(body), {
    params: Promise.resolve({ id: 'visit-synthetic-1' }),
  });
}

beforeEach(() => {
  vi.clearAllMocks();
  mocks.sameOrigin.mockReturnValue(true);
  mocks.requireDoctorSession.mockResolvedValue(SESSION);
  mocks.reviewField.mockResolvedValue({
    manifestVersion: 5,
    status: 'verified',
    counts: { filled: 1, needsReview: 0, notMentioned: 0, conflicts: 0 },
    outputSha256: 'b'.repeat(64),
    roundTripVerified: true,
    certificationUrl: null,
  });
});

describe('visit Template Twin corrections route', () => {
  it('rejects cross-origin mutation before authentication or service work', async () => {
    mocks.sameOrigin.mockReturnValue(false);

    const response = await call();

    expect(response.status).toBe(403);
    expect(mocks.requireDoctorSession).not.toHaveBeenCalled();
    expect(mocks.reviewField).not.toHaveBeenCalled();
    expect(response.headers.get('Cache-Control')).toBe('no-store, private');
  });

  it('requires an authenticated physician session', async () => {
    mocks.requireDoctorSession.mockRejectedValue(
      new AuthError('UNAUTHENTICATED', 'expired'),
    );

    const response = await call();

    expect(response.status).toBe(401);
    expect(mocks.reviewField).not.toHaveBeenCalled();
  });

  it.each(['STAFF', 'ADMIN'] as const)(
    'rejects a fresh %s role before reading the correction payload',
    async (role) => {
      mocks.requireDoctorSession.mockRejectedValue(
        new AuthError('FORBIDDEN', `Synthetic ${role} is not a physician.`),
      );

      const response = await call();

      expect(response.status).toBe(403);
      expect(mocks.reviewField).not.toHaveBeenCalled();
    },
  );

  it.each([PATCH, POST])(
    'threads tenant ownership and the optimistic correction through %s',
    async (method) => {
      const response = await call(method);

      expect(response.status).toBe(200);
      expect(mocks.reviewField).toHaveBeenCalledWith({
        visitId: 'visit-synthetic-1',
        actor: {
          userId: SESSION.user.id,
          userEmail: SESSION.user.email,
          practiceId: SESSION.user.practiceId,
        },
        correction: CORRECTION,
      });
      expect(await response.json()).toEqual({
        ok: true,
        result: expect.objectContaining({ manifestVersion: 5 }),
      });
    },
  );

  it('maps a transaction-time optimistic race to conflict without leaking data', async () => {
    mocks.reviewField.mockRejectedValue(
      new TemplateTwinReviewError(
        'OPTIMISTIC_CONFLICT',
        'This review changed in another session. Refresh and try again.',
      ),
    );

    const response = await call();

    expect(response.status).toBe(409);
    expect(await response.json()).toEqual({
      ok: false,
      error: 'This review changed in another session. Refresh and try again.',
    });
  });

  it('rejects malformed field corrections before service execution', async () => {
    const response = await call(PATCH, {
      ...CORRECTION,
      fieldId: 'not-a-template-twin-field-id',
    });

    expect(response.status).toBe(400);
    expect(mocks.reviewField).not.toHaveBeenCalled();
  });
});
