import { beforeEach, describe, expect, it, vi } from "vitest";

import { TEMPLATE_TWIN_SYNTHETIC_QA_PATIENT_EXTERNAL_ID } from "@/lib/template-twin/synthetic-qa-patient";

const mocks = vi.hoisted(() => ({
  patientFindFirst: vi.fn(),
  transaction: vi.fn(),
  authorityQuery: vi.fn(),
  patientUpdateMany: vi.fn(),
  transactionPatientFindFirst: vi.fn(),
  visibleVisitAggregateQuery: vi.fn(),
  getSession: vi.fn(),
  rateLimitOr429: vi.fn(),
}));

vi.mock("@meddoc/db", () => ({
  default: {
    transcribeMdPatient: {
      findFirst: mocks.patientFindFirst,
    },
    $transaction: mocks.transaction,
    $queryRaw: mocks.visibleVisitAggregateQuery,
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

const patientId = "patient-record-1";
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
  const tx = {
    $queryRaw: mocks.authorityQuery,
    transcribeMdPatient: {
      updateMany: mocks.patientUpdateMany,
      findFirst: mocks.transactionPatientFindFirst,
    },
  };
  mocks.transaction.mockImplementation(
    async (run: (client: typeof tx) => Promise<unknown>) => run(tx),
  );
  // The query-native reserved-ID predicate excludes the row in the database;
  // the route never receives the reserved patient's identifying projection.
  mocks.patientFindFirst.mockResolvedValue(null);
  mocks.visibleVisitAggregateQuery.mockResolvedValue([
    { count: 0, maxCreatedAt: null, avgDraftedInSeconds: null },
  ]);
});

describe("reserved Template Twin synthetic QA patient", () => {
  it.each([
    ["GET", () => GET(request("GET"), context)],
    ["PATCH", () => PATCH(request("PATCH", { name: "Changed" }), context)],
    ["DELETE", () => DELETE(request("DELETE"), context)],
  ])("returns a non-revealing 404 for %s", async (method, invoke) => {
    if (method !== "GET") {
      mocks.authorityQuery
        .mockResolvedValueOnce([{ id: "practice-synthetic" }])
        .mockResolvedValueOnce([{ id: "doctor-synthetic" }])
        .mockResolvedValueOnce([]);
    }
    const response = await invoke();

    expect(response.status).toBe(404);
    await expect(response.json()).resolves.toEqual({ error: "not found" });
    expect(mocks.patientUpdateMany).not.toHaveBeenCalled();
    expect(mocks.visibleVisitAggregateQuery).not.toHaveBeenCalled();
    if (method === "GET") {
      expect(mocks.patientFindFirst).toHaveBeenCalledWith(
        expect.objectContaining({
          where: expect.objectContaining({
            id: patientId,
            practiceId: "practice-synthetic",
            OR: [
              { externalId: null },
              {
                externalId: {
                  not: TEMPLATE_TWIN_SYNTHETIC_QA_PATIENT_EXTERNAL_ID,
                },
              },
            ],
            practice: {
              is: expect.objectContaining({
                id: "practice-synthetic",
                isActive: true,
                users: {
                  some: expect.objectContaining({
                    id: "doctor-synthetic",
                    role: "DOCTOR",
                    products: { has: "TRANSCRIBE_MD" },
                  }),
                },
              }),
            },
          }),
        }),
      );
    } else {
      const patientSql = mocks.authorityQuery.mock.calls[2]?.[0];
      expect(patientSql?.strings?.join(" ")).toContain(
        'patient."externalId" IS DISTINCT FROM',
      );
    }
  });

  it("does not let an ordinary patient adopt the reserved external ID", async () => {
    mocks.patientFindFirst.mockResolvedValue({
      id: patientId,
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
    expect(mocks.transaction).not.toHaveBeenCalled();
    expect(mocks.patientUpdateMany).not.toHaveBeenCalled();
  });

  it("continues serving ordinary same-practice patient records", async () => {
    mocks.patientFindFirst.mockResolvedValue({
      id: patientId,
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
    const response = await GET(request("GET"), context);

    expect(response.status).toBe(200);
    await expect(response.json()).resolves.toMatchObject({
      patient: { id: patientId, externalId: "EXAMPLE-001" },
    });
    expect(mocks.visibleVisitAggregateQuery).toHaveBeenCalledOnce();
  });
});
