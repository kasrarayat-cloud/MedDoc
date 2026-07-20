import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  auth: vi.fn(),
  validateSession: vi.fn(),
  findUser: vi.fn(),
  evaluateRollout: vi.fn(),
  pinRollout: vi.fn(),
  sessionStale: vi.fn(),
  headers: vi.fn(),
  adminHost: vi.fn(),
}));

vi.mock("@/lib/auth", () => ({
  AuthError: class AuthError extends Error {
    constructor(
      public readonly code: "UNAUTHENTICATED" | "FORBIDDEN",
      message: string,
    ) {
      super(message);
    }
  },
}));
vi.mock("@/lib/nextauth", () => ({ auth: mocks.auth }));
vi.mock("next/headers", () => ({ headers: mocks.headers }));
vi.mock("@/lib/admin-host", () => ({
  isAdminRequestHost: mocks.adminHost,
}));
vi.mock("@meddoc/auth", () => ({
  validateSession: mocks.validateSession,
}));
vi.mock("@/lib/admin-session-freshness", () => ({
  isAdminSessionStale: mocks.sessionStale,
}));
vi.mock("@meddoc/db", () => ({
  default: { user: { findUnique: mocks.findUser } },
}));
vi.mock("../rollout", () => ({
  TemplateTwinRolloutError: class TemplateTwinRolloutError extends Error {},
  evaluateTemplateTwinRollout: mocks.evaluateRollout,
  pinTemplateTwinRollout: mocks.pinRollout,
}));

import { requireTemplateTwinStaticAssetAdmin } from "../static-asset-admin";

function currentAdmin(overrides: Record<string, unknown> = {}) {
  return {
    id: "admin_synthetic",
    email: "admin@synthetic.test",
    role: "ADMIN",
    practiceId: "practice_synthetic",
    products: ["TRANSCRIBE_MD"],
    isActive: true,
    deactivatedAt: null,
    suspendedAt: null,
    softDeletedAt: null,
    mfaEnabled: false,
    mfaSecret: null,
    mfaVerifiedAt: null,
    practice: {
      id: "practice_synthetic",
      isActive: true,
      templateTwinEnabled: true,
    },
    ...overrides,
  };
}

beforeEach(() => {
  vi.clearAllMocks();
  vi.stubEnv("QUILLMD_SERVICE_ROLE", "template-twin-admin-app");
  mocks.headers.mockResolvedValue(new Headers({ host: "admin.quillmd.com" }));
  mocks.adminHost.mockReturnValue(true);
  mocks.auth.mockResolvedValue({
    user: {
      id: "admin_synthetic",
      sessionId: "session_synthetic",
      practiceId: "practice_synthetic",
    },
  });
  mocks.sessionStale.mockResolvedValue(false);
  mocks.validateSession.mockResolvedValue({
    user: {
      id: "admin_synthetic",
      email: "admin@synthetic.test",
      role: "ADMIN",
      practiceId: "practice_synthetic",
    },
  });
  mocks.findUser.mockResolvedValue(currentAdmin());
  mocks.evaluateRollout.mockReturnValue({ allowed: true });
  mocks.pinRollout.mockResolvedValue({
    practiceId: "practice_synthetic",
    globalGeneration: 1,
    practiceGeneration: 1,
  });
});

afterEach(() => {
  vi.unstubAllEnvs();
});

