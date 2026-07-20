import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  runTransaction: vi.fn(),
  lockRollout: vi.fn(),
  queryRaw: vi.fn(),
  createAudit: vi.fn(),
}));

vi.mock("@meddoc/db", () => ({
  default: { $transaction: vi.fn() },
}));
vi.mock("@/lib/db/transaction-retry", () => ({
  runSerializableTransactionWithRetry: mocks.runTransaction,
}));
vi.mock("../rollout", () => ({
  lockTemplateTwinRolloutForFinalClaim: mocks.lockRollout,
}));

import {
  recordTemplateTwinStaticAssetInventoryAccess,
  TemplateTwinStaticAssetAccessAuditError,
} from "../static-asset-access-audit";

const POSTGRES_ECMASCRIPT_TRIM_WHITESPACE_CLASS =
  "U&'[\\0009-\\000D\\0020\\00A0\\1680\\2000-\\200A\\2028\\2029\\202F\\205F\\3000\\FEFF]'";

const ROLLOUT_TOKEN = {
  practiceId: "practice_synthetic",
  globalGeneration: BigInt(7),
  practiceGeneration: BigInt(11),
};

const ACTOR = {
  userId: "admin_synthetic",
  userEmail: "jwt-email-is-not-authoritative@synthetic.test",
  practiceId: "practice_synthetic",
  role: "ADMIN",
  rolloutToken: ROLLOUT_TOKEN,
};

beforeEach(() => {
  vi.clearAllMocks();
  mocks.lockRollout.mockResolvedValue({
    allowed: true,
    token: ROLLOUT_TOKEN,
  });
  mocks.queryRaw
    .mockResolvedValueOnce([{ id: "practice_synthetic" }])
    .mockResolvedValueOnce([
      {
        id: "admin_synthetic",
        email: "current-admin@synthetic.test",
        practiceId: "practice_synthetic",
        role: "ADMIN",
      },
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

describe("required Template Twin static-asset inventory access audit", () => {
  it.each([
    [
      "page" as const,
      "ADMIN_DASHBOARD_ACCESS",
      "rsc:/settings/note-format/static-assets",
    ],
    [
      "api" as const,
      "ADMIN_API_ACCESS",
      "api:get:/api/note-templates/template-twin/static-assets",
    ],
  ])(
    "rechecks rollout, practice, then actor before persisting fixed %s details",
    async (surface, action, source) => {
      await recordTemplateTwinStaticAssetInventoryAccess({
        actor: ACTOR,
        surface,
      });

      expect(mocks.lockRollout).toHaveBeenCalledWith(
        expect.objectContaining({
          practiceId: ACTOR.practiceId,
          pinnedToken: ROLLOUT_TOKEN,
        }),
      );
      expect(mocks.queryRaw).toHaveBeenCalledTimes(2);
      expect(mocks.lockRollout.mock.invocationCallOrder[0]).toBeLessThan(
        mocks.queryRaw.mock.invocationCallOrder[0]!,
      );
      expect(mocks.queryRaw.mock.invocationCallOrder[0]).toBeLessThan(
        mocks.queryRaw.mock.invocationCallOrder[1]!,
      );
      expect(mocks.queryRaw.mock.invocationCallOrder[1]).toBeLessThan(
        mocks.createAudit.mock.invocationCallOrder[0]!,
      );
      const practiceSql = (
        mocks.queryRaw.mock.calls[0]![0] as { strings: readonly string[] }
      ).strings.join(" ");
      const actorSql = (
        mocks.queryRaw.mock.calls[1]![0] as { strings: readonly string[] }
      ).strings.join(" ");
      expect(practiceSql).toContain('FROM "practices" practice');
      expect(practiceSql).toContain('practice."isActive" = TRUE');
      expect(practiceSql).toContain('practice."templateTwinEnabled" = TRUE');
      expect(practiceSql).toContain("FOR UPDATE");
      expect(actorSql).toContain('FROM "users" actor');
      expect(actorSql).toContain('actor."practiceId" =');
      expect(actorSql).toContain('actor."role" IN');
      expect(actorSql).toContain('actor."isActive" = TRUE');
      expect(actorSql).toContain('actor."deactivatedAt" IS NULL');
      expect(actorSql).toContain('actor."suspendedAt" IS NULL');
      expect(actorSql).toContain('actor."softDeletedAt" IS NULL');
      expect(actorSql).toContain("'TRANSCRIBE_MD'::\"Product\"");
      expect(actorSql).toContain("NOT ('SUPER_ADMIN'::\"Product\"");
      expect(actorSql).toContain('actor."mfaEnabled" = TRUE');
      expect(actorSql).toContain("regexp_replace(");
      expect(actorSql).toContain('actor."mfaSecret",');
      expect(actorSql).toContain(POSTGRES_ECMASCRIPT_TRIM_WHITESPACE_CLASS);
      expect(actorSql).toMatch(/\)\s*<> ''/u);
      expect(actorSql).not.toContain('btrim(actor."mfaSecret")');
      expect(actorSql).not.toContain("[[:space:]]");
      expect(actorSql).toContain('actor."mfaVerifiedAt" <= CURRENT_TIMESTAMP');
      expect(actorSql).toContain("FOR UPDATE");
      expect(mocks.createAudit).toHaveBeenCalledWith({
        data: {
          userId: ACTOR.userId,
          userEmailSnapshot: "current-admin@synthetic.test",
          action,
          targetId: ACTOR.practiceId,
          targetType: "TemplateTwinStaticAssetIndex",
          metadata: { source },
          success: true,
          practiceId: ACTOR.practiceId,
        },
      });
    },
  );

  it("returns only a fixed failure when the underlying audit write rejects", async () => {
    mocks.createAudit.mockRejectedValue(
      new Error("postgresql://secret@synthetic.invalid/internal-detail"),
    );

    await expect(
      recordTemplateTwinStaticAssetInventoryAccess({
        actor: ACTOR,
        surface: "api",
      }),
    ).rejects.toEqual(new TemplateTwinStaticAssetAccessAuditError());
  });

  it("does not write when the active practice or current admin fence fails", async () => {
    mocks.queryRaw.mockReset().mockResolvedValueOnce([]);

    await expect(
      recordTemplateTwinStaticAssetInventoryAccess({
        actor: ACTOR,
        surface: "page",
      }),
    ).rejects.toEqual(new TemplateTwinStaticAssetAccessAuditError());
    expect(mocks.createAudit).not.toHaveBeenCalled();
  });
});
