import { beforeEach, describe, expect, it, vi } from "vitest";

import { TEMPLATE_TWIN_SYNTHETIC_QA_PATIENT_EXTERNAL_ID } from "@/lib/template-twin/synthetic-qa-patient";

const mocks = vi.hoisted(() => ({
  patientCreate: vi.fn(),
  transaction: vi.fn(),
  authorityQuery: vi.fn(),
  getSession: vi.fn(),
  rateLimitOr429: vi.fn(),
}));

vi.mock("@meddoc/db", () => ({
  default: {
    $transaction: mocks.transaction,
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
  const tx = {
    $queryRaw: mocks.authorityQuery,
    transcribeMdPatient: { create: mocks.patientCreate },
  };
  mocks.transaction.mockImplementation(
    async (run: (client: typeof tx) => Promise<unknown>) => run(tx),
  );
});

function createRequest(externalId: string | null = null) {
  return new Request("http://localhost/api/patients", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      name: "Synthetic Example",
      dateOfBirth: "2099-01-01",
      externalId,
    }),
  }) as Parameters<typeof POST>[0];
}

describe("POST /api/patients reserved synthetic identity", () => {
  it("rejects the reserved external ID before database creation", async () => {
    const response = await POST(
      createRequest(TEMPLATE_TWIN_SYNTHETIC_QA_PATIENT_EXTERNAL_ID),
      { params: Promise.resolve({}) },
    );

    expect(response.status).toBe(400);
    expect(mocks.patientCreate).not.toHaveBeenCalled();
  });

  it("locks the exact active practice then current physician before creation", async () => {
    mocks.authorityQuery
      .mockResolvedValueOnce([{ id: "practice-synthetic" }])
      .mockResolvedValueOnce([{ id: "doctor-synthetic" }]);
    mocks.patientCreate.mockResolvedValue({
      id: "patient-synthetic",
      name: "Synthetic Example",
      dateOfBirth: new Date("2099-01-01T00:00:00.000Z"),
      externalId: null,
      createdAt: new Date("2099-01-01T00:00:00.000Z"),
    });

    const response = await POST(createRequest(), {
      params: Promise.resolve({}),
    });

    expect(response.status).toBe(201);
    expect(mocks.transaction).toHaveBeenCalledOnce();
    expect(mocks.authorityQuery).toHaveBeenCalledTimes(2);
    expect(
      mocks.authorityQuery.mock.calls[0]?.[0]?.strings?.join(" "),
    ).toContain('FROM "practices" practice');
    expect(
      mocks.authorityQuery.mock.calls[1]?.[0]?.strings?.join(" "),
    ).toContain('FROM "users" actor');
    expect(mocks.patientCreate).toHaveBeenCalledWith(
      expect.objectContaining({
        data: expect.objectContaining({
          practiceId: "practice-synthetic",
        }),
      }),
    );
  });

  it("fails closed when a practice transfer revokes the exact actor lock", async () => {
    mocks.authorityQuery
      .mockResolvedValueOnce([{ id: "practice-synthetic" }])
      .mockResolvedValueOnce([]);

    const response = await POST(createRequest(), {
      params: Promise.resolve({}),
    });

    expect(response.status).toBe(404);
    expect(mocks.patientCreate).not.toHaveBeenCalled();
  });
});
