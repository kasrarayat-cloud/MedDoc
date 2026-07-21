import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  validateSession: vi.fn(),
  recordSessionLogin: vi.fn(),
  randomSessionToken: vi.fn(),
  computeDeviceFingerprint: vi.fn(),
  headers: vi.fn(),
}));

vi.mock("./user-session", () => ({
  validateSession: mocks.validateSession,
  recordSessionLogin: mocks.recordSessionLogin,
  revokeSession: vi.fn(),
  revokeAllUserSessionsFromCurrentSession: vi.fn(),
  revokeAllUserSessions: vi.fn(),
  getUserSessions: vi.fn(),
  randomSessionToken: mocks.randomSessionToken,
  computeDeviceFingerprint: mocks.computeDeviceFingerprint,
}));
vi.mock("next/headers", () => ({ headers: mocks.headers }));
vi.mock("@meddoc/db", () => ({
  default: { user: { findUnique: vi.fn() } },
}));

import { authConfig, createSessionValidationJwtCallback } from "./index";

const SYNTHETIC_QA_DATABASE_CREDENTIAL = "s".repeat(43);

function useExactSyntheticQaProfile(): void {
  for (const [key, value] of Object.entries({
    NODE_ENV: "production",
    QUILLMD_SERVICE_ROLE: "physician-app",
    QUILLMD_DATABASE_PRINCIPAL_PROFILE: "synthetic-disposable-qa-v1",
    TEMPLATE_TWIN_STAGING_QA_ENVIRONMENT: "qa",
    TEMPLATE_TWIN_STAGING_QA_RESOURCE_ATTESTATION: "isolated-disposable-qa-v1",
    TEMPLATE_TWIN_STORAGE_PROFILE: "qa",
    DATABASE_URL: `postgresql://meddoc_runtime:${SYNTHETIC_QA_DATABASE_CREDENTIAL}@postgres:5432/meddoc_qa_test?schema=public&options=-c%20search_path%3Dpg_catalog%2Cpublic`,
    REDIS_URL: "redis://redis:6379/15",
    MINIO_ENDPOINT: "minio:9000",
    MINIO_USE_SSL: "false",
    TRANSCRIBE_MD_MINIO_BUCKET: "transcribe-md-audio-qa",
    TRANSCRIBE_MD_TEMPLATE_BUCKET: "transcribe-md-template-artifacts-qa",
    ADMIN_SYNTHETIC_QA_SHARED_HOST_ATTESTATION:
      "accepted-isolated-synthetic-qa-shared-host",
    ADMIN_PUBLIC_HOST: "localhost",
    PHYSICIAN_PUBLIC_HOST: "localhost",
    AUTH_URL: "http://localhost:9020",
    NEXTAUTH_URL: "http://localhost:9020",
  })) {
    vi.stubEnv(key, value);
  }
}

function currentValidation() {
  return {
    id: "session-row-current",
    userId: "doctor-current",
    createdAt: new Date("2026-07-20T10:00:00.000Z"),
    expiresAt: new Date("2026-07-21T10:00:00.000Z"),
    user: {
      id: "doctor-current",
      email: "current-doctor@synthetic.test",
      name: "Current Synthetic Doctor",
      role: "DOCTOR",
      practiceId: "practice-current",
    },
  };
}

function currentToken(overrides: Record<string, unknown> = {}) {
  return {
    id: "doctor-current",
    sub: "doctor-current",
    email: "stale-doctor@synthetic.test",
    name: "Stale Synthetic Doctor",
    role: "STAFF",
    practiceId: "practice-current",
    sessionId: "session-current",
    ...overrides,
  };
}

const jwt = createSessionValidationJwtCallback({
  allowedRoles: ["DOCTOR"],
  requiredProducts: ["TRANSCRIBE_MD"],
});

async function runJwt(input: {
  token: Record<string, unknown>;
  user?: Record<string, unknown>;
}) {
  return jwt(input as never);
}

beforeEach(() => {
  vi.clearAllMocks();
  vi.stubEnv("NODE_ENV", "test");
  vi.spyOn(console, "error").mockImplementation(() => undefined);
  mocks.validateSession.mockResolvedValue(currentValidation());
  mocks.recordSessionLogin.mockResolvedValue({ id: "session-row-current" });
  mocks.randomSessionToken.mockReturnValue("session-current");
  mocks.computeDeviceFingerprint.mockReturnValue("fingerprint-current");
  mocks.headers.mockResolvedValue(new Headers());
});

