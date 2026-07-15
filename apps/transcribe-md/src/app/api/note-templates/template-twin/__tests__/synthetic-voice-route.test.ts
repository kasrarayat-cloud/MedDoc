import { beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  findTemplate: vi.fn(),
  rateLimitOr429: vi.fn(),
  requireDoctorSession: vi.fn(),
  runSyntheticTest: vi.fn(),
  transcribe: vi.fn(),
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

vi.mock('@meddoc/ai', () => ({ transcribe: mocks.transcribe }));
vi.mock('@meddoc/db', () => ({
  default: {
    noteTemplate: { findFirst: mocks.findTemplate },
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
vi.mock('@/lib/audio-sniff', () => ({
  SNIFF_MIN_BYTES: 12,
  sniffAudioMagicBytes: () => ({ detected: 'audio/webm' }),
  magicBytesMatchClaimedMime: () => true,
}));
vi.mock('@/lib/rate-limit', () => ({
  RATE_LIMITS: { UPLOAD: { key: 'synthetic-upload' } },
  rateLimitOr429: mocks.rateLimitOr429,
}));
vi.mock('@/lib/template-twin/request-security', () => ({
  isSameOriginTemplateTwinMutation: () => true,
}));
vi.mock('@/lib/template-twin/synthetic-test', () => ({
  TemplateTwinSyntheticTestError: class TemplateTwinSyntheticTestError extends Error {
    code = 'CONFLICT';
  },
  runTemplateTwinSyntheticTest: mocks.runSyntheticTest,
}));

import { POST } from '../[id]/synthetic-test-voice/route';
import { AuthError } from '@/lib/auth';

const HASH = 'a'.repeat(64);
const SESSION = {
  user: {
    id: 'doctor-synthetic-voice',
    email: 'voice-doctor@synthetic.test',
    practiceId: 'practice-synthetic-voice',
  },
};

beforeEach(() => {
  vi.clearAllMocks();
  mocks.requireDoctorSession.mockResolvedValue(SESSION);
  mocks.rateLimitOr429.mockReturnValue(null);
  mocks.findTemplate.mockResolvedValue({
    templateTwinCompiledVersion: {
      certificationStatus: 'DRAFT',
      sourceArtifact: { practiceId: SESSION.user.practiceId },
    },
  });
  mocks.transcribe.mockResolvedValue({
    transcript: 'Synthetic voice encounter evidence only.',
  });
  mocks.runSyntheticTest.mockResolvedValue({
    template: { id: 'template-synthetic-voice' },
    mappingsSha256: HASH,
  });
});

describe('Template Twin synthetic voice certification route', () => {
  it.each(['STAFF', 'ADMIN'] as const)(
    'rejects a fresh %s role before template lookup or transcription',
    async (role) => {
      mocks.requireDoctorSession.mockRejectedValue(
        new AuthError('FORBIDDEN', `Synthetic ${role} is not a physician.`),
      );

      const response = await POST(
        { headers: new Headers() } as unknown as Request,
        { params: Promise.resolve({ id: 'template-synthetic-voice' }) },
      );

      expect(response.status).toBe(403);
      expect(mocks.findTemplate).not.toHaveBeenCalled();
      expect(mocks.transcribe).not.toHaveBeenCalled();
      expect(mocks.runSyntheticTest).not.toHaveBeenCalled();
    },
  );

  it('uses the shared transcription boundary without fallback, then runs the dictation fill pipeline', async () => {
    const form = new FormData();
    form.set(
      'audio',
      new File([Buffer.alloc(32, 1)], 'synthetic-voice.webm', {
        type: 'audio/webm',
      }),
    );
    form.set('expectedMappingsSha256', HASH);

    const response = await POST(
      {
        headers: new Headers(),
        formData: async () => form,
      } as unknown as Request,
      { params: Promise.resolve({ id: 'template-synthetic-voice' }) },
    );

    expect(response.status).toBe(200);
    expect(mocks.findTemplate).toHaveBeenCalledWith({
      where: {
        id: 'template-synthetic-voice',
        doctorId: SESSION.user.id,
        templateKind: 'template_twin_docx',
      },
      select: {
        templateTwinCompiledVersion: {
          select: {
            certificationStatus: true,
            sourceArtifact: { select: { practiceId: true } },
          },
        },
      },
    });
    expect(mocks.transcribe).toHaveBeenCalledWith({
      practiceId: SESSION.user.practiceId,
      userId: SESSION.user.id,
      visitId: null,
      purpose: 'tm_transcribe',
      audio: expect.any(Buffer),
      mimeType: 'audio/webm',
      allowCrossProviderFallback: false,
      deepgram: { options: { diarize: false, utterances: false } },
    });
    expect(mocks.runSyntheticTest).toHaveBeenCalledWith({
      noteTemplateId: 'template-synthetic-voice',
      actor: {
        userId: SESSION.user.id,
        userEmail: SESSION.user.email,
        practiceId: SESSION.user.practiceId,
      },
      expectedMappingsSha256: HASH,
      encounterText: 'Synthetic voice encounter evidence only.',
      encounterMode: 'dictation',
    });
    expect(await response.json()).toEqual({
      ok: true,
      workspace: {
        template: { id: 'template-synthetic-voice' },
        mappingsSha256: HASH,
      },
    });
  });
});
