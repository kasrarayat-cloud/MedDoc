import { beforeEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";

const mocks = vi.hoisted(() => ({
  findCandidate: vi.fn(),
  lockToken: vi.fn(),
  consumeToken: vi.fn(),
  findUser: vi.fn(),
  updateUser: vi.fn(),
  deleteSessions: vi.fn(),
  invalidateTokens: vi.fn(),
  transaction: vi.fn(),
  logInfo: vi.fn(),
  createAudit: vi.fn(),
  sendChangedNotification: vi.fn(),
}));

vi.mock("@meddoc/db", () => ({
  default: { $transaction: mocks.transaction },
}));
vi.mock("@/lib/nextauth", () => ({ auth: vi.fn() }));
vi.mock("@/lib/auth-tokens", () => {
  class AuthTokenAuthorityError extends Error {}
  return {
    AuthTokenAuthorityError,
    findAuthTokenCandidate: mocks.findCandidate,
    lockCurrentAuthTokenForMutation: mocks.lockToken,
    consumeLockedAuthToken: mocks.consumeToken,
  };
});
vi.mock("@/lib/rate-limit", () => ({
  RATE_LIMITS: { AUTH_EMAIL: {} },
  clientIpFromRequest: vi.fn(() => "192.0.2.2"),
  sharedRateLimitOr429: vi.fn(async () => null),
}));
vi.mock("@/lib/email", () => ({
  sendEmailChangedNotification: mocks.sendChangedNotification,
}));
vi.mock("@/lib/email-enabled", () => ({
  isEmailDeliveryEnabled: vi.fn(() => false),
}));
vi.mock("@/lib/log", () => ({ log: { info: mocks.logInfo } }));

import { POST as confirmEmail } from "@/app/api/auth/confirm-email/route";
import { POST as verifyEmail } from "@/app/api/auth/verify-email/route";

const RAW_TOKEN = "synthetic-email-token-value-long-enough";
const NOW = new Date("2026-07-20T12:00:00.000Z");

function request(path: string): NextRequest {
  return new NextRequest(`https://app.quillmd.com${path}`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ token: RAW_TOKEN }),
  });
}

beforeEach(() => {
  vi.clearAllMocks();
  mocks.findCandidate.mockResolvedValue({ id: "token-row", userId: "user-1" });
  mocks.lockToken.mockImplementation(
    async (_tx: unknown, input: { purpose: string }) => ({
      token: {
        id: "token-row",
        metadata:
          input.purpose === "EMAIL_CHANGE"
            ? {
                oldEmail: "old@synthetic.invalid",
                newEmail: "new@synthetic.invalid",
              }
            : { email: "old@synthetic.invalid" },
      },
      user: {
        id: "user-1",
        email: "old@synthetic.invalid",
        name: "Synthetic Doctor",
        practiceId: "practice-1",
      },
      now: NOW,
    }),
  );
  mocks.findUser.mockResolvedValue(null);
  mocks.updateUser.mockResolvedValue({ name: "Synthetic Doctor" });
  mocks.deleteSessions.mockResolvedValue({ count: 1 });
  mocks.consumeToken.mockResolvedValue(undefined);
  mocks.invalidateTokens.mockResolvedValue({ count: 0 });
  mocks.createAudit.mockResolvedValue({ id: "audit-row" });
  mocks.transaction.mockImplementation(
    async (callback: (tx: unknown) => Promise<unknown>) =>
      callback({
        user: {
          findUnique: mocks.findUser,
          update: mocks.updateUser,
        },
        userSession: { deleteMany: mocks.deleteSessions },
        authToken: { updateMany: mocks.invalidateTokens },
        auditLog: { create: mocks.createAudit },
      }),
  );
});