afterEach(() => {
  vi.unstubAllEnvs();
  vi.restoreAllMocks();
});

describe("shared JWT current-session enforcement", () => {
  it("denies legacy JWTs without a sessionId", async () => {
    await expect(
      runJwt({ token: currentToken({ sessionId: undefined }) }),
    ).resolves.toBeNull();
    expect(mocks.validateSession).not.toHaveBeenCalled();
  });

  it("fails closed when the current-session validator errors", async () => {
    vi.stubEnv("NODE_ENV", "production");
    vi.stubEnv("QUILLMD_SERVICE_ROLE", "physician-app");
    mocks.validateSession.mockRejectedValue(
      new Error("synthetic database unavailable"),
    );

    await expect(runJwt({ token: currentToken() })).resolves.toBeNull();
    expect(console.error).toHaveBeenCalledWith(
      "[auth] UserSession validation failed; session denied.",
    );
  });

  it("denies a validator rejection without preserving stale JWT claims", async () => {
    mocks.validateSession.mockResolvedValue(null);

    await expect(runJwt({ token: currentToken() })).resolves.toBeNull();
  });

  it("refreshes email, name, role, and tenant from current database identity", async () => {
    await expect(runJwt({ token: currentToken() })).resolves.toMatchObject({
      id: "doctor-current",
      sub: "doctor-current",
      email: "current-doctor@synthetic.test",
      name: "Current Synthetic Doctor",
      role: "DOCTOR",
      practiceId: "practice-current",
      sessionId: "session-current",
    });
    expect(mocks.validateSession).toHaveBeenCalledWith({
      sessionToken: "session-current",
      expectedUserId: "doctor-current",
      expectedPracticeId: "practice-current",
      allowedRoles: ["DOCTOR"],
      requiredProducts: ["TRANSCRIBE_MD"],
    });
  });

  it("projects refreshed identity into the raw auth session", async () => {
    const sessionCallback = authConfig.callbacks?.session;
    expect(sessionCallback).toBeTypeOf("function");

    const result = await sessionCallback!({
      session: {
        user: {
          id: "doctor-current",
          email: "stale-doctor@synthetic.test",
          name: "Stale Synthetic Doctor",
          role: "STAFF",
          practiceId: "practice-current",
        },
        expires: "2026-07-21T10:00:00.000Z",
      },
      token: currentToken({
        email: "current-doctor@synthetic.test",
        name: "Current Synthetic Doctor",
        role: "DOCTOR",
      }),
    } as never);

    expect(result.user).toMatchObject({
      id: "doctor-current",
      email: "current-doctor@synthetic.test",
      name: "Current Synthetic Doctor",
      role: "DOCTOR",
      practiceId: "practice-current",
      sessionId: "session-current",
    });
  });

  it("fails closed when the server-side session row cannot be recorded at sign-in", async () => {
    mocks.recordSessionLogin.mockRejectedValue(
      new Error("synthetic session write failure"),
    );

    await expect(
      runJwt({
        token: currentToken({ sessionId: undefined }),
        user: {
          id: "doctor-current",
          email: "current-doctor@synthetic.test",
          name: "Current Synthetic Doctor",
          role: "DOCTOR",
          practiceId: "practice-current",
        },
      }),
    ).resolves.toBeNull();
    expect(mocks.validateSession).not.toHaveBeenCalled();
    expect(console.error).toHaveBeenCalledWith(
      "[auth] UserSession record failed; sign-in denied.",
    );
  });

  it("accepts an explicitly trusted prevalidated session without creating a second row", async () => {
    const trustedJwt = createSessionValidationJwtCallback(
      {
        allowedRoles: ["DOCTOR"],
        requiredProducts: ["TRANSCRIBE_MD"],
      },
      { acceptPrevalidatedSession: true },
    );

    await expect(
      trustedJwt({
        token: currentToken({ sessionId: undefined }),
        user: {
          id: "doctor-current",
          email: "current-doctor@synthetic.test",
          name: "Current Synthetic Doctor",
          role: "DOCTOR",
          practiceId: "practice-current",
          prevalidatedSessionId: "prevalidated-session-current",
        },
      } as never),
    ).resolves.toMatchObject({
      id: "doctor-current",
      sessionId: "prevalidated-session-current",
    });
    expect(mocks.recordSessionLogin).not.toHaveBeenCalled();
    expect(mocks.validateSession).toHaveBeenCalledWith(
      expect.objectContaining({
        sessionToken: "prevalidated-session-current",
        expectedUserId: "doctor-current",
      }),
    );
  });

  it("does not trust a prevalidated-session field unless the caller opts in", async () => {
    await expect(
      runJwt({
        token: currentToken({ sessionId: undefined }),
        user: {
          id: "doctor-current",
          email: "current-doctor@synthetic.test",
          name: "Current Synthetic Doctor",
          role: "DOCTOR",
          practiceId: "practice-current",
          prevalidatedSessionId: "untrusted-session-value",
        },
      }),
    ).resolves.toMatchObject({ sessionId: "session-current" });
    expect(mocks.recordSessionLogin).toHaveBeenCalledTimes(1);
  });

  it("passes the MedDoc Pro current-entitlement alternatives to the validator", async () => {
    const meddocJwt = createSessionValidationJwtCallback({
      anyOf: [
        { requiredProducts: ["MEDDOC_PRO"] },
        { requiredProducts: ["SUPER_ADMIN"] },
      ],
    });

    await expect(
      meddocJwt({ token: currentToken() } as never),
    ).resolves.toMatchObject({ id: "doctor-current" });
    expect(mocks.validateSession).toHaveBeenCalledWith({
      sessionToken: "session-current",
      expectedUserId: "doctor-current",
      expectedPracticeId: "practice-current",
      allowedRoles: undefined,
      requiredProducts: undefined,
      anyOf: [
        { requiredProducts: ["MEDDOC_PRO"] },
        { requiredProducts: ["SUPER_ADMIN"] },
      ],
    });
  });

  it("does not activate the control-session exception from role and principal alone", async () => {
    vi.stubEnv("NODE_ENV", "production");
    vi.stubEnv("QUILLMD_SERVICE_ROLE", "template-twin-admin-control");
    vi.stubEnv("QUILLMD_DATABASE_PRINCIPAL_PROFILE", "exact-production-v1");

    await expect(runJwt({ token: currentToken() })).resolves.toMatchObject({
      id: "doctor-current",
    });
    expect(mocks.validateSession).toHaveBeenCalledTimes(1);
  });

  it("activates the narrow control-session exception only with its explicit verifier profile", async () => {
    vi.stubEnv("NODE_ENV", "production");
    vi.stubEnv("QUILLMD_SERVICE_ROLE", "template-twin-admin-control");
    vi.stubEnv("QUILLMD_DATABASE_PRINCIPAL_PROFILE", "exact-production-v1");
    vi.stubEnv(
      "QUILLMD_AUTH_SESSION_VERIFIER_PROFILE",
      "template-twin-admin-control-v1",
    );

    await expect(runJwt({ token: currentToken() })).resolves.toEqual(
      currentToken(),
    );
    expect(mocks.validateSession).not.toHaveBeenCalled();
  });
});

