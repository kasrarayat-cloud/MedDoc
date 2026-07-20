import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";

type CapturedAuthorize = (
  credentials: Record<string, unknown>,
  request: Request,
) => Promise<unknown>;

const mocks = vi.hoisted(() => ({
  authorize: null as CapturedAuthorize | null,
  findUser: vi.fn(),
  transaction: vi.fn(),
  finalizeCredentialSession: vi.fn(),
  recordCredentialFailure: vi.fn(),
  comparePassword: vi.fn(),
  verifyStoredTotp: vi.fn(),
  findRecovery: vi.fn(),
  logAudit: vi.fn(),
  rawAuth: vi.fn(),
  authGet: vi.fn(),
  authPost: vi.fn(),
  requestHeaders: vi.fn(),
  verificationRequired: vi.fn(),
  checkSharedRateLimit: vi.fn(),
  clientIpFromHeaders: vi.fn(),
  readSignedSessionAuthority: vi.fn(),
  revokeSession: vi.fn(),
}));

vi.mock("next-auth", () => ({
  default: vi.fn(() => ({
    handlers: { GET: mocks.authGet, POST: mocks.authPost },
    auth: mocks.rawAuth,
    signIn: vi.fn(),
    signOut: vi.fn(),
  })),
}));
vi.mock("next/headers", () => ({ headers: mocks.requestHeaders }));
vi.mock("next-auth/providers/credentials", () => ({
  default: vi.fn((options: { authorize: CapturedAuthorize }) => {
    mocks.authorize = options.authorize;
    return { id: "credentials", type: "credentials", ...options };
  }),
}));
vi.mock("bcryptjs", () => ({
  default: {
    hashSync: vi.fn(() => "synthetic-dummy-hash"),
    compare: mocks.comparePassword,
  },
}));
vi.mock("@sentry/nextjs", () => ({}));
vi.mock("@/lib/auth.config", () => ({ default: { callbacks: {} } }));
vi.mock("@meddoc/db", () => ({
  default: {
    user: { findUnique: mocks.findUser },
    $transaction: mocks.transaction,
  },
}));
vi.mock("@meddoc/auth", () => ({
  createSessionValidationJwtCallback: vi.fn(() => vi.fn()),
  computeDeviceFingerprint: vi.fn(() => "fingerprint-synthetic"),
  randomSessionToken: vi.fn(() => "session-synthetic-prevalidated"),
  revokeSession: mocks.revokeSession,
  revokeAllUserSessions: vi.fn(),
}));
vi.mock("@meddoc/ai", () => ({ redactPhi: (value: unknown) => value }));
vi.mock("@/lib/mfa", () => ({
  verifyStoredMfaTotpToken: mocks.verifyStoredTotp,
  findMatchingRecoveryHash: mocks.findRecovery,
}));
vi.mock("@/lib/email-enabled", () => ({
  isEmailVerificationRequired: mocks.verificationRequired,
}));
vi.mock("@/lib/audit", () => ({ logAudit: mocks.logAudit }));
vi.mock("@/lib/credential-session-authority", () => ({
  CredentialSessionAuthorityError: class extends Error {},
  finalizeCredentialSession: mocks.finalizeCredentialSession,
  recordCredentialFailure: mocks.recordCredentialFailure,
}));
vi.mock("@/lib/rate-limit", () => ({
  RATE_LIMITS: {
    LOGIN: { bucket: "synthetic-login", windows: [] },
  },
  checkSharedRateLimit: mocks.checkSharedRateLimit,
  clientIpFromHeaders: mocks.clientIpFromHeaders,
}));
vi.mock("@/lib/signed-session-authority", () => ({
  readSignedSessionAuthority: mocks.readSignedSessionAuthority,
}));

const { auth, handlers } = await import("../nextauth");

function request(requestHeaders: HeadersInit = {}): Request {
  return new Request(
    "https://transport.invalid/api/auth/callback/credentials",
    {
      method: "POST",
      headers: requestHeaders,
    },
  );
}

const credentials = {
  email: "synthetic-user@example.test",
  password: "SyntheticPass123",
};

