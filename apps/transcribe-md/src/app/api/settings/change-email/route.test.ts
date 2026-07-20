import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { beforeEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";

const mocks = vi.hoisted(() => ({
  auth: vi.fn(),
  deliveryEnabled: vi.fn(),
  findCurrentUser: vi.fn(),
  transaction: vi.fn(),
  comparePassword: vi.fn(),
  sharedRateLimit: vi.fn(),
  lockAuthority: vi.fn(),
  enqueueChange: vi.fn(),
  createToken: vi.fn(),
  sendEmail: vi.fn(),
  createAudit: vi.fn(),
  logInfo: vi.fn(),
}));

vi.mock("@meddoc/db", () => ({
  default: {
    user: { findUnique: mocks.findCurrentUser },
    $transaction: mocks.transaction,
  },
}));
vi.mock("bcryptjs", () => ({
  default: { compare: mocks.comparePassword },
}));
vi.mock("@/lib/nextauth", () => ({ auth: mocks.auth }));
vi.mock("@/lib/email-enabled", () => ({
  isEmailDeliveryEnabled: mocks.deliveryEnabled,
}));
vi.mock("@/lib/account-mutation-authority", () => {
  class AccountMutationAuthorityError extends Error {}
  return {
    AccountMutationAuthorityError,
    lockCurrentAccountMutationAuthority: mocks.lockAuthority,
  };
});
vi.mock("@/lib/auth-email-outbox", () => ({
  enqueueAuthEmailChangeRequestInTransaction: mocks.enqueueChange,
}));
// These legacy collaborators are deliberately absent from the route. Keeping
// explicit mocks makes any future synchronous token/provider regression
// observable in the behavioral assertions below.
vi.mock("@/lib/auth-tokens", () => ({
  createAuthTokenInTransaction: mocks.createToken,
}));
vi.mock("@/lib/email", () => ({
  sendEmailChangeRequestEmail: mocks.sendEmail,
}));
vi.mock("@/lib/rate-limit", () => ({
  RATE_LIMITS: { SETTINGS: {} },
  sharedRateLimitOr429: mocks.sharedRateLimit,
}));
vi.mock("@/lib/log", () => ({ log: { info: mocks.logInfo } }));

import { AccountMutationAuthorityError } from "@/lib/account-mutation-authority";
import { POST } from "./route";

function request(): NextRequest {
  return new NextRequest("https://app.quillmd.com/api/settings/change-email", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      newEmail: "new@synthetic.invalid",
      password: "CurrentPass8",
    }),
  });
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
  mocks.deliveryEnabled.mockReturnValue(true);
  mocks.findCurrentUser.mockResolvedValue({
    id: "user-1",
    email: "old@synthetic.invalid",
    name: "Synthetic Doctor",
    practiceId: "practice-1",
    passwordHash: "current-hash",
  });
  mocks.comparePassword.mockResolvedValue(true);
  mocks.sharedRateLimit.mockResolvedValue(null);
  mocks.lockAuthority.mockResolvedValue({
    user: {
      id: "user-1",
      email: "old@synthetic.invalid",
      name: "Synthetic Doctor",
      practiceId: "practice-1",
      passwordHash: "current-hash",
    },
  });
  mocks.enqueueChange.mockResolvedValue(undefined);
  mocks.createAudit.mockResolvedValue({ id: "audit-row" });
  mocks.transaction.mockImplementation(
    async (callback: (tx: unknown) => Promise<unknown>) =>
      callback({ auditLog: { create: mocks.createAudit } }),
  );
});

