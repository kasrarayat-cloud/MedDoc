import { beforeEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";

const mocks = vi.hoisted(() => ({
  resolveActor: vi.fn(),
  findUser: vi.fn(),
  updateUser: vi.fn(),
  deleteSessions: vi.fn(),
  transaction: vi.fn(),
  comparePassword: vi.fn(),
  lockAuthority: vi.fn(),
  generateEnrollment: vi.fn(),
  encryptSecret: vi.fn(),
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
vi.mock("bcryptjs", () => ({
  default: { compare: mocks.comparePassword },
}));
vi.mock("@/lib/account-mutation-authority", async (importOriginal) => {
  const actual =
    (await importOriginal()) as typeof import("@/lib/account-mutation-authority");
  return {
    ...actual,
    lockCurrentAccountMutationAuthority: mocks.lockAuthority,
  };
});
vi.mock("@/lib/mfa-request-actor", () => ({
  resolveMfaRequestActor: mocks.resolveActor,
}));
vi.mock("@/lib/mfa", () => ({
  generateMfaEnrollment: mocks.generateEnrollment,
}));
vi.mock("@/lib/mfa-secret-envelope", () => ({
  encryptMfaSecretForUser: mocks.encryptSecret,
}));
vi.mock("@/lib/audit", () => ({
  logAudit: mocks.logAudit,
  appendAuthMutationAuditInTransaction: mocks.appendAudit,
}));

import { POST } from "./route";

function request(host = "app.quillmd.com"): NextRequest {
  return new NextRequest(`https://${host}/api/mfa/enroll`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ password: "SyntheticPass123" }),
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
    passwordHash: "synthetic-password-hash",
    mfaEnabled: true,
    mfaSecret: "synthetic-existing-secret",
    mfaVerifiedAt: new Date("2026-07-20T08:00:00.000Z"),
    mfaBackupCodes: ["synthetic-existing-code"],
  });
  mocks.generateEnrollment.mockResolvedValue({
    secret: "synthetic-secret",
    otpauthUri: "otpauth://synthetic.invalid",
    qrPngDataUrl: "data:image/png;base64,c3ludGhldGlj",
  });
  mocks.encryptSecret.mockReturnValue(
    "qmfa:v1:synthetic-key:synthetic-encrypted-envelope",
  );
  mocks.updateUser.mockResolvedValue({});
  mocks.deleteSessions.mockResolvedValue({ count: 0 });
  mocks.comparePassword.mockResolvedValue(true);
  mocks.lockAuthority.mockResolvedValue({
    user: {
      id: "platform_admin_synthetic",
      email: "admin@synthetic.invalid",
      practiceId: "practice_synthetic",
      mfaEnabled: false,
      mfaSecret: null,
      mfaVerifiedAt: null,
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

describe("MFA enrollment authorization boundary", () => {
  it("rejects a sessionless claim before reading or generating a factor", async () => {
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
    expect(mocks.generateEnrollment).not.toHaveBeenCalled();
    expect(mocks.transaction).not.toHaveBeenCalled();
  });

  it("does not rotate an enrolled Product.SUPER_ADMIN factor from the physician host", async () => {
    const response = await POST(request(), { params: Promise.resolve({}) });
    expect(response.status).toBe(409);
    await expect(response.json()).resolves.toMatchObject({
      code: "MFA_ALREADY_ENABLED",
    });
    expect(mocks.generateEnrollment).not.toHaveBeenCalled();
    expect(mocks.updateUser).not.toHaveBeenCalled();
  });

  it("allows a fresh platform administrator to begin first enrollment", async () => {
    mocks.findUser.mockResolvedValueOnce({
      id: "platform_admin_synthetic",
      email: "admin@synthetic.invalid",
      practiceId: "practice_synthetic",
      passwordHash: "synthetic-password-hash",
      mfaEnabled: false,
      mfaSecret: null,
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
    expect(mocks.updateUser).toHaveBeenCalledTimes(1);
    expect(mocks.encryptSecret).toHaveBeenCalledWith({
      userId: "platform_admin_synthetic",
      plaintextSecret: "synthetic-secret",
    });
    expect(mocks.updateUser).toHaveBeenCalledWith({
      where: { id: "platform_admin_synthetic" },
      data: {
        mfaEnabled: false,
        mfaSecret: "qmfa:v1:synthetic-key:synthetic-encrypted-envelope",
        mfaVerifiedAt: null,
        mfaBackupCodes: [],
      },
    });
    expect(JSON.stringify(mocks.updateUser.mock.calls)).not.toContain(
      '"synthetic-secret"',
    );
    expect(mocks.lockAuthority).toHaveBeenCalledWith(
      expect.anything(),
      expect.objectContaining({
        sessionId: "session_synthetic",
        expectedPasswordHash: "synthetic-password-hash",
        surface: "platform-admin",
      }),
    );
    expect(mocks.deleteSessions).toHaveBeenCalledWith({
      where: {
        userId: "platform_admin_synthetic",
        NOT: { sessionToken: "session_synthetic" },
      },
    });
    expect(mocks.appendAudit).toHaveBeenCalledWith(expect.anything(), {
      action: "MFA_ENROLLMENT_STARTED",
      userId: "platform_admin_synthetic",
      userEmail: "admin@synthetic.invalid",
      practiceId: "practice_synthetic",
      metadata: { stage: "enrollment_started" },
    });
  });

  it("requires password reauthentication before generating a secret", async () => {
    const missingPassword = new NextRequest(
      "https://app.quillmd.com/api/mfa/enroll",
      {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({}),
      },
    );
    const response = await POST(missingPassword, {
      params: Promise.resolve({}),
    });
    expect(response.status).toBe(400);
    expect(mocks.findUser).not.toHaveBeenCalled();
    expect(mocks.generateEnrollment).not.toHaveBeenCalled();
    expect(mocks.encryptSecret).not.toHaveBeenCalled();
  });

  it("does not report enrollment success when the transactional audit cannot commit", async () => {
    mocks.findUser.mockResolvedValueOnce({
      id: "platform_admin_synthetic",
      email: "admin@synthetic.invalid",
      practiceId: "practice_synthetic",
      passwordHash: "synthetic-password-hash",
      mfaEnabled: false,
      mfaSecret: null,
      mfaVerifiedAt: null,
      mfaBackupCodes: [],
    });
    mocks.appendAudit.mockRejectedValueOnce(
      new Error("synthetic audit outage"),
    );

    const response = await POST(request(), { params: Promise.resolve({}) });

    expect(response.status).toBe(500);
    expect(mocks.appendAudit).toHaveBeenCalledTimes(1);
  });
});
