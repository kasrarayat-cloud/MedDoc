import { beforeEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";

const mocks = vi.hoisted(() => ({
  resolveActor: vi.fn(),
  findUser: vi.fn(),
  updateUser: vi.fn(),
  comparePassword: vi.fn(),
  verifyTotp: vi.fn(),
  findRecovery: vi.fn(),
  logAudit: vi.fn(),
}));

vi.mock("@meddoc/db", () => ({
  default: {
    user: {
      findUnique: mocks.findUser,
      update: mocks.updateUser,
    },
  },
}));
vi.mock("bcryptjs", () => ({ default: { compare: mocks.comparePassword } }));
vi.mock("@/lib/mfa-request-actor", () => ({
  resolveMfaRequestActor: mocks.resolveActor,
}));
vi.mock("@/lib/mfa", () => ({
  verifyTotpToken: mocks.verifyTotp,
  findMatchingRecoveryHash: mocks.findRecovery,
}));
vi.mock("@/lib/audit", () => ({ logAudit: mocks.logAudit }));

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
    mfaBackupCodes: [],
  });
  mocks.comparePassword.mockResolvedValue(true);
  mocks.verifyTotp.mockReturnValue(true);
  mocks.updateUser.mockResolvedValue({});
  mocks.logAudit.mockResolvedValue(undefined);
});

describe("MFA disable boundary", () => {
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
      isAdminHost: true,
      isPlatformAdmin: true,
    });
    const response = await POST(request(), { params: Promise.resolve({}) });
    expect(response.status).toBe(404);
    expect(mocks.findUser).not.toHaveBeenCalled();
    expect(mocks.updateUser).not.toHaveBeenCalled();
  });
});
