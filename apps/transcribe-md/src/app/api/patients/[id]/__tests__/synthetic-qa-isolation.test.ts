import { beforeEach, describe, expect, it, vi } from "vitest";

import { TEMPLATE_TWIN_SYNTHETIC_QA_PATIENT_EXTERNAL_ID } from "@/lib/template-twin/synthetic-qa-patient";

const mocks = vi.hoisted(() => ({
  patientFindUnique: vi.fn(),
  patientUpdate: vi.fn(),
  visitAggregate: vi.fn(),
  getSession: vi.fn(),
  rateLimitOr429: vi.fn(),
}));

vi.mock("@meddoc/db", () => ({
  default: {
    transcribeMdPatient: {
      findUnique: mocks.patientFindUnique,
      update: mocks.patientUpdate,
    },
    transcribeVisit: { aggregate: mocks.visitAggregate },
  },
}));
vi.mock("@/lib/auth", () => ({ getSession: mocks.getSession }));
vi.mock("@/lib/rate-limit", () => ({
  RATE_LIMITS: {
    PATIENT_READ: { bucket: "patient-read" },
    PATIENT_OPS: { bucket: "patient-ops" },
  },
  rateLimitOr429: mocks.rateLimitOr429,
}));
vi.mock("@/lib/audit", () => ({ logAudit: vi.fn() }));

import { DELETE, GET, PATCH } from "../route";

const patientId = "ttqa-synthetic-patient";
const context = { params: Promise.resolve({ id: patientId }) };

function request(method: string, body?: unknown) {
  return new Request(`http://localhost/api/patients/${patientId}`, {
    method,
    body: body === undefined ? undefined : JSON.stringify(body),
    headers:
      body === undefined ? undefined : { "content-type": "application/json" },
  }) as Parameters<typeof GET>[0];
}

beforeEach(() => {
  vi.clearAllMocks();
  mocks.getSession.mockResolvedValue({
    user: { id: "doctor-synthetic", practiceId: "practice-synthetic" },
  });
  mocks.rateLimitOr429.mockReturnValue(null);
  mocks.patientFindUnique.mockResolvedValue({
    id: patientId,
    practiceId: "practice-synthetic",
    name: "Template Twin Synthetic QA",
    dateOfBirth: null,
    externalId: TEMPLATE_TWIN_SYNTHETIC_QA_PATIENT_EXTERNAL_ID,
    mrn: null,
    insurance: null,
    problemList: null,
    deletedAt: null,
    createdAt: new Date("2099-01-01T00:00:00.000Z"),
    updatedAt: new Date("2099-01-01T00:00:00.000Z"),
  });
});

describe("reserved Template Twin synthetic QA patient", () => {
  it.each([
    ["GET", () => GET(request("GET"), context)],
    ["PATCH", () => PATCH(request("PATCH", { name: "Changed" }), context)],
    ["DELETE", () => DELETE(request("DELETE"), context)],
  ])("returns a non-revealing 404 for %s", async (_method, invoke) => {
    const response = await invoke();

    expect(response.status).toBe(404);
    await expect(response.json()).resolves.toEqual({ error: "not found" });
    expect(mocks.patientUpdate).not.toHaveBeenCalled();
    expect(mocks.visitAggregate).not.toHaveBeenCalled();
  });

  it("does not let an ordinary patient adopt the reserved external ID", async () => {
    mocks.patientFindUnique.mockResolvedValue({
      id: "ordinary-patient",
      practiceId: "practice-synthetic",
      name: "Example Patient",
      dateOfBirth: null,
      externalId: "EXAMPLE-001",
      mrn: null,
      insurance: null,
      problemList: null,
      deletedAt: null,
      createdAt: new Date("2099-01-01T00:00:00.000Z"),
      updatedAt: new Date("2099-01-01T00:00:00.000Z"),
    });

    const response = await PATCH(
      request("PATCH", {
        externalId: TEMPLATE_TWIN_SYNTHETIC_QA_PATIENT_EXTERNAL_ID,
      }),
      context,
    );

    expect(response.status).toBe(400);
    expect(mocks.patientUpdate).not.toHaveBeenCalled();
  });

  it("continues serving ordinary same-practice patient records", async () => {
    mocks.patientFindUnique.mockResolvedValue({
      id: "ordinary-patient",
      practiceId: "practice-synthetic",
      name: "Example Patient",
      dateOfBirth: null,
      externalId: "EXAMPLE-001",
      mrn: null,
      insurance: null,
      problemList: null,
      deletedAt: null,
      createdAt: new Date("2099-01-01T00:00:00.000Z"),
      updatedAt: new Date("2099-01-01T00:00:00.000Z"),
    });
    mocks.visitAggregate.mockResolvedValue({
      _count: { _all: 0 },
      _max: { createdAt: null },
    });

    const response = await GET(request("GET"), context);

    expect(response.status).toBe(200);
    await expect(response.json()).resolves.toMatchObject({
      patient: { id: "ordinary-patient", externalId: "EXAMPLE-001" },
    });
  });
});
