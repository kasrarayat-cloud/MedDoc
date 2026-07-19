import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  requireDoctorSession: vi.fn(),
  mappingRateLimit: vi.fn(),
  updateMappings: vi.fn(),
  sameOrigin: vi.fn(),
  lifecycleGuard: vi.fn(async (input: { operation: () => unknown }) =>
    input.operation(),
  ),
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

vi.mock("@/lib/auth", () => ({
  AuthError: class AuthError extends Error {},
  requireDoctorSession: mocks.requireDoctorSession,
}));

vi.mock("@/lib/template-twin/mapping-save-rate-limit", () => ({
  templateTwinMappingSaveRateLimitOrError: mocks.mappingRateLimit,
}));

vi.mock("@/lib/template-twin/certification-lifecycle", () => ({
  TemplateTwinLifecycleError: class TemplateTwinLifecycleError extends Error {},
  updateTemplateTwinMappings: mocks.updateMappings,
}));

vi.mock("@/lib/template-twin/contracts", () => ({
  TemplateTwinUpdateMappingsRequestSchema: { safeParse: vi.fn() },
}));

vi.mock("@/lib/template-twin/request-security", () => ({
  isSameOriginTemplateTwinMutation: mocks.sameOrigin,
}));

vi.mock("@/lib/template-twin/staging-qa-lifecycle-guard", () => ({
  TemplateTwinStagingQaLifecycleGuardError: class TemplateTwinStagingQaLifecycleGuardError extends Error {},
  runWithTemplateTwinStagingQaLifecycleGuard: mocks.lifecycleGuard,
}));

import { PATCH } from "../route";

const SESSION = {
  templateTwinRolloutToken: {
    practiceId: "practice-synthetic-1",
    globalGeneration: BigInt(1),
    practiceGeneration: BigInt(1),
  },
  user: {
    id: "doctor-synthetic-1",
    email: "doctor@synthetic.test",
    practiceId: "practice-synthetic-1",
  },
};

beforeEach(() => {
  vi.clearAllMocks();
  mocks.sameOrigin.mockReturnValue(true);
  mocks.requireDoctorSession.mockResolvedValue(SESSION);
  mocks.mappingRateLimit.mockResolvedValue(null);
});

describe("Template Twin mapping-save rate limit", () => {
  it("uses the dedicated asynchronous mapping-save limiter", async () => {
    const blocked = {
      status: 429,
      headers: new Headers({
        "Cache-Control": "no-store, private",
        "Retry-After": "17",
      }),
      json: async () => ({
        ok: false,
        code: "RATE_LIMITED",
        error: "Mapping saves are temporarily limited.",
        retryAfterSec: 17,
        limitType: "burst_30s",
        resetAtIso: "2026-07-19T02:03:21.250Z",
      }),
    };
    mocks.mappingRateLimit.mockResolvedValue(blocked);
    const readBody = vi.fn();

    const response = await PATCH(
      {
        headers: new Headers(),
        json: readBody,
      } as unknown as Request,
      {
        params: Promise.resolve({ id: "template-synthetic-1" }),
      },
    );

    expect(response).toBe(blocked);
    expect(mocks.mappingRateLimit).toHaveBeenCalledWith(SESSION.user.id);
    expect(response.status).toBe(429);
    expect(response.headers.get("Retry-After")).toBe("17");
    expect(await response.json()).toMatchObject({
      ok: false,
      code: "RATE_LIMITED",
      retryAfterSec: 17,
      limitType: "burst_30s",
      resetAtIso: "2026-07-19T02:03:21.250Z",
    });
    expect(readBody).not.toHaveBeenCalled();
    expect(mocks.updateMappings).not.toHaveBeenCalled();
  });

  it("fails closed before reading mappings when Redis cannot verify the limiter", async () => {
    const unavailable = {
      status: 503,
      headers: new Headers({
        "Cache-Control": "no-store, private",
        "Retry-After": "5",
      }),
      json: async () => ({
        ok: false,
        code: "RATE_LIMIT_UNAVAILABLE",
        error: "The safety limiter could not be verified.",
        retryAfterSec: 5,
      }),
    };
    mocks.mappingRateLimit.mockResolvedValue(unavailable);
    const readBody = vi.fn();

    const response = await PATCH(
      {
        headers: new Headers(),
        json: readBody,
      } as unknown as Request,
      { params: Promise.resolve({ id: "template-synthetic-1" }) },
    );

    expect(response).toBe(unavailable);
    expect(response.status).toBe(503);
    expect(response.headers.get("Retry-After")).toBe("5");
    expect(readBody).not.toHaveBeenCalled();
    expect(mocks.updateMappings).not.toHaveBeenCalled();
  });
});
