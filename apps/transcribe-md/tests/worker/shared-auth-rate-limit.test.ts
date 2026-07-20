import crypto from "node:crypto";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  ensureReady: vi.fn(),
  eval: vi.fn(),
}));

vi.mock("@/lib/auth-rate-limit-redis", () => ({
  ensureAuthRateLimitRedisReady: mocks.ensureReady,
}));

import {
  RATE_LIMITS,
  checkSharedRateLimit,
  sharedRateLimitOr429,
} from "@/lib/rate-limit";

beforeEach(() => {
  vi.clearAllMocks();
  vi.stubEnv("NODE_ENV", "production");
  vi.stubEnv("RATE_LIMIT_DISABLED", "false");
  vi.stubEnv("RATE_LIMIT_DISABLE_ALLOW_IN_PROD", "false");
  mocks.ensureReady.mockResolvedValue({ eval: mocks.eval });
});

afterEach(() => {
  vi.unstubAllEnvs();
});

describe("shared authentication rate limit", () => {
  it("does not honor both bypass flags outside the exact isolated QA profile", async () => {
    vi.stubEnv("RATE_LIMIT_DISABLED", "true");
    vi.stubEnv("RATE_LIMIT_DISABLE_ALLOW_IN_PROD", "true");
    mocks.ensureReady.mockRejectedValueOnce(new Error("synthetic outage"));

    await expect(
      checkSharedRateLimit(RATE_LIMITS.AUTH_EMAIL, "192.0.2.40"),
    ).resolves.toMatchObject({
      allowed: false,
      limitType: "shared_limiter_unavailable",
    });
    expect(mocks.ensureReady).toHaveBeenCalledTimes(1);
  });

  it("honors the bypass only under the exact attested localhost QA profile", async () => {
    vi.stubEnv("RATE_LIMIT_DISABLED", "true");
    vi.stubEnv("RATE_LIMIT_DISABLE_ALLOW_IN_PROD", "true");
    vi.stubEnv("QUILLMD_SERVICE_ROLE", "physician-app");
    vi.stubEnv("TEMPLATE_TWIN_STORAGE_PROFILE", "qa");
    vi.stubEnv(
      "ADMIN_SYNTHETIC_QA_SHARED_HOST_ATTESTATION",
      "accepted-isolated-synthetic-qa-shared-host",
    );
    vi.stubEnv("ADMIN_PUBLIC_HOST", "localhost");
    vi.stubEnv("PHYSICIAN_PUBLIC_HOST", "localhost");
    vi.stubEnv("AUTH_URL", "http://localhost:9020");
    vi.stubEnv("NEXTAUTH_URL", "http://localhost:9020");

    await expect(
      checkSharedRateLimit(RATE_LIMITS.AUTH_EMAIL, "192.0.2.41"),
    ).resolves.toEqual({ allowed: true, retryAfterSec: 0 });
    expect(mocks.ensureReady).not.toHaveBeenCalled();
  });

  it("fails closed when the shared Redis authority is unavailable", async () => {
    mocks.ensureReady.mockRejectedValueOnce(new Error("synthetic outage"));

    const result = await checkSharedRateLimit(
      RATE_LIMITS.AUTH_EMAIL,
      "192.0.2.44",
    );

    expect(result).toMatchObject({
      allowed: false,
      retryAfterSec: 60,
      limitType: "shared_limiter_unavailable",
    });
    expect(result.resetAtMs).toEqual(expect.any(Number));
  });

  it("fails closed on a malformed shared-authority response", async () => {
    mocks.eval.mockResolvedValueOnce({ unexpected: true });

    const result = await checkSharedRateLimit(
      RATE_LIMITS.AUTH_EMAIL,
      "192.0.2.45",
    );

    expect(result).toMatchObject({
      allowed: false,
      retryAfterSec: 60,
      limitType: "shared_limiter_unavailable",
    });
  });

  it("surfaces shared-authority outage as a bounded fail-closed 429", async () => {
    mocks.ensureReady.mockRejectedValueOnce(new Error("synthetic outage"));

    const response = await sharedRateLimitOr429(
      RATE_LIMITS.AUTH_EMAIL,
      "192.0.2.47",
    );

    expect(response?.status).toBe(429);
    expect(response?.headers.get("Retry-After")).toBe("60");
    expect(response?.headers.get("X-RateLimit-Limit-Type")).toBe(
      "shared_limiter_unavailable",
    );
    await expect(response?.json()).resolves.toMatchObject({
      ok: false,
      code: "RATE_LIMITED",
      retryAfterSec: 60,
      limitType: "shared_limiter_unavailable",
    });
  });

  it("hashes the identifier before constructing the shared Redis key", async () => {
    const identifier = "doctor@synthetic.invalid";
    const identifierHash = crypto
      .createHash("sha256")
      .update(identifier)
      .digest("hex");
    mocks.eval.mockResolvedValueOnce([1, 0, 0]);

    await expect(
      checkSharedRateLimit(RATE_LIMITS.AUTH_EMAIL, identifier),
    ).resolves.toEqual({ allowed: true, retryAfterSec: 0 });

    const evalArgs = mocks.eval.mock.calls[0] ?? [];
    expect(evalArgs).toContain(
      `quillmd:rate-limit:v1:auth-email:3600000:${identifierHash}`,
    );
    expect(JSON.stringify(evalArgs)).not.toContain(identifier);
  });

  it("returns bounded retry metadata and a structured 429", async () => {
    mocks.eval.mockResolvedValueOnce([0, 1_500, 1]);

    const response = await sharedRateLimitOr429(
      RATE_LIMITS.AUTH_EMAIL,
      "192.0.2.46",
    );

    expect(response?.status).toBe(429);
    expect(response?.headers.get("Retry-After")).toBe("2");
    expect(response?.headers.get("X-RateLimit-Limit-Type")).toBe("hourly");
    expect(response?.headers.get("X-RateLimit-Reset")).toBeTruthy();
    await expect(response?.json()).resolves.toMatchObject({
      ok: false,
      code: "RATE_LIMITED",
      retryAfterSec: 2,
      limitType: "hourly",
    });
  });
});

describe("shared Redis client bounded-failure contract", () => {
  const source = readFileSync(
    resolve(__dirname, "../../src/lib/auth-rate-limit-redis.ts"),
    "utf8",
  );

  it("disables offline queueing and bounds connection and command retries", () => {
    expect(source).toMatch(/lazyConnect:\s*true/);
    expect(source).toMatch(/enableOfflineQueue:\s*false/);
    expect(source).toMatch(/maxRetriesPerRequest:\s*1/);
    expect(source).toMatch(/connectTimeout:\s*1_500/);
    expect(source).toMatch(/commandTimeout:\s*1_500/);
    expect(source).toMatch(/retryStrategy:\s*\(\)\s*=>\s*null/);
  });

  it("logs only a fixed shared-authority failure message", () => {
    const errorHandler = source.slice(
      source.indexOf('nextClient.on("error"'),
      source.indexOf('nextClient.on("ready"'),
    );
    expect(errorHandler).toContain(
      'console.error("[auth-rate-limit] shared authority unavailable")',
    );
    expect(errorHandler).not.toMatch(/console\.error\([^)]*,/);
  });
});