function currentUser(overrides: Record<string, unknown> = {}) {
  return {
    id: "user-synthetic",
    email: "synthetic-user@example.test",
    name: "Synthetic User",
    role: "DOCTOR",
    practiceId: "practice-synthetic",
    products: ["TRANSCRIBE_MD"],
    passwordHash: "synthetic-password-hash",
    isActive: true,
    suspendedAt: null,
    softDeletedAt: null,
    lockedUntil: null,
    emailVerified: new Date("2020-01-01T00:00:00.000Z"),
    failedLoginCount: 0,
    mfaEnabled: true,
    mfaSecret: "SYNTHETIC-SECRET",
    mfaVerifiedAt: new Date("2020-01-01T00:00:00.000Z"),
    mfaBackupCodes: ["synthetic-recovery-hash"],
    ...overrides,
  };
}

beforeEach(() => {
  vi.clearAllMocks();
  vi.stubEnv("ADMIN_PUBLIC_HOST", "admin.quillmd.com");
  vi.stubEnv("PHYSICIAN_PUBLIC_HOST", "app.quillmd.com");
  vi.stubEnv("AUTH_COOKIE_DOMAIN", "");
  mocks.findUser.mockResolvedValue(null);
  mocks.transaction.mockImplementation(
    async (callback: (tx: object) => Promise<unknown>) => callback({}),
  );
  mocks.finalizeCredentialSession.mockResolvedValue({
    session: { id: "session-row" },
  });
  mocks.recordCredentialFailure.mockResolvedValue({
    recorded: true,
    locked: false,
    failedLoginCount: 1,
  });
  mocks.comparePassword.mockResolvedValue(false);
  mocks.verifyStoredTotp.mockReturnValue(false);
  mocks.findRecovery.mockReturnValue(null);
  mocks.verificationRequired.mockReturnValue(false);
  mocks.checkSharedRateLimit.mockResolvedValue({
    allowed: true,
    retryAfterSec: 0,
  });
  mocks.clientIpFromHeaders.mockReturnValue("192.0.2.44");
  mocks.readSignedSessionAuthority.mockResolvedValue({
    cookiePresent: false,
    sessionId: null,
    userId: null,
  });
  mocks.revokeSession.mockResolvedValue(undefined);
  mocks.rawAuth.mockResolvedValue({
    user: { id: "user-synthetic", sessionId: "session-synthetic" },
  });
  mocks.authGet.mockResolvedValue(new Response(null, { status: 204 }));
  mocks.authPost.mockResolvedValue(new Response(null, { status: 204 }));
  mocks.requestHeaders.mockResolvedValue(
    new Headers({ host: "app.quillmd.com" }),
  );
});

afterEach(() => {
  vi.unstubAllEnvs();
});

