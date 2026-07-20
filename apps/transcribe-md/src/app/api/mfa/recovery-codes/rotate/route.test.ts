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
  generateCodes: vi.fn(),
  hashCodes: vi.fn(),
  logAudit: vi.fn(),
  appendAudit: vi.fn(),
}));

vi.mock("@meddoc/db", () => ({
  default: {
    user: { findUnique: mocks.findUser, update: mocks.updateUser },
    userSession: { deleteMany: mocks.deleteSessions },
    $transaction: mocks.transaction,
  },
}));
vi.mock("bcryptjs", () => ({ default: { compare: mocks.comparePassword } }));
vi.mock("@/lib/account-mutation-authority", async (importOriginal) => {
  const actual =
    await importOriginal<typeof import("@/lib/account-mutation-authority")>();
  return {
    ...actual,
    lockCurrentAccountMutationAuthority: mocks.lockAuthority,
  };
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

const VERIFIED_AT = new Date("2026-07-20T08:00:00.000Z");
const PLAINTEXT_CODES = [
  "ABCD-EFGH-JKLM-NPQR-STUV-WXYZ-2345",
  "BCDE-FGHJ-KLMN-PQRS-TUVW-XYZ2-3456",
];
const HASHED_CODES = PLAINTEXT_CODES.map(
  (_, index) =>
    `qmfa-recovery:v2:sha256:${String(index + 1).padStart(64, "0")}`,
);

function request(host = "app.quillmd.com"): NextRequest {
  return new NextRequest(`https://${host}/api/mfa/recovery-codes/rotate`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      password: "synthetic-password",
      token: "123456",
    }),
  });
}

function enrolledUser() {
  return {
    id: "doctor_synthetic",
    email: "doctor@synthetic.invalid",
    practiceId: "practice_synthetic",
    passwordHash: "synthetic-password-hash",
    mfaEnabled: true,
    mfaSecret: "qmfa:v1:synthetic-envelope",
    mfaVerifiedAt: VERIFIED_AT,
    mfaBackupCodes: ["legacy-unversioned-verifier"],
  };
}

