import { beforeEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";

const mocks = vi.hoisted(() => ({
  auth: vi.fn(),
  findUser: vi.fn(),
  updateUser: vi.fn(),
  invalidateTokens: vi.fn(),
  deleteSessions: vi.fn(),
  transaction: vi.fn(),
  comparePassword: vi.fn(),
  hashPassword: vi.fn(),
  sharedRateLimit: vi.fn(),
  lockAuthority: vi.fn(),
  createAudit: vi.fn(),
  logInfo: vi.fn(),
}));

vi.mock("@meddoc/db", () => ({
  default: {
    user: { findUnique: mocks.findUser },
    $transaction: mocks.transaction,
  },
}));
vi.mock("bcryptjs", () => ({
  default: {
    compare: mocks.comparePassword,
    hash: mocks.hashPassword,
  },
}));
vi.mock("@/lib/nextauth", () => ({ auth: mocks.auth }));
vi.mock("@/lib/account-mutation-authority", () => {
  class AccountMutationAuthorityError extends Error {}
  return {
    AccountMutationAuthorityError,
    lockCurrentAccountMutationAuthority: mocks.lockAuthority,
  };
});
vi.mock("@/lib/rate-limit", () => ({
  RATE_LIMITS: { SETTINGS: {} },
  sharedRateLimitOr429: mocks.sharedRateLimit,
}));
vi.mock("@/lib/log", () => ({ log: { info: mocks.logInfo } }));

import { AccountMutationAuthorityError } from "@/lib/account-mutation-authority";
import { POST } from "./route";

function request(): NextRequest {
  return new NextRequest(
    "https://app.quillmd.com/api/settings/change-password",
    {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        currentPassword: "CurrentPass8",
        newPassword: "ReplacementPass9",
        confirmPassword: "ReplacementPass9",
      }),
    },
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  mocks.auth.mockResolvedValue({
    user: {
      id: "user-1",
      practiceId: "practice-1",
      sessionId: "session-1",
    },
  });
  mocks.findUser.mockResolvedValue({
    id: "user-1",
    email: "doctor@synthetic.invalid",
    practiceId: "practice-1",
    passwordHash: "current-hash",
  });
  mocks.comparePassword.mockResolvedValue(true);
  mocks.hashPassword.mockResolvedValue("replacement-hash");
  mocks.sharedRateLimit.mockResolvedValue(null);
  mocks.lockAuthority.mockResolvedValue({
    user: {
      id: "user-1",
      email: "doctor@synthetic.invalid",
      practiceId: "practice-1",
    },
  });
  mocks.updateUser.mockResolvedValue({});
  mocks.invalidateTokens.mockResolvedValue({ count: 2 });
  mocks.deleteSessions.mockResolvedValue({ count: 1 });
  mocks.createAudit.mockResolvedValue({ id: "audit-row" });
  mocks.transaction.mockImplementation(
    async (callback: (tx: unknown) => Promise<unknown>) =>
      callback({
        user: { update: mocks.updateUser },
        authToken: { updateMany: mocks.invalidateTokens },
        userSession: { deleteMany: mocks.deleteSessions },
        auditLog: { create: mocks.createAudit },
      }),
  );
});

describe("change-password final authority", () => {
  it("fails closed before credential work when the shared limiter is unavailable", async () => {
    mocks.sharedRateLimit.mockResolvedValueOnce(
      Response.json(
        {
          ok: false,
          code: "RATE_LIMITED",
          limitType: "shared_limiter_unavailable",
        },
        { status: 429 },
      ),
    );

    const response = await POST(request(), { params: Promise.resolve({}) });

    expect(response.status).toBe(429);
    await expect(response.json()).resolves.toMatchObject({
      code: "RATE_LIMITED",
      limitType: "shared_limiter_unavailable",
    });
    expect(mocks.sharedRateLimit).toHaveBeenCalledWith({}, "user-1");
    expect(mocks.findUser).not.toHaveBeenCalled();
    expect(mocks.comparePassword).not.toHaveBeenCalled();
    expect(mocks.hashPassword).not.toHaveBeenCalled();
    expect(mocks.transaction).not.toHaveBeenCalled();
    expect(mocks.updateUser).not.toHaveBeenCalled();
    expect(mocks.invalidateTokens).not.toHaveBeenCalled();
    expect(mocks.deleteSessions).not.toHaveBeenCalled();
    expect(mocks.createAudit).not.toHaveBeenCalled();
  });

  it("revalidates the exact session, tenant, password hash, and email before mutating", async () => {
    const response = await POST(request(), { params: Promise.resolve({}) });

    expect(response.status).toBe(200);
    expect(mocks.lockAuthority).toHaveBeenCalledWith(expect.anything(), {
      userId: "user-1",
      sessionId: "session-1",
      expectedPracticeId: "practice-1",
      expectedPasswordHash: "current-hash",
      expectedEmail: "doctor@synthetic.invalid",
      surface: "physician",
    });
    expect(mocks.invalidateTokens).toHaveBeenCalledWith({
      where: {
        userId: "user-1",
        purpose: { in: ["PASSWORD_RESET", "EMAIL_CHANGE"] },
        usedAt: null,
      },
      data: { usedAt: expect.any(Date) },
    });
    expect(mocks.deleteSessions).toHaveBeenCalledWith({
      where: {
        userId: "user-1",
        NOT: { sessionToken: "session-1" },
      },
    });
    expect(mocks.createAudit).toHaveBeenCalledWith({
      data: {
        userId: "user-1",
        userEmailSnapshot: "doctor@synthetic.invalid",
        action: "PASSWORD_CHANGED",
        targetId: "user-1",
        targetType: "User",
        metadata: { keptCurrentSession: true },
        success: true,
        practiceId: "practice-1",
        timestamp: expect.any(Date),
      },
    });
  });

  it("fails the credential transaction when its audit receipt cannot commit", async () => {
    mocks.createAudit.mockRejectedValueOnce(
      new Error("synthetic audit outage"),
    );

    const response = await POST(request(), { params: Promise.resolve({}) });

    expect(response.status).toBe(500);
    expect(mocks.transaction).toHaveBeenCalledTimes(1);
    expect(mocks.createAudit).toHaveBeenCalledTimes(1);
    expect(mocks.logInfo).not.toHaveBeenCalled();
  });

  it("returns a stale-authority conflict without updating the password", async () => {
    mocks.lockAuthority.mockRejectedValueOnce(
      new AccountMutationAuthorityError(),
    );

    const response = await POST(request(), { params: Promise.resolve({}) });

    expect(response.status).toBe(409);
    await expect(response.json()).resolves.toMatchObject({
      code: "ACCOUNT_AUTHORITY_CHANGED",
    });
    expect(mocks.updateUser).not.toHaveBeenCalled();
    expect(mocks.invalidateTokens).not.toHaveBeenCalled();
    expect(mocks.deleteSessions).not.toHaveBeenCalled();
  });

  it("requires an exact raw UserSession claim before reading the account", async () => {
    mocks.auth.mockResolvedValueOnce({
      user: { id: "user-1", practiceId: "practice-1" },
    });

    const response = await POST(request(), { params: Promise.resolve({}) });

    expect(response.status).toBe(401);
    expect(mocks.findUser).not.toHaveBeenCalled();
    expect(mocks.transaction).not.toHaveBeenCalled();
  });
});