describe("confirm-email atomic identity mutation", () => {
  it("binds oldEmail to the locked current identity and revokes every session in the same transaction", async () => {
    const response = await confirmEmail(request("/api/auth/confirm-email"), {
      params: Promise.resolve({}),
    });

    expect(response.status).toBe(303);
    expect(response.headers.get("location")).toContain("emailChange=ok");
    expect(response.headers.get("Referrer-Policy")).toBe("no-referrer");
    expect(response.headers.get("X-Response-Time")).toBeNull();
    expect(response.headers.get("Server-Timing")).toBeNull();
    expect(mocks.updateUser).toHaveBeenCalledWith({
      where: { id: "user-1" },
      data: { email: "new@synthetic.invalid", emailVerified: NOW },
      select: { name: true },
    });
    expect(mocks.deleteSessions).toHaveBeenCalledWith({
      where: { userId: "user-1" },
    });
    expect(mocks.consumeToken).toHaveBeenCalledWith(
      expect.anything(),
      "token-row",
      NOW,
    );
    expect(mocks.invalidateTokens).toHaveBeenCalledWith({
      where: {
        userId: "user-1",
        purpose: {
          in: ["PASSWORD_RESET", "EMAIL_VERIFICATION", "EMAIL_CHANGE"],
        },
        usedAt: null,
      },
      data: { usedAt: NOW },
    });
    expect(mocks.createAudit).toHaveBeenCalledWith({
      data: {
        userId: "user-1",
        userEmailSnapshot: "new@synthetic.invalid",
        action: "EMAIL_CHANGE_CONFIRMED",
        targetId: "user-1",
        targetType: "User",
        metadata: {
          newEmailDomain: "synthetic.invalid",
          oldEmailDomain: "synthetic.invalid",
        },
        success: true,
        practiceId: "practice-1",
        timestamp: expect.any(Date),
      },
    });
  });

  it("fails the identity transaction when its audit receipt cannot commit", async () => {
    mocks.createAudit.mockRejectedValueOnce(
      new Error("synthetic audit outage"),
    );

    const response = await confirmEmail(request("/api/auth/confirm-email"), {
      params: Promise.resolve({}),
    });

    expect(response.headers.get("location")).toContain("emailChange=error");
    expect(mocks.createAudit).toHaveBeenCalledTimes(1);
    expect(mocks.logInfo).not.toHaveBeenCalled();
    expect(mocks.sendChangedNotification).not.toHaveBeenCalled();
  });

  it("fails closed when the token's oldEmail no longer matches the locked account", async () => {
    mocks.lockToken.mockResolvedValueOnce({
      token: {
        id: "token-row",
        metadata: {
          oldEmail: "stale@synthetic.invalid",
          newEmail: "new@synthetic.invalid",
        },
      },
      user: {
        id: "user-1",
        email: "old@synthetic.invalid",
        name: "Synthetic Doctor",
      },
      now: NOW,
    });

    const response = await confirmEmail(request("/api/auth/confirm-email"), {
      params: Promise.resolve({}),
    });

    expect(response.status).toBe(303);
    expect(response.headers.get("location")).toContain(
      "emailChange=invalid-or-expired",
    );
    expect(mocks.updateUser).not.toHaveBeenCalled();
    expect(mocks.consumeToken).not.toHaveBeenCalled();
  });

  it("rechecks target uniqueness under lock before consuming the token", async () => {
    mocks.findUser.mockResolvedValueOnce({ id: "other-user" });

    const response = await confirmEmail(request("/api/auth/confirm-email"), {
      params: Promise.resolve({}),
    });

    expect(response.headers.get("location")).toContain("emailChange=conflict");
    expect(mocks.updateUser).not.toHaveBeenCalled();
    expect(mocks.consumeToken).not.toHaveBeenCalled();
  });

  it("maps a cross-user unique-index race to conflict and rolls back consumption", async () => {
    mocks.updateUser.mockRejectedValueOnce({ code: "P2002" });

    const response = await confirmEmail(request("/api/auth/confirm-email"), {
      params: Promise.resolve({}),
    });

    expect(response.headers.get("location")).toContain("emailChange=conflict");
    expect(mocks.consumeToken).toHaveBeenCalledWith(
      expect.anything(),
      "token-row",
      NOW,
    );
    expect(mocks.consumeToken.mock.invocationCallOrder[0]).toBeLessThan(
      mocks.updateUser.mock.invocationCallOrder[0]!,
    );
    expect(mocks.deleteSessions).not.toHaveBeenCalled();
  });
});

describe("verify-email atomic token binding", () => {
  it("updates only the email named by the locked token and revokes sessions before commit", async () => {
    const response = await verifyEmail(request("/api/auth/verify-email"), {
      params: Promise.resolve({}),
    });

    expect(response.status).toBe(303);
    expect(response.headers.get("location")).toContain("verify=ok");
    expect(response.headers.get("Referrer-Policy")).toBe("no-referrer");
    expect(response.headers.get("X-Response-Time")).toBeNull();
    expect(response.headers.get("Server-Timing")).toBeNull();
    expect(mocks.updateUser).toHaveBeenCalledWith({
      where: { id: "user-1" },
      data: { emailVerified: NOW },
    });
    expect(mocks.deleteSessions).toHaveBeenCalledWith({
      where: { userId: "user-1" },
    });
    expect(mocks.consumeToken).toHaveBeenCalledWith(
      expect.anything(),
      "token-row",
      NOW,
    );
    expect(mocks.createAudit).toHaveBeenCalledWith({
      data: {
        userId: "user-1",
        userEmailSnapshot: "old@synthetic.invalid",
        action: "EMAIL_VERIFIED",
        targetId: "user-1",
        targetType: "User",
        metadata: { via: "verification_token" },
        success: true,
        practiceId: "practice-1",
        timestamp: expect.any(Date),
      },
    });
  });

  it("fails the verification transaction when its audit receipt cannot commit", async () => {
    mocks.createAudit.mockRejectedValueOnce(
      new Error("synthetic audit outage"),
    );

    const response = await verifyEmail(request("/api/auth/verify-email"), {
      params: Promise.resolve({}),
    });

    expect(response.headers.get("location")).toContain("verify=error");
    expect(mocks.createAudit).toHaveBeenCalledTimes(1);
    expect(mocks.logInfo).not.toHaveBeenCalled();
  });

  it("rejects a verification token after the account email changed", async () => {
    mocks.lockToken.mockResolvedValueOnce({
      token: {
        id: "token-row",
        metadata: { email: "stale@synthetic.invalid" },
      },
      user: {
        id: "user-1",
        email: "current@synthetic.invalid",
        name: "Synthetic Doctor",
      },
      now: NOW,
    });

    const response = await verifyEmail(request("/api/auth/verify-email"), {
      params: Promise.resolve({}),
    });

    expect(response.headers.get("location")).toContain(
      "verify=invalid-or-expired",
    );
    expect(mocks.updateUser).not.toHaveBeenCalled();
    expect(mocks.consumeToken).not.toHaveBeenCalled();
  });
});
