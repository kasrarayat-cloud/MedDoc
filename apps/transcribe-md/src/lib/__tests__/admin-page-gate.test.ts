import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  headers: vi.fn(),
  notFound: vi.fn(() => {
    throw new Error("NOT_FOUND");
  }),
  auth: vi.fn(),
  hostAllowed: vi.fn(),
  verify: vi.fn(),
  requiredAudit: vi.fn(),
}));

vi.mock("server-only", () => ({}));
vi.mock("next/headers", () => ({ headers: mocks.headers }));
vi.mock("next/navigation", () => ({ notFound: mocks.notFound }));
vi.mock("@/lib/nextauth", () => ({ auth: mocks.auth }));
vi.mock("@/lib/admin-host", () => ({
  isAdminRequestHost: mocks.hostAllowed,
}));
vi.mock("@/lib/admin-session-freshness", () => ({
  verifyFreshPlatformAdminSession: mocks.verify,
}));
vi.mock("@/lib/audit", () => ({
  logRequiredAdminAudit: mocks.requiredAudit,
}));

import { requireFreshPlatformAdminPage } from "../admin-page-gate";

const VERIFIED = {
  userId: "admin_synthetic",
  email: "admin@synthetic.invalid",
  role: "DOCTOR",
  practiceId: "practice_synthetic",
  sessionId: "session_synthetic",
  sessionCreatedAt: new Date("2026-07-19T08:00:00.000Z"),
  sessionExpiresAt: new Date("2026-07-19T20:00:00.000Z"),
  mfaEnabled: true,
  mfaVerifiedAt: new Date("2026-07-19T07:00:00.000Z"),
  mfaComplete: true,
};

beforeEach(() => {
  vi.clearAllMocks();
  mocks.headers.mockResolvedValue(new Headers({ host: "admin.quillmd.com" }));
  mocks.hostAllowed.mockReturnValue(true);
  mocks.auth.mockResolvedValue({
    user: { id: "jwt_synthetic", sessionId: "session_synthetic" },
  });
  mocks.verify.mockResolvedValue(VERIFIED);
  mocks.requiredAudit.mockResolvedValue(undefined);
});

describe("fresh platform-admin page gate", () => {
  it("binds required audit persistence to the freshly verified identity", async () => {
    await expect(
      requireFreshPlatformAdminPage({ routeKey: "/admin/users" }),
    ).resolves.toEqual(VERIFIED);
    expect(mocks.verify).toHaveBeenCalledWith({
      claimedUserId: "jwt_synthetic",
      sessionId: "session_synthetic",
      requireMfa: undefined,
    });
    expect(mocks.requiredAudit).toHaveBeenCalledWith(
      expect.objectContaining({
        userId: VERIFIED.userId,
        userEmail: VERIFIED.email,
        practiceId: VERIFIED.practiceId,
        targetType: "AdminPage",
        targetId: "/admin/users",
      }),
    );
  });

  it("re-checks authorization on every invocation instead of relying on layout state", async () => {
    await requireFreshPlatformAdminPage({ routeKey: "/admin" });
    mocks.verify.mockResolvedValueOnce(null);
    await expect(
      requireFreshPlatformAdminPage({ routeKey: "/admin/usage" }),
    ).rejects.toThrow("NOT_FOUND");
    expect(mocks.verify).toHaveBeenCalledTimes(2);
  });

  it("fails closed before data access on host, authority, or audit failure", async () => {
    mocks.hostAllowed.mockReturnValueOnce(false);
    await expect(
      requireFreshPlatformAdminPage({ routeKey: "/admin/queues" }),
    ).rejects.toThrow("NOT_FOUND");
    expect(mocks.auth).not.toHaveBeenCalled();

    mocks.hostAllowed.mockReturnValue(true);
    mocks.requiredAudit.mockRejectedValueOnce(new Error("synthetic failure"));
    const consoleSpy = vi.spyOn(console, "error").mockImplementation(() => {});
    await expect(
      requireFreshPlatformAdminPage({ routeKey: "/admin/hipaa" }),
    ).rejects.toThrow("NOT_FOUND");
    expect(JSON.stringify(consoleSpy.mock.calls)).not.toContain(
      "synthetic failure",
    );
    consoleSpy.mockRestore();
  });
});