beforeEach(() => {
  vi.clearAllMocks();
  const user = enrolledUser();
  mocks.resolveActor.mockResolvedValue({
    userId: user.id,
    sessionId: "session_synthetic",
    practiceId: user.practiceId,
    isAdminHost: false,
    isPlatformAdmin: false,
  });
  mocks.findUser.mockResolvedValue(user);
  mocks.comparePassword.mockResolvedValue(true);
  mocks.verifyTotp.mockReturnValue(true);
  mocks.generateCodes.mockReturnValue(PLAINTEXT_CODES);
  mocks.hashCodes.mockReturnValue(HASHED_CODES);
  mocks.updateUser.mockResolvedValue({});
  mocks.deleteSessions.mockResolvedValue({ count: 2 });
  mocks.lockAuthority.mockResolvedValue({ user });
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

describe("MFA recovery-code rotation authority", () => {
  it("replaces every verifier for the exact physician and keeps only the current session", async () => {
    const response = await POST(request(), { params: Promise.resolve({}) });

    expect(response.status).toBe(200);
    await expect(response.json()).resolves.toEqual({
      ok: true,
      recoveryCodes: PLAINTEXT_CODES,
    });
    expect(mocks.comparePassword).toHaveBeenCalledWith(
      "synthetic-password",
      "synthetic-password-hash",
    );
    expect(mocks.verifyTotp).toHaveBeenCalledWith(
      "doctor_synthetic",
      "qmfa:v1:synthetic-envelope",
      "123456",
    );
    expect(mocks.lockAuthority).toHaveBeenCalledWith(expect.anything(), {
      userId: "doctor_synthetic",
      sessionId: "session_synthetic",
      expectedPracticeId: "practice_synthetic",
      expectedPasswordHash: "synthetic-password-hash",
      expectedEmail: "doctor@synthetic.invalid",
      surface: "physician",
    });
    expect(mocks.updateUser).toHaveBeenCalledWith({
      where: { id: "doctor_synthetic" },
      data: { mfaBackupCodes: HASHED_CODES },
    });
    expect(mocks.deleteSessions).toHaveBeenCalledWith({
      where: {
        userId: "doctor_synthetic",
        NOT: { sessionToken: "session_synthetic" },
      },
    });
    expect(mocks.appendAudit).toHaveBeenCalledWith(expect.anything(), {
      action: "MFA_RECOVERY_CODES_ROTATED",
      userId: "doctor_synthetic",
      userEmail: "doctor@synthetic.invalid",
      practiceId: "practice_synthetic",
      metadata: {
        recoveryCodesIssued: 10,
        keptCurrentSession: true,
        authorizationMethod: "password_and_totp",
      },
    });
  });

  it("uses platform-admin authority for an enrolled admin-surface actor", async () => {
    const user = {
      ...enrolledUser(),
      id: "platform_admin_synthetic",
      email: "admin@synthetic.invalid",
    };
    mocks.resolveActor.mockResolvedValueOnce({
      userId: user.id,
      sessionId: "admin_session_synthetic",
      practiceId: user.practiceId,
      isAdminHost: true,
      isPlatformAdmin: true,
    });
    mocks.findUser.mockResolvedValueOnce(user);
    mocks.lockAuthority.mockResolvedValueOnce({ user });

    const response = await POST(request("admin.quillmd.com"), {
      params: Promise.resolve({}),
    });

    expect(response.status).toBe(200);
    expect(mocks.lockAuthority).toHaveBeenCalledWith(
      expect.anything(),
      expect.objectContaining({
        userId: "platform_admin_synthetic",
        sessionId: "admin_session_synthetic",
        surface: "platform-admin",
      }),
    );
  });

  it("preserves physician authority for a dual-entitled doctor on the physician host", async () => {
    const user = {
      ...enrolledUser(),
      role: "DOCTOR",
      products: ["TRANSCRIBE_MD", "SUPER_ADMIN"],
    };
    mocks.findUser.mockResolvedValueOnce(user);
    mocks.lockAuthority.mockResolvedValueOnce({ user });

    const response = await POST(request("app.quillmd.com"), {
      params: Promise.resolve({}),
    });

    expect(response.status).toBe(200);
    expect(mocks.lockAuthority).toHaveBeenCalledWith(
      expect.anything(),
      expect.objectContaining({
        userId: "doctor_synthetic",
        surface: "physician",
      }),
    );
  });

  it("rejects a sessionless claim before reading or generating credentials", async () => {
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
    expect(mocks.generateCodes).not.toHaveBeenCalled();
    expect(mocks.transaction).not.toHaveBeenCalled();
  });

  it("fails closed for plaintext, wrong-user, or tampered stored secret states", async () => {
    mocks.findUser.mockResolvedValueOnce({
      ...enrolledUser(),
      mfaSecret: "plaintext-or-tampered-secret",
    });
    mocks.verifyTotp.mockReturnValueOnce(false);

    const response = await POST(request(), { params: Promise.resolve({}) });

    expect(response.status).toBe(400);
    await expect(response.json()).resolves.toMatchObject({
      code: "INVALID_TOKEN",
    });
    expect(mocks.verifyTotp).toHaveBeenCalledWith(
      "doctor_synthetic",
      "plaintext-or-tampered-secret",
      "123456",
    );
    expect(mocks.generateCodes).not.toHaveBeenCalled();
    expect(mocks.transaction).not.toHaveBeenCalled();
  });

  it("returns no codes when exact MFA state changes under the account lock", async () => {
    mocks.lockAuthority.mockResolvedValueOnce({
      user: {
        ...enrolledUser(),
        mfaSecret: "qmfa:v1:concurrent-replacement",
      },
    });

    const response = await POST(request(), { params: Promise.resolve({}) });
    const body = await response.json();

    expect(response.status).toBe(409);
    expect(body).toMatchObject({ code: "MFA_STATE_CHANGED" });
    expect(body).not.toHaveProperty("recoveryCodes");
    expect(mocks.updateUser).not.toHaveBeenCalled();
    expect(mocks.deleteSessions).not.toHaveBeenCalled();
    expect(mocks.appendAudit).not.toHaveBeenCalled();
  });

  it("returns no codes when the immutable audit receipt cannot commit", async () => {
    mocks.appendAudit.mockRejectedValueOnce(
      new Error("synthetic audit outage"),
    );

    const response = await POST(request(), { params: Promise.resolve({}) });
    const body = await response.json();

    expect(response.status).toBe(500);
    expect(body).not.toHaveProperty("recoveryCodes");
    expect(mocks.appendAudit).toHaveBeenCalledTimes(1);
  });
});
