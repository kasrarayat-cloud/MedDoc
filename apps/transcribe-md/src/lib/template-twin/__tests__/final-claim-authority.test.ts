import { describe, expect, it, vi } from "vitest";

import {
  lockAndAssertActiveTemplateTwinPractice,
  lockAndAssertCurrentTemplateTwinPatient,
  lockAndAssertCurrentTemplateTwinPhysician,
  TemplateTwinCurrentPhysicianAuthorityError,
} from "../final-claim-authority";

describe("Template Twin current-physician final claim", () => {
  it("locks exactly one active practice before multi-statement authority work", async () => {
    const query = vi.fn().mockResolvedValue([{ id: "practice-1" }]);

    await expect(
      lockAndAssertActiveTemplateTwinPractice({
        tx: { $queryRaw: query },
        practiceId: "practice-1",
      }),
    ).resolves.toBeUndefined();

    const text = query.mock.calls[0]?.[0]?.strings?.join(" ") ?? "";
    expect(text).toContain('FROM "practices"');
    expect(text).toContain('practice."isActive" = true');
    expect(text).toContain("FOR UPDATE");
  });

  it.each([
    { rows: [] },
    { rows: [{ id: "other-practice" }] },
    { rows: [{ id: "practice-1" }, { id: "practice-1" }] },
  ])(
    "fails closed when the active-practice lock is absent, mismatched, or ambiguous",
    async ({ rows }) => {
      await expect(
        lockAndAssertActiveTemplateTwinPractice({
          tx: { $queryRaw: vi.fn().mockResolvedValue(rows) },
          practiceId: "practice-1",
        }),
      ).rejects.toBeInstanceOf(TemplateTwinCurrentPhysicianAuthorityError);
    },
  );

  it("accepts exactly one locked current physician row", async () => {
    const query = vi
      .fn()
      .mockResolvedValue([{ id: "doctor-1", email: "current@example.test" }]);

    await expect(
      lockAndAssertCurrentTemplateTwinPhysician({
        tx: { $queryRaw: query },
        actor: { userId: "doctor-1", practiceId: "practice-1" },
      }),
    ).resolves.toEqual({ email: "current@example.test" });

    const sql = query.mock.calls[0]?.[0];
    const text = sql?.strings?.join(" ") ?? "";
    expect(text).toContain('actor."practiceId"');
    expect(text).toContain('actor."email"');
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
    { rows: [{ id: "other-doctor", email: "other@example.test" }] },
    { rows: [{ id: "doctor-1", email: null }] },
    { rows: [{ id: "doctor-1", email: "" }] },
    {
      rows: [
        { id: "doctor-1", email: "one@example.test" },
        { id: "doctor-1", email: "two@example.test" },
      ],
    },
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

  it("accepts exactly one locked patient in the actor practice", async () => {
    const query = vi
      .fn()
      .mockResolvedValue([{ id: "patient-1", practiceId: "practice-1" }]);

    await expect(
      lockAndAssertCurrentTemplateTwinPatient({
        tx: { $queryRaw: query },
        patientId: "patient-1",
        practiceId: "practice-1",
      }),
    ).resolves.toBeUndefined();

    const text = query.mock.calls[0]?.[0]?.strings?.join(" ") ?? "";
    expect(text).toContain('FROM "transcribe_md_patients" patient');
    expect(text).toContain('patient."practiceId"');
    expect(text).toContain("FOR UPDATE");
  });

  it.each([
    { rows: [] },
    { rows: [{ id: "patient-1", practiceId: "other-practice" }] },
    { rows: [{ id: "other-patient", practiceId: "practice-1" }] },
    {
      rows: [
        { id: "patient-1", practiceId: "practice-1" },
        { id: "patient-1", practiceId: "practice-1" },
      ],
    },
  ])(
    "fails closed when the patient lock is absent, moved, mismatched, or ambiguous",
    async ({ rows }) => {
      await expect(
        lockAndAssertCurrentTemplateTwinPatient({
          tx: { $queryRaw: vi.fn().mockResolvedValue(rows) },
          patientId: "patient-1",
          practiceId: "practice-1",
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
