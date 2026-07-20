import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

type RedisEvent = "error" | "ready";
type ConnectOutcome = "ready" | "fail";

interface FakeRedisClient {
  readonly url: string;
  readonly options: Record<string, unknown>;
  status: string;
  connect: ReturnType<typeof vi.fn>;
  disconnect: ReturnType<typeof vi.fn>;
}

const mocks = vi.hoisted(() => ({
  connectOutcomes: [] as ConnectOutcome[],
  instances: [] as FakeRedisClient[],
}));

vi.mock("ioredis", () => {
  class FakeIORedis {
    status = "wait";
    private readonly handlers = new Map<RedisEvent, Set<() => void>>();

    readonly connect = vi.fn(async () => {
      const outcome = mocks.connectOutcomes.shift() ?? "ready";
      if (outcome === "fail") {
        this.status = "end";
        this.emit("error");
        throw new Error("synthetic transient Redis connect failure");
      }

      this.status = "ready";
      this.emit("ready");
    });

    readonly disconnect = vi.fn(() => {
      this.status = "end";
    });

    constructor(
      readonly url: string,
      readonly options: Record<string, unknown>,
    ) {
      mocks.instances.push(this);
    }

    on(event: RedisEvent, handler: () => void): this {
      const handlers = this.handlers.get(event) ?? new Set<() => void>();
      handlers.add(handler);
      this.handlers.set(event, handlers);
      return this;
    }

    private emit(event: RedisEvent): void {
      for (const handler of this.handlers.get(event) ?? []) handler();
    }
  }

  return { default: FakeIORedis };
});

import {
  __resetAuthRateLimitRedisForTests,
  ensureAuthRateLimitRedisReady,
  getAuthRateLimitRedis,
} from "../auth-rate-limit-redis";

beforeEach(() => {
  __resetAuthRateLimitRedisForTests();
  mocks.connectOutcomes.length = 0;
  mocks.instances.length = 0;
  vi.clearAllMocks();
  vi.stubEnv("REDIS_URL", "redis://synthetic-rate-limit.test:6379/9");
});

afterEach(() => {
  __resetAuthRateLimitRedisForTests();
  vi.unstubAllEnvs();
  vi.restoreAllMocks();
});

describe("authentication rate-limit Redis lifecycle", () => {
  it("keeps command buffering and unbounded retries disabled", () => {
    const redis = getAuthRateLimitRedis();

    expect(redis).toBe(mocks.instances[0]);
    expect(mocks.instances[0]?.url).toBe(
      "redis://synthetic-rate-limit.test:6379/9",
    );
    expect(mocks.instances[0]?.options).toMatchObject({
      lazyConnect: true,
      enableOfflineQueue: false,
      maxRetriesPerRequest: 1,
      connectTimeout: 1_500,
      commandTimeout: 1_500,
    });
    const retryStrategy = mocks.instances[0]?.options.retryStrategy;
    expect(retryStrategy).toBeTypeOf("function");
    expect((retryStrategy as () => null)()).toBeNull();
  });

  it("fails closed during a transient connect failure, then recreates an ended client on a later request", async () => {
    const errorLog = vi.spyOn(console, "error").mockImplementation(() => {});
    mocks.connectOutcomes.push("fail", "ready");

    const first = getAuthRateLimitRedis();
    await expect(ensureAuthRateLimitRedisReady()).rejects.toThrow(
      "synthetic transient Redis connect failure",
    );
    expect(first.status).toBe("end");
    expect(errorLog).toHaveBeenCalledWith(
      "[auth-rate-limit] shared authority unavailable",
    );

    const recovered = await ensureAuthRateLimitRedisReady();

    expect(recovered).not.toBe(first);
    expect(recovered).toBe(mocks.instances[1]);
    expect(recovered.status).toBe("ready");
    expect(mocks.instances).toHaveLength(2);
    expect(mocks.instances[0]?.connect).toHaveBeenCalledTimes(1);
    expect(mocks.instances[1]?.connect).toHaveBeenCalledTimes(1);
    expect(mocks.instances[1]?.options.enableOfflineQueue).toBe(false);
  });

  it("does not replace a non-terminal unready client or admit the request", async () => {
    const redis = getAuthRateLimitRedis();
    redis.status = "connecting";

    await expect(ensureAuthRateLimitRedisReady()).rejects.toThrow(
      "Shared authentication rate-limit authority unavailable.",
    );

    expect(getAuthRateLimitRedis()).toBe(redis);
    expect(mocks.instances).toHaveLength(1);
    expect(mocks.instances[0]?.connect).not.toHaveBeenCalled();
  });
});
