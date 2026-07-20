import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  auth: vi.fn(),
  configurationError: vi.fn(),
  adminHost: vi.fn(),
  physicianHost: vi.fn(),
  adminService: vi.fn(),
  physicianService: vi.fn(),
  verify: vi.fn(),
}));

vi.mock("server-only", () => ({}));
vi.mock("@/lib/nextauth", () => ({ auth: mocks.auth }));
vi.mock("@/lib/admin-host", () => ({
  adminSurfaceConfigurationError: mocks.configurationError,
  isAdminRequestHost: mocks.adminHost,
  isPhysicianRequestHost: mocks.physicianHost,
}));
vi.mock("@/lib/admin-session-freshness", () => ({
  verifyFreshPlatformAdminSession: mocks.verify,
}));
vi.mock("@/lib/template-twin/admin-app-service", () => ({
  isTemplateTwinAdminAppService: mocks.adminService,
  isTranscribeMdPhysicianAppService: mocks.physicianService,
}));

import { resolveMfaRequestActor } from "../mfa-request-actor";

beforeEach(() => {
  vi.clearAllMocks();
  mocks.configurationError.mockReturnValue(null);
  mocks.adminHost.mockReturnValue(false);
  mocks.physicianHost.mockReturnValue(true);
  mocks.adminService.mockReturnValue(false);
  mocks.physicianService.mockReturnValue(true);
  mocks.auth.mockResolvedValue({
    user: {
      id: "user_synthetic",
      sessionId: "session_synthetic",
      practiceId: "practice_synthetic",
    },
  });
});

describe("MFA request actor boundary", () => {
  it("preserves ordinary physician-host MFA behavior", async () => {
    await expect(resolveMfaRequestActor(new Headers())).resolves.toEqual({
      userId: "user_synthetic",
      sessionId: "session_synthetic",
      practiceId: "practice_synthetic",
      isAdminHost: false,
      isPlatformAdmin: false,
    });
    expect(mocks.verify).not.toHaveBeenCalled();
  });

  it("requires a fresh Product.SUPER_ADMIN session on the admin host", async () => {
    mocks.adminHost.mockReturnValue(true);
    mocks.physicianHost.mockReturnValue(false);
    mocks.adminService.mockReturnValue(true);
    mocks.physicianService.mockReturnValue(false);
    mocks.verify.mockResolvedValueOnce(null);
    await expect(resolveMfaRequestActor(new Headers())).resolves.toBeNull();

    mocks.verify.mockResolvedValueOnce({
      userId: "platform_admin_synthetic",
      sessionId: "session_db_synthetic",
      practiceId: "practice_synthetic",
    });
    await expect(resolveMfaRequestActor(new Headers())).resolves.toEqual({
      userId: "platform_admin_synthetic",
      sessionId: "session_db_synthetic",
      practiceId: "practice_synthetic",
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

  it.each([
    ["physician service on admin Host", false, true, true, false],
    ["admin service on physician Host", true, false, false, true],
    ["unknown service on physician Host", false, false, false, true],
    ["missing service on no reviewed Host", false, false, false, false],
  ])(
    "denies %s before auth or current-authority work",
    async (
      _label,
      adminService,
      physicianService,
      adminHost,
      physicianHost,
    ) => {
      mocks.adminService.mockReturnValue(adminService);
      mocks.physicianService.mockReturnValue(physicianService);
      mocks.adminHost.mockReturnValue(adminHost);
      mocks.physicianHost.mockReturnValue(physicianHost);

      await expect(resolveMfaRequestActor(new Headers())).resolves.toBeNull();
      expect(mocks.auth).not.toHaveBeenCalled();
      expect(mocks.verify).not.toHaveBeenCalled();
    },
  );
});
