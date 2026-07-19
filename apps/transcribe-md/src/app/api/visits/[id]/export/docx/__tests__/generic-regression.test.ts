import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  auth: vi.fn(),
  loadVisitExportData: vi.fn(),
  generateVisitDocx: vi.fn(),
  logDelivery: vi.fn(),
  logAudit: vi.fn(),
  isOwnedTemplateTwinStagingQaVisit: vi.fn(),
  isTemplateTwinStagingQaRequested: vi.fn(),
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
vi.mock("@/lib/visit-export", () => ({
  filenameSlug: () => "synthetic-patient",
  formatVisitDate: () => "2026-07-15",
}));
vi.mock("@/lib/visit-export-server", () => ({
  loadVisitExportData: mocks.loadVisitExportData,
}));
vi.mock("@/lib/docx-generator", () => ({
  generateVisitDocx: mocks.generateVisitDocx,
}));
vi.mock("@/lib/deliveries", () => ({ logDelivery: mocks.logDelivery }));
vi.mock("@/lib/audit", () => ({ logAudit: mocks.logAudit }));
vi.mock("@/lib/template-twin/staging-qa-access", () => ({
  isOwnedTemplateTwinStagingQaVisit: mocks.isOwnedTemplateTwinStagingQaVisit,
}));
vi.mock("@/lib/template-twin/staging-qa-gate", () => ({
  isTemplateTwinStagingQaRequested: mocks.isTemplateTwinStagingQaRequested,
}));
vi.mock("@meddoc/ai", () => ({ redactPhi: (value: unknown) => value }));

import { GET } from "../route";

const DOCUMENT = Buffer.from("synthetic-generic-docx");
const STRUCTURED_EXPORT = {
  visitId: "visit-structured-1",
  noteTemplateKind: "structured",
  patientName: "Synthetic Patient",
  clinicianName: "Synthetic Clinician",
  specialty: "Synthetic Specialty",
  signedAt: new Date("2026-07-15T12:00:00.000Z"),
  createdAt: new Date("2026-07-15T11:00:00.000Z"),
  soapText: "Synthetic structured SOAP.",
  icdCodes: [],
  procedures: [],
  modifiers: [],
  prescriptions: [],
  rxWarnings: [],
  referrals: [],
};

beforeEach(() => {
  vi.clearAllMocks();
  mocks.auth.mockResolvedValue({ user: { id: "doctor-structured-1" } });
  mocks.loadVisitExportData.mockResolvedValue(STRUCTURED_EXPORT);
  mocks.generateVisitDocx.mockResolvedValue(DOCUMENT);
  mocks.isOwnedTemplateTwinStagingQaVisit.mockResolvedValue(false);
  mocks.isTemplateTwinStagingQaRequested.mockReturnValue(false);
});

describe("generic DOCX export regression", () => {
  it("keeps the existing structured-template export on the generic generator path", async () => {
    const response = await GET({} as never, {
      params: Promise.resolve({ id: "visit-structured-1" }),
    });

    expect(response.status).toBe(200);
    expect(response.body).toEqual(DOCUMENT);
    expect(response.headers.get("Content-Type")).toBe(
      "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    );
    expect(response.headers.get("Content-Disposition")).toBe(
      'attachment; filename="visit-synthetic-patient-2026-07-15.docx"',
    );
    expect(response.headers.get("Cache-Control")).toBe("no-store, private");
    expect(mocks.loadVisitExportData).toHaveBeenCalledWith(
      "visit-structured-1",
      "doctor-structured-1",
    );
    expect(mocks.isOwnedTemplateTwinStagingQaVisit).toHaveBeenCalledWith({
      visitId: "visit-structured-1",
      userId: "doctor-structured-1",
    });
    expect(mocks.generateVisitDocx).toHaveBeenCalledWith(STRUCTURED_EXPORT);
    expect(mocks.logDelivery).toHaveBeenCalledWith({
      visitId: "visit-structured-1",
      channel: "docx",
      sizeBytes: DOCUMENT.byteLength,
    });
    expect(mocks.logAudit).toHaveBeenCalledWith(
      expect.objectContaining({ action: "EXPORT_DOCX_DOWNLOADED" }),
    );
  });

  it("rejects a generic export when synthetic QA requires durable admission", async () => {
    mocks.isTemplateTwinStagingQaRequested.mockReturnValue(true);

    const response = await GET({} as never, {
      params: Promise.resolve({ id: "visit-structured-1" }),
    });

    expect(response).toEqual({ error: "not found", status: 404 });
    expect(mocks.loadVisitExportData).not.toHaveBeenCalled();
    expect(mocks.generateVisitDocx).not.toHaveBeenCalled();
  });
});
