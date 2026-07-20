import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";

const mocks = vi.hoisted(() => ({
  deliveryEnabled: vi.fn(),
  enqueue: vi.fn(),
  logInfo: vi.fn(),
}));

vi.mock("@/lib/email-enabled", () => ({
  isEmailDeliveryEnabled: mocks.deliveryEnabled,
}));
vi.mock("@prisma/client", () => ({
  AuthEmailPurpose: {
    PASSWORD_RESET: "PASSWORD_RESET",
    EMAIL_VERIFICATION: "EMAIL_VERIFICATION",
  },
}));
vi.mock("@/lib/auth-email-outbox", () => ({
  enqueueAuthEmailRequest: mocks.enqueue,
}));
vi.mock("@/lib/rate-limit", () => ({
  RATE_LIMITS: { AUTH_EMAIL: {} },
  clientIpFromRequest: vi.fn(() => "192.0.2.3"),
  sharedRateLimitOr429: vi.fn(async () => null),
}));
vi.mock("@/lib/log", () => ({ log: { info: mocks.logInfo } }));

import { POST as forgotPassword } from "@/app/api/auth/forgot-password/route";
import { POST as resendVerification } from "@/app/api/auth/resend-verification/route";

function request(path: string): NextRequest {
  return new NextRequest(`https://app.quillmd.com${path}`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ email: "doctor@synthetic.invalid" }),
  });
}

beforeEach(() => {
  vi.clearAllMocks();
  mocks.deliveryEnabled.mockReturnValue(false);
  mocks.enqueue.mockResolvedValue(undefined);
});

describe("auth email delivery gate", () => {
  it.each([
    ["forgot password", forgotPassword, "/api/auth/forgot-password"],
    [
      "resend verification",
      resendVerification,
      "/api/auth/resend-verification",
    ],
  ])(
    "%s returns generic 200 without enqueueing when delivery is disabled",
    async (_label, handler, path) => {
      const response = await handler(request(path), {
        params: Promise.resolve({}),
      });

      expect(response.status).toBe(200);
      expect(mocks.enqueue).not.toHaveBeenCalled();
      expect(response.headers.get("X-Response-Time")).toBeNull();
      expect(response.headers.get("Server-Timing")).toBeNull();
    },
  );

  it("durably enqueues resend verification with the normalized email", async () => {
    mocks.deliveryEnabled.mockReturnValueOnce(true);

    const response = await resendVerification(
      request("/api/auth/resend-verification"),
      { params: Promise.resolve({}) },
    );

    expect(response.status).toBe(200);
    expect(mocks.enqueue).toHaveBeenCalledWith({
      email: "doctor@synthetic.invalid",
      purpose: "EMAIL_VERIFICATION",
    });
    expect(response.headers.get("X-Response-Time")).toBeNull();
    expect(response.headers.get("Server-Timing")).toBeNull();
  });

  it("durably enqueues password reset with the normalized email", async () => {
    mocks.deliveryEnabled.mockReturnValueOnce(true);

    const response = await forgotPassword(
      request("/api/auth/forgot-password"),
      { params: Promise.resolve({}) },
    );

    expect(response.status).toBe(200);
    expect(mocks.enqueue).toHaveBeenCalledWith({
      email: "doctor@synthetic.invalid",
      purpose: "PASSWORD_RESET",
    });
    expect(response.headers.get("X-Response-Time")).toBeNull();
    expect(response.headers.get("Server-Timing")).toBeNull();
  });

  it.each([
    ["forgot password", forgotPassword, "/api/auth/forgot-password"],
    [
      "resend verification",
      resendVerification,
      "/api/auth/resend-verification",
    ],
  ])(
    "%s keeps enqueue failures generic and free of provider details",
    async (_label, handler, path) => {
      mocks.deliveryEnabled.mockReturnValueOnce(true);
      mocks.enqueue.mockRejectedValueOnce(
        new Error("provider secret doctor@synthetic.invalid"),
      );
      const errorSpy = vi.spyOn(console, "error").mockImplementation(() => {});
      try {
        const response = await handler(request(path), {
          params: Promise.resolve({}),
        });
        const body = await response.text();

        expect(response.status).toBe(200);
        expect(body).not.toContain("provider secret");
        expect(body).not.toContain("doctor@synthetic.invalid");
        expect(response.headers.get("X-Response-Time")).toBeNull();
        expect(response.headers.get("Server-Timing")).toBeNull();
        expect(JSON.stringify(errorSpy.mock.calls)).not.toContain(
          "provider secret",
        );
        expect(errorSpy.mock.calls[0]).toHaveLength(1);
      } finally {
        errorSpy.mockRestore();
      }
    },
  );
});

describe("auth email log and binding source contract", () => {
  const appRoot = resolve(__dirname, "../..");
  const routeSources = [
    "src/app/api/auth/forgot-password/route.ts",
    "src/app/api/auth/resend-verification/route.ts",
    "src/app/api/settings/change-email/route.ts",
  ].map((path) => readFileSync(resolve(appRoot, path), "utf8"));

  it("never sends raw URL/token variables or provider exception content to a logger", () => {
    for (const source of routeSources) {
      const logCalls =
        source.match(/console\.(?:log|info|warn|error)\([\s\S]*?\);/g) ?? [];
      for (const logCall of logCalls) {
        expect(logCall).not.toMatch(/resetUrl|verifyUrl|confirmUrl|\.token/);
      }
      expect(source).not.toMatch(/redactPhi\s*\(/);
    }
  });

  it("uses the transactional outbox for both signup dispositions", () => {
    const source = readFileSync(
      resolve(appRoot, "src/actions/auth.ts"),
      "utf8",
    );
    const signup = source.slice(
      source.indexOf("export async function signupAction"),
    );
    expect(signup).toMatch(
      /enqueueAuthEmailRequestInTransaction\(tx,\s*\{[\s\S]*?email:\s*emailLower,[\s\S]*?purpose:\s*AuthEmailPurpose\.EMAIL_VERIFICATION/,
    );
    expect(signup).toMatch(
      /enqueueAuthEmailRequestInTransaction\(tx,\s*\{[\s\S]*?email:\s*emailLower,[\s\S]*?purpose:\s*AuthEmailPurpose\.ACCOUNT_EXISTS/,
    );
    expect(signup).not.toMatch(
      /createAuthToken|sendEmailVerification|sendAccountExistsEmail/,
    );
  });

  it("binds admin password-reset tokens to the locked account email", () => {
    const source = readFileSync(
      resolve(appRoot, "src/app/api/admin/users/[id]/reset-password/route.ts"),
      "utf8",
    );
    const resetMint = source.slice(
      source.indexOf("purpose: AuthTokenPurpose.PASSWORD_RESET"),
      source.indexOf(
        ");",
        source.indexOf("purpose: AuthTokenPurpose.PASSWORD_RESET"),
      ),
    );
    expect(resetMint).toMatch(/expectedUserEmail:\s*user\.email/);
  });

  it("sanitizes provider failures before logging or rethrowing", () => {
    const source = readFileSync(resolve(appRoot, "src/lib/email.ts"), "utf8");
    const errorLogs = source.match(/console\.error\([\s\S]*?\);/g) ?? [];
    for (const errorLog of errorLogs) {
      expect(errorLog).not.toMatch(/,\s*message\s*\)/);
    }
    expect(source).not.toMatch(/\$\{message\}/);
  });
});
