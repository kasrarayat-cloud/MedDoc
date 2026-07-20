import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  patientFindFirst: vi.fn(),
  transaction: vi.fn(),
  authorityQuery: vi.fn(),
  patientUpdateMany: vi.fn(),
  transactionPatientFindFirst: vi.fn(),
  aggregateQuery: vi.fn(),
  getSession: vi.fn(),
  rateLimitOr429: vi.fn(),
  logAudit: vi.fn(),
}));

vi.mock("@meddoc/db", () => ({
  default: {
    transcribeMdPatient: { findFirst: mocks.patientFindFirst },
    $transaction: mocks.transaction,
    $queryRaw: mocks.aggregateQuery,
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
vi.mock("@/lib/audit", () => ({ logAudit: mocks.logAudit }));

import { DELETE, PATCH } from "../route";

const actor = { userId: "doctor-1", practiceId: "practice-1" };
const patientId = "patient-1";
const context = { params: Promise.resolve({ id: patientId }) };
const epoch = new Date("2026-07-20T00:00:00.000Z");

function patient(overrides: Record<string, unknown> = {}) {
  return {
    id: patientId,
    practiceId: actor.practiceId,
    name: "Synthetic Example",
    dateOfBirth: null,
    externalId: null,
    mrn: null,
    insurance: null,
    problemList: null,
    deletedAt: null,
    createdAt: epoch,
    updatedAt: epoch,
    ...overrides,
  };
}

function request(method: string, body?: unknown) {
  return new Request(`http://localhost/api/patients/${patientId}`, {
    method,
    body: body === undefined ? undefined : JSON.stringify(body),
    headers:
      body === undefined ? undefined : { "content-type": "application/json" },
  }) as Parameters<typeof PATCH>[0];
}

beforeEach(() => {
  vi.clearAllMocks();
  mocks.getSession.mockResolvedValue({
    user: { id: actor.userId, practiceId: actor.practiceId },
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
});

function admitPatient(row: Record<string, unknown> = patient()) {
  mocks.authorityQuery
    .mockResolvedValueOnce([{ id: actor.practiceId }])
    .mockResolvedValueOnce([{ id: actor.userId }])
    .mockResolvedValueOnce([row]);
}

describe("patient PATCH final authority", () => {
  it("uses current actor/tenant scope and the locked patient epoch for CAS", async () => {
    admitPatient();
    mocks.patientUpdateMany.mockResolvedValue({ count: 1 });
    mocks.transactionPatientFindFirst.mockResolvedValue(
      patient({ name: "Changed", updatedAt: new Date(epoch.getTime() + 1) }),
    );

    const response = await PATCH(
      request("PATCH", { name: "Changed" }),
      context,
    );

    expect(response.status).toBe(200);
    expect(mocks.patientUpdateMany).toHaveBeenCalledWith(
      expect.objectContaining({
        where: expect.objectContaining({
          id: patientId,
          practiceId: actor.practiceId,
          deletedAt: null,
          updatedAt: epoch,
          practice: {
            is: expect.objectContaining({
              id: actor.practiceId,
              isActive: true,
              users: {
                some: expect.objectContaining({
                  id: actor.userId,
                  suspendedAt: null,
                  products: { has: "TRANSCRIBE_MD" },
                }),
              },
            }),
          },
        }),
      }),
    );
  });

  it("blocks practice transfer before patient PHI projection or write", async () => {
    mocks.authorityQuery
      .mockResolvedValueOnce([{ id: actor.practiceId }])
      .mockResolvedValueOnce([]);

    const response = await PATCH(
      request("PATCH", { name: "Changed" }),
      context,
    );

    expect(response.status).toBe(404);
    expect(mocks.authorityQuery).toHaveBeenCalledTimes(2);
    expect(mocks.patientUpdateMany).not.toHaveBeenCalled();
    expect(mocks.transactionPatientFindFirst).not.toHaveBeenCalled();
  });

  it.each(["patient deletion", "reserved-marker transition"])(
    "blocks %s before write",
    async () => {
      mocks.authorityQuery
        .mockResolvedValueOnce([{ id: actor.practiceId }])
        .mockResolvedValueOnce([{ id: actor.userId }])
        .mockResolvedValueOnce([]);

      const response = await PATCH(
        request("PATCH", { name: "Changed" }),
        context,
      );
      expect(response.status).toBe(404);
      expect(mocks.patientUpdateMany).not.toHaveBeenCalled();
      expect(mocks.transactionPatientFindFirst).not.toHaveBeenCalled();
    },
  );

  it("fails closed when the scoped current-epoch CAS misses", async () => {
    admitPatient();
    mocks.patientUpdateMany.mockResolvedValue({ count: 0 });

    const response = await PATCH(
      request("PATCH", { name: "Changed" }),
      context,
    );

    expect(response.status).toBe(404);
    expect(mocks.transactionPatientFindFirst).not.toHaveBeenCalled();
  });
});

describe("patient DELETE final authority", () => {
  it("preserves idempotent repeated deletion without another write", async () => {
    admitPatient(patient({ deletedAt: epoch }));

    const response = await DELETE(request("DELETE"), context);

    expect(response.status).toBe(200);
    await expect(response.json()).resolves.toEqual({
      ok: true,
      alreadyDeleted: true,
    });
    expect(mocks.patientUpdateMany).not.toHaveBeenCalled();
  });

  it("soft-deletes with exact actor/tenant and current-epoch CAS", async () => {
    admitPatient();
    mocks.patientUpdateMany.mockResolvedValue({ count: 1 });

    const response = await DELETE(request("DELETE"), context);

    expect(response.status).toBe(200);
    expect(mocks.patientUpdateMany).toHaveBeenCalledWith(
      expect.objectContaining({
        where: expect.objectContaining({
          id: patientId,
          practiceId: actor.practiceId,
          deletedAt: null,
          updatedAt: epoch,
        }),
      }),
    );
  });

  it("does not write when transfer or reserved-marker drift denies the final lock", async () => {
    mocks.authorityQuery
      .mockResolvedValueOnce([{ id: actor.practiceId }])
      .mockResolvedValueOnce([]);

    const response = await DELETE(request("DELETE"), context);

    expect(response.status).toBe(404);
    expect(mocks.authorityQuery).toHaveBeenCalledTimes(2);
    expect(mocks.patientUpdateMany).not.toHaveBeenCalled();
  });
});