describe("production mock-auth isolation", () => {
  it("does not honor AUTH_USE_MOCK outside the exact isolated QA profile", () => {
    vi.stubEnv("NODE_ENV", "production");
    vi.stubEnv("AUTH_USE_MOCK", "true");
    const authorized = authConfig.callbacks?.authorized;
    expect(authorized).toBeTypeOf("function");

    expect(
      authorized!({
        auth: null,
        request: { nextUrl: new URL("https://app.quillmd.com/dashboard") },
      } as never),
    ).toBe(false);
  });

  it("honors AUTH_USE_MOCK only under the exact attested localhost QA profile", () => {
    vi.stubEnv("AUTH_USE_MOCK", "true");
    useExactSyntheticQaProfile();
    const authorized = authConfig.callbacks?.authorized;

    expect(
      authorized!({
        auth: null,
        request: { nextUrl: new URL("http://localhost:9020/dashboard") },
      } as never),
    ).toBe(true);
  });
});

describe("production Auth.js cookie posture", () => {
  it("forces secure defaults for session and every auxiliary Auth.js cookie", async () => {
    vi.resetModules();
    vi.stubEnv("NODE_ENV", "production");
    vi.stubEnv("NEXT_PHASE", "phase-production-build");
    vi.stubEnv("AUTH_COOKIE_DOMAIN", "");

    const productionConfig = (await import("./index")).authConfig;

    expect(productionConfig.useSecureCookies).toBe(true);
    expect(productionConfig.cookies?.sessionToken).toMatchObject({
      name: "__Secure-authjs.session-token",
      options: {
        httpOnly: true,
        sameSite: "lax",
        path: "/",
        secure: true,
      },
    });
  });
});
