import { createHash } from "node:crypto";

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  queryRaw: vi.fn(),
  sendPasswordResetEmail: vi.fn(),
  sendEmailVerification: vi.fn(),
  sendEmailChangeRequestEmail: vi.fn(),
  sendAccountExistsEmail: vi.fn(),
}));

vi.mock("@meddoc/db", () => ({
  default: { $queryRaw: mocks.queryRaw },
}));
vi.mock("@/lib/constants", () => ({
  APP_URL: "https://app.quillmd.com",
}));
vi.mock("@/lib/email", () => ({
  sendPasswordResetEmail: mocks.sendPasswordResetEmail,
  sendEmailVerification: mocks.sendEmailVerification,
  sendEmailChangeRequestEmail: mocks.sendEmailChangeRequestEmail,
  sendAccountExistsEmail: mocks.sendAccountExistsEmail,
}));

import { drainAuthEmailOutbox } from "../auth-email-delivery";

type Purpose =
  | "PASSWORD_RESET"
  | "EMAIL_VERIFICATION"
  | "EMAIL_CHANGE"
  | "ACCOUNT_EXISTS";

interface SqlStatement {
  strings?: readonly string[];
  values?: readonly unknown[];
}

const REQUEST_ID = "11111111-1111-4111-8111-111111111111";
const CLAIM_TOKEN = "22222222-2222-4222-8222-222222222222";
const EMAIL = "doctor@synthetic.invalid";
const NAME = "Synthetic Doctor";
const PROVIDER_RECEIPT = "provider-receipt-synthetic-001";
const HEALTH_ROW = {
  pending: 2,
  claimed: 1,
  ambiguous: 0,
  oldestPendingSeconds: 17,
};
const EXPECTED_HEALTH = {
  pending: 2,
  claimed: 1,
  ambiguous: 0,
  oldestPendingSeconds: 17,
};

function sqlText(statement: unknown): string {
  const sql = statement as SqlStatement;
  return sql.strings?.join("?") ?? String(statement);
}

function sqlValues(callIndex: number): readonly unknown[] {
  const statement = mocks.queryRaw.mock.calls[callIndex]?.[0] as
    | SqlStatement
    | undefined;
  return statement?.values ?? [];
}

function senderFor(purpose: Purpose) {
  switch (purpose) {
    case "PASSWORD_RESET":
      return mocks.sendPasswordResetEmail;
    case "EMAIL_VERIFICATION":
      return mocks.sendEmailVerification;
    case "EMAIL_CHANGE":
      return mocks.sendEmailChangeRequestEmail;
    case "ACCOUNT_EXISTS":
      return mocks.sendAccountExistsEmail;
  }
}

function queueClaimAndPrepare(purpose: Purpose): void {
  mocks.queryRaw
    .mockResolvedValueOnce([{ id: REQUEST_ID, claimToken: CLAIM_TOKEN }])
    .mockImplementationOnce(async (statement: SqlStatement) => [
      {
        userId: "user_synthetic",
        email: EMAIL,
        name: NAME,
        tokenId:
          purpose === "ACCOUNT_EXISTS" ? null : String(statement.values?.[2]),
        purpose,
      },
    ]);
}

function queueOrdinaryDelivery(purpose: Purpose): void {
  queueClaimAndPrepare(purpose);
  mocks.queryRaw
    .mockResolvedValueOnce([{ completed: true }])
    .mockResolvedValueOnce([{ count: 0 }])
    .mockResolvedValueOnce([HEALTH_ROW]);
}

function expectSqlOrder(expected: readonly string[]): void {
  expect(mocks.queryRaw).toHaveBeenCalledTimes(expected.length);
  expected.forEach((functionName, index) => {
    expect(sqlText(mocks.queryRaw.mock.calls[index]?.[0])).toContain(
      functionName,
    );
  });
}

beforeEach(() => {
  vi.useRealTimers();
  vi.clearAllMocks();
  for (const sender of [
    mocks.sendPasswordResetEmail,
    mocks.sendEmailVerification,
    mocks.sendEmailChangeRequestEmail,
    mocks.sendAccountExistsEmail,
  ]) {
    sender.mockResolvedValue({ id: PROVIDER_RECEIPT, toEmail: EMAIL });
  }
});

afterEach(() => {
  vi.useRealTimers();
});

