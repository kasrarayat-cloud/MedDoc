import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  auth: vi.fn(),
  headers: vi.fn(),
  runTransaction: vi.fn(),
  queryRaw: vi.fn(),
  createAudit: vi.fn(),
}));

vi.mock("@meddoc/db", () => ({
  default: { $transaction: vi.fn() },
}));
vi.mock("next/headers", () => ({ headers: mocks.headers }));
vi.mock("@/lib/nextauth", () => ({ auth: mocks.auth }));
vi.mock("@/lib/redis", () => ({
  getRedis: vi.fn(),
  isRedisReady: () => false,
  ADMIN_AUDIT_STREAM_CHANNEL: "synthetic-audit-stream",
}));
vi.mock("@/lib/db/transaction-retry", () => ({
  runSerializableTransactionWithRetry: mocks.runTransaction,
}));

import { logRequiredAdminAudit } from "../audit";

beforeEach(() => {
  vi.clearAllMocks();
  mocks.headers.mockResolvedValue(new Headers());
  mocks.queryRaw
    .mockResolvedValueOnce([{ id: "practice_synthetic" }])
    .mockResolvedValueOnce([
      { id: "admin_synthetic", practiceId: "practice_synthetic" },
    ]);
  mocks.createAudit.mockResolvedValue({});
  mocks.runTransaction.mockImplementation(
    async (input: { transaction: (tx: unknown) => Promise<unknown> }) =>
      input.transaction({
        $queryRaw: mocks.queryRaw,
        auditLog: { create: mocks.createAudit },
      }),
  );
});

describe("required platform-admin audit", () => {
  it("uses only the supplied verified actor and persists before returning", async () => {
    await logRequiredAdminAudit({
      action: "ADMIN_API_ACCESS",
      userId: "admin_synthetic",
      userEmail: "admin@synthetic.invalid",
      practiceId: "practice_synthetic",
      targetType: "AdminAPI",
      targetId: "synthetic:route",
    });

    expect(mocks.auth).not.toHaveBeenCalled();
    expect(mocks.createAudit).toHaveBeenCalledTimes(1);
    expect(mocks.createAudit).toHaveBeenCalledWith({
      data: expect.objectContaining({
        userId: "admin_synthetic",
        userEmailSnapshot: "admin@synthetic.invalid",
        practiceId: "practice_synthetic",
        action: "ADMIN_API_ACCESS",
      }),
    });
  });

  it("fails closed with a fixed error if current authority is unavailable", async () => {
    mocks.queryRaw
      .mockReset()
      .mockResolvedValueOnce([{ id: "practice_synthetic" }])
      .mockResolvedValueOnce([]);

    await expect(
      logRequiredAdminAudit({
        action: "ADMIN_DASHBOARD_ACCESS",
        userId: "admin_synthetic",
        practiceId: "practice_synthetic",
        targetType: "AdminPage",
        targetId: "/admin",
      }),
    ).rejects.toThrow("Required admin audit persistence failed.");
    expect(mocks.createAudit).not.toHaveBeenCalled();
  });
});
