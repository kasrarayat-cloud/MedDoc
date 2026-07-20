import { beforeEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";

const mocks = vi.hoisted(() => ({
  resolveActor: vi.fn(),
  findUser: vi.fn(),
  updateUser: vi.fn(),
  deleteSessions: vi.fn(),
  transaction: vi.fn(),
  lockAuthority: vi.fn(),
  comparePassword: vi.fn(),
  verifyTotp: vi.fn(),
  findRecovery: vi.fn(),
  logAudit: vi.fn(),
  appendAudit: vi.fn(),
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
vi.mock("bcryptjs", () => ({ default: { compare: mocks.comparePassword } }));
vi.mock("@/lib/mfa-request-actor", () => ({
  resolveMfaRequestActor: mocks.resolveActor,
}));
vi.mock("@/lib/mfa", () => ({
  verifyStoredMfaTotpToken: mocks.verifyTotp,
  findMatchingRecoveryHash: mocks.findRecovery,
}));
vi.mock("@/lib/audit", () => ({
  logAudit: mocks.logAudit,
  appendAuthMutationAuditInTransaction: mocks.appendAudit,
}));

import { POST } from "./route";

function request(): NextRequest {
  return new NextRequest("https://app.quillmd.com/api/mfa/disable", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ password: "synthetic-password", token: "123456" }),
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
    role: "DOCTOR",
    products: ["TRANSCRIBE_MD", "SUPER_ADMIN"],
    practiceId: "practice_synthetic",
    passwordHash: "synthetic-hash",
    mfaEnabled: true,
    mfaSecret: "synthetic-secret",
    mfaVerifiedAt: new Date("2026-07-20T08:00:00.000Z"),
    mfaBackupCodes: [],
  });
  mocks.comparePassword.mockResolvedValue(true);
  mocks.verifyTotp.mockReturnValue(true);
  mocks.updateUser.mockResolvedValue({});
  mocks.deleteSessions.mockResolvedValue({ count: 0 });
  mocks.lockAuthority.mockResolvedValue({
    user: {
      id: "doctor_synthetic",
      email: "doctor@synthetic.invalid",
      practiceId: "practice_synthetic",
      role: "DOCTOR",
      products: ["TRANSCRIBE_MD"],
      mfaEnabled: true,
      mfaSecret: "synthetic-secret",
      mfaVerifiedAt: new Date("2026-07-20T08:00:00.000Z"),
      mfaBackupCodes: [],
    },
  });
  mocks.transaction.mockImplementation(
    async (callback: (tx: unknown) => Promise<unknown>) =>
      callback({
        user: { update: mocks.updateUser },
        userSession: { deleteMany: mocks.deleteSessions },
      }),
  );
  mocks.logAudit.mockResolvedValue(undefined);
  mocks.appendAudit.mockResolvedValue(undefined);
});

describe("MFA disable boundary", () => {
  it("rejects a sessionless claim before reading or challenging the account", async () => {
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
    expect(mocks.comparePassword).not.toHaveBeenCalled();
    expect(mocks.transaction).not.toHaveBeenCalled();
  });

  it("blocks Product.SUPER_ADMIN even when the UserRole is DOCTOR", async () => {
    const response = await POST(request(), { params: Promise.resolve({}) });
    expect(response.status).toBe(403);
    await expect(response.json()).resolves.toMatchObject({
      code: "PLATFORM_ADMIN_MFA_REQUIRED",
    });
    expect(mocks.comparePassword).not.toHaveBeenCalled();
    expect(mocks.updateUser).not.toHaveBeenCalled();
  });

  it("never exposes the disable operation on the admin host", async () => {
    mocks.resolveActor.mockResolvedValueOnce({
      userId: "platform_admin_synthetic",
      sessionId: "session_synthetic",
      practiceId: "practice_synthetic",
      isAdminHost: true,
      isPlatformAdmin: true,
    });
    const response = await POST(request(), { params: Promise.resolve({}) });
    expect(response.status).toBe(404);
    expect(mocks.findUser).not.toHaveBeenCalled();
    expect(mocks.updateUser).not.toHaveBeenCalled();
  });

  it("clears only the exact current ordinary physician factor", async () => {
    mocks.findUser.mockResolvedValueOnce({
      id: "doctor_synthetic",
      email: "doctor@synthetic.invalid",
      role: "DOCTOR",
      products: ["TRANSCRIBE_MD"],
      practiceId: "practice_synthetic",
      passwordHash: "synthetic-hash",
      mfaEnabled: true,
      mfaSecret: "synthetic-secret",
      mfaVerifiedAt: new Date("2026-07-20T08:00:00.000Z"),
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
    expect(response.status).toBe(200);
    expect(mocks.verifyTotp).toHaveBeenCalledWith(
      "doctor_synthetic",
      "synthetic-secret",
      "123456",
    );
    expect(mocks.lockAuthority).toHaveBeenCalledWith(
      expect.anything(),
      expect.objectContaining({
        sessionId: "session_synthetic",
        expectedPasswordHash: "synthetic-hash",
      }),
    );
    expect(mocks.updateUser).toHaveBeenCalledWith({
      where: { id: "doctor_synthetic" },
      data: {
        mfaEnabled: false,
        mfaSecret: null,
        mfaVerifiedAt: null,
        mfaBackupCodes: [],
      },
    });
    expect(mocks.appendAudit).toHaveBeenCalledWith(expect.anything(), {
      action: "MFA_DISABLED",
      userId: "doctor_synthetic",
      userEmail: "doctor@synthetic.invalid",
      practiceId: "practice_synthetic",
      metadata: { method: "totp" },
    });
  });

  it("fails closed when the stored ciphertext cannot authenticate", async () => {
    mocks.findUser.mockResolvedValueOnce({
      id: "doctor_synthetic",
      email: "doctor@synthetic.invalid",
      role: "DOCTOR",
      products: ["TRANSCRIBE_MD"],
      practiceId: "practice_synthetic",
      passwordHash: "synthetic-hash",
      mfaEnabled: true,
      mfaSecret: "plaintext-or-tampered-secret",
      mfaVerifiedAt: new Date("2026-07-20T08:00:00.000Z"),
      mfaBackupCodes: [],
    });
    mocks.verifyTotp.mockReturnValueOnce(false);

    const response = await POST(request(), { params: Promise.resolve({}) });

    expect(response.status).toBe(400);
    await expect(response.json()).resolves.toMatchObject({
      code: "INVALID_SECOND_FACTOR",
    });
    expect(mocks.transaction).not.toHaveBeenCalled();
  });

  it("does not report factor removal when the transactional audit cannot commit", async () => {
    mocks.findUser.mockResolvedValueOnce({
      id: "doctor_synthetic",
      email: "doctor@synthetic.invalid",
      role: "DOCTOR",
      products: ["TRANSCRIBE_MD"],
      practiceId: "practice_synthetic",
      passwordHash: "synthetic-hash",
      mfaEnabled: true,
      mfaSecret: "synthetic-secret",
      mfaVerifiedAt: new Date("2026-07-20T08:00:00.000Z"),
      mfaBackupCodes: [],
    });
    mocks.appendAudit.mockRejectedValueOnce(new Error("synthetic audit outage"));

    const response = await POST(request(), { params: Promise.resolve({}) });

    expect(response.status).toBe(500);
    expect(mocks.appendAudit).toHaveBeenCalledTimes(1);
  });
});
