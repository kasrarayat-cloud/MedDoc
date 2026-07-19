import { beforeEach, describe, expect, it, vi } from "vitest";
import { NextRequest, NextResponse } from "next/server";

const mocks = vi.hoisted(() => ({
  auth: vi.fn(),
  hostAllowed: vi.fn(),
  verify: vi.fn(),
  requiredAudit: vi.fn(),
}));

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

import { adminApi, type AdminContext } from "../admin-api-gate";

beforeEach(() => {
  vi.clearAllMocks();
  mocks.hostAllowed.mockReturnValue(true);
  mocks.auth.mockResolvedValue({
    user: {
      id: "jwt_user_synthetic",
      email: "stale-jwt@synthetic.invalid",
      role: "STAFF",
      practiceId: "stale_practice",
      sessionId: "session_synthetic",
    },
  });
  mocks.verify.mockResolvedValue({
    userId: "admin_synthetic",
    email: "admin@synthetic.invalid",
    role: "SUPER_ADMIN",
    practiceId: "practice_synthetic",
    sessionId: "session_synthetic",
    sessionCreatedAt: new Date("2026-07-19T08:00:00.000Z"),
    sessionExpiresAt: new Date("2026-07-19T20:00:00.000Z"),
    mfaEnabled: true,
    mfaVerifiedAt: new Date("2026-07-19T07:00:00.000Z"),
  });
  mocks.requiredAudit.mockResolvedValue(undefined);
});

describe("admin API gate", () => {
  it("cloaks physician-host requests before reading authentication", async () => {
    mocks.hostAllowed.mockReturnValue(false);
    const handler = vi.fn();
    const response = await adminApi(
      "synthetic:route",
      handler,
    )(new NextRequest("https://app.quillmd.com/api/admin/synthetic"));

    expect(response.status).toBe(404);
    expect(await response.text()).toBe("Not Found");
    expect(mocks.auth).not.toHaveBeenCalled();
    expect(mocks.verify).not.toHaveBeenCalled();
    expect(handler).not.toHaveBeenCalled();
  });

  it("passes only the current database-confirmed identity to the handler", async () => {
    const handler = vi.fn(
      async (_request: NextRequest, context: AdminContext) =>
        NextResponse.json(context.session.user),
    );
    const response = await adminApi(
      "synthetic:route",
      handler,
    )(new NextRequest("https://admin.quillmd.com/api/admin/synthetic"));

    expect(mocks.verify).toHaveBeenCalledWith({
      claimedUserId: "jwt_user_synthetic",
      sessionId: "session_synthetic",
    });
    await expect(response.json()).resolves.toEqual({
      id: "admin_synthetic",
      email: "admin@synthetic.invalid",
      role: "SUPER_ADMIN",
      practiceId: "practice_synthetic",
    });
    expect(mocks.requiredAudit).toHaveBeenCalledWith(
      expect.objectContaining({
        action: "ADMIN_API_ACCESS",
        userId: "admin_synthetic",
        userEmail: "admin@synthetic.invalid",
        practiceId: "practice_synthetic",
        targetId: "synthetic:route",
      }),
    );
  });

  it("cloaks auth, database, lifecycle, entitlement, expiry, or MFA failures identically", async () => {
    const handler = vi.fn();
    mocks.verify.mockResolvedValue(null);
    const response = await adminApi(
      "synthetic:route",
      handler,
    )(new NextRequest("https://admin.quillmd.com/api/admin/synthetic"));

    expect(response.status).toBe(404);
    expect(await response.text()).toBe("Not Found");
    expect(handler).not.toHaveBeenCalled();
    expect(mocks.requiredAudit).not.toHaveBeenCalled();
  });

  it("denies the handler when required audit persistence fails", async () => {
    mocks.requiredAudit.mockRejectedValue(new Error("synthetic db detail"));
    const handler = vi.fn();
    const consoleSpy = vi.spyOn(console, "error").mockImplementation(() => {});
    const response = await adminApi(
      "synthetic:route",
      handler,
    )(new NextRequest("https://admin.quillmd.com/api/admin/synthetic"));

    expect(response.status).toBe(404);
    expect(handler).not.toHaveBeenCalled();
    expect(consoleSpy).not.toHaveBeenCalledWith(
      expect.stringContaining("synthetic db detail"),
    );
    consoleSpy.mockRestore();
  });

  it("does not log a privileged handler error message", async () => {
    const consoleSpy = vi.spyOn(console, "error").mockImplementation(() => {});
    const response = await adminApi("synthetic:route", async () => {
      throw new Error("postgresql://user:secret@db/clinical-value");
    })(new NextRequest("https://admin.quillmd.com/api/admin/synthetic"));

    expect(response.status).toBe(500);
    const rendered = JSON.stringify(consoleSpy.mock.calls);
    expect(rendered).not.toContain("postgresql://");
    expect(rendered).not.toContain("clinical-value");
    consoleSpy.mockRestore();
  });
});
