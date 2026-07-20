import { beforeEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";

const mocks = vi.hoisted(() => ({
  resolveActor: vi.fn(),
  findUser: vi.fn(),
  updateUser: vi.fn(),
  deleteSessions: vi.fn(),
  transaction: vi.fn(),
  verifyTotp: vi.fn(),
  generateCodes: vi.fn(),
  hashCodes: vi.fn(),
  logAudit: vi.fn(),
  appendAudit: vi.fn(),
  lockAuthority: vi.fn(),
}));

vi.mock("@meddoc/db", () => ({
  default: {
    user: {
      findUnique: mocks.findUser,
      update: mocks.updateUser,
    },
    userSession: { deleteMany: mocks.deleteSessions },
    $transaction: mocks.transaction,
  },
}));
vi.mock("@/lib/account-mutation-authority", async (importOriginal) => {
  const actual =
    await importOriginal<typeof import("@/lib/account-mutation-authority")>();
  return { ...actual, lockCurrentAccountMutationAuthority: mocks.lockAuthority };
});
vi.mock("@/lib/mfa-request-actor", () => ({
  resolveMfaRequestActor: mocks.resolveActor,
}));
vi.mock("@/lib/mfa", () => ({
  verifyStoredMfaTotpToken: mocks.verifyTotp,
  generateRecoveryCodes: mocks.generateCodes,
  hashRecoveryCodes: mocks.hashCodes,
}));
vi.mock("@/lib/audit", () => ({
  logAudit: mocks.logAudit,
  appendAuthMutationAuditInTransaction: mocks.appendAudit,
}));

import { POST } from "./route";

function request(host = "app.quillmd.com"): NextRequest {
  return new NextRequest(`https://${host}/api/mfa/verify-enrollment`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ token: "123456" }),
  });
}

beforeEach(() => {
  vi.clearAllMocks();
  mocks.resolveActor.mockResolvedValue({
    userId: "platform_admin_synthetic",
    sessionId: "session_synthetic",
    practiceId: "practice_synthetic",
    isAdminHost: false,
    isPlatformAdmin: false,
  });
  mocks.findUser.mockResolvedValue({
    id: "platform_admin_synthetic",
    email: "admin@synthetic.invalid",
    practiceId: "practice_synthetic",
    mfaSecret: "synthetic-secret",
    mfaEnabled: true,
    mfaVerifiedAt: new Date("2026-07-20T08:00:00.000Z"),
    mfaBackupCodes: ["synthetic-old-hash"],
  });
  mocks.verifyTotp.mockReturnValue(true);
  mocks.generateCodes.mockReturnValue(["SYNTHETIC-CODE"]);
  mocks.hashCodes.mockReturnValue(["synthetic-hash"]);
  mocks.updateUser.mockResolvedValue({});
  mocks.deleteSessions.mockResolvedValue({ count: 0 });
  mocks.transaction.mockImplementation(
    async (callback: (tx: unknown) => Promise<unknown>) =>
      callback({
        user: { update: mocks.updateUser },
        userSession: { deleteMany: mocks.deleteSessions },
      }),
  );
  mocks.lockAuthority.mockResolvedValue({
    user: {
      id: "platform_admin_synthetic",
      email: "admin@synthetic.invalid",
      practiceId: "practice_synthetic",
      mfaEnabled: false,
      mfaSecret: "synthetic-secret",
      mfaVerifiedAt: null,
      mfaBackupCodes: [],
    },
  });
  mocks.logAudit.mockResolvedValue(undefined);
  mocks.appendAudit.mockResolvedValue(undefined);
});

