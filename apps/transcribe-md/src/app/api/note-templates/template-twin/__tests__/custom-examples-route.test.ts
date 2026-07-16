import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  session: vi.fn(),
  run: vi.fn(),
  acknowledge: vi.fn(),
  sameOrigin: vi.fn(() => true),
}));

vi.mock("@/lib/auth", () => ({
  AuthError: class AuthError extends Error {
    code = "UNAUTHORIZED";
  },
  requireDoctorSession: mocks.session,
}));
vi.mock("@/lib/rate-limit", () => ({
  RATE_LIMITS: { SETTINGS: {} },
  rateLimitOr429: vi.fn(() => null),
}));
vi.mock("@/lib/template-twin/request-security", () => ({
  isSameOriginTemplateTwinMutation: mocks.sameOrigin,
}));
vi.mock("@/lib/template-twin/custom-example-service", () => ({
  TemplateTwinCustomExampleError: class TemplateTwinCustomExampleError extends Error {
    constructor(
      readonly code: string,
      message: string,
    ) {
      super(message);
    }
  },
  runTemplateTwinCustomExamples: mocks.run,
  acknowledgeTemplateTwinCustomExamples: mocks.acknowledge,
}));

import { POST } from "../[id]/custom-examples/route";

const COVERAGE = {
  requiredCount: 3,
  passedCount: 3,
  acknowledgedCount: 0,
  ready: false,
  stale: false,
  latestBatchId: "00000000-0000-4000-8000-000000000001",
  proofSha256: null,
  examples: [],
};

function request(body: unknown) {
  return new Request("https://app.example.test/api/template", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

describe("custom-concept example route", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.sameOrigin.mockReturnValue(true);
    mocks.session.mockResolvedValue({
      user: {
        id: "doctor-custom@example.test",
        email: "doctor-custom@example.test",
        practiceId: "practice-custom-example",
      },
      templateTwinRolloutToken: {
        practiceId: "practice-custom-example",
        globalGeneration: BigInt(2),
        practiceGeneration: BigInt(3),
      },
    });
    mocks.run.mockResolvedValue(COVERAGE);
    mocks.acknowledge.mockResolvedValue({
      ...COVERAGE,
      acknowledgedCount: 3,
      ready: true,
      proofSha256: "a".repeat(64),
    });
  });

  it("runs the exact saved example set for the authenticated physician", async () => {
    const response = await POST(request({ action: "run" }), {
      params: Promise.resolve({ id: "template-custom-example" }),
    });
    expect(response.status).toBe(200);
    expect(mocks.run).toHaveBeenCalledWith(
      expect.objectContaining({
        noteTemplateId: "template-custom-example",
        actor: expect.objectContaining({
          userId: "doctor-custom@example.test",
          practiceId: "practice-custom-example",
        }),
      }),
    );
  });

  it("records one-time physician acknowledgement for the exact batch", async () => {
    const response = await POST(
      request({ action: "acknowledge", batchId: COVERAGE.latestBatchId }),
      { params: Promise.resolve({ id: "template-custom-example" }) },
    );
    expect(response.status).toBe(200);
    expect(mocks.acknowledge).toHaveBeenCalledWith(
      expect.objectContaining({
        noteTemplateId: "template-custom-example",
        batchId: COVERAGE.latestBatchId,
      }),
    );
  });

  it("rejects malformed and cross-origin actions before persistence", async () => {
    expect(
      (
        await POST(request({ action: "acknowledge", batchId: "not-a-uuid" }), {
          params: Promise.resolve({ id: "template-custom-example" }),
        })
      ).status,
    ).toBe(400);
    mocks.sameOrigin.mockReturnValue(false);
    expect(
      (
        await POST(request({ action: "run" }), {
          params: Promise.resolve({ id: "template-custom-example" }),
        })
      ).status,
    ).toBe(403);
    expect(mocks.run).not.toHaveBeenCalled();
  });
});
