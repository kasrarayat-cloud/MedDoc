// @vitest-environment node

import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  requireDoctor: vi.fn(),
  loadReviewed: vi.fn(),
  lifecycleGuard: vi.fn(),
}));

vi.mock("@/lib/auth", () => ({
  AuthError: class AuthError extends Error {
    constructor(
      public readonly code: string,
      message: string,
    ) {
      super(message);
    }
  },
  requireDoctorSession: mocks.requireDoctor,
}));
vi.mock("@/lib/template-twin/staging-qa-reviewed-mappings", () => ({
  TemplateTwinStagingQaReviewedMappingsError:
    class TemplateTwinStagingQaReviewedMappingsError extends Error {
      constructor(
        public readonly code: string,
        message: string,
      ) {
        super(message);
      }
    },
  loadTemplateTwinStagingQaReviewedMappingDraft: mocks.loadReviewed,
}));
vi.mock("@/lib/template-twin/staging-qa-lifecycle-guard", () => ({
  TemplateTwinStagingQaLifecycleGuardError:
    class TemplateTwinStagingQaLifecycleGuardError extends Error {},
  runWithTemplateTwinStagingQaLifecycleGuard: mocks.lifecycleGuard,
}));

import { AuthError } from "@/lib/auth";
import { TemplateTwinStagingQaLifecycleGuardError } from "@/lib/template-twin/staging-qa-lifecycle-guard";
import { TemplateTwinStagingQaReviewedMappingsError } from "@/lib/template-twin/staging-qa-reviewed-mappings";

import { POST } from "../route";

const ENDPOINT =
  "https://app.synthetic.test/api/note-templates/template-twin/template-reviewed-1/staging-qa/reviewed-mappings";
const REVIEWED = {
  contractVersion: "template-twin-staging-reviewed-mappings/1.0.0",
  template: { id: "template-reviewed-1", version: 1 },
  mappings: Array.from({ length: 8 }, (_, index) => ({ index })),
  fieldIntents: [{ intentKind: "supported_concept" }],
  physicianReviewSummary: {
    fieldCount: 8,
    explicitConfirmationRequired: true,
    activationPerformed: false,
  },
};

function request(origin = "https://app.synthetic.test"): Request {
  return new Request(ENDPOINT, {
    method: "POST",
    headers: {
      origin,
      "sec-fetch-site":
        origin === "https://app.synthetic.test" ? "same-origin" : "cross-site",
    },
  });
}

function context() {
  return { params: Promise.resolve({ id: "template-reviewed-1" }) };
}

beforeEach(() => {
  vi.clearAllMocks();
  mocks.requireDoctor.mockResolvedValue({
    user: {
      id: "doctor-reviewed-1",
      email: "doctor@synthetic.test",
      practiceId: "practice-reviewed-1",
    },
    templateTwinRolloutToken: {
      practiceId: "practice-reviewed-1",
      globalGeneration: BigInt(2),
      practiceGeneration: BigInt(3),
    },
  });
  mocks.loadReviewed.mockResolvedValue(REVIEWED);
  mocks.lifecycleGuard.mockImplementation(
    (input: { operation: () => unknown }) => input.operation(),
  );
});

describe("reviewed synthetic mappings route", () => {
  it("returns the read-only reviewed draft through exact doctor, practice, and staging guards", async () => {
    const result = await POST(request(), context());

    expect(result.status).toBe(200);
    expect(result.headers.get("cache-control")).toBe("no-store, private");
    await expect(result.json()).resolves.toEqual({
      ok: true,
      reviewed: REVIEWED,
    });
    expect(mocks.loadReviewed).toHaveBeenCalledWith({
      noteTemplateId: "template-reviewed-1",
      doctorId: "doctor-reviewed-1",
      practiceId: "practice-reviewed-1",
    });
    expect(mocks.lifecycleGuard).toHaveBeenCalledWith(
      expect.objectContaining({
        noteTemplateId: "template-reviewed-1",
        purpose: "reviewed-mappings-load",
        actor: expect.objectContaining({
          userId: "doctor-reviewed-1",
          practiceId: "practice-reviewed-1",
        }),
        operation: expect.any(Function),
      }),
    );
    expect(mocks.loadReviewed.mock.invocationCallOrder[0]).toBeLessThan(
      mocks.lifecycleGuard.mock.invocationCallOrder[0]!,
    );
  });

  it("rejects cross-origin requests before authentication or fixture reads", async () => {
    const result = await POST(request("https://evil.synthetic.test"), context());

    expect(result.status).toBe(403);
    expect(mocks.requireDoctor).not.toHaveBeenCalled();
    expect(mocks.loadReviewed).not.toHaveBeenCalled();
    expect(mocks.lifecycleGuard).not.toHaveBeenCalled();
  });

  it("fails closed for arbitrary or structurally drifted templates", async () => {
    mocks.loadReviewed.mockRejectedValue(
      new TemplateTwinStagingQaReviewedMappingsError(
        "CONTRACT_MISMATCH",
        "field lookalike drifted",
      ),
    );
    const result = await POST(request(), context());

    expect(result.status).toBe(404);
    await expect(result.json()).resolves.toEqual({
      ok: false,
      error: "Reviewed synthetic mappings are unavailable.",
    });
    expect(mocks.lifecycleGuard).not.toHaveBeenCalled();
  });

  it("keeps immutable versions recoverable without loading into them", async () => {
    mocks.loadReviewed.mockRejectedValue(
      new TemplateTwinStagingQaReviewedMappingsError(
        "NOT_EDITABLE",
        "Reviewed synthetic mappings can be loaded only into an editable draft version.",
      ),
    );
    const result = await POST(request(), context());

    expect(result.status).toBe(409);
    await expect(result.json()).resolves.toMatchObject({
      ok: false,
      error: expect.stringMatching(/editable draft version/u),
    });
  });

  it("requires a current doctor session", async () => {
    mocks.requireDoctor.mockRejectedValue(
      new AuthError("UNAUTHENTICATED", "login required"),
    );
    const result = await POST(request(), context());

    expect(result.status).toBe(401);
    await expect(result.json()).resolves.toEqual({
      ok: false,
      error: "Sign in again before loading reviewed mappings.",
    });
    expect(mocks.loadReviewed).not.toHaveBeenCalled();
  });

  it("does not disclose eligibility when the staging lifecycle guard denies admission", async () => {
    mocks.lifecycleGuard.mockRejectedValue(
      new TemplateTwinStagingQaLifecycleGuardError(),
    );
    const result = await POST(request(), context());

    expect(result.status).toBe(404);
    await expect(result.json()).resolves.toEqual({
      ok: false,
      error: "Reviewed synthetic mappings are unavailable.",
    });
  });
});
