import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  auth: vi.fn(),
  findVisit: vi.fn(),
  requireRead: vi.fn(),
  reassertRead: vi.fn(),
  requireSynthetic: vi.fn(),
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
  default: { transcribeVisit: { findFirst: mocks.findVisit } },
}));
vi.mock("@/lib/auth", () => ({
  AuthError: class AuthError extends Error {},
  requireFreshDoctorIdentity: vi.fn(),
}));
vi.mock("@/lib/template-twin/staging-qa-gate", () => ({
  isTemplateTwinStagingQaRequested: vi.fn(() => false),
  TemplateTwinStagingQaDisabledError: class TemplateTwinStagingQaDisabledError extends Error {},
}));
vi.mock("@/lib/template-twin/staging-qa-visit-guard", () => ({
  assertTemplateTwinStagingQaVisitGuard: vi.fn(),
  TEMPLATE_TWIN_STAGING_QA_RUN_GUARD_SELECT: { id: true },
  TemplateTwinStagingQaVisitGuardError: class TemplateTwinStagingQaVisitGuardError extends Error {},
}));
vi.mock("@/lib/template-twin/read-authority", () => ({
  TemplateTwinVisitReadAuthorityError: class TemplateTwinVisitReadAuthorityError extends Error {},
  requireTemplateTwinVisitReadAuthority: mocks.requireRead,
  reassertTemplateTwinVisitReadAuthority: mocks.reassertRead,
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
  attempt: 3,
};

beforeEach(() => {
  vi.clearAllMocks();
  mocks.auth.mockResolvedValue({ user: { id: "doctor-1" } });
  mocks.findVisit.mockResolvedValue({
    id: "visit-1",
    userId: "doctor-1",
    status: "READY",
    needsReview: false,
    reviewReason: null,
    audioDurationSec: 10,
    deletedAt: null,
    archivedAt: null,
    processingStartedAt: null,
    icdCodes: null,
    cptCodes: null,
    soapDraft: null,
    templateTwinSyntheticQaRun: null,
  });
  mocks.requireRead.mockResolvedValue(ordinaryDecision);
  mocks.reassertRead.mockResolvedValue(twinDecision);
  mocks.requireSynthetic.mockResolvedValue(null);
});

describe("visit status/progress final Template Twin read authority", () => {
  it("does not project status/SOAP fields before current Twin authority", async () => {
    mocks.requireRead.mockRejectedValueOnce(
      new TemplateTwinVisitReadAuthorityError(),
    );

    const response = await GET({} as never, context);

    expect(response).toEqual({ error: "not found", status: 404 });
    expect(mocks.findVisit).not.toHaveBeenCalled();
    expect(mocks.reassertRead).not.toHaveBeenCalled();
  });

  it("allows base status after rollout revocation but performs a final locked recheck", async () => {
    mocks.requireRead.mockResolvedValue(twinDecision);

    const response = await GET({} as never, context);

    expect(response).toMatchObject({ status: 200 });
    expect(mocks.reassertRead).toHaveBeenCalledWith({
      db: expect.anything(),
      visitId: "visit-1",
      actorUserId: "doctor-1",
      expectedPracticeId: "practice-current",
    });
  });

  it("returns not-found when authority is lost at the final poll boundary", async () => {
    mocks.requireRead.mockResolvedValue(twinDecision);
    mocks.reassertRead.mockRejectedValue(
      new TemplateTwinVisitReadAuthorityError(),
    );

    const response = await GET({} as never, context);

    expect(response).toEqual({ error: "not found", status: 404 });
  });

  it("preserves ordinary status behavior without the Twin lock transaction", async () => {
    const response = await GET({} as never, context);

    expect(response).toMatchObject({ status: 200 });
    expect(mocks.reassertRead).not.toHaveBeenCalled();
  });

  it("returns no status PHI when durable lineage appears between ordinary classification and projection", async () => {
    mocks.findVisit.mockImplementationOnce(async (query) => {
      expect(query.where).toMatchObject({ id: "visit-1" });
      expect(JSON.stringify(query.where)).toContain(
        "templateTwinCompiledVersion",
      );
      return null;
    });

    const response = await GET({} as never, context);

    expect(response).toEqual({ error: "not found", status: 404 });
    expect(mocks.reassertRead).not.toHaveBeenCalled();
  });

  it.each([
    "admission-only synthetic",
    "pre-certification synthetic",
    "orphan reserved-patient synthetic",
  ])("denies %s before status/SOAP projection", async () => {
    mocks.requireRead.mockResolvedValue(syntheticDecision);
    mocks.requireSynthetic.mockImplementationOnce(async () => {
      expect(mocks.findVisit).not.toHaveBeenCalled();
      throw new TemplateTwinSyntheticReadAdmissionError();
    });

    const response = await GET({} as never, context);

    expect(response).toEqual({ error: "not found", status: 404 });
    expect(mocks.findVisit).not.toHaveBeenCalled();
    expect(mocks.reassertRead).not.toHaveBeenCalled();
  });

  it("reasserts the exact run after status PHI and at the poll response", async () => {
    mocks.requireRead.mockResolvedValue(syntheticDecision);
    mocks.reassertRead.mockResolvedValue(syntheticDecision);
    mocks.requireSynthetic.mockResolvedValue(syntheticAdmission);
    mocks.findVisit.mockResolvedValue({
      id: "visit-1",
      userId: "doctor-1",
      status: "READY",
      needsReview: false,
      reviewReason: null,
      audioDurationSec: 10,
      deletedAt: null,
      archivedAt: null,
      processingStartedAt: null,
      icdCodes: null,
      cptCodes: null,
      soapDraft: null,
      templateTwinSyntheticQaRun: { id: "run-1", attempt: 3 },
    });

    const response = await GET({} as never, context);

    expect(response).toMatchObject({ status: 200 });
    expect(mocks.requireSynthetic).toHaveBeenCalledTimes(3);
    expect(mocks.reassertRead).toHaveBeenCalledTimes(1);
  });

  it("returns no poll payload after final run epoch revocation", async () => {
    mocks.requireRead.mockResolvedValue(syntheticDecision);
    mocks.reassertRead.mockResolvedValue(syntheticDecision);
    mocks.requireSynthetic
      .mockResolvedValueOnce(syntheticAdmission)
      .mockResolvedValueOnce(syntheticAdmission)
      .mockRejectedValueOnce(new TemplateTwinSyntheticReadAdmissionError());
    mocks.findVisit.mockResolvedValue({
      id: "visit-1",
      userId: "doctor-1",
      status: "READY",
      needsReview: false,
      reviewReason: null,
      audioDurationSec: 10,
      deletedAt: null,
      archivedAt: null,
      processingStartedAt: null,
      icdCodes: null,
      cptCodes: null,
      soapDraft: null,
      templateTwinSyntheticQaRun: { id: "run-1", attempt: 3 },
    });

    const response = await GET({} as never, context);

    expect(response).toEqual({ error: "not found", status: 404 });
  });
});
