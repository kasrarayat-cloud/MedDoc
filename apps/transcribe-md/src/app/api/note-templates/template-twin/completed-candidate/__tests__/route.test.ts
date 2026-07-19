import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  session: vi.fn(),
  rateLimit: vi.fn(),
  sameOrigin: vi.fn(),
  boundedMultipart: vi.fn(),
  createCandidate: vi.fn(),
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
  RATE_LIMITS: { UPLOAD: {} },
  rateLimitOr429: mocks.rateLimit,
}));

vi.mock("@/lib/note-template-docx", () => ({
  TemplateDocxError: class TemplateDocxError extends Error {
    code = "XML_INVALID";
  },
}));

vi.mock("@/lib/template-twin/completed-candidate-converter", () => ({
  CompletedCandidateConversionError: class CompletedCandidateConversionError extends Error {
    code = "STRUCTURE_MISMATCH";
  },
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
  createCompletedCandidate: mocks.createCandidate,
}));

vi.mock("@/lib/template-twin/malware-scan", () => ({
  TemplateTwinMalwareRejectedError: class TemplateTwinMalwareRejectedError extends Error {},
  TemplateTwinMalwareScanUnavailableError: class TemplateTwinMalwareScanUnavailableError extends Error {},
}));

vi.mock("@/lib/template-twin/quarantine-admission", () => ({
  TemplateTwinQuarantineError: class TemplateTwinQuarantineError extends Error {
    code = "TEMPLATE_TWIN_QUARANTINE_STATE_CONFLICT";
  },
}));

vi.mock("@/lib/template-twin/request-security", () => ({
  boundedMultipartFormData: mocks.boundedMultipart,
  isMultipartFile: (value: unknown) => value instanceof File,
  isSameOriginTemplateTwinMutation: mocks.sameOrigin,
  TemplateTwinMultipartError: class TemplateTwinMultipartError extends Error {
    code = "MULTIPART_INVALID";
  },
}));

vi.mock("@/lib/template-twin/staging-qa-gate", () => ({
  isTemplateTwinStagingQaRequested: mocks.stagingRequested,
}));

vi.mock("@/lib/template-twin/storage", () => ({
  TemplateTwinArtifactTooLargeError: class TemplateTwinArtifactTooLargeError extends Error {},
  TemplateTwinStorageUnavailableError: class TemplateTwinStorageUnavailableError extends Error {},
}));

import { POST } from "../route";

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
    "https://app.example.test/api/note-templates/template-twin/completed-candidate",
    { method: "POST", body: new Uint8Array([1]) },
  );
}

function intake(attested = true): FormData {
  const form = new FormData();
  form.append(
    "examples",
    new File(["one"], "synthetic-one.docx", {
      type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    }),
  );
  form.append(
    "examples",
    new File(["two"], "synthetic-two.docx", {
      type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    }),
  );
  form.set("candidateName", "Synthetic candidate");
  form.set("encounterScope", "Synthetic follow-up");
  form.set("versionDescription", "Two matching synthetic examples");
  form.set("syntheticAttestation", String(attested));
  return form;
}

beforeEach(() => {
  vi.clearAllMocks();
  vi.stubEnv(
    "TEMPLATE_TWIN_COMPLETED_CANDIDATE_MODE",
    "synthetic-review-v1",
  );
  mocks.stagingRequested.mockReturnValue(false);
  mocks.sameOrigin.mockReturnValue(true);
  mocks.rateLimit.mockReturnValue(null);
  mocks.session.mockResolvedValue(SESSION);
  mocks.boundedMultipart.mockResolvedValue(intake());
  mocks.createCandidate.mockResolvedValue({
    candidateId: "123e4567-e89b-42d3-a456-426614174000",
    reviewUrl:
      "/settings/note-format/completed-candidate/123e4567-e89b-42d3-a456-426614174000",
  });
});

afterEach(() => {
  vi.unstubAllEnvs();
});

describe("completed candidate upload route", () => {
  it("is undiscoverable unless the exact synthetic selector is present", async () => {
    vi.stubEnv("TEMPLATE_TWIN_COMPLETED_CANDIDATE_MODE", "true");
    const response = await POST(request());
    expect(response.status).toBe(404);
    expect(mocks.session).not.toHaveBeenCalled();
  });

  it("stays hidden from the staging-only surface", async () => {
    mocks.stagingRequested.mockReturnValue(true);
    const response = await POST(request());
    expect(response.status).toBe(404);
    expect(mocks.session).not.toHaveBeenCalled();
  });

  it("rejects cross-origin requests before authentication or parsing", async () => {
    mocks.sameOrigin.mockReturnValue(false);
    const response = await POST(request());
    expect(response.status).toBe(403);
    expect(mocks.session).not.toHaveBeenCalled();
    expect(mocks.boundedMultipart).not.toHaveBeenCalled();
  });

  it("requires the explicit no-PHI synthetic attestation", async () => {
    mocks.boundedMultipart.mockResolvedValue(intake(false));
    const response = await POST(request());
    expect(response.status).toBe(400);
    expect(mocks.createCandidate).not.toHaveBeenCalled();
  });

  it("passes only the authenticated physician and bounded example bytes to the service", async () => {
    const response = await POST(request());
    expect(response.status).toBe(201);
    expect(mocks.createCandidate).toHaveBeenCalledWith({
      examples: [new Uint8Array([111, 110, 101]), new Uint8Array([116, 119, 111])],
      identity: {
        name: "Synthetic candidate",
        encounterScope: "Synthetic follow-up",
        versionDescription: "Two matching synthetic examples",
      },
      actor: {
        userId: SESSION.user.id,
        userEmail: SESSION.user.email,
        practiceId: SESSION.user.practiceId,
        rolloutToken: SESSION.templateTwinRolloutToken,
      },
    });
  });
});