describe("Credentials provider exact service and host boundary", () => {
  it("denies a direct callback at the shared limiter before user lookup", async () => {
    vi.stubEnv("QUILLMD_SERVICE_ROLE", "physician-app");
    mocks.checkSharedRateLimit.mockResolvedValue({
      allowed: false,
      retryAfterSec: 60,
    });

    await expect(
      mocks.authorize!(
        credentials,
        request({ host: "app.quillmd.com", "x-forwarded-for": "192.0.2.44" }),
      ),
    ).resolves.toBeNull();
    expect(mocks.checkSharedRateLimit).toHaveBeenCalledWith(
      expect.objectContaining({ bucket: "synthetic-login" }),
      "192.0.2.44",
    );
    expect(mocks.findUser).not.toHaveBeenCalled();
    expect(mocks.comparePassword).not.toHaveBeenCalled();
  });

  it("runs the timing equalizer for an unknown account", async () => {
    vi.stubEnv("QUILLMD_SERVICE_ROLE", "physician-app");

    await expect(
      mocks.authorize!(credentials, request({ host: "app.quillmd.com" })),
    ).resolves.toBeNull();
    expect(mocks.comparePassword).toHaveBeenCalledWith(
      credentials.password,
      "synthetic-dummy-hash",
    );
  });

  it("rate-limits and equalizes malformed credentials before database access", async () => {
    vi.stubEnv("QUILLMD_SERVICE_ROLE", "physician-app");

    await expect(
      mocks.authorize!(
        { email: "", password: "" },
        request({ host: "app.quillmd.com" }),
      ),
    ).resolves.toBeNull();
    expect(mocks.checkSharedRateLimit).toHaveBeenCalledOnce();
    expect(mocks.comparePassword).toHaveBeenCalledWith(
      "",
      "synthetic-dummy-hash",
    );
    expect(mocks.findUser).not.toHaveBeenCalled();
  });

  it("logs no driver credential material when lookup fails", async () => {
    vi.stubEnv("QUILLMD_SERVICE_ROLE", "physician-app");
    const consoleError = vi.spyOn(console, "error").mockImplementation(() => {});
    mocks.findUser.mockRejectedValue(
      new Error(
        "synthetic failure postgresql://user:synthetic-secret@db.invalid/auth",
      ),
    );

    await expect(
      mocks.authorize!(credentials, request({ host: "app.quillmd.com" })),
    ).resolves.toBeNull();
    expect(consoleError).toHaveBeenCalledWith(
      "[auth] user lookup failed; login denied",
    );
    expect(JSON.stringify(consoleError.mock.calls)).not.toContain(
      "synthetic-secret",
    );
    expect(mocks.comparePassword).toHaveBeenCalledWith(
      credentials.password,
      "synthetic-dummy-hash",
    );
    consoleError.mockRestore();
  });

  it("denies an unverified production account while email delivery is unavailable", async () => {
    vi.stubEnv("NODE_ENV", "production");
    vi.stubEnv("QUILLMD_SERVICE_ROLE", "physician-app");
    vi.stubEnv("RESEND_API_KEY", "");
    vi.stubEnv("RESEND_FROM_VERIFIED", "false");
    mocks.verificationRequired.mockReturnValue(true);
    mocks.findUser.mockResolvedValue(
      currentUser({ emailVerified: null, mfaEnabled: false }),
    );

    await expect(
      mocks.authorize!(credentials, request({ host: "app.quillmd.com" })),
    ).resolves.toBeNull();
    expect(mocks.comparePassword).toHaveBeenCalledWith(
      credentials.password,
      "synthetic-dummy-hash",
    );
    expect(mocks.finalizeCredentialSession).not.toHaveBeenCalled();
  });

  it.each([
    [
      "physician service on admin host",
      "physician-app",
      { host: "admin.quillmd.com" },
    ],
    [
      "admin service on physician host",
      "template-twin-admin-app",
      { host: "app.quillmd.com" },
    ],
    ["unknown service", "unreviewed-service", { host: "app.quillmd.com" }],
    ["missing Host", "physician-app", {}],
    [
      "forwarded-host spoof",
      "physician-app",
      { host: "unreviewed.invalid", "x-forwarded-host": "app.quillmd.com" },
    ],
  ])("denies %s before user lookup", async (_label, role, requestHeaders) => {
    vi.stubEnv("QUILLMD_SERVICE_ROLE", role);

    await expect(
      mocks.authorize!(credentials, request(requestHeaders)),
    ).resolves.toBeNull();
    expect(mocks.findUser).not.toHaveBeenCalled();
  });

  it.each([
    ["physician", "physician-app", "app.quillmd.com"],
    ["admin", "template-twin-admin-app", "admin.quillmd.com"],
  ])(
    "admits the exact %s origin to credential lookup",
    async (_label, role, host) => {
      vi.stubEnv("QUILLMD_SERVICE_ROLE", role);

      await expect(
        mocks.authorize!(credentials, request({ host })),
      ).resolves.toBeNull();
      expect(mocks.findUser).toHaveBeenCalledTimes(1);
    },
  );

  it.each([
    ["missing secret", { mfaSecret: null }],
    ["blank secret", { mfaSecret: "   " }],
    ["missing verification", { mfaVerifiedAt: null }],
    [
      "future verification",
      { mfaVerifiedAt: new Date("2999-01-01T00:00:00.000Z") },
    ],
  ])("fails closed on %s for an enabled MFA account", async (_label, state) => {
    vi.stubEnv("QUILLMD_SERVICE_ROLE", "physician-app");
    mocks.findUser.mockResolvedValue(currentUser(state));
    mocks.comparePassword.mockResolvedValue(true);

    await expect(
      mocks.authorize!(credentials, request({ host: "app.quillmd.com" })),
    ).resolves.toBeNull();
    expect(mocks.finalizeCredentialSession).not.toHaveBeenCalled();
    expect(mocks.logAudit).toHaveBeenCalledWith(
      expect.objectContaining({ errorCode: "MFA_ENROLLMENT_INCOMPLETE" }),
    );
  });

  it("fails closed when recovery-code consumption and session issuance cannot commit", async () => {
    vi.stubEnv("QUILLMD_SERVICE_ROLE", "physician-app");
    mocks.findUser.mockResolvedValue(currentUser());
    mocks.comparePassword.mockResolvedValue(true);
    mocks.findRecovery.mockReturnValue("synthetic-recovery-hash");
    mocks.finalizeCredentialSession.mockRejectedValue(
      new Error("synthetic database outage"),
    );

    await expect(
      mocks.authorize!(
        { ...credentials, recoveryCode: "synthetic-recovery-code" },
        request({ host: "app.quillmd.com" }),
      ),
    ).resolves.toBeNull();
    expect(mocks.finalizeCredentialSession).toHaveBeenCalledTimes(1);
  });

  it("binds TOTP verification to the exact user and encrypted secret", async () => {
    vi.stubEnv("QUILLMD_SERVICE_ROLE", "physician-app");
    mocks.findUser.mockResolvedValue(
      currentUser({ mfaSecret: "qmfa:v1:synthetic-envelope" }),
    );
    mocks.comparePassword.mockResolvedValue(true);
    mocks.verifyStoredTotp.mockReturnValue(true);

    await expect(
      mocks.authorize!(
        { ...credentials, totpToken: "123456" },
        request({ host: "app.quillmd.com" }),
      ),
    ).resolves.toMatchObject({ id: "user-synthetic" });
    expect(mocks.verifyStoredTotp).toHaveBeenCalledWith(
      "user-synthetic",
      "qmfa:v1:synthetic-envelope",
      "123456",
    );
    expect(mocks.finalizeCredentialSession).toHaveBeenCalledOnce();
  });

  it("denies login when plaintext, unknown-key, or tampered MFA storage fails verification", async () => {
    vi.stubEnv("QUILLMD_SERVICE_ROLE", "physician-app");
    mocks.findUser.mockResolvedValue(currentUser({ mfaSecret: "plaintext" }));
    mocks.comparePassword.mockResolvedValue(true);
    mocks.verifyStoredTotp.mockReturnValue(false);

    await expect(
      mocks.authorize!(
        { ...credentials, totpToken: "123456" },
        request({ host: "app.quillmd.com" }),
      ),
    ).resolves.toBeNull();
    expect(mocks.finalizeCredentialSession).not.toHaveBeenCalled();
    expect(mocks.logAudit).toHaveBeenCalledWith(
      expect.objectContaining({ errorCode: "INVALID_TOTP" }),
    );
  });

  it("permits at most one login when the same recovery code is presented twice", async () => {
    vi.stubEnv("QUILLMD_SERVICE_ROLE", "physician-app");
    mocks.findUser.mockImplementation(async () => currentUser());
    mocks.comparePassword.mockResolvedValue(true);
    mocks.findRecovery.mockReturnValue("synthetic-recovery-hash");
    // The first final transaction consumes the code and creates the session;
    // the replay observes changed MFA state under lock and fails closed.
    mocks.finalizeCredentialSession
      .mockResolvedValueOnce({ session: { id: "session-row" } })
      .mockRejectedValueOnce(new Error("synthetic stale recovery snapshot"));

    const login = () =>
      mocks.authorize!(
        { ...credentials, recoveryCode: "synthetic-recovery-code" },
        request({ host: "app.quillmd.com" }),
      );
    const results = [await login(), await login()];

    expect(results.filter((result) => result !== null)).toHaveLength(1);
    expect(mocks.findUser).toHaveBeenCalledTimes(2);
    expect(mocks.comparePassword).toHaveBeenCalledTimes(2);
    expect(mocks.findRecovery).toHaveBeenCalledTimes(2);
    expect(mocks.finalizeCredentialSession).toHaveBeenCalledTimes(2);
  });
});

