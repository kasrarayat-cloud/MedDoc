import { beforeEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";

const mocks = vi.hoisted(() => ({
  findCandidate: vi.fn(),
  lockToken: vi.fn(),
  consumeToken: vi.fn(),
  updateUser: vi.fn(),
  deleteSessions: vi.fn(),
  invalidateTokens: vi.fn(),
  transaction: vi.fn(),
  hashPassword: vi.fn(),
  createAudit: vi.fn(),
  logInfo: vi.fn(),
}));

vi.mock("@meddoc/db", () => ({
  default: { $transaction: mocks.transaction },
}));
vi.mock("bcryptjs", () => ({
  default: { hash: mocks.hashPassword },
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
  clientIpFromRequest: vi.fn(() => "192.0.2.1"),
  sharedRateLimitOr429: vi.fn(async () => null),
}));
vi.mock("@/lib/log", () => ({ log: { info: mocks.logInfo } }));

import { AuthTokenAuthorityError } from "@/lib/auth-tokens";
import { POST } from "./route";

const RAW_TOKEN = "synthetic-reset-token-value-long-enough";
const NOW = new Date("2026-07-20T12:00:00.000Z");

function request(): NextRequest {
  return new NextRequest("https://app.quillmd.com/api/auth/reset-password", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      token: RAW_TOKEN,
      password: "ReplacementPass9",
      confirmPassword: "ReplacementPass9",
    }),
  });
}

beforeEach(() => {
  vi.clearAllMocks();
  mocks.findCandidate.mockResolvedValue({ id: "token-row", userId: "user-1" });
  mocks.hashPassword.mockResolvedValue("replacement-hash");
  mocks.lockToken.mockResolvedValue({
    token: { id: "token-row" },
    user: {
      id: "user-1",
      email: "doctor@synthetic.invalid",
      practiceId: "practice-1",
    },
    now: NOW,
  });
  mocks.updateUser.mockResolvedValue({});
  mocks.deleteSessions.mockResolvedValue({ count: 2 });
  mocks.consumeToken.mockResolvedValue(undefined);
  mocks.invalidateTokens.mockResolvedValue({ count: 1 });
  mocks.createAudit.mockResolvedValue({ id: "audit-row" });
  mocks.transaction.mockImplementation(
    async (callback: (tx: unknown) => Promise<unknown>) =>
      callback({
        user: { update: mocks.updateUser },
        userSession: { deleteMany: mocks.deleteSessions },
        authToken: { updateMany: mocks.invalidateTokens },
        auditLog: { create: mocks.createAudit },
      }),
  );
});

describe("reset-password atomic redemption", () => {
  it("mutates the credential, consumes the exact token, invalidates sibling credential tokens, and revokes sessions in one transaction", async () => {
    const response = await POST(request(), { params: Promise.resolve({}) });

    expect(response.status).toBe(200);
    expect(response.headers.get("X-Response-Time")).toBeNull();
    expect(response.headers.get("Server-Timing")).toBeNull();
    expect(mocks.transaction).toHaveBeenCalledTimes(1);
    expect(mocks.lockToken).toHaveBeenCalledWith(
      expect.objectContaining({
        user: { update: mocks.updateUser },
        userSession: { deleteMany: mocks.deleteSessions },
        authToken: { updateMany: mocks.invalidateTokens },
        auditLog: { create: mocks.createAudit },
      }),
      {
        token: RAW_TOKEN,
        purpose: "PASSWORD_RESET",
        candidate: { id: "token-row", userId: "user-1" },
      },
    );
    expect(mocks.updateUser).toHaveBeenCalledWith({
      where: { id: "user-1" },
      data: {
        passwordHash: "replacement-hash",
        failedLoginCount: 0,
        lockedUntil: null,
      },
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
        purpose: { in: ["PASSWORD_RESET", "EMAIL_CHANGE"] },
        usedAt: null,
      },
      data: { usedAt: NOW },
    });
    expect(mocks.createAudit).toHaveBeenCalledWith({
      data: {
        userId: "user-1",
        userEmailSnapshot: "doctor@synthetic.invalid",
        action: "PASSWORD_CHANGED",
        targetId: "user-1",
        targetType: "User",
        metadata: { via: "reset_token" },
        success: true,
        practiceId: "practice-1",
        timestamp: expect.any(Date),
      },
    });
  });

  it("fails the transaction when the immutable audit receipt cannot be appended", async () => {
    mocks.createAudit.mockRejectedValueOnce(
      new Error("synthetic audit outage"),
    );

    const response = await POST(request(), { params: Promise.resolve({}) });

    expect(response.status).toBe(500);
    expect(mocks.transaction).toHaveBeenCalledTimes(1);
    expect(mocks.createAudit).toHaveBeenCalledTimes(1);
    expect(mocks.logInfo).not.toHaveBeenCalled();
  });

  it("fails closed without any credential mutation when final token authority changed", async () => {
    mocks.lockToken.mockRejectedValueOnce(new AuthTokenAuthorityError());

    const response = await POST(request(), { params: Promise.resolve({}) });

    expect(response.status).toBe(400);
    expect(mocks.updateUser).not.toHaveBeenCalled();
    expect(mocks.deleteSessions).not.toHaveBeenCalled();
    expect(mocks.consumeToken).not.toHaveBeenCalled();
  });

  it("rejects an unknown token before hashing or opening a transaction", async () => {
    mocks.findCandidate.mockResolvedValueOnce(null);

    const response = await POST(request(), { params: Promise.resolve({}) });

    expect(response.status).toBe(400);
    expect(mocks.hashPassword).not.toHaveBeenCalled();
    expect(mocks.transaction).not.toHaveBeenCalled();
  });
});
