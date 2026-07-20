import { describe, expect, it, vi } from "vitest";

import {
  lockAndAssertCurrentTemplateTwinPhysician,
  TemplateTwinCurrentPhysicianAuthorityError,
} from "../final-claim-authority";

describe("Template Twin current-physician final claim", () => {
  it("accepts exactly one locked current physician row", async () => {
    const query = vi.fn().mockResolvedValue([{ id: "doctor-1" }]);

    await expect(
      lockAndAssertCurrentTemplateTwinPhysician({
        tx: { $queryRaw: query },
        actor: { userId: "doctor-1", practiceId: "practice-1" },
      }),
    ).resolves.toBeUndefined();

    const sql = query.mock.calls[0]?.[0];
    const text = sql?.strings?.join(" ") ?? "";
    expect(text).toContain('actor."practiceId"');
    expect(text).toContain('actor."role"');
    expect(text).toContain('actor."isActive"');
    expect(text).toContain('actor."deactivatedAt" IS NULL');
    expect(text).toContain('actor."suspendedAt" IS NULL');
    expect(text).toContain('actor."softDeletedAt" IS NULL');
    expect(text).toContain("'TRANSCRIBE_MD'::\"Product\"");
    expect(text).toContain("FOR UPDATE");
  });

  it.each([
    { rows: [] },
    { rows: [{ id: "other-doctor" }] },
    { rows: [{ id: "doctor-1" }, { id: "doctor-1" }] },
  ])(
    "fails closed for a missing, mismatched, or duplicate authority result",
    async ({ rows }) => {
      await expect(
        lockAndAssertCurrentTemplateTwinPhysician({
          tx: { $queryRaw: vi.fn().mockResolvedValue(rows) },
          actor: { userId: "doctor-1", practiceId: "practice-1" },
        }),
      ).rejects.toBeInstanceOf(TemplateTwinCurrentPhysicianAuthorityError);
    },
  );

  it("exposes only a stable, non-sensitive denial", () => {
    const error = new TemplateTwinCurrentPhysicianAuthorityError();
    expect(error).toMatchObject({
      code: "TEMPLATE_TWIN_CURRENT_PHYSICIAN_REQUIRED",
      message: "Current physician authorization is required for Template Twin.",
    });
    expect(JSON.stringify(error)).not.toMatch(
      /providerOwnership|executionPlan|receipt|patient|email/i,
    );
  });
});
