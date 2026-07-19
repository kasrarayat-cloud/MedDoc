import { EventEmitter } from "node:events";

import { beforeEach, describe, expect, it, vi } from "vitest";

const redisSingleton = vi.hoisted(() => ({
  status: "ready",
  eval: vi.fn(),
}));

vi.mock("@/lib/redis", () => ({
  getRedis: () => redisSingleton,
}));

import {
  TEMPLATE_TWIN_MAPPING_SAVE_WINDOWS,
  checkTemplateTwinMappingSaveRateLimit,
  templateTwinMappingSaveRateLimitOrError,
  type TemplateTwinMappingSaveRedisClient,
} from "@/lib/template-twin/mapping-save-rate-limit";

const START_MS = Date.parse("2026-07-19T02:03:04.250Z");
const QA_ENV = {
  APP_VERSION: "b46c62f97544a0193c60929d5ac8e8870b20dc4b",
  NODE_ENV: "production",
  TEMPLATE_TWIN_STAGING_QA_ENVIRONMENT: "qa",
  AUTH_URL: "https://founder:secret@staging.quillmd.com:19021/certify",
  DATABASE_URL:
    "postgresql://qa-user:db-secret@postgres:5432/meddoc_tt_qa_task?schema=public",
  REDIS_URL: "redis://redis-secret@redis:6379/15",
} as const;

type StoredWindow = { count: number; resetAtMs: number };

class AtomicRedisFake implements TemplateTwinMappingSaveRedisClient {
  readonly calls: Array<{
    script: string;
    numberOfKeys: number;
    args: string[];
  }> = [];

  readonly windows = new Map<string, StoredWindow>();

  constructor(public nowMs = START_MS) {}

  advance(milliseconds: number) {
    this.nowMs += milliseconds;
  }

  async eval(
    script: string,
    numberOfKeys: number,
    ...args: string[]
  ): Promise<unknown> {
    this.calls.push({ script, numberOfKeys, args });
    const keys = args.slice(0, numberOfKeys);
    const windowArgs = args.slice(numberOfKeys);
    let latestResetAtMs = 0;
    let latestBlockedIndex = 0;

    for (let index = 0; index < keys.length; index += 1) {
      const key = keys[index]!;
      const limit = Number(windowArgs[index * 2]);
      const windowMs = Number(windowArgs[index * 2 + 1]);
      const existing = this.windows.get(key);
      const active =
        existing && existing.resetAtMs > this.nowMs ? existing : undefined;
      const count = active?.count ?? 0;
      const resetAtMs = active?.resetAtMs ?? this.nowMs + windowMs;
      if (count >= limit && resetAtMs > latestResetAtMs) {
        latestResetAtMs = resetAtMs;
        latestBlockedIndex = index + 1;
      }
    }

    if (latestBlockedIndex > 0) {
      return [0, latestResetAtMs, latestBlockedIndex, this.nowMs];
    }

    for (let index = 0; index < keys.length; index += 1) {
      const key = keys[index]!;
      const windowMs = Number(windowArgs[index * 2 + 1]);
      const existing = this.windows.get(key);
      if (!existing || existing.resetAtMs <= this.nowMs) {
        this.windows.set(key, {
          count: 1,
          resetAtMs: this.nowMs + windowMs,
        });
      } else {
        existing.count += 1;
      }
    }

    return [1, 0, 0, this.nowMs];
  }
}

