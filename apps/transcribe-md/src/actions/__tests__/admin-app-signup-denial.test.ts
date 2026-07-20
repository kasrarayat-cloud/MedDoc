import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  findUser: vi.fn(),
  transaction: vi.fn(),
  signIn: vi.fn(),
  headers: vi.fn(),
  rateLimit: vi.fn(),
  deliveryEnabled: vi.fn(),
  verificationRequired: vi.fn(),
  autoConfirm: vi.fn(),
  enqueueAuthEmail: vi.fn(),
  createToken: vi.fn(),
  sendVerification: vi.fn(),
  sendExisting: vi.fn(),
  passwordHash: vi.fn(),
  comparePassword: vi.fn(),
  practiceCreate: vi.fn(),
  userCreate: vi.fn(),
}));

vi.mock("bcryptjs", () => ({
  default: {
    compare: mocks.comparePassword,
    hash: mocks.passwordHash,
    hashSync: vi.fn(() => "synthetic-dummy-password-hash"),
  },
}));

vi.mock("@meddoc/db", () => ({
  default: {
    user: { findUnique: mocks.findUser },
    $transaction: mocks.transaction,
  },
}));
vi.mock("next/headers", () => ({ headers: mocks.headers }));
vi.mock("@/lib/nextauth", () => ({ signIn: mocks.signIn }));
vi.mock("@/lib/auth-tokens", () => ({ createAuthToken: mocks.createToken }));
vi.mock("@/lib/email", () => ({
  sendEmailVerification: mocks.sendVerification,
  sendAccountExistsEmail: mocks.sendExisting,
}));
vi.mock("@/lib/email-enabled", () => ({
  isEmailDeliveryEnabled: mocks.deliveryEnabled,
  isEmailVerificationRequired: mocks.verificationRequired,
}));
vi.mock("@/lib/email-auto-confirm", () => ({
  isAutoConfirmDomain: mocks.autoConfirm,
}));
vi.mock("@/lib/auth-email-outbox", () => ({
  enqueueAuthEmailRequestInTransaction: mocks.enqueueAuthEmail,
}));
vi.mock("@/lib/rate-limit", () => ({
  RATE_LIMITS: {
    SIGNUP: { bucket: "synthetic-signup", windows: [] },
    LOGIN: { bucket: "synthetic-login", windows: [] },
    LOGIN_PREFLIGHT: { bucket: "synthetic-login-preflight", windows: [] },
  },
  checkSharedRateLimit: mocks.rateLimit,
  clientIpFromHeaders: vi.fn(),
}));

import { loginAction, signupAction } from "../auth";

function validSignup(email = "new-physician@example.com"): FormData {
  const form = new FormData();
  form.set("email", email);
  form.set("name", "Synthetic Boundary User");
  form.set("password", "SyntheticPass123");
  form.set("acceptTerms", "on");
  return form;
}

function invalidLogin(): FormData {
  return new FormData();
}

function validLogin(totpToken?: string): FormData {
  const form = new FormData();
  form.set("email", "platform-admin@synthetic.test");
  form.set("password", "SyntheticPass123");
  if (totpToken) form.set("totpToken", totpToken);
  return form;
}

function platformAdmin(overrides: Record<string, unknown> = {}) {
  return {
    id: "platform-admin-synthetic",
    passwordHash: "synthetic-password-hash",
    emailVerified: new Date("2026-07-20T00:00:00.000Z"),
    products: ["SUPER_ADMIN"],
    role: "DOCTOR",
    isActive: true,
    lockedUntil: null,
    mfaEnabled: false,
    mfaSecret: null,
    mfaVerifiedAt: null,
    ...overrides,
  };
}

function physicianAccount(overrides: Record<string, unknown> = {}) {
  return {
    id: "physician-synthetic",
    passwordHash: "synthetic-password-hash",
    emailVerified: new Date("2026-07-20T00:00:00.000Z"),
    products: ["TRANSCRIBE_MD"],
    role: "DOCTOR",
    isActive: true,
    lockedUntil: null,
    mfaEnabled: false,
    mfaSecret: null,
    mfaVerifiedAt: null,
    ...overrides,
  };
}

