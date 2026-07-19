import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  auth: vi.fn(),
  configurationError: vi.fn(),
  adminHost: vi.fn(),
  verify: vi.fn(),
}));

vi.mock("server-only", () => ({}));
vi.mock("@/lib/nextauth", () => ({ auth: mocks.auth }));
vi.mock("@/lib/admin-host", () => ({
  adminSurfaceConfigurationError: mocks.configurationError,
  isAdminRequestHost: mocks.adminHost,
}));
vi.mock("@/lib/admin-session-freshness", () => ({
  verifyFreshPlatformAdminSession: mocks.verify,
}));

import { resolveMfaRequestActor } from "../mfa-request-actor";

beforeEach(() => {
  vi.clearAllMocks();
  mocks.configurationError.mockReturnValue(null);
  mocks.adminHost.mockReturnValue(false);
  mocks.auth.mockResolvedValue({
    user: { id: "user_synthetic", sessionId: "session_synthetic" },
  });
});

describe("MFA request actor boundary", () => {
  it("preserves ordinary physician-host MFA behavior", async () => {
    await expect(resolveMfaRequestActor(new Headers())).resolves.toEqual({
      userId: "user_synthetic",
      sessionId: "session_synthetic",
      isAdminHost: false,
      isPlatformAdmin: false,
    });
    expect(mocks.verify).not.toHaveBeenCalled();
  });

  it("requires a fresh Product.SUPER_ADMIN session on the admin host", async () => {
    mocks.adminHost.mockReturnValue(true);
    mocks.verify.mockResolvedValueOnce(null);
    await expect(resolveMfaRequestActor(new Headers())).resolves.toBeNull();

    mocks.verify.mockResolvedValueOnce({
      userId: "platform_admin_synthetic",
      sessionId: "session_db_synthetic",
    });
    await expect(resolveMfaRequestActor(new Headers())).resolves.toEqual({
      userId: "platform_admin_synthetic",
      sessionId: "session_db_synthetic",
      isAdminHost: true,
      isPlatformAdmin: true,
    });
    expect(mocks.verify).toHaveBeenLastCalledWith({
      claimedUserId: "user_synthetic",
      sessionId: "session_synthetic",
      requireMfa: false,
    });
  });

  it("fails closed before auth when the origin configuration is unsafe", async () => {
    mocks.configurationError.mockReturnValue("ADMIN_PHYSICIAN_HOST_COLLISION");
    await expect(resolveMfaRequestActor(new Headers())).resolves.toBeNull();
    expect(mocks.auth).not.toHaveBeenCalled();
  });
});
