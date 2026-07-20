import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  auth: vi.fn(),
  findVisit: vi.fn(),
  requireRead: vi.fn(),
  requireSynthetic: vi.fn(),
  logAudit: vi.fn(),
  logRequiredAudit: vi.fn(),
}));

vi.mock("next/server", () => ({
  NextResponse: {
    json: (body: unknown, init?: { status?: number }) => ({
      body,
      status: init?.status ?? 200,
    }),
  },
}));
vi.mock("@/lib/api-error", () => ({
  apiError: (error: string, status: number) => ({ error, status }),
  withApiHandler: (_scope: string, handler: (...args: unknown[]) => unknown) =>
    handler,
}));
vi.mock("@/lib/nextauth", () => ({ auth: mocks.auth }));
vi.mock("@meddoc/db", () => ({
  default: {
    transcribeVisit: { findFirst: mocks.findVisit, findUnique: vi.fn() },
    user: { findUnique: vi.fn() },
  },
}));
vi.mock("@/lib/audit", () => ({
  logAudit: mocks.logAudit,
  logRequiredAudit: mocks.logRequiredAudit,
}));
vi.mock("@/lib/log", () => ({
  log: { info: vi.fn(), warn: vi.fn(), error: vi.fn() },
}));
vi.mock("@/lib/rate-limit", () => ({
  RATE_LIMITS: { VISIT_OPS: {} },
  rateLimitOr429: vi.fn(() => null),
}));
vi.mock("@/lib/auth", () => ({
  AuthError: class AuthError extends Error {},
  requireFreshDoctorIdentity: vi.fn(),
}));
vi.mock("@/lib/template-twin/staging-qa-gate", () => ({
  isTemplateTwinStagingQaRequested: vi.fn(() => false),
  TemplateTwinStagingQaDisabledError: class TemplateTwinStagingQaDisabledError extends Error {},
}));
vi.mock("@/lib/template-twin/staging-qa-access", () => ({
  isOwnedTemplateTwinStagingQaVisit: vi.fn(async () => false),
}));
vi.mock("@/lib/template-twin/staging-qa-visit-guard", () => ({
  assertTemplateTwinStagingQaVisitGuard: vi.fn(),
  TEMPLATE_TWIN_STAGING_QA_RUN_GUARD_SELECT: { id: true },
  TemplateTwinStagingQaVisitGuardError: class TemplateTwinStagingQaVisitGuardError extends Error {},
}));
vi.mock("@/lib/template-twin/synthetic-qa-patient", () => ({
  isTemplateTwinSyntheticQaPatient: vi.fn(() => false),
  TEMPLATE_TWIN_SYNTHETIC_QA_PATIENT_EXTERNAL_ID: "SYNTHETIC-QA-ONLY",
}));
vi.mock("@/lib/template-twin/read-authority", () => ({
  TemplateTwinVisitReadAuthorityError: class TemplateTwinVisitReadAuthorityError extends Error {},
  requireTemplateTwinVisitReadAuthority: mocks.requireRead,
}));
vi.mock("@/lib/template-twin/synthetic-read-admission", () => ({
  TemplateTwinSyntheticReadAdmissionError: class TemplateTwinSyntheticReadAdmissionError extends Error {},
  requireTemplateTwinSyntheticReadAdmission: mocks.requireSynthetic,
}));

import { TemplateTwinVisitReadAuthorityError } from "@/lib/template-twin/read-authority";
import { TemplateTwinSyntheticReadAdmissionError } from "@/lib/template-twin/synthetic-read-admission";
import { GET } from "../route";

const context = { params: Promise.resolve({ id: "visit-1" }) };
const ordinaryDecision = {
  visitId: "visit-1",
  isTemplateTwin: false,
  isSyntheticTemplateTwin: false,
  practiceId: null,
  templateTwinEnabled: null,
};
const twinDecision = {
  visitId: "visit-1",
  isTemplateTwin: true,
  isSyntheticTemplateTwin: false,
  practiceId: "practice-current",
  templateTwinEnabled: false,
};
const syntheticDecision = {
  ...twinDecision,
  isSyntheticTemplateTwin: true,
};
const syntheticAdmission = {
  visitId: "visit-1",
  practiceId: "practice-current",
  runId: "run-1",
  attempt: 2,
};

beforeEach(() => {
  vi.clearAllMocks();
  mocks.auth.mockResolvedValue({ user: { id: "doctor-1" } });
  mocks.findVisit.mockResolvedValue({
    id: "visit-1",
    userId: "doctor-1",
    status: "READY",
    templateTwinSyntheticQaRun: null,
  });
  mocks.requireRead.mockResolvedValue(ordinaryDecision);
  mocks.requireSynthetic.mockResolvedValue(null);
  mocks.logRequiredAudit.mockResolvedValue(undefined);
});