class ConnectingRedisFake
  extends EventEmitter
  implements TemplateTwinMappingSaveRedisClient
{
  status = "connecting";
  readonly eval = vi.fn().mockResolvedValue([1, 0, 0, START_MS]);

  becomeReady() {
    this.status = "ready";
    this.emit("ready");
  }
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("Template Twin mapping-save Redis limiter", () => {
  it("defines mapping-only short windows with no hourly lockout", () => {
    expect(TEMPLATE_TWIN_MAPPING_SAVE_WINDOWS).toEqual([
      { label: "burst_30s", limit: 24, windowMs: 30_000 },
      { label: "sustained_5min", limit: 120, windowMs: 300_000 },
    ]);
  });

  it("allows an eight-field setup plus ordinary retries", async () => {
    const redis = new AtomicRedisFake();

    for (let pass = 1; pass <= 2; pass += 1) {
      for (let field = 1; field <= 8; field += 1) {
        await expect(
          checkTemplateTwinMappingSaveRateLimit("doctor-1", {
            redis,
            env: QA_ENV,
          }),
        ).resolves.toEqual({ allowed: true });
      }
    }

    expect(redis.calls).toHaveLength(16);
    expect(redis.calls.every((call) => call.numberOfKeys === 2)).toBe(true);
  });

  it("admits the first save after a bounded Redis cold-start handshake", async () => {
    const redis = new ConnectingRedisFake();
    const result = checkTemplateTwinMappingSaveRateLimit("doctor-cold-start", {
      redis,
      env: QA_ENV,
    });

    expect(redis.eval).not.toHaveBeenCalled();
    redis.becomeReady();

    await expect(result).resolves.toEqual({ allowed: true });
    expect(redis.eval).toHaveBeenCalledTimes(1);
  });

  it("atomically admits only the burst limit under concurrent requests", async () => {
    const redis = new AtomicRedisFake();

    const results = await Promise.all(
      Array.from({ length: 25 }, () =>
        checkTemplateTwinMappingSaveRateLimit("doctor-concurrent", {
          redis,
          env: QA_ENV,
        }),
      ),
    );

    expect(results.filter((result) => result.allowed)).toHaveLength(24);
    expect(results.filter((result) => !result.allowed)).toEqual([
      {
        allowed: false,
        reason: "limited",
        retryAfterSec: 30,
        resetAtMs: START_MS + 30_000,
        limitType: "burst_30s",
      },
    ]);
    expect(redis.calls).toHaveLength(25);
    expect(
      redis.calls.every(
        (call) =>
          call.script.includes('redis.call("TIME")') &&
          call.script.includes('redis.call("PTTL", KEYS[index])') &&
          call.script.includes('redis.call("INCR", KEYS[index])'),
      ),
    ).toBe(true);
  });

  it("does not partially consume the sustained window when burst rejects", async () => {
    const redis = new AtomicRedisFake();
    for (let index = 0; index < 24; index += 1) {
      await checkTemplateTwinMappingSaveRateLimit("doctor-two-phase", {
        redis,
        env: QA_ENV,
      });
    }

    await checkTemplateTwinMappingSaveRateLimit("doctor-two-phase", {
      redis,
      env: QA_ENV,
    });

    expect([...redis.windows.values()].map((window) => window.count)).toEqual([
      24, 24,
    ]);
    redis.advance(30_001);
    await expect(
      checkTemplateTwinMappingSaveRateLimit("doctor-two-phase", {
        redis,
        env: QA_ENV,
      }),
    ).resolves.toEqual({ allowed: true });
    expect([...redis.windows.values()].map((window) => window.count)).toEqual([
      1, 25,
    ]);
  });

  it("returns the exact Redis reset instant and rounded Retry-After", async () => {
    const redis = new AtomicRedisFake();
    for (let index = 0; index < 24; index += 1) {
      await checkTemplateTwinMappingSaveRateLimit("doctor-retry", {
        redis,
        env: QA_ENV,
      });
    }
    redis.advance(1_250);

    await expect(
      checkTemplateTwinMappingSaveRateLimit("doctor-retry", {
        redis,
        env: QA_ENV,
      }),
    ).resolves.toEqual({
      allowed: false,
      reason: "limited",
      retryAfterSec: 29,
      resetAtMs: START_MS + 30_000,
      limitType: "burst_30s",
    });
  });

  it("selects the later sustained reset when both windows reject", async () => {
    const redis = new AtomicRedisFake();
    for (let batch = 0; batch < 5; batch += 1) {
      for (let index = 0; index < 24; index += 1) {
        await checkTemplateTwinMappingSaveRateLimit("doctor-sustained", {
          redis,
          env: QA_ENV,
        });
      }
      if (batch < 4) redis.advance(30_001);
    }

    await expect(
      checkTemplateTwinMappingSaveRateLimit("doctor-sustained", {
        redis,
        env: QA_ENV,
      }),
    ).resolves.toEqual({
      allowed: false,
      reason: "limited",
      retryAfterSec: 180,
      resetAtMs: START_MS + 300_000,
      limitType: "sustained_5min",
    });
  });

  it("isolates users and deployment scopes without putting secrets in keys", async () => {
    const redis = new AtomicRedisFake();
    await checkTemplateTwinMappingSaveRateLimit("doctor-a@synthetic.test", {
      redis,
      env: QA_ENV,
    });
    await checkTemplateTwinMappingSaveRateLimit("doctor-b@synthetic.test", {
      redis,
      env: QA_ENV,
    });
    await checkTemplateTwinMappingSaveRateLimit("doctor-a@synthetic.test", {
      redis,
      env: { ...QA_ENV, APP_VERSION: "different-exact-head" },
    });

    const keyPairs = redis.calls.map((call) =>
      call.args.slice(0, call.numberOfKeys),
    );
    expect(keyPairs[0]).not.toEqual(keyPairs[1]);
    expect(keyPairs[0]).not.toEqual(keyPairs[2]);
    for (const keys of keyPairs) {
      expect(keys[0]?.match(/\{[^}]+\}/u)?.[0]).toBe(
        keys[1]?.match(/\{[^}]+\}/u)?.[0],
      );
      expect(keys.join(" ")).not.toMatch(
        /synthetic\.test|founder|secret|meddoc_tt_qa_task/u,
      );
    }
  });

  it("fails closed without an in-memory fallback when Redis is unavailable", async () => {
    const errorSpy = vi.spyOn(console, "error").mockImplementation(() => {});
    const redis: TemplateTwinMappingSaveRedisClient = {
      eval: vi.fn().mockRejectedValue(new Error("connection unavailable")),
    };

    await expect(
      checkTemplateTwinMappingSaveRateLimit("doctor-fail-closed", {
        redis,
        env: QA_ENV,
      }),
    ).resolves.toEqual({
      allowed: false,
      reason: "unavailable",
      retryAfterSec: 5,
    });
    await checkTemplateTwinMappingSaveRateLimit("doctor-fail-closed", {
      redis,
      env: QA_ENV,
    });

    expect(redis.eval).toHaveBeenCalledTimes(2);
    expect(errorSpy).toHaveBeenCalledTimes(2);
    expect(errorSpy.mock.calls.flat().join(" ")).not.toContain(
      "connection unavailable",
    );
    errorSpy.mockRestore();
  });

  it("fails closed on a malformed Redis script response", async () => {
    const errorSpy = vi.spyOn(console, "error").mockImplementation(() => {});

    await expect(
      checkTemplateTwinMappingSaveRateLimit("doctor-malformed", {
        redis: { eval: vi.fn().mockResolvedValue([1, 2]) },
        env: QA_ENV,
      }),
    ).resolves.toEqual({
      allowed: false,
      reason: "unavailable",
      retryAfterSec: 5,
    });
    errorSpy.mockRestore();
  });
});

