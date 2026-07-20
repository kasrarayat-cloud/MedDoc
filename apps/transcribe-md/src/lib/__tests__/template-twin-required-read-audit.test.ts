import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  queryRaw: vi.fn(),
  createAudit: vi.fn(),
}));

vi.mock("next/headers", () => ({
  headers: vi.fn(async () => new Headers()),
}));
vi.mock("@/lib/nextauth", () => ({ auth: vi.fn(async () => null) }));
vi.mock("@meddoc/db", () => ({
  default: {
    $queryRaw: mocks.queryRaw,
    auditLog: { create: mocks.createAudit },
  },
}));
vi.mock("@/lib/redis", () => ({
  getRedis: vi.fn(),
  isRedisReady: vi.fn(() => false),
  ADMIN_AUDIT_STREAM_CHANNEL: "synthetic-audit-channel",
}));
vi.mock("@/lib/db/transaction-retry", () => ({
  runSerializableTransactionWithRetry: vi.fn(
    async (input: { transaction: (tx: unknown, attempt: number) => unknown }) =>
      input.transaction(
        {
          $queryRaw: mocks.queryRaw,
          auditLog: { create: mocks.createAudit },
        },
        1,
      ),
  ),
}));

import { logRequiredAudit } from "../audit";
import { TemplateTwinVisitReadAuthorityError } from "../template-twin/read-authority";

beforeEach(() => {
  vi.clearAllMocks();
});

describe("Template Twin required read-audit race boundary", () => {
  it("maps a practice loss between classification and final audit to uniform not-found authority", async () => {
    mocks.queryRaw.mockResolvedValueOnce([]);

    await expect(
      logRequiredAudit({
        action: "VIEWED_VISIT",
        targetId: "visit-twin-1",
        targetType: "TranscribeVisit",
        userId: "doctor-1",
        practiceId: "practice-current",
        metadata: { source: "synthetic-race-test" },
        templateTwinReadAuthority: {
          expectedPracticeId: "practice-current",
        },
      }),
    ).rejects.toBeInstanceOf(TemplateTwinVisitReadAuthorityError);

    expect(mocks.queryRaw).toHaveBeenCalledTimes(1);
    expect(mocks.createAudit).not.toHaveBeenCalled();
  });

  it("maps current actor loss after the practice lock to the same fixed denial", async () => {
    mocks.queryRaw
      .mockResolvedValueOnce([{ id: "practice-current" }])
      .mockResolvedValueOnce([]);

    await expect(
      logRequiredAudit({
        action: "VIEWED_VISIT_AUDIO",
        targetId: "visit-twin-1",
        targetType: "TranscribeVisit",
        userId: "doctor-1",
        practiceId: "practice-current",
        templateTwinReadAuthority: {
          expectedPracticeId: "practice-current",
        },
      }),
    ).rejects.toBeInstanceOf(TemplateTwinVisitReadAuthorityError);

    expect(mocks.queryRaw).toHaveBeenCalledTimes(2);
    expect(mocks.createAudit).not.toHaveBeenCalled();
  });
});
