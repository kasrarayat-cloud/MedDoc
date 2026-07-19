import { beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  requireDoctorSession: vi.fn(),
  findFirst: vi.fn(),
  readOutputArtifact: vi.fn(),
}));

vi.mock('next/server', () => {
  class FakeNextResponse {
    status: number;
    body: unknown;

    constructor(body: unknown, init?: { status?: number }) {
      this.body = body;
      this.status = init?.status ?? 200;
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
  default: { noteTemplate: { findFirst: mocks.findFirst } },
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
vi.mock('@/lib/template-twin/storage', () => ({
  DOCX_MIME_TYPE:
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  createTemplateTwinArtifactStore: () => ({
    readOutputArtifact: mocks.readOutputArtifact,
  }),
}));

import { AuthError } from '@/lib/auth';

import { GET } from '../[id]/test-output/route';

function call() {
  return GET({} as Request, {
    params: Promise.resolve({ id: 'template-1' }),
  });
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe('GET Template Twin synthetic test output authorization', () => {
  it.each(['STAFF', 'ADMIN'] as const)(
    'rejects a fresh %s role before template or object lookup',
    async (role) => {
      mocks.requireDoctorSession.mockRejectedValue(
        new AuthError('FORBIDDEN', `Synthetic ${role} is not a physician.`),
      );

      const response = await call();

      expect(response.status).toBe(403);
      expect(mocks.findFirst).not.toHaveBeenCalled();
      expect(mocks.readOutputArtifact).not.toHaveBeenCalled();
    },
  );
});