describe("Template Twin mapping-save rate-limit HTTP response", () => {
  it("returns exact structured retry metadata for a limited save", async () => {
    redisSingleton.eval.mockResolvedValue([
      0,
      START_MS + 30_000,
      1,
      START_MS + 1_250,
    ]);

    const response = await templateTwinMappingSaveRateLimitOrError("doctor-1");

    expect(response?.status).toBe(429);
    expect(response?.headers.get("Cache-Control")).toBe("no-store, private");
    expect(response?.headers.get("Retry-After")).toBe("29");
    await expect(response?.json()).resolves.toMatchObject({
      ok: false,
      code: "RATE_LIMITED",
      retryAfterSec: 29,
      limitType: "burst_30s",
      resetAtIso: "2026-07-19T02:03:34.250Z",
    });
  });

  it("returns a retryable 503 instead of allowing an unverifiable save", async () => {
    const errorSpy = vi.spyOn(console, "error").mockImplementation(() => {});
    redisSingleton.eval.mockRejectedValue(new Error("down"));

    const response = await templateTwinMappingSaveRateLimitOrError("doctor-1");

    expect(response?.status).toBe(503);
    expect(response?.headers.get("Retry-After")).toBe("5");
    await expect(response?.json()).resolves.toMatchObject({
      ok: false,
      code: "RATE_LIMIT_UNAVAILABLE",
      retryAfterSec: 5,
      error: expect.stringContaining("safety limiter could not be verified"),
    });
    errorSpy.mockRestore();
  });
});