describe("generic visit GET durable Template Twin read authority", () => {
  it("returns uniform not-found for stale or inconsistent Twin authority", async () => {
    mocks.requireRead.mockRejectedValue(
      new TemplateTwinVisitReadAuthorityError(),
    );

    const response = await GET({} as never, context);

    expect(response).toEqual({ error: "not found", status: 404 });
    expect(mocks.findVisit).not.toHaveBeenCalled();
    expect(mocks.logAudit).not.toHaveBeenCalled();
    expect(mocks.logRequiredAudit).not.toHaveBeenCalled();
  });

  it("maps authority loss in the final required-audit transaction to not-found", async () => {
    mocks.requireRead.mockResolvedValue(twinDecision);
    mocks.logRequiredAudit.mockRejectedValue(
      new TemplateTwinVisitReadAuthorityError(),
    );

    const response = await GET({} as never, context);

    expect(response).toEqual({ error: "not found", status: 404 });
    expect(mocks.logRequiredAudit).toHaveBeenCalledWith(
      expect.objectContaining({
        userId: "doctor-1",
        practiceId: "practice-current",
        templateTwinReadAuthority: {
          expectedPracticeId: "practice-current",
        },
      }),
    );
  });

  it("preserves ordinary GET behavior and best-effort auditing", async () => {
    const response = await GET({} as never, context);

    expect(response).toMatchObject({ status: 200 });
    expect(mocks.logAudit).toHaveBeenCalledWith(
      expect.objectContaining({ action: "VIEWED_VISIT" }),
    );
    expect(mocks.logRequiredAudit).not.toHaveBeenCalled();
  });

  it("requires durable ordinary exclusion in the PHI select when lineage appears after classification", async () => {
    mocks.findVisit.mockImplementationOnce(async (query) => {
      expect(query.where).toMatchObject({ id: "visit-1" });
      expect(JSON.stringify(query.where)).toMatch(
        /templateTwinCompiledVersion.*templateTwinFill.*templateTwinSyntheticQaRun.*templateTwinSyntheticQaAdmission.*templateTwinProviderExecutions/,
      );
      return null;
    });

    const response = await GET({} as never, context);

    expect(response).toEqual({ error: "not found", status: 404 });
    expect(mocks.logAudit).not.toHaveBeenCalled();
    expect(mocks.logRequiredAudit).not.toHaveBeenCalled();
  });

  it.each([
    "admission-only synthetic",
    "pre-certification synthetic",
    "orphan reserved-patient synthetic",
  ])("denies %s before the full PHI projection", async () => {
    mocks.requireRead.mockResolvedValue(syntheticDecision);
    mocks.requireSynthetic.mockImplementationOnce(async () => {
      expect(mocks.findVisit).not.toHaveBeenCalled();
      throw new TemplateTwinSyntheticReadAdmissionError();
    });

    const response = await GET({} as never, context);

    expect(response).toEqual({ error: "not found", status: 404 });
    expect(mocks.findVisit).not.toHaveBeenCalled();
    expect(mocks.logRequiredAudit).not.toHaveBeenCalled();
  });

  it("reasserts the exact synthetic run after PHI and at response", async () => {
    mocks.requireRead.mockResolvedValue(syntheticDecision);
    mocks.requireSynthetic.mockResolvedValue(syntheticAdmission);
    mocks.findVisit.mockResolvedValue({
      id: "visit-1",
      userId: "doctor-1",
      status: "READY",
      templateTwinSyntheticQaRun: { id: "run-1", attempt: 2 },
    });

    const response = await GET({} as never, context);

    expect(response).toMatchObject({ status: 200 });
    expect(mocks.requireSynthetic).toHaveBeenCalledTimes(3);
    expect(mocks.requireSynthetic.mock.calls[1]?.[0]).toMatchObject({
      expected: syntheticAdmission,
    });
    expect(mocks.requireSynthetic.mock.calls[2]?.[0]).toMatchObject({
      expected: syntheticAdmission,
    });
    expect(mocks.requireRead).toHaveBeenCalledTimes(3);
  });

  it("returns no PHI when the run epoch is revoked before response", async () => {
    mocks.requireRead.mockResolvedValue(syntheticDecision);
    mocks.requireSynthetic
      .mockResolvedValueOnce(syntheticAdmission)
      .mockResolvedValueOnce(syntheticAdmission)
      .mockRejectedValueOnce(new TemplateTwinSyntheticReadAdmissionError());
    mocks.findVisit.mockResolvedValue({
      id: "visit-1",
      userId: "doctor-1",
      status: "READY",
      templateTwinSyntheticQaRun: { id: "run-1", attempt: 2 },
    });

    const response = await GET({} as never, context);

    expect(response).toEqual({ error: "not found", status: 404 });
    expect(mocks.requireSynthetic).toHaveBeenCalledTimes(3);
  });
});
