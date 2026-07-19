import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  requireDoctorSession: vi.fn(),
  mappingRateLimit: vi.fn(),
  updateMappings: vi.fn(),
  sameOrigin: vi.fn(),
  lifecycleGuard: vi.fn(async (input: { operation: () => unknown }) =>
    input.operation(),
  ),
  readWorkspace: vi.fn(),
  readGuardedRecovery: vi.fn(),
}));

vi.mock("next/server", () => {
  class FakeNextResponse {
    status: number;
    headers: Headers;
    constructor(
      private readonly payload: unknown,
      init?: { status?: number; headers?: Record<string, string> },
    ) {
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
  requireDoctorSession: mocks.requireDoctorSession,
}));
vi.mock("@/lib/template-twin/mapping-save-rate-limit", () => ({
  templateTwinMappingSaveRateLimitOrError: mocks.mappingRateLimit,
}));
vi.mock("@/lib/template-twin/certification-lifecycle", () => ({
  TemplateTwinLifecycleError: class TemplateTwinLifecycleError extends Error {
    constructor(
      readonly code: string,
      message: string,
      readonly fieldErrors: readonly unknown[] = [],
    ) {
      super(message);
    }
  },
  updateTemplateTwinMappings: mocks.updateMappings,
}));
vi.mock("@/lib/template-twin/request-security", () => ({
  isSameOriginTemplateTwinMutation: mocks.sameOrigin,
}));
vi.mock("@/lib/template-twin/staging-qa-lifecycle-guard", () => ({
  TemplateTwinStagingQaLifecycleGuardError: class TemplateTwinStagingQaLifecycleGuardError extends Error {},
  runWithTemplateTwinStagingQaLifecycleGuard: mocks.lifecycleGuard,
}));
vi.mock("@/lib/template-twin/workspace-read", () => ({
  readTemplateTwinWorkspace: mocks.readWorkspace,
}));
vi.mock("@/lib/template-twin/workspace-recovery-guarded", () => ({
  readGuardedTemplateTwinWorkspaceRecovery: mocks.readGuardedRecovery,
}));

import { PATCH } from "../route";
import { TemplateTwinLifecycleError } from "@/lib/template-twin/certification-lifecycle";
import { TemplateTwinStagingQaLifecycleGuardError } from "@/lib/template-twin/staging-qa-lifecycle-guard";

const FIELD_ID = `ttf_${"b".repeat(24)}`;
const HASH = "a".repeat(64);
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

function request(body: unknown): Request {
  return { headers: new Headers(), json: async () => body } as Request;
}

function validMapping() {
  return {
    fieldId: FIELD_ID,
    clinicalConcept: null,
    expectedDataType: "text",
    polarityBehavior: "value_only",
    temporality: "any",
    laterality: "not_applicable",
    unitPolicy: "not_applicable",
    approvedSynonyms: [],
    required: true,
    blankPolicy: "requires_input",
    unknownPolicy: "requires_input",
    practiceDefault: null,
    status: "certified",
  };
}

beforeEach(() => {
  vi.clearAllMocks();
  mocks.sameOrigin.mockReturnValue(true);
  mocks.requireDoctorSession.mockResolvedValue(SESSION);
  mocks.mappingRateLimit.mockResolvedValue(null);
  mocks.lifecycleGuard.mockImplementation(
    async (input: { operation: () => unknown }) => input.operation(),
  );
  mocks.readWorkspace.mockResolvedValue(null);
  mocks.readGuardedRecovery.mockResolvedValue(null);
});

describe("mapping route validation and version recovery", () => {
  it("identifies the exact field and clinical-detail setting before service work", async () => {
    const response = await PATCH(
      request({
        expectedMappingsSha256: HASH,
        expectedFieldIntentsSha256: HASH,
        mappings: [validMapping()],
        fieldIntents: [
          {
            fieldId: FIELD_ID,
            intentKind: "supported_concept",
            supportedConcept: "",
          },
        ],
      }),
      { params: Promise.resolve({ id: "template-v1" }) },
    );

    expect(response.status).toBe(422);
    expect(await response.json()).toMatchObject({
      ok: false,
      code: "MAPPING_INVALID",
      fieldErrors: [
        {
          fieldId: FIELD_ID,
          setting: "clinicalDetail",
          message: "Choose a clinical detail before confirming this field.",
        },
      ],
    });
    expect(mocks.updateMappings).not.toHaveBeenCalled();
  });

  it("returns current workspace state for a recoverable optimistic conflict", async () => {
    const latestWorkspace = {
      template: { id: "template-v1", version: 1 },
      mappingsSha256: "c".repeat(64),
    };
    mocks.updateMappings.mockRejectedValue(
      new TemplateTwinLifecycleError(
        "CONFLICT",
        "This mapping draft changed in another tab.",
      ),
    );
    mocks.readWorkspace.mockResolvedValue(latestWorkspace);

    const response = await PATCH(
      request({
        expectedMappingsSha256: HASH,
        mappings: [{ ...validMapping(), clinicalConcept: "chief_complaint" }],
      }),
      { params: Promise.resolve({ id: "template-v1" }) },
    );

    expect(response.status).toBe(409);
    expect(await response.json()).toMatchObject({
      ok: false,
      code: "VERSION_CONFLICT",
      recoverable: true,
      latestTemplateId: "template-v1",
      latestWorkspace,
    });
    const guardInput = mocks.lifecycleGuard.mock.calls[0]?.[0] as unknown as {
      isExpectedBusinessError?: (error: unknown) => boolean;
    };
    expect(
      guardInput.isExpectedBusinessError?.(
        new TemplateTwinLifecycleError("CONFLICT", "conflict"),
      ),
    ).toBe(true);
    expect(
      guardInput.isExpectedBusinessError?.(
        new Error("privacy provider unavailable"),
      ),
    ).toBe(false);
  });

  it("turns a stale lifecycle guard into a successor/rebase response", async () => {
    const latestWorkspace = {
      template: { id: "template-v2", version: 2 },
      canEdit: true,
      mappingsSha256: "c".repeat(64),
    };
    mocks.lifecycleGuard.mockRejectedValue(
      new TemplateTwinStagingQaLifecycleGuardError(),
    );
    mocks.readGuardedRecovery.mockResolvedValue({
      candidate: { id: "template-v2", version: 2 },
      workspace: latestWorkspace,
    });

    const response = await PATCH(
      request({
        expectedMappingsSha256: HASH,
        mappings: [{ ...validMapping(), clinicalConcept: "chief_complaint" }],
      }),
      { params: Promise.resolve({ id: "template-v1" }) },
    );

    expect(response.status).toBe(409);
    expect(await response.json()).toEqual({
      ok: false,
      code: "VERSION_STALE",
      error:
        "This Template Twin version changed or its synthetic authorization expired. Refresh an available version to recover your draft.",
      recoverable: true,
      latestTemplateId: "template-v2",
      latestWorkspace,
    });
  });

  it("returns only a guarded editable successor for an immutable version", async () => {
    const successorWorkspace = {
      template: { id: "template-v2", version: 2 },
      canEdit: true,
      mappingsSha256: "d".repeat(64),
    };
    mocks.updateMappings.mockRejectedValue(
      new TemplateTwinLifecycleError(
        "IMMUTABLE",
        "legacy immutable message",
      ),
    );
    mocks.readWorkspace.mockResolvedValue({
      template: { id: "template-v1", version: 1 },
      canEdit: false,
    });
    mocks.readGuardedRecovery.mockResolvedValue({
      candidate: { id: "template-v2", version: 2 },
      workspace: successorWorkspace,
    });

    const response = await PATCH(
      request({
        expectedMappingsSha256: HASH,
        mappings: [{ ...validMapping(), clinicalConcept: "chief_complaint" }],
      }),
      { params: Promise.resolve({ id: "template-v1" }) },
    );

    expect(response.status).toBe(409);
    expect(await response.json()).toEqual({
      ok: false,
      code: "VERSION_IMMUTABLE",
      error:
        "This saved version is immutable. Refresh its editable successor to recover your draft.",
      recoverable: true,
      latestTemplateId: "template-v2",
      latestWorkspace: successorWorkspace,
      fieldErrors: [],
    });
    expect(mocks.readWorkspace).not.toHaveBeenCalled();
  });
});