describe("MFA enrollment verification authorization boundary", () => {
  it("rejects a sessionless claim before reading or mutating the account", async () => {
    mocks.resolveActor.mockResolvedValueOnce({
      userId: "doctor_synthetic",
      sessionId: null,
      practiceId: "practice_synthetic",
      isAdminHost: false,
      isPlatformAdmin: false,
    });

    const response = await POST(request(), { params: Promise.resolve({}) });

    expect(response.status).toBe(401);
    expect(mocks.findUser).not.toHaveBeenCalled();
    expect(mocks.verifyTotp).not.toHaveBeenCalled();
    expect(mocks.transaction).not.toHaveBeenCalled();
  });

  it("does not reissue recovery codes for an enrolled Product.SUPER_ADMIN", async () => {
    const response = await POST(request(), { params: Promise.resolve({}) });
    expect(response.status).toBe(409);
    await expect(response.json()).resolves.toMatchObject({
      code: "MFA_ALREADY_ENABLED",
    });
    expect(mocks.verifyTotp).not.toHaveBeenCalled();
    expect(mocks.generateCodes).not.toHaveBeenCalled();
    expect(mocks.transaction).not.toHaveBeenCalled();
  });

  it("completes first enrollment from a freshly authorized admin-host session", async () => {
    mocks.findUser.mockResolvedValueOnce({
      id: "platform_admin_synthetic",
      email: "admin@synthetic.invalid",
      practiceId: "practice_synthetic",
      mfaSecret: "synthetic-secret",
      mfaEnabled: false,
      mfaVerifiedAt: null,
      mfaBackupCodes: [],
    });
    mocks.resolveActor.mockResolvedValueOnce({
      userId: "platform_admin_synthetic",
      sessionId: "session_synthetic",
      practiceId: "practice_synthetic",
      isAdminHost: true,
      isPlatformAdmin: true,
    });

    const response = await POST(request("admin.quillmd.com"), {
      params: Promise.resolve({}),
    });
    expect(response.status).toBe(200);
    await expect(response.json()).resolves.toMatchObject({ ok: true });
    expect(mocks.transaction).toHaveBeenCalledTimes(1);
    expect(mocks.verifyTotp).toHaveBeenCalledWith(
      "platform_admin_synthetic",
      "synthetic-secret",
      "123456",
    );
    expect(mocks.updateUser).toHaveBeenCalledWith({
      where: { id: "platform_admin_synthetic" },
      data: {
        mfaEnabled: true,
        mfaVerifiedAt: expect.any(Date),
        mfaBackupCodes: ["synthetic-hash"],
      },
    });
    expect(mocks.deleteSessions).toHaveBeenCalledOnce();
    expect(mocks.deleteSessions).toHaveBeenCalledWith({
      where: {
        userId: "platform_admin_synthetic",
        NOT: { sessionToken: "session_synthetic" },
      },
    });
    expect(mocks.appendAudit).toHaveBeenCalledWith(expect.anything(), {
      action: "MFA_ENABLED",
      userId: "platform_admin_synthetic",
      userEmail: "admin@synthetic.invalid",
      practiceId: "practice_synthetic",
      metadata: {
        stage: "enrollment_completed",
        recoveryCodesIssued: 10,
        keptCurrentSession: true,
      },
    });
  });

  it("fails closed when the staged ciphertext cannot be authenticated", async () => {
    mocks.findUser.mockResolvedValueOnce({
      id: "platform_admin_synthetic",
      email: "admin@synthetic.invalid",
      practiceId: "practice_synthetic",
      mfaSecret: "plaintext-or-tampered-secret",
      mfaEnabled: false,
      mfaVerifiedAt: null,
      mfaBackupCodes: [],
    });
    mocks.verifyTotp.mockReturnValueOnce(false);

    const response = await POST(request(), { params: Promise.resolve({}) });

    expect(response.status).toBe(400);
    await expect(response.json()).resolves.toMatchObject({
      code: "INVALID_TOKEN",
    });
    expect(mocks.verifyTotp).toHaveBeenCalledWith(
      "platform_admin_synthetic",
      "plaintext-or-tampered-secret",
      "123456",
    );
    expect(mocks.transaction).not.toHaveBeenCalled();
  });

  it("does not return recovery codes when the transactional audit cannot commit", async () => {
    mocks.findUser.mockResolvedValueOnce({
      id: "platform_admin_synthetic",
      email: "admin@synthetic.invalid",
      practiceId: "practice_synthetic",
      mfaSecret: "synthetic-secret",
      mfaEnabled: false,
      mfaVerifiedAt: null,
      mfaBackupCodes: [],
    });
    mocks.appendAudit.mockRejectedValueOnce(new Error("synthetic audit outage"));

    const response = await POST(request(), { params: Promise.resolve({}) });

    expect(response.status).toBe(500);
    const body = await response.json();
    expect(body).not.toHaveProperty("recoveryCodes");
    expect(mocks.appendAudit).toHaveBeenCalledTimes(1);
  });

  it("fails closed when concurrent enrollment replaces the verified staged secret", async () => {
    mocks.findUser.mockResolvedValueOnce({
      id: "platform_admin_synthetic",
      email: "admin@synthetic.invalid",
      practiceId: "practice_synthetic",
      mfaSecret: "synthetic-secret",
      mfaEnabled: false,
      mfaVerifiedAt: null,
      mfaBackupCodes: [],
    });
    mocks.resolveActor.mockResolvedValueOnce({
      userId: "platform_admin_synthetic",
      sessionId: "session_synthetic",
      practiceId: "practice_synthetic",
      isAdminHost: true,
      isPlatformAdmin: true,
    });
    mocks.lockAuthority.mockResolvedValueOnce({
      user: {
        mfaEnabled: false,
        mfaSecret: "synthetic-concurrent-replacement",
        mfaVerifiedAt: null,
        mfaBackupCodes: [],
      },
    });

    const response = await POST(request("admin.quillmd.com"), {
      params: Promise.resolve({}),
    });

    expect(response.status).toBe(409);
    const body = await response.json();
    expect(body).toMatchObject({
      code: "MFA_ENROLLMENT_STATE_CHANGED",
    });
    expect(body).not.toHaveProperty("recoveryCodes");
    expect(mocks.deleteSessions).not.toHaveBeenCalled();
    expect(mocks.logAudit).not.toHaveBeenCalledWith(
      expect.objectContaining({ action: "MFA_ENABLED", success: true }),
    );
  });

  it("rejects an ordinary user's attempted enabled-factor rotation", async () => {
    mocks.findUser.mockResolvedValueOnce({
      id: "doctor_synthetic",
      email: "doctor@synthetic.invalid",
      practiceId: "practice_synthetic",
      mfaSecret: "synthetic-rotated-secret",
      mfaEnabled: true,
      mfaVerifiedAt: null,
      mfaBackupCodes: [],
    });
    mocks.resolveActor.mockResolvedValueOnce({
      userId: "doctor_synthetic",
      sessionId: "session_synthetic",
      practiceId: "practice_synthetic",
      isAdminHost: false,
      isPlatformAdmin: false,
    });

    const response = await POST(request(), { params: Promise.resolve({}) });

    expect(response.status).toBe(409);
    await expect(response.json()).resolves.toMatchObject({
      code: "MFA_ALREADY_ENABLED",
    });
    expect(mocks.updateUser).not.toHaveBeenCalled();
  });
});
