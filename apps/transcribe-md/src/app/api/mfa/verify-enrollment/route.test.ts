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
vi.mock("@/lib/mfa-request-actor", () => ({
  resolveMfaRequestActor: mocks.resolveActor,
}));
vi.mock("@/lib/mfa", () => ({
  verifyTotpToken: mocks.verifyTotp,
  generateRecoveryCodes: mocks.generateCodes,
  hashRecoveryCodes: mocks.hashCodes,
}));
vi.mock("@/lib/audit", () => ({ logAudit: mocks.logAudit }));

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
    isAdminHost: false,
    isPlatformAdmin: false,
  });
  mocks.findUser.mockResolvedValue({
    id: "platform_admin_synthetic",
    email: "admin@synthetic.invalid",
    practiceId: "practice_synthetic",
    mfaSecret: "synthetic-secret",
    mfaEnabled: true,
    products: ["TRANSCRIBE_MD", "SUPER_ADMIN"],
  });
  mocks.verifyTotp.mockReturnValue(true);
  mocks.generateCodes.mockReturnValue(["SYNTHETIC-CODE"]);
  mocks.hashCodes.mockReturnValue(["synthetic-hash"]);
  mocks.updateUser.mockReturnValue(Promise.resolve({}));
  mocks.deleteSessions.mockReturnValue(Promise.resolve({ count: 0 }));
  mocks.transaction.mockResolvedValue([]);
  mocks.logAudit.mockResolvedValue(undefined);
});

describe("MFA enrollment verification authorization boundary", () => {
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
      products: ["SUPER_ADMIN"],
    });
    mocks.resolveActor.mockResolvedValueOnce({
      userId: "platform_admin_synthetic",
      sessionId: "session_synthetic",
      isAdminHost: true,
      isPlatformAdmin: true,
    });

    const response = await POST(request("admin.quillmd.com"), {
      params: Promise.resolve({}),
    });
    expect(response.status).toBe(200);
    await expect(response.json()).resolves.toMatchObject({ ok: true });
    expect(mocks.transaction).toHaveBeenCalledTimes(1);
  });
});
