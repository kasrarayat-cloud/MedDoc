import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  session: vi.fn(),
  rateLimit: vi.fn(),
  sameOrigin: vi.fn(),
  issuePreview: vi.fn(),
  stagingRequested: vi.fn(),
}));

vi.mock("next/server", () => {
  class FakeNextResponse {
    readonly status: number;
    readonly headers: Headers;
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
  AuthError: class AuthError extends Error {
    constructor(
      readonly code: "UNAUTHENTICATED" | "FORBIDDEN",
      message: string,
    ) {
      super(message);
    }
  },
  requireDoctorSession: mocks.session,
}));

vi.mock("@/lib/rate-limit", () => ({
  RATE_LIMITS: { SETTINGS: {} },
  rateLimitOr429: mocks.rateLimit,
}));

vi.mock("@/lib/template-twin/completed-candidate-service", () => ({
  CompletedCandidateServiceError: class CompletedCandidateServiceError extends Error {
    constructor(
      readonly code: string,
      message: string,
    ) {
      super(message);
    }
  },
  issueCompletedCandidateReviewPreview: mocks.issuePreview,
}));

vi.mock("@/lib/template-twin/request-security", () => ({
  isSameOriginTemplateTwinMutation: mocks.sameOrigin,
}));

vi.mock("@/lib/template-twin/staging-qa-gate", () => ({
  isTemplateTwinStagingQaRequested: mocks.stagingRequested,
}));

import { POST } from "../route";

const CANDIDATE_ID = "123e4567-e89b-42d3-a456-426614174000";
const RECEIPT = `${CANDIDATE_ID}.${"A".repeat(43)}`;
const SESSION = {
  user: {
    id: "doctor_candidate_synthetic",
    email: "doctor@synthetic.test",
    practiceId: "practice_candidate_synthetic",
  },
  templateTwinRolloutToken: {
    practiceId: "practice_candidate_synthetic",
    globalGeneration: BigInt(2),
    practiceGeneration: BigInt(3),
  },
};

function request() {
  return new Request(
    `https://app.example.test/api/note-templates/template-twin/completed-candidate/${CANDIDATE_ID}/review-preview`,
    { method: "POST" },
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  vi.stubEnv("TEMPLATE_TWIN_COMPLETED_CANDIDATE_MODE", "synthetic-review-v1");
  mocks.stagingRequested.mockReturnValue(false);
  mocks.sameOrigin.mockReturnValue(true);
  mocks.rateLimit.mockReturnValue(null);
  mocks.session.mockResolvedValue(SESSION);
  mocks.issuePreview.mockResolvedValue({
    projection: { profileVersion: "safe-redacted-projection" },
    reviewReceipt: RECEIPT,
    expiresAtIso: "2026-07-19T10:15:00.000Z",
  });
});

afterEach(() => {
  vi.unstubAllEnvs();
});

describe("completed candidate review-preview route", () => {
  it("rejects cross-origin requests before authentication", async () => {
    mocks.sameOrigin.mockReturnValue(false);
    const response = await POST(request(), {
      params: Promise.resolve({ id: CANDIDATE_ID }),
    });

    expect(response.status).toBe(403);
    expect(mocks.session).not.toHaveBeenCalled();
    expect(mocks.issuePreview).not.toHaveBeenCalled();
  });

  it("returns one no-store memory-only proof for the authenticated owner", async () => {
    const response = await POST(request(), {
      params: Promise.resolve({ id: CANDIDATE_ID }),
    });

    expect(response.status).toBe(200);
    expect(response.headers.get("cache-control")).toBe("no-store, private");
    expect(response.headers.get("referrer-policy")).toBe("no-referrer");
    await expect(response.json()).resolves.toMatchObject({
      ok: true,
      reviewReceipt: RECEIPT,
      expiresAtIso: "2026-07-19T10:15:00.000Z",
    });
    expect(mocks.issuePreview).toHaveBeenCalledWith({
      candidateId: CANDIDATE_ID,
      actor: {
        userId: SESSION.user.id,
        userEmail: SESSION.user.email,
        practiceId: SESSION.user.practiceId,
        rolloutToken: SESSION.templateTwinRolloutToken,
      },
    });
  });
});