beforeEach(() => {
  vi.clearAllMocks();
  vi.stubEnv("ADMIN_PUBLIC_HOST", "admin.quillmd.com");
  vi.stubEnv("PHYSICIAN_PUBLIC_HOST", "app.quillmd.com");
  vi.stubEnv("AUTH_COOKIE_DOMAIN", "");
  mocks.headers.mockResolvedValue(new Headers({ host: "app.quillmd.com" }));
  mocks.rateLimit.mockResolvedValue({ allowed: true, retryAfterSec: 0 });
  mocks.deliveryEnabled.mockReturnValue(false);
  mocks.verificationRequired.mockReturnValue(false);
  mocks.autoConfirm.mockReturnValue(false);
  mocks.enqueueAuthEmail.mockResolvedValue(undefined);
  mocks.passwordHash.mockResolvedValue("synthetic-password-hash");
  mocks.comparePassword.mockResolvedValue(false);
  mocks.transaction.mockImplementation(
    async (callback: (tx: unknown) => Promise<unknown>) =>
      callback({
        user: {
          findUnique: mocks.findUser,
          create: mocks.userCreate,
        },
        practice: { create: mocks.practiceCreate },
      }),
  );
});

afterEach(() => {
  vi.unstubAllEnvs();
});

describe("admin-process public-registration denial", () => {
  it("denies the admin service before registration work", async () => {
    vi.stubEnv("QUILLMD_SERVICE_ROLE", "template-twin-admin-app");

    await expect(signupAction(null, validSignup())).resolves.toEqual({
      ok: false,
      errors: { _form: "Public registration is unavailable on this host." },
    });

    expect(mocks.headers).toHaveBeenCalledTimes(1);
    expect(mocks.rateLimit).not.toHaveBeenCalled();
    expect(mocks.findUser).not.toHaveBeenCalled();
    expect(mocks.transaction).not.toHaveBeenCalled();
    expect(mocks.createToken).not.toHaveBeenCalled();
    expect(mocks.sendVerification).not.toHaveBeenCalled();
    expect(mocks.sendExisting).not.toHaveBeenCalled();
    expect(mocks.signIn).not.toHaveBeenCalled();
  });

  it.each([
    ["arbitrary", new Headers({ host: "unreviewed.invalid" })],
    ["missing", new Headers()],
    [
      "forwarded-host spoofed",
      new Headers({
        host: "unreviewed.invalid",
        "x-forwarded-host": "app.quillmd.com",
      }),
    ],
  ])("denies signup on a %s physician-process host", async (_label, h) => {
    vi.stubEnv("QUILLMD_SERVICE_ROLE", "physician-app");
    mocks.headers.mockResolvedValue(h);

    await expect(signupAction(null, validSignup())).resolves.toEqual({
      ok: false,
      errors: { _form: "Public registration is unavailable on this host." },
    });
    expect(mocks.rateLimit).not.toHaveBeenCalled();
    expect(mocks.findUser).not.toHaveBeenCalled();
    expect(mocks.transaction).not.toHaveBeenCalled();
  });

  it("denies signup on an unknown service even with the physician host", async () => {
    vi.stubEnv("QUILLMD_SERVICE_ROLE", "unreviewed-service");

    await expect(signupAction(null, validSignup())).resolves.toEqual({
      ok: false,
      errors: { _form: "Public registration is unavailable on this host." },
    });
    expect(mocks.rateLimit).not.toHaveBeenCalled();
    expect(mocks.findUser).not.toHaveBeenCalled();
  });

  it("denies an admin-host action handled by the ordinary process before any work", async () => {
    vi.stubEnv("QUILLMD_SERVICE_ROLE", "physician-app");
    mocks.headers.mockResolvedValue(new Headers({ host: "admin.quillmd.com" }));

    await expect(signupAction(null, validSignup())).resolves.toEqual({
      ok: false,
      errors: { _form: "Public registration is unavailable on this host." },
    });

    expect(mocks.headers).toHaveBeenCalledTimes(1);
    expect(mocks.rateLimit).not.toHaveBeenCalled();
    expect(mocks.findUser).not.toHaveBeenCalled();
    expect(mocks.transaction).not.toHaveBeenCalled();
    expect(mocks.passwordHash).not.toHaveBeenCalled();
    expect(mocks.createToken).not.toHaveBeenCalled();
    expect(mocks.sendVerification).not.toHaveBeenCalled();
    expect(mocks.sendExisting).not.toHaveBeenCalled();
    expect(mocks.signIn).not.toHaveBeenCalled();
  });

  it("creates a production account pending verification and enqueues the verification email transactionally", async () => {
    vi.stubEnv("QUILLMD_SERVICE_ROLE", "physician-app");
    mocks.deliveryEnabled.mockReturnValue(true);
    mocks.findUser.mockResolvedValue(null);
    mocks.practiceCreate.mockResolvedValue({ id: "practice-synthetic" });
    mocks.userCreate.mockResolvedValue({ id: "user-synthetic" });

    await expect(signupAction(null, validSignup())).resolves.toEqual({
      ok: true,
      redirect: "/check-email",
    });

    expect(mocks.headers).toHaveBeenCalledTimes(2);
    expect(mocks.rateLimit).toHaveBeenCalledTimes(1);
    expect(mocks.findUser).toHaveBeenCalledTimes(1);
    expect(mocks.practiceCreate).toHaveBeenCalledTimes(1);
    expect(mocks.userCreate).toHaveBeenCalledWith(
      expect.objectContaining({
        data: expect.objectContaining({
          practiceId: "practice-synthetic",
          emailVerified: null,
        }),
      }),
    );
    const tx = mocks.enqueueAuthEmail.mock.calls[0]?.[0];
    expect(tx).toEqual(
      expect.objectContaining({
        user: expect.any(Object),
        practice: expect.any(Object),
      }),
    );
    expect(mocks.enqueueAuthEmail).toHaveBeenCalledWith(tx, {
      email: "new-physician@example.com",
      purpose: "EMAIL_VERIFICATION",
    });
    expect(mocks.createToken).not.toHaveBeenCalled();
    expect(mocks.sendVerification).not.toHaveBeenCalled();
    expect(mocks.signIn).not.toHaveBeenCalled();
  });

  it("enqueues ACCOUNT_EXISTS in the same transaction without minting or sending synchronously", async () => {
    vi.stubEnv("QUILLMD_SERVICE_ROLE", "physician-app");
    mocks.deliveryEnabled.mockReturnValue(true);
    mocks.findUser.mockResolvedValue({ id: "existing-user" });

    await expect(signupAction(null, validSignup())).resolves.toEqual({
      ok: true,
      redirect: "/check-email",
    });

    expect(mocks.enqueueAuthEmail).toHaveBeenCalledWith(expect.anything(), {
      email: "new-physician@example.com",
      purpose: "ACCOUNT_EXISTS",
    });
    expect(mocks.practiceCreate).not.toHaveBeenCalled();
    expect(mocks.userCreate).not.toHaveBeenCalled();
    expect(mocks.createToken).not.toHaveBeenCalled();
    expect(mocks.sendExisting).not.toHaveBeenCalled();
    expect(mocks.signIn).not.toHaveBeenCalled();
  });

  it("rejects production signup during delivery outage before creating or auto-verifying", async () => {
    vi.stubEnv("QUILLMD_SERVICE_ROLE", "physician-app");
    mocks.deliveryEnabled.mockReturnValue(false);
    mocks.autoConfirm.mockReturnValue(false);

    await expect(signupAction(null, validSignup())).resolves.toEqual({
      ok: false,
      errors: {
        _form:
          "Account registration is temporarily unavailable. Try again later.",
      },
      values: {
        email: "new-physician@example.com",
        name: "Synthetic Boundary User",
      },
    });

    expect(mocks.transaction).not.toHaveBeenCalled();
    expect(mocks.practiceCreate).not.toHaveBeenCalled();
    expect(mocks.userCreate).not.toHaveBeenCalled();
    expect(mocks.enqueueAuthEmail).not.toHaveBeenCalled();
    expect(mocks.signIn).not.toHaveBeenCalled();
  });

  it("auto-verifies and auto-logs in only under explicit synthetic policy", async () => {
    vi.stubEnv("QUILLMD_SERVICE_ROLE", "physician-app");
    mocks.deliveryEnabled.mockReturnValue(false);
    mocks.autoConfirm.mockReturnValue(true);
    mocks.findUser.mockResolvedValue(null);
    mocks.practiceCreate.mockResolvedValue({ id: "practice-synthetic" });
    mocks.userCreate.mockResolvedValue({ id: "user-synthetic" });
    mocks.signIn.mockResolvedValue(undefined);

    await expect(
      signupAction(null, validSignup("synthetic-qa@synthetic.test")),
    ).resolves.toEqual({
      ok: true,
      redirect: "/dashboard",
    });

    expect(mocks.userCreate).toHaveBeenCalledWith(
      expect.objectContaining({
        data: expect.objectContaining({
          practiceId: "practice-synthetic",
          emailVerified: expect.any(Date),
        }),
      }),
    );
    expect(mocks.enqueueAuthEmail).not.toHaveBeenCalled();
    expect(mocks.createToken).not.toHaveBeenCalled();
    expect(mocks.sendVerification).not.toHaveBeenCalled();
    expect(mocks.signIn).toHaveBeenCalledWith("credentials", {
      redirect: false,
      email: "synthetic-qa@synthetic.test",
      password: "SyntheticPass123",
    });
  });

  it.each([
    ["physician service on admin host", "physician-app", "admin.quillmd.com"],
    [
      "admin service on physician host",
      "template-twin-admin-app",
      "app.quillmd.com",
    ],
    [
      "unknown service on physician host",
      "unreviewed-service",
      "app.quillmd.com",
    ],
    [
      "physician service on arbitrary host",
      "physician-app",
      "unreviewed.invalid",
    ],
  ])("denies login for %s before auth work", async (_label, role, host) => {
    vi.stubEnv("QUILLMD_SERVICE_ROLE", role);
    mocks.headers.mockResolvedValue(new Headers({ host }));

    await expect(loginAction(null, invalidLogin())).resolves.toEqual({
      ok: false,
      errors: { _form: "Sign in is unavailable on this host." },
    });
    expect(mocks.rateLimit).not.toHaveBeenCalled();
    expect(mocks.findUser).not.toHaveBeenCalled();
    expect(mocks.signIn).not.toHaveBeenCalled();
  });

  it.each([
    ["physician", "physician-app", "app.quillmd.com"],
    ["admin", "template-twin-admin-app", "admin.quillmd.com"],
  ])(
    "admits the exact %s login origin to validation",
    async (_label, role, host) => {
      vi.stubEnv("QUILLMD_SERVICE_ROLE", role);
      mocks.headers.mockResolvedValue(new Headers({ host }));

      const result = await loginAction(null, invalidLogin());

      expect(result).toMatchObject({ ok: false });
      expect(mocks.rateLimit).toHaveBeenCalledTimes(1);
    },
  );

  it("denies an unverified production login while email delivery is unavailable", async () => {
    vi.stubEnv("NODE_ENV", "production");
    vi.stubEnv("QUILLMD_SERVICE_ROLE", "physician-app");
    vi.stubEnv("RESEND_API_KEY", "");
    vi.stubEnv("RESEND_FROM_VERIFIED", "false");
    mocks.deliveryEnabled.mockReturnValue(false);
    mocks.verificationRequired.mockReturnValue(true);
    mocks.findUser.mockResolvedValue({
      id: "unverified-user-synthetic",
      passwordHash: "synthetic-password-hash",
      emailVerified: null,
      products: ["TRANSCRIBE_MD"],
      role: "DOCTOR",
      isActive: true,
      lockedUntil: null,
      mfaEnabled: false,
      mfaSecret: null,
      mfaVerifiedAt: null,
    });
    mocks.comparePassword.mockResolvedValue(true);

    await expect(loginAction(null, validLogin())).resolves.toEqual({
      ok: false,
      errors: { _form: "Please verify your email before signing in." },
      values: { email: "platform-admin@synthetic.test" },
      needsVerificationFor: "platform-admin@synthetic.test",
    });
    expect(mocks.signIn).not.toHaveBeenCalled();
  });

  it.each([
    ["unknown", null, false, false, true],
    [
      "inactive",
      physicianAccount({ isActive: false }),
      true,
      false,
      true,
    ],
    [
      "locked",
      physicianAccount({ lockedUntil: new Date("2099-01-01T00:00:00.000Z") }),
      true,
      false,
      true,
    ],
    ["verified and entitled", physicianAccount(), true, false, false],
    [
      "unverified",
      physicianAccount({ emailVerified: null }),
      true,
      true,
      false,
    ],
    [
      "non-entitled",
      physicianAccount({ products: [] }),
      true,
      false,
      false,
    ],
    [
      "MFA-enrolled",
      physicianAccount({
        mfaEnabled: true,
        mfaSecret: "SYNTHETIC-SECRET",
        mfaVerifiedAt: new Date("2026-07-20T00:00:00.000Z"),
      }),
      true,
      false,
      false,
    ],
    ["wrong password", physicianAccount(), false, false, true],
  ])(
    "uses one account lookup and one preflight bcrypt operation for %s",
    async (_label, user, passwordMatches, requireVerification, rejectSignIn) => {
      vi.stubEnv("QUILLMD_SERVICE_ROLE", "physician-app");
      mocks.findUser.mockResolvedValue(user);
      mocks.comparePassword.mockResolvedValue(passwordMatches);
      mocks.verificationRequired.mockReturnValue(requireVerification);
      if (rejectSignIn) {
        mocks.signIn.mockRejectedValue(new Error("synthetic denial"));
      } else {
        mocks.signIn.mockResolvedValue(undefined);
      }

      await loginAction(null, validLogin());

      expect(mocks.findUser).toHaveBeenCalledTimes(1);
      expect(mocks.comparePassword).toHaveBeenCalledTimes(1);
      expect(mocks.comparePassword).toHaveBeenCalledWith(
        "SyntheticPass123",
        user?.passwordHash ?? "synthetic-dummy-password-hash",
      );
    },
  );

  it("routes an unenrolled platform admin to controlled MFA enrollment", async () => {
    vi.stubEnv("QUILLMD_SERVICE_ROLE", "template-twin-admin-app");
    mocks.headers.mockResolvedValue(new Headers({ host: "admin.quillmd.com" }));
    mocks.findUser.mockResolvedValue(platformAdmin());
    mocks.comparePassword.mockResolvedValue(true);
    mocks.signIn.mockResolvedValue(undefined);

    await expect(loginAction(null, validLogin())).resolves.toEqual({
      ok: true,
      redirect: "/settings/security/mfa?reason=super_admin_required",
    });
    expect(mocks.signIn).toHaveBeenCalledTimes(1);
  });

  it("routes a completely enrolled platform admin to exact release control", async () => {
    vi.stubEnv("QUILLMD_SERVICE_ROLE", "template-twin-admin-app");
    mocks.headers.mockResolvedValue(new Headers({ host: "admin.quillmd.com" }));
    mocks.findUser.mockResolvedValue(
      platformAdmin({
        mfaEnabled: true,
        mfaSecret: "SYNTHETIC-SECRET",
        mfaVerifiedAt: new Date("2020-01-01T00:00:00.000Z"),
      }),
    );
    mocks.comparePassword.mockResolvedValue(true);
    mocks.signIn.mockResolvedValue(undefined);

    await expect(loginAction(null, validLogin("123456"))).resolves.toEqual({
      ok: true,
      redirect: "/admin/template-twin-release",
    });
    expect(mocks.signIn).toHaveBeenCalledTimes(1);
  });

  it("fails an inconsistent enabled MFA record closed before sign-in", async () => {
    vi.stubEnv("QUILLMD_SERVICE_ROLE", "template-twin-admin-app");
    mocks.headers.mockResolvedValue(new Headers({ host: "admin.quillmd.com" }));
    mocks.findUser.mockResolvedValue(
      platformAdmin({ mfaEnabled: true, mfaSecret: null }),
    );
    mocks.comparePassword.mockResolvedValue(true);

    await expect(loginAction(null, validLogin())).resolves.toMatchObject({
      ok: false,
      errors: {
        _form: expect.stringContaining("controlled repair"),
      },
    });
    expect(mocks.signIn).not.toHaveBeenCalled();
  });
});
