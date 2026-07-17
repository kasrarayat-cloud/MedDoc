import { beforeEach, describe, expect, it, vi } from "vitest";

import { TEMPLATE_TWIN_SYNTHETIC_QA_PATIENT_EXTERNAL_ID } from "@/lib/template-twin/synthetic-qa-patient";

const mocks = vi.hoisted(() => ({
  patientCreate: vi.fn(),
  getSession: vi.fn(),
  rateLimitOr429: vi.fn(),
}));

vi.mock("@meddoc/db", () => ({
  default: {
    transcribeMdPatient: { create: mocks.patientCreate },
  },
}));
vi.mock("@/lib/auth", () => ({ getSession: mocks.getSession }));
vi.mock("@/lib/rate-limit", () => ({
  RATE_LIMITS: { PATIENT_CREATE: { bucket: "patient-create" } },
  rateLimitOr429: mocks.rateLimitOr429,
}));
vi.mock("@/lib/audit", () => ({ logAudit: vi.fn() }));

import { POST } from "../route";

beforeEach(() => {
  vi.clearAllMocks();
  mocks.getSession.mockResolvedValue({
    user: { id: "doctor-synthetic", practiceId: "practice-synthetic" },
  });
  mocks.rateLimitOr429.mockReturnValue(null);
});

describe("POST /api/patients reserved synthetic identity", () => {
  it("rejects the reserved external ID before database creation", async () => {
    const response = await POST(
      new Request("http://localhost/api/patients", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          name: "Example Person",
          dateOfBirth: "2099-01-01",
          externalId: TEMPLATE_TWIN_SYNTHETIC_QA_PATIENT_EXTERNAL_ID,
        }),
      }) as Parameters<typeof POST>[0],
      { params: Promise.resolve({}) },
    );

    expect(response.status).toBe(400);
    expect(mocks.patientCreate).not.toHaveBeenCalled();
  });
});
