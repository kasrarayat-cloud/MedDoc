import { beforeEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";

const mocks = vi.hoisted(() => ({
  resolveActor: vi.fn(),
  findUser: vi.fn(),
  updateUser: vi.fn(),
  generateEnrollment: vi.fn(),
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
vi.mock("@/lib/mfa-request-actor", () => ({
  resolveMfaRequestActor: mocks.resolveActor,
}));
vi.mock("@/lib/mfa", () => ({
  generateMfaEnrollment: mocks.generateEnrollment,
}));
vi.mock("@/lib/audit", () => ({ logAudit: mocks.logAudit }));

import { POST } from "./route";

function request(host = "app.quillmd.com"): NextRequest {
  return new NextRequest(`https://${host}/api/mfa/enroll`, {
    method: "POST",
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
    mfaEnabled: true,
    products: ["TRANSCRIBE_MD", "SUPER_ADMIN"],
  });
  mocks.generateEnrollment.mockResolvedValue({
    secret: "synthetic-secret",
    otpauthUri: "otpauth://synthetic.invalid",
    qrPngDataUrl: "data:image/png;base64,c3ludGhldGlj",
  });
  mocks.updateUser.mockResolvedValue({});
  mocks.logAudit.mockResolvedValue(undefined);
});

describe("MFA enrollment authorization boundary", () => {
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
    expect(mocks.updateUser).toHaveBeenCalledTimes(1);
  });
});
