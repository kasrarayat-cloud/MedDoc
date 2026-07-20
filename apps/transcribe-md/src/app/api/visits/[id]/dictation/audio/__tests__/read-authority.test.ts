import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  auth: vi.fn(),
  findVisit: vi.fn(),
  downloadAudio: vi.fn(),
  logAudit: vi.fn(),
  logRequiredAudit: vi.fn(),
  isSyntheticRun: vi.fn(),
  requireRead: vi.fn(),
}));

vi.mock("next/server", () => {
  class FakeNextResponse {
    status: number;
    headers: Headers;
    body: unknown;

    constructor(
      body: unknown,
      init?: { status?: number; headers?: Record<string, string> },
    ) {
      this.body = body;
      this.status = init?.status ?? 200;
      this.headers = new Headers(init?.headers);
    }
  }
  return { NextResponse: FakeNextResponse };
});
vi.mock("@/lib/api-error", () => ({
  apiError: (error: string, status: number) => ({ error, status }),
  withApiHandler: (_scope: string, handler: (...args: unknown[]) => unknown) =>
    handler,
}));
vi.mock("@/lib/nextauth", () => ({ auth: mocks.auth }));
vi.mock("@meddoc/db", () => ({
  default: { transcribeVisit: { findFirst: mocks.findVisit } },
}));
vi.mock("@/lib/minio", () => ({ downloadAudio: mocks.downloadAudio }));
vi.mock("@meddoc/ai", () => ({ redactPhi: (value: unknown) => value }));
vi.mock("@/lib/audit", () => ({
  logAudit: mocks.logAudit,
  logRequiredAudit: mocks.logRequiredAudit,
}));
vi.mock("@/lib/template-twin/staging-qa-access", () => ({
  isOwnedTemplateTwinStagingQaVisit: mocks.isSyntheticRun,
}));
vi.mock("@/lib/template-twin/read-authority", () => ({
  TemplateTwinVisitReadAuthorityError: class TemplateTwinVisitReadAuthorityError extends Error {},
  requireTemplateTwinVisitReadAuthority: mocks.requireRead,
}));

import { TemplateTwinVisitReadAuthorityError } from "@/lib/template-twin/read-authority";
import { GET } from "../route";

const context = { params: Promise.resolve({ id: "visit-1" }) };
const ordinaryDecision = {
  visitId: "visit-1",
  isTemplateTwin: false,
  isSyntheticTemplateTwin: false,
  practiceId: null,
  templateTwinEnabled: null,
};
const liveTwinDecision = {
  visitId: "visit-1",
  isTemplateTwin: true,
  isSyntheticTemplateTwin: false,
  practiceId: "practice-current",
  templateTwinEnabled: false,
};

beforeEach(() => {
  vi.clearAllMocks();
  mocks.auth.mockResolvedValue({ user: { id: "doctor-1" } });
  mocks.isSyntheticRun.mockResolvedValue(false);
  mocks.findVisit.mockResolvedValue({
    userId: "doctor-1",
    dictationAudioKey: "visits/visit-1/dictation.webm",
    audioMimeType: "audio/webm",
  });
  mocks.downloadAudio.mockResolvedValue(Buffer.from("synthetic-audio"));
  mocks.requireRead.mockResolvedValue(ordinaryDecision);
});

describe("dictation audio durable Template Twin read authority", () => {
  it("denies a pre-certification admission before object storage is read", async () => {
    mocks.requireRead.mockRejectedValueOnce(
      new TemplateTwinVisitReadAuthorityError(),
    );

    const response = await GET({} as never, context);

    expect(response).toEqual({ error: "not found", status: 404 });
    expect(mocks.findVisit).not.toHaveBeenCalled();
    expect(mocks.downloadAudio).not.toHaveBeenCalled();
  });

  it("denies an orphan reserved-patient visit before resolving an object key", async () => {
    mocks.requireRead.mockRejectedValueOnce(
      new TemplateTwinVisitReadAuthorityError(),
    );

    const response = await GET({} as never, context);

    expect(response).toEqual({ error: "not found", status: 404 });
    expect(mocks.findVisit).not.toHaveBeenCalled();
    expect(mocks.downloadAudio).not.toHaveBeenCalled();
  });

  it("denies an admission-only durable synthetic mode before resolving its object key", async () => {
    mocks.requireRead.mockResolvedValueOnce({
      ...liveTwinDecision,
      isSyntheticTemplateTwin: true,
    });

    const response = await GET({} as never, context);

    expect(response).toEqual({ error: "not found", status: 404 });
    expect(mocks.findVisit).not.toHaveBeenCalled();
    expect(mocks.downloadAudio).not.toHaveBeenCalled();
  });

  it("rechecks and durably audits a live Twin immediately before returning bytes", async () => {
    mocks.requireRead.mockResolvedValue(liveTwinDecision);

    const response = await GET({} as never, context);

    expect(response.status).toBe(200);
    expect(response.body).toEqual(Buffer.from("synthetic-audio"));
    expect(mocks.requireRead).toHaveBeenCalledTimes(2);
    expect(mocks.logRequiredAudit).toHaveBeenCalledWith(
      expect.objectContaining({
        action: "VIEWED_VISIT_AUDIO",
        userId: "doctor-1",
        practiceId: "practice-current",
        templateTwinReadAuthority: {
          expectedPracticeId: "practice-current",
        },
      }),
    );
    expect(mocks.logAudit).not.toHaveBeenCalled();
  });

  it("does not return already-loaded bytes when final authority is lost", async () => {
    mocks.requireRead
      .mockResolvedValueOnce(liveTwinDecision)
      .mockRejectedValueOnce(new TemplateTwinVisitReadAuthorityError());

    const response = await GET({} as never, context);

    expect(mocks.downloadAudio).toHaveBeenCalledTimes(1);
    expect(response).toEqual({ error: "not found", status: 404 });
    expect(mocks.logRequiredAudit).not.toHaveBeenCalled();
  });

  it("preserves the ordinary best-effort audit response", async () => {
    const response = await GET({} as never, context);

    expect(response.status).toBe(200);
    expect(mocks.logAudit).toHaveBeenCalledWith(
      expect.objectContaining({ action: "VIEWED_VISIT_AUDIO" }),
    );
    expect(mocks.logRequiredAudit).not.toHaveBeenCalled();
  });

  it("does not resolve an object key when durable lineage appears after ordinary classification", async () => {
    mocks.findVisit.mockImplementationOnce(async (query) => {
      expect(query.where).toMatchObject({ id: "visit-1" });
      expect(JSON.stringify(query.where)).toContain(
        "templateTwinCompiledVersion",
      );
      return null;
    });

    const response = await GET({} as never, context);

    expect(response).toEqual({ error: "not found", status: 404 });
    expect(mocks.downloadAudio).not.toHaveBeenCalled();
    expect(mocks.logAudit).not.toHaveBeenCalled();
  });
});
