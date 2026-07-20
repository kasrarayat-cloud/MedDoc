import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  findTemplate: vi.fn(),
  rateLimitOr429: vi.fn(),
  requireDoctorSession: vi.fn(),
  runSyntheticTest: vi.fn(),
  transcribeSyntheticVoice: vi.fn(),
}));

vi.mock("next/server", () => {
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

vi.mock("@meddoc/db", () => ({
  default: {
    noteTemplate: { findFirst: mocks.findTemplate },
  },
}));
vi.mock("@/lib/auth", () => ({
  AuthError: class AuthError extends Error {
    constructor(
      public readonly code: "UNAUTHENTICATED" | "FORBIDDEN",
      message: string,
    ) {
      super(message);
    }
  },
  requireDoctorSession: mocks.requireDoctorSession,
}));
vi.mock("@/lib/audio-sniff", () => ({
  SNIFF_MIN_BYTES: 12,
  sniffAudioMagicBytes: () => ({ detected: "audio/webm" }),
  magicBytesMatchClaimedMime: () => true,
}));
vi.mock("@/lib/rate-limit", () => ({
  RATE_LIMITS: { UPLOAD: { key: "synthetic-upload" } },
  rateLimitOr429: mocks.rateLimitOr429,
}));
vi.mock("@/lib/template-twin/request-security", () => ({
  isSameOriginTemplateTwinMutation: () => true,
  boundedMultipartFormData: (request: Request) => request.formData(),
  isMultipartFile: (value: unknown) =>
    Boolean(
      value &&
      typeof value === "object" &&
      "arrayBuffer" in value &&
      typeof value.arrayBuffer === "function",
    ),
  TemplateTwinMultipartError: class TemplateTwinMultipartError extends Error {
    code = "MULTIPART_INVALID";
  },
}));
vi.mock("@/lib/template-twin/synthetic-voice-provider", () => ({
  TemplateTwinSyntheticVoiceProviderError: class TemplateTwinSyntheticVoiceProviderError extends Error {},
  transcribeTemplateTwinSyntheticVoice: mocks.transcribeSyntheticVoice,
}));
vi.mock("@/lib/template-twin/synthetic-test", () => ({
  TemplateTwinSyntheticTestError: class TemplateTwinSyntheticTestError extends Error {
    code = "CONFLICT";
  },
  runTemplateTwinSyntheticTest: mocks.runSyntheticTest,
}));

import { POST } from "../[id]/synthetic-test-voice/route";
import { AuthError } from "@/lib/auth";
import { TemplateTwinSyntheticVoiceProviderError } from "@/lib/template-twin/synthetic-voice-provider";
const HASH = "a".repeat(64);
const SESSION = {
  templateTwinRolloutToken: {
    practiceId: "practice-synthetic-voice",
    globalGeneration: BigInt(6),
    practiceGeneration: BigInt(10),
  },
  user: {
    id: "doctor-synthetic-voice",
    email: "voice-doctor@synthetic.test",
    practiceId: "practice-synthetic-voice",
  },
};

beforeEach(() => {
  vi.clearAllMocks();
  mocks.requireDoctorSession.mockResolvedValue(SESSION);
  mocks.rateLimitOr429.mockReturnValue(null);
  mocks.findTemplate.mockResolvedValue({
    templateTwinCompiledVersion: {
      certificationStatus: "NEEDS_CONFIRMATION",
    },
  });
  mocks.transcribeSyntheticVoice.mockResolvedValue({
    transcript: "Synthetic voice encounter evidence only.",
  });
  mocks.runSyntheticTest.mockResolvedValue({
    template: { id: "template-synthetic-voice" },
    mappingsSha256: HASH,
  });
});

describe("Template Twin synthetic voice certification route", () => {
  it.each(["STAFF", "ADMIN"] as const)(
    "rejects a fresh %s role before template lookup or transcription",
    async (role) => {
      mocks.requireDoctorSession.mockRejectedValue(
        new AuthError("FORBIDDEN", `Synthetic ${role} is not a physician.`),
      );

      const response = await POST(
        { headers: new Headers() } as unknown as Request,
        { params: Promise.resolve({ id: "template-synthetic-voice" }) },
      );

      expect(response.status).toBe(403);
      expect(mocks.findTemplate).not.toHaveBeenCalled();
      expect(mocks.transcribeSyntheticVoice).not.toHaveBeenCalled();
      expect(mocks.runSyntheticTest).not.toHaveBeenCalled();
    },
  );

  it("passes the exact audio identity only to the owned synthetic voice service", async () => {
    const form = new FormData();
    form.set(
      "audio",
      new File([Buffer.alloc(32, 1)], "synthetic-voice.webm", {
        type: "audio/webm",
      }),
    );
    form.set("expectedMappingsSha256", HASH);

    const response = await POST(
      {
        headers: new Headers(),
        formData: async () => form,
      } as unknown as Request,
      { params: Promise.resolve({ id: "template-synthetic-voice" }) },
    );

    expect(response.status).toBe(200);
    expect(mocks.findTemplate).toHaveBeenCalledWith({
      where: {
        id: "template-synthetic-voice",
        doctorId: SESSION.user.id,
        templateKind: "template_twin_docx",
      },
      select: {
        templateTwinCompiledVersion: {
          select: {
            certificationStatus: true,
          },
        },
      },
    });
    expect(mocks.transcribeSyntheticVoice).toHaveBeenCalledWith({
      noteTemplateId: "template-synthetic-voice",
      actor: {
        userId: SESSION.user.id,
        userEmail: SESSION.user.email,
        practiceId: SESSION.user.practiceId,
        rolloutToken: SESSION.templateTwinRolloutToken,
      },
      audio: expect.any(Buffer),
      mimeType: "audio/webm",
      audioSha256: expect.stringMatching(/^[a-f0-9]{64}$/),
      expectedMappingConfirmation: { mappingsSha256: HASH },
    });
    expect(
      mocks.transcribeSyntheticVoice.mock.invocationCallOrder[0],
    ).toBeLessThan(mocks.runSyntheticTest.mock.invocationCallOrder[0]!);
    expect(mocks.runSyntheticTest).toHaveBeenCalledWith({
      noteTemplateId: "template-synthetic-voice",
      actor: {
        userId: SESSION.user.id,
        userEmail: SESSION.user.email,
        practiceId: SESSION.user.practiceId,
        rolloutToken: SESSION.templateTwinRolloutToken,
      },
      expectedMappingsSha256: HASH,
      expectedFieldIntentsSha256: undefined,
      encounterText: "Synthetic voice encounter evidence only.",
      encounterMode: "dictation",
    });
    expect(await response.json()).toEqual({
      ok: true,
      workspace: {
        template: { id: "template-synthetic-voice" },
        mappingsSha256: HASH,
      },
    });
  });

  it("rejects an ordinary or unowned template before synthetic testing", async () => {
    mocks.transcribeSyntheticVoice.mockRejectedValue(
      new TemplateTwinSyntheticVoiceProviderError(),
    );
    const form = new FormData();
    form.set(
      "audio",
      new File([Buffer.alloc(32, 1)], "synthetic-voice.webm", {
        type: "audio/webm",
      }),
    );
    form.set("expectedMappingsSha256", HASH);

    const response = await POST(
      {
        headers: new Headers(),
        formData: async () => form,
      } as unknown as Request,
      { params: Promise.resolve({ id: "template-synthetic-voice" }) },
    );

    expect(response.status).toBe(422);
    expect(mocks.transcribeSyntheticVoice).toHaveBeenCalledOnce();
    expect(mocks.runSyntheticTest).not.toHaveBeenCalled();
    expect(await response.json()).toMatchObject({
      ok: false,
      code: "SYNTHETIC_VOICE_UNAVAILABLE",
    });
  });
});