describe("durable authentication email delivery", () => {
  it.each<{
    purpose: Purpose;
    linkField: "resetUrl" | "verifyUrl" | "confirmUrl" | "signInUrl";
    linkBase: string;
  }>([
    {
      purpose: "PASSWORD_RESET",
      linkField: "resetUrl",
      linkBase: "https://app.quillmd.com/reset-password?token=",
    },
    {
      purpose: "EMAIL_VERIFICATION",
      linkField: "verifyUrl",
      linkBase: "https://app.quillmd.com/api/auth/verify-email?token=",
    },
    {
      purpose: "EMAIL_CHANGE",
      linkField: "confirmUrl",
      linkBase: "https://app.quillmd.com/api/auth/confirm-email?token=",
    },
    {
      purpose: "ACCOUNT_EXISTS",
      linkField: "signInUrl",
      linkBase: "https://app.quillmd.com/login",
    },
  ])(
    "delivers $purpose with exact binding, sender, link, and receipt contract",
    async ({ purpose, linkField, linkBase }) => {
      queueOrdinaryDelivery(purpose);
      const progress = vi.fn();

      const result = await drainAuthEmailOutbox({
        limit: 1,
        onProgress: progress,
      });

      expect(result).toEqual({
        claimed: 1,
        delivered: 1,
        noop: 0,
        ambiguous: 0,
        purged: 0,
        health: EXPECTED_HEALTH,
      });
      expect(progress).toHaveBeenCalledTimes(3);
      expectSqlOrder([
        "auth_email_claim",
        "auth_email_prepare_delivery",
        "auth_email_finish_delivery",
        "auth_email_purge",
        "auth_email_health",
      ]);

      expect(sqlValues(0)).toEqual([1]);
      const prepareValues = sqlValues(1);
      expect(prepareValues[0]).toBe(REQUEST_ID);
      expect(prepareValues[1]).toBe(CLAIM_TOKEN);
      expect(prepareValues[2]).toEqual(expect.any(String));
      expect(prepareValues[3]).toMatch(/^[0-9a-f]{64}$/u);

      const selectedSender = senderFor(purpose);
      expect(selectedSender).toHaveBeenCalledOnce();
      expect(progress.mock.invocationCallOrder[0]).toBeLessThan(
        selectedSender.mock.invocationCallOrder[0] ?? Number.POSITIVE_INFINITY,
      );
      expect(selectedSender.mock.invocationCallOrder[0]).toBeLessThan(
        progress.mock.invocationCallOrder[1] ?? Number.POSITIVE_INFINITY,
      );
      expect(mocks.queryRaw.mock.invocationCallOrder[4]).toBeLessThan(
        progress.mock.invocationCallOrder[2] ?? Number.POSITIVE_INFINITY,
      );
      for (const sender of [
        mocks.sendPasswordResetEmail,
        mocks.sendEmailVerification,
        mocks.sendEmailChangeRequestEmail,
        mocks.sendAccountExistsEmail,
      ]) {
        expect(sender).toHaveBeenCalledTimes(sender === selectedSender ? 1 : 0);
      }
      const emailInput = selectedSender.mock.calls[0]?.[0] as Record<
        string,
        unknown
      >;
      const options = selectedSender.mock.calls[0]?.[1];
      expect(emailInput).toMatchObject({ toEmail: EMAIL, userName: NAME });
      expect(options).toEqual({
        trackUsage: false,
        idempotencyKey: `auth-email-${REQUEST_ID}`,
      });
      expect(JSON.stringify(options)).not.toContain(EMAIL);
      expect(JSON.stringify(options)).not.toContain(CLAIM_TOKEN);

      if (purpose === "ACCOUNT_EXISTS") {
        expect(emailInput[linkField]).toBe(linkBase);
        expect(JSON.stringify(emailInput)).not.toMatch(/[?&]token=/u);
      } else {
        const link = String(emailInput[linkField]);
        const token = new URL(link).searchParams.get("token");
        expect(token).toBeTruthy();
        expect(link).toBe(`${linkBase}${encodeURIComponent(String(token))}`);
        expect(JSON.stringify(options)).not.toContain(String(token));
        expect(prepareValues[3]).toBe(
          createHash("sha256").update(String(token)).digest("hex"),
        );
      }

      const finishValues = sqlValues(2);
      expect(finishValues.slice(0, 2)).toEqual([REQUEST_ID, CLAIM_TOKEN]);
      expect(finishValues[2]).toBe(
        purpose === "ACCOUNT_EXISTS" ? null : prepareValues[2],
      );
      expect(finishValues[3]).toBe(true);
      expect(finishValues[4]).toBeNull();
      expect(finishValues[5]).toBe(
        createHash("sha256").update(`resend:${PROVIDER_RECEIPT}`).digest("hex"),
      );
      expect(finishValues).not.toContain(PROVIDER_RECEIPT);
    },
  );

  it.each([
    {
      scenario: "missing provider receipt",
      configure: () =>
        mocks.sendPasswordResetEmail.mockResolvedValueOnce({
          id: null,
          toEmail: EMAIL,
        }),
    },
    {
      scenario: "provider rejection",
      configure: () =>
        mocks.sendPasswordResetEmail.mockRejectedValueOnce(
          new Error("synthetic provider rejection detail"),
        ),
    },
  ])(
    "terminalizes $scenario as ambiguous without resending",
    async ({ configure }) => {
      configure();
      queueOrdinaryDelivery("PASSWORD_RESET");

      const result = await drainAuthEmailOutbox({ limit: 1 });

      expect(result.ambiguous).toBe(1);
      expect(result.delivered).toBe(0);
      expect(mocks.sendPasswordResetEmail).toHaveBeenCalledOnce();
      expectSqlOrder([
        "auth_email_claim",
        "auth_email_prepare_delivery",
        "auth_email_finish_delivery",
        "auth_email_purge",
        "auth_email_health",
      ]);
      const finishValues = sqlValues(2);
      expect(finishValues.slice(0, 5)).toEqual([
        REQUEST_ID,
        CLAIM_TOKEN,
        sqlValues(1)[2],
        false,
        "AUTH_EMAIL_PROVIDER_AMBIGUOUS",
      ]);
      expect(finishValues[5]).toBeNull();
    },
  );

  it("does not resend after provider acceptance when database completion fails", async () => {
    vi.useFakeTimers();
    queueClaimAndPrepare("PASSWORD_RESET");
    mocks.queryRaw
      .mockRejectedValueOnce(new Error("synthetic finish failure one"))
      .mockRejectedValueOnce(new Error("synthetic finish failure two"))
      .mockRejectedValueOnce(new Error("synthetic finish failure three"))
      .mockResolvedValueOnce([{ completed: true }])
      .mockResolvedValueOnce([{ count: 0 }])
      .mockResolvedValueOnce([HEALTH_ROW]);

    const pending = drainAuthEmailOutbox({ limit: 1 });
    await vi.runAllTimersAsync();
    const result = await pending;

    expect(result.ambiguous).toBe(1);
    expect(result.delivered).toBe(0);
    expect(mocks.sendPasswordResetEmail).toHaveBeenCalledOnce();
    const finishCalls = mocks.queryRaw.mock.calls.filter(([statement]) =>
      sqlText(statement).includes("auth_email_finish_delivery"),
    );
    expect(finishCalls).toHaveLength(4);
    for (const [statement] of finishCalls.slice(0, 3)) {
      expect((statement as SqlStatement).values?.[3]).toBe(true);
    }
    expect((finishCalls[3]?.[0] as SqlStatement).values?.slice(3, 6)).toEqual([
      false,
      "AUTH_EMAIL_PROVIDER_AMBIGUOUS",
      null,
    ]);
  });

  it("bounds an unresolved provider call and terminalizes it as ambiguous", async () => {
    vi.useFakeTimers();
    mocks.sendPasswordResetEmail.mockReturnValueOnce(
      new Promise<never>(() => undefined),
    );
    queueOrdinaryDelivery("PASSWORD_RESET");

    const pending = drainAuthEmailOutbox({ limit: 1 });
    await vi.advanceTimersByTimeAsync(0);
    expect(vi.getTimerCount()).toBe(1);
    await vi.advanceTimersByTimeAsync(30_000);
    const result = await pending;

    expect(result.ambiguous).toBe(1);
    expect(result.delivered).toBe(0);
    expect(mocks.sendPasswordResetEmail).toHaveBeenCalledOnce();
    expect(sqlValues(2).slice(3, 6)).toEqual([
      false,
      "AUTH_EMAIL_PROVIDER_AMBIGUOUS",
      null,
    ]);
  });

  it("reports progress for an empty drain without inventing delivery work", async () => {
    mocks.queryRaw
      .mockResolvedValueOnce([])
      .mockResolvedValueOnce([{ count: 3 }])
      .mockResolvedValueOnce([HEALTH_ROW]);
    const progress = vi.fn();

    const result = await drainAuthEmailOutbox({
      limit: 1,
      onProgress: progress,
    });

    expect(result).toEqual({
      claimed: 0,
      delivered: 0,
      noop: 0,
      ambiguous: 0,
      purged: 3,
      health: EXPECTED_HEALTH,
    });
    expect(progress).toHaveBeenCalledTimes(2);
    expectSqlOrder([
      "auth_email_claim",
      "auth_email_purge",
      "auth_email_health",
    ]);
    for (const sender of [
      mocks.sendPasswordResetEmail,
      mocks.sendEmailVerification,
      mocks.sendEmailChangeRequestEmail,
      mocks.sendAccountExistsEmail,
    ]) {
      expect(sender).not.toHaveBeenCalled();
    }
  });
});