describe("raw session exact service and host boundary", () => {
  it.each([
    ["physician", "physician-app", "app.quillmd.com"],
    ["admin", "template-twin-admin-app", "admin.quillmd.com"],
    ["control", "template-twin-admin-control", "admin.quillmd.com"],
  ])("admits the exact %s process/origin pair", async (_label, role, host) => {
    vi.stubEnv("QUILLMD_SERVICE_ROLE", role);
    mocks.requestHeaders.mockResolvedValue(new Headers({ host }));

    await expect(auth()).resolves.toMatchObject({
      user: { id: "user-synthetic" },
    });
    expect(mocks.rawAuth).toHaveBeenCalledTimes(1);
  });

  it.each([
    ["physician on admin host", "physician-app", "admin.quillmd.com"],
    ["admin on physician host", "template-twin-admin-app", "app.quillmd.com"],
    [
      "control on physician host",
      "template-twin-admin-control",
      "app.quillmd.com",
    ],
    ["unknown process", "unreviewed-service", "app.quillmd.com"],
  ])(
    "denies %s before Auth.js session resolution",
    async (_label, role, host) => {
      vi.stubEnv("QUILLMD_SERVICE_ROLE", role);
      mocks.requestHeaders.mockResolvedValue(new Headers({ host }));

      await expect(auth()).resolves.toBeNull();
      expect(mocks.rawAuth).not.toHaveBeenCalled();
    },
  );

  it("fails closed when no request header context exists", async () => {
    vi.stubEnv("QUILLMD_SERVICE_ROLE", "physician-app");
    mocks.requestHeaders.mockRejectedValue(
      new Error("synthetic non-request context"),
    );

    await expect(auth()).resolves.toBeNull();
    expect(mocks.rawAuth).not.toHaveBeenCalled();
  });

  it("fences Auth.js HTTP handlers before cookie resolution", async () => {
    vi.stubEnv("QUILLMD_SERVICE_ROLE", "physician-app");
    const denied = await handlers.GET(
      new NextRequest("https://admin.quillmd.com/api/auth/session", {
        headers: { host: "admin.quillmd.com" },
      }),
    );
    expect(denied.status).toBe(404);
    expect(mocks.authGet).not.toHaveBeenCalled();

    const admittedRequest = new NextRequest(
      "https://app.quillmd.com/api/auth/session",
      { headers: { host: "app.quillmd.com" } },
    );
    await expect(handlers.GET(admittedRequest)).resolves.toMatchObject({
      status: 204,
    });
    expect(mocks.authGet).toHaveBeenCalledWith(admittedRequest);
  });

  it("does not clear a raw sign-out cookie when durable revocation fails", async () => {
    vi.stubEnv("QUILLMD_SERVICE_ROLE", "physician-app");
    mocks.readSignedSessionAuthority.mockResolvedValue({
      cookiePresent: true,
      sessionId: "session-synthetic",
      userId: "user-synthetic",
    });
    mocks.revokeSession.mockRejectedValue(
      new Error("synthetic database outage with secret material"),
    );
    const consoleError = vi.spyOn(console, "error").mockImplementation(() => {});
    const signOutRequest = new NextRequest(
      "https://app.quillmd.com/api/auth/signout",
      {
        method: "POST",
        headers: { host: "app.quillmd.com" },
      },
    );

    const response = await handlers.POST(signOutRequest);

    expect(response.status).toBe(503);
    expect(response.headers.get("set-cookie")).toBeNull();
    expect(mocks.authPost).not.toHaveBeenCalled();
    expect(consoleError).toHaveBeenCalledWith(
      "[auth:signOut] durable pre-revocation failed",
    );
    expect(JSON.stringify(consoleError.mock.calls)).not.toContain(
      "secret material",
    );
    consoleError.mockRestore();
  });

  it("revokes a raw sign-out session before Auth.js clears its cookie", async () => {
    vi.stubEnv("QUILLMD_SERVICE_ROLE", "physician-app");
    mocks.readSignedSessionAuthority.mockResolvedValue({
      cookiePresent: true,
      sessionId: "session-synthetic",
      userId: "user-synthetic",
    });
    const signOutRequest = new NextRequest(
      "https://app.quillmd.com/api/auth/signout",
      {
        method: "POST",
        headers: { host: "app.quillmd.com" },
      },
    );

    await expect(handlers.POST(signOutRequest)).resolves.toMatchObject({
      status: 204,
    });
    expect(mocks.revokeSession).toHaveBeenCalledWith("session-synthetic");
    expect(mocks.revokeSession.mock.invocationCallOrder[0]).toBeLessThan(
      mocks.authPost.mock.invocationCallOrder[0]!,
    );
  });
});