describe("change-email durable authority boundary", () => {
  it("fails closed before credential or enqueue work when the shared limiter is unavailable", async () => {
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
    expect(mocks.deliveryEnabled).not.toHaveBeenCalled();
    expect(mocks.findCurrentUser).not.toHaveBeenCalled();
    expect(mocks.comparePassword).not.toHaveBeenCalled();
    expect(mocks.transaction).not.toHaveBeenCalled();
    expect(mocks.lockAuthority).not.toHaveBeenCalled();
    expect(mocks.enqueueChange).not.toHaveBeenCalled();
    expect(mocks.createAudit).not.toHaveBeenCalled();
    expect(mocks.createToken).not.toHaveBeenCalled();
    expect(mocks.sendEmail).not.toHaveBeenCalled();
  });

  it("enqueues under exact current session, practice, password, and email authority", async () => {
    const response = await POST(request(), { params: Promise.resolve({}) });

    expect(response.status).toBe(200);
    expect(mocks.lockAuthority).toHaveBeenCalledWith(expect.anything(), {
      userId: "user-1",
      sessionId: "session-1",
      expectedPracticeId: "practice-1",
      expectedPasswordHash: "current-hash",
      expectedEmail: "old@synthetic.invalid",
      surface: "physician",
    });
    const tx = mocks.lockAuthority.mock.calls[0]?.[0];
    expect(mocks.enqueueChange).toHaveBeenCalledWith(tx, {
      userId: "user-1",
      expectedCurrentEmail: "old@synthetic.invalid",
      requestedNewEmail: "new@synthetic.invalid",
      expectedPracticeId: "practice-1",
      expectedSessionToken: "session-1",
      expectedPasswordHash: "current-hash",
    });
    expect(mocks.createAudit).toHaveBeenCalledWith({
      data: {
        userId: "user-1",
        userEmailSnapshot: "old@synthetic.invalid",
        action: "EMAIL_CHANGE_REQUESTED",
        targetId: "user-1",
        targetType: "User",
        metadata: { newEmailDomain: "synthetic.invalid" },
        success: true,
        practiceId: "practice-1",
        timestamp: expect.any(Date),
      },
    });
    expect(mocks.createToken).not.toHaveBeenCalled();
    expect(mocks.sendEmail).not.toHaveBeenCalled();
  });

  it("returns 503 before account reads or enqueue when delivery is unavailable", async () => {
    mocks.deliveryEnabled.mockReturnValueOnce(false);

    const response = await POST(request(), { params: Promise.resolve({}) });

    expect(response.status).toBe(503);
    await expect(response.json()).resolves.toMatchObject({
      code: "EMAIL_DELIVERY_UNAVAILABLE",
    });
    expect(mocks.findCurrentUser).not.toHaveBeenCalled();
    expect(mocks.transaction).not.toHaveBeenCalled();
    expect(mocks.enqueueChange).not.toHaveBeenCalled();
    expect(mocks.createToken).not.toHaveBeenCalled();
    expect(mocks.sendEmail).not.toHaveBeenCalled();
  });

  it("returns a stale-authority conflict without enqueueing", async () => {
    mocks.lockAuthority.mockRejectedValueOnce(
      new AccountMutationAuthorityError(),
    );

    const response = await POST(request(), { params: Promise.resolve({}) });

    expect(response.status).toBe(409);
    expect(mocks.enqueueChange).not.toHaveBeenCalled();
    expect(mocks.createAudit).not.toHaveBeenCalled();
    expect(mocks.createToken).not.toHaveBeenCalled();
    expect(mocks.sendEmail).not.toHaveBeenCalled();
  });

  it("fails closed when the durable request cannot be accepted", async () => {
    mocks.enqueueChange.mockRejectedValueOnce(
      new Error("synthetic durable enqueue outage"),
    );

    const response = await POST(request(), { params: Promise.resolve({}) });

    expect(response.status).toBe(500);
    expect(mocks.transaction).toHaveBeenCalledTimes(1);
    expect(mocks.createAudit).not.toHaveBeenCalled();
    expect(mocks.logInfo).not.toHaveBeenCalled();
    expect(mocks.createToken).not.toHaveBeenCalled();
    expect(mocks.sendEmail).not.toHaveBeenCalled();
  });

  it("fails the durable transaction when its audit receipt cannot commit", async () => {
    mocks.createAudit.mockRejectedValueOnce(
      new Error("synthetic audit outage"),
    );

    const response = await POST(request(), { params: Promise.resolve({}) });

    expect(response.status).toBe(500);
    expect(mocks.enqueueChange).toHaveBeenCalledTimes(1);
    expect(mocks.createAudit).toHaveBeenCalledTimes(1);
    expect(mocks.logInfo).not.toHaveBeenCalled();
    expect(mocks.createToken).not.toHaveBeenCalled();
    expect(mocks.sendEmail).not.toHaveBeenCalled();
  });

  it("has no synchronous token mint or provider-send path", () => {
    const source = readFileSync(resolve(__dirname, "route.ts"), "utf8");
    expect(source).toContain("enqueueAuthEmailChangeRequestInTransaction");
    expect(source).not.toMatch(/createAuthToken|sendEmailChangeRequestEmail/);
  });
});