describe("fresh Template Twin static-asset administrator authorization", () => {
  it("rejects a proxy misroute or ordinary physician process before reading a cookie", async () => {
    vi.stubEnv("QUILLMD_SERVICE_ROLE", "physician-app");
    await expect(requireTemplateTwinStaticAssetAdmin()).rejects.toMatchObject({
      code: "FORBIDDEN",
    });
    expect(mocks.headers).not.toHaveBeenCalled();
    expect(mocks.auth).not.toHaveBeenCalled();

    vi.stubEnv("QUILLMD_SERVICE_ROLE", "template-twin-admin-app");
    mocks.adminHost.mockReturnValue(false);
    await expect(requireTemplateTwinStaticAssetAdmin()).rejects.toMatchObject({
      code: "FORBIDDEN",
    });
    expect(mocks.auth).not.toHaveBeenCalled();
  });

  it("returns only the current database-confirmed practice and admin role", async () => {
    await expect(requireTemplateTwinStaticAssetAdmin()).resolves.toEqual({
      userId: "admin_synthetic",
      userEmail: "admin@synthetic.test",
      practiceId: "practice_synthetic",
      role: "ADMIN",
      rolloutToken: {
        practiceId: "practice_synthetic",
        globalGeneration: 1,
        practiceGeneration: 1,
      },
    });
    expect(mocks.pinRollout).toHaveBeenCalledWith({
      practiceId: "practice_synthetic",
    });
    expect(mocks.validateSession).toHaveBeenCalledWith({
      sessionToken: "session_synthetic",
      expectedUserId: "admin_synthetic",
      expectedPracticeId: "practice_synthetic",
      allowedRoles: ["ADMIN", "SUPER_ADMIN"],
      requiredProducts: ["TRANSCRIBE_MD"],
    });
  });

  it.each(["DOCTOR", "STAFF"])(
    "rejects a fresh %s database role",
    async (role) => {
      mocks.validateSession.mockResolvedValue({
        user: {
          id: "admin_synthetic",
          email: "user@synthetic.test",
          role,
          practiceId: "practice_synthetic",
        },
      });
      await expect(requireTemplateTwinStaticAssetAdmin()).rejects.toMatchObject(
        {
          code: "FORBIDDEN",
        },
      );
      expect(mocks.pinRollout).not.toHaveBeenCalled();
    },
  );

  it("rejects invalid current sessions, disabled rollout, and database outages without JWT fallback", async () => {
    mocks.validateSession.mockResolvedValueOnce(null);
    await expect(requireTemplateTwinStaticAssetAdmin()).rejects.toMatchObject({
      code: "FORBIDDEN",
    });

    mocks.findUser.mockResolvedValueOnce(
      currentAdmin({
        practice: {
          id: "practice_synthetic",
          isActive: true,
          templateTwinEnabled: false,
        },
      }),
    );
    mocks.evaluateRollout.mockReturnValueOnce({
      allowed: false,
      reason: "Synthetic rollout is disabled.",
    });
    await expect(requireTemplateTwinStaticAssetAdmin()).rejects.toMatchObject({
      code: "FORBIDDEN",
    });

    mocks.validateSession.mockRejectedValueOnce(
      new Error("synthetic database outage"),
    );
    await expect(requireTemplateTwinStaticAssetAdmin()).rejects.toMatchObject({
      code: "FORBIDDEN",
    });
  });

  it("rejects a missing or stale administrator session before database authorization", async () => {
    mocks.sessionStale.mockResolvedValueOnce(true);
    await expect(requireTemplateTwinStaticAssetAdmin()).rejects.toMatchObject({
      code: "FORBIDDEN",
    });
    expect(mocks.validateSession).not.toHaveBeenCalled();
  });

  it("rejects an inactive practice and a transferred session tenant", async () => {
    mocks.findUser.mockResolvedValueOnce(
      currentAdmin({
        practice: {
          id: "practice_synthetic",
          isActive: false,
          templateTwinEnabled: true,
        },
      }),
    );
    await expect(requireTemplateTwinStaticAssetAdmin()).rejects.toMatchObject({
      code: "FORBIDDEN",
    });

    mocks.validateSession.mockResolvedValueOnce(null);
    await expect(requireTemplateTwinStaticAssetAdmin()).rejects.toMatchObject({
      code: "FORBIDDEN",
    });
    expect(mocks.pinRollout).not.toHaveBeenCalled();
  });

  it.each([
    {
      label: "disabled",
      mfaEnabled: false,
      mfaSecret: "SYNTHETIC-SECRET",
      mfaVerifiedAt: new Date("2026-07-20T08:00:00.000Z"),
    },
    {
      label: "missing secret",
      mfaEnabled: true,
      mfaSecret: null,
      mfaVerifiedAt: new Date("2026-07-20T08:00:00.000Z"),
    },
    {
      label: "tab/newline-only secret",
      mfaEnabled: true,
      mfaSecret: "\t\r\n",
      mfaVerifiedAt: new Date("2026-07-20T08:00:00.000Z"),
    },
    {
      label: "unverified",
      mfaEnabled: true,
      mfaSecret: "SYNTHETIC-SECRET",
      mfaVerifiedAt: null,
    },
  ])(
    "rejects dual-entitled platform authority with $label MFA",
    async (mfa) => {
      mocks.findUser.mockResolvedValue(
        currentAdmin({
          products: ["TRANSCRIBE_MD", "SUPER_ADMIN"],
          ...mfa,
        }),
      );

      await expect(requireTemplateTwinStaticAssetAdmin()).rejects.toMatchObject(
        {
          code: "FORBIDDEN",
        },
      );
      expect(mocks.pinRollout).not.toHaveBeenCalled();
    },
  );

  it("admits dual-entitled platform authority only with complete MFA", async () => {
    mocks.findUser.mockResolvedValue(
      currentAdmin({
        products: ["TRANSCRIBE_MD", "SUPER_ADMIN"],
        mfaEnabled: true,
        mfaSecret: "SYNTHETIC-SECRET",
        mfaVerifiedAt: new Date("2026-07-20T08:00:00.000Z"),
      }),
    );

    await expect(requireTemplateTwinStaticAssetAdmin()).resolves.toMatchObject({
      userId: "admin_synthetic",
      practiceId: "practice_synthetic",
      role: "ADMIN",
    });
  });
});
