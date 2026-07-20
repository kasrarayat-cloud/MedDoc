import { beforeEach, describe, expect, it, vi } from "vitest";
import type { NextRequest } from "next/server";

const mocks = vi.hoisted(() => ({
  auth: vi.fn(),
  load: vi.fn(),
  generatePdf: vi.fn(),
  sendEmail: vi.fn(),
  authorize: vi.fn(),
  logDelivery: vi.fn(),
  logAudit: vi.fn(),
}));

vi.mock("@/lib/nextauth", () => ({ auth: mocks.auth }));
vi.mock("@/lib/visit-export", () => ({ formatVisitDate: () => "2026-07-20" }));
vi.mock("@/lib/visit-export-server", () => ({
  loadVisitExportData: mocks.load,
}));
vi.mock("@/lib/pdf-generator", () => ({
  generateVisitPdf: mocks.generatePdf,
}));
vi.mock("@/lib/email", () => ({ sendVisitPdfEmail: mocks.sendEmail }));
vi.mock("@/lib/deliveries", () => ({ logDelivery: mocks.logDelivery }));
vi.mock("@/lib/audit", () => ({ logAudit: mocks.logAudit }));
vi.mock("@/lib/log", () => ({
  log: { warn: vi.fn(), info: vi.fn(), error: vi.fn() },
}));
vi.mock("@meddoc/ai", () => ({ redactPhi: (value: unknown) => value }));
vi.mock("@/lib/template-twin/staging-qa-access", () => ({
  isOwnedTemplateTwinStagingQaVisit: vi.fn(async () => false),
}));
vi.mock("@/lib/template-twin/staging-qa-gate", () => ({
  isTemplateTwinStagingQaRequested: vi.fn(() => false),
}));
vi.mock("@/lib/template-twin/delivery-authorization", () => ({
  TemplateTwinDeliveryAuthorizationError: class TemplateTwinDeliveryAuthorizationError extends Error {
    constructor(
      public readonly code: string,
      public readonly status: number,
    ) {
      super("Template Twin delivery authorization changed.");
    }
  },
  authorizeVisitDeliveryFinalClaim: mocks.authorize,
}));
vi.mock("@/lib/api-error", () => ({
  apiError: (
    error: string,
    status: number,
    details?: Record<string, unknown>,
  ) => Response.json({ error, ...details }, { status }),
  withApiHandler: (
    _name: string,
    handler: (
      request: Request,
      context: { params: Promise<{ id: string }> },
    ) => Promise<Response>,
  ) => handler,
}));

import { TemplateTwinDeliveryAuthorizationError } from "@/lib/template-twin/delivery-authorization";
import { POST } from "../route";

const context = { params: Promise.resolve({ id: "visit-1" }) };

function request(to?: string): NextRequest {
  return new Request(
    "https://app.example.test/api/visits/visit-1/export/email",
    {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(to === undefined ? {} : { to }),
    },
  ) as NextRequest;
}

beforeEach(() => {
  vi.clearAllMocks();
  vi.stubEnv("RESEND_API_KEY", "synthetic-test-key");
  mocks.auth.mockResolvedValue({
    user: { id: "doctor-1", email: "stale-session@example.test" },
  });
  mocks.load.mockResolvedValue({
    clinicianName: "Synthetic clinician",
    patientName: "Synthetic patient",
    signedAt: new Date("2026-07-20T00:00:00.000Z"),
    createdAt: new Date("2026-07-19T00:00:00.000Z"),
  });
  mocks.generatePdf.mockResolvedValue(Buffer.from("synthetic pdf"));
  mocks.sendEmail.mockResolvedValue({ id: "message-1" });
  mocks.authorize.mockResolvedValue({
    templateTwin: true,
    currentPhysicianEmail: "current-db@example.test",
  });
});

describe("dedicated Template Twin email final authorization", () => {
  it("uses the current locked DB email when the session snapshot is stale", async () => {
    const response = await POST(request(), context);

    expect(response.status).toBe(200);
    expect(mocks.authorize).toHaveBeenCalledWith({
      visitId: "visit-1",
      actorUserId: "doctor-1",
      emailDelivery: {},
    });
    expect(mocks.sendEmail).toHaveBeenCalledWith(
      expect.objectContaining({ toEmail: "current-db@example.test" }),
    );
  });

  it("does not send when a concurrent email update invalidates an explicit target", async () => {
    mocks.authorize.mockRejectedValue(
      new TemplateTwinDeliveryAuthorizationError(
        "TEMPLATE_TWIN_DELIVERY_BLOCKED",
        409,
      ),
    );

    const response = await POST(request("stale-session@example.test"), context);

    expect(response.status).toBe(409);
    expect(mocks.authorize).toHaveBeenCalledWith({
      visitId: "visit-1",
      actorUserId: "doctor-1",
      emailDelivery: { targetEmail: "stale-session@example.test" },
    });
    expect(mocks.sendEmail).not.toHaveBeenCalled();
    expect(mocks.logDelivery).not.toHaveBeenCalled();
  });

  it("preserves the ordinary session-email destination rule", async () => {
    mocks.authorize.mockResolvedValue({ templateTwin: false });

    const response = await POST(request("other@example.test"), context);

    expect(response.status).toBe(403);
    await expect(response.json()).resolves.toMatchObject({
      code: "INVALID_DESTINATION",
    });
    expect(mocks.sendEmail).not.toHaveBeenCalled();
  });
});
