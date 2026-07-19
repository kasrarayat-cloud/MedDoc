import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  sequence: [] as string[],
  headers: vi.fn(),
  notFound: vi.fn(),
  adminHost: vi.fn(),
  auth: vi.fn(),
  verify: vi.fn(),
  processEnabled: vi.fn(),
  recordPageAccess: vi.fn(),
  inspect: vi.fn(),
}));

vi.mock("next/headers", () => ({ headers: mocks.headers }));
vi.mock("next/navigation", () => ({ notFound: mocks.notFound }));
vi.mock("@/lib/admin-host", () => ({ isAdminRequestHost: mocks.adminHost }));
vi.mock("@/lib/nextauth", () => ({ auth: mocks.auth }));
vi.mock("@/lib/admin-session-freshness", () => ({
  verifyFreshPlatformAdminSession: mocks.verify,
}));
vi.mock("@/lib/template-twin/release-control-db", () => ({
  templateTwinReleaseControlProcessEnabled: mocks.processEnabled,
}));
vi.mock("@/lib/template-twin/release-control-access-audit", () => ({
  recordTemplateTwinReleasePageAccess: mocks.recordPageAccess,
}));
vi.mock("@/lib/template-twin/release-control", () => ({
  inspectTemplateTwinReleaseControl: mocks.inspect,
}));
vi.mock("../_components/TemplateTwinReleaseWorkbench.client", () => ({
  default: () => null,
}));

import TemplateTwinReleasePage from "../page";

const requestHeaders = new Headers({
  host: "admin.quillmd.com",
  "x-real-ip": "192.0.2.10",
  "user-agent": "synthetic-page-reviewer",
});
const verified = {
  userId: "admin_synthetic",
  email: "admin@synthetic.invalid",
  role: "SUPER_ADMIN",
  practiceId: "practice_synthetic",
  sessionId: "session_synthetic_123456789",
  sessionCreatedAt: new Date("2026-07-19T12:00:00.000Z"),
  sessionExpiresAt: new Date("2026-07-19T20:00:00.000Z"),
  mfaEnabled: true,
  mfaVerifiedAt: new Date("2026-07-19T12:00:00.000Z"),
};
const control = {
  global: {
    enabled: false,
    generation: "1",
    rollbackFenceState: "CLEAR",
  },
  release: null,
};

beforeEach(() => {
  vi.clearAllMocks();
  mocks.sequence.length = 0;
  mocks.processEnabled.mockReturnValue(true);
  mocks.headers.mockResolvedValue(requestHeaders);
  mocks.adminHost.mockImplementation(() => {
    mocks.sequence.push("host");
    return true;
  });
  mocks.auth.mockResolvedValue({
    user: { id: verified.userId, sessionId: verified.sessionId },
  });
  mocks.verify.mockImplementation(async () => {
    mocks.sequence.push("session");
    return verified;
  });
  mocks.recordPageAccess.mockImplementation(async () => {
    mocks.sequence.push("audit");
  });
  mocks.inspect.mockImplementation(async () => {
    mocks.sequence.push("inspect");
    return control;
  });
  mocks.notFound.mockImplementation(() => {
    throw new Error("NEXT_NOT_FOUND");
  });
});

describe("Template Twin release server page", () => {
  it("awaits its durable receipt before inspecting sensitive control state", async () => {
    const result = await TemplateTwinReleasePage();

    expect(mocks.recordPageAccess).toHaveBeenCalledWith({
      actorId: verified.userId,
      actorEmail: verified.email,
      practiceId: verified.practiceId,
      headers: requestHeaders,
    });
    expect(mocks.verify).toHaveBeenCalledWith({
      claimedUserId: verified.userId,
      sessionId: verified.sessionId,
    });
    expect(mocks.sequence).toEqual(["host", "session", "audit", "inspect"]);
    expect(result.props.initial).toBe(control);
  });

  it("fails closed without inspection when the durable receipt fails", async () => {
    mocks.recordPageAccess.mockRejectedValueOnce(new Error("synthetic outage"));

    await expect(TemplateTwinReleasePage()).rejects.toThrow("NEXT_NOT_FOUND");
    expect(mocks.inspect).not.toHaveBeenCalled();
  });
});
