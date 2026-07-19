import { createHash } from "node:crypto";

import { NextResponse } from "next/server";

import { getRedis } from "@/lib/redis";

const SECOND_MS = 1_000;
const REDIS_FAILURE_RETRY_SECONDS = 5;
const REDIS_READY_WAIT_MS = 2_000;

/**
 * Mapping saves are deliberately isolated from the SETTINGS limiter. A normal
 * certification pass can save all eight reviewed fields and retry mistakes,
 * while the short windows still stop a runaway browser loop. There is no
 * hourly window that can strand a physician for the rest of a session.
 */
export const TEMPLATE_TWIN_MAPPING_SAVE_WINDOWS = [
  { label: "burst_30s", limit: 24, windowMs: 30 * SECOND_MS },
  { label: "sustained_5min", limit: 120, windowMs: 5 * 60 * SECOND_MS },
] as const;

type RateLimitEnvironment = Readonly<Record<string, string | undefined>>;

export interface TemplateTwinMappingSaveRedisClient {
  readonly status?: string;
  eval(
    script: string,
    numberOfKeys: number,
    ...args: string[]
  ): Promise<unknown>;
  once?(
    event: "ready" | "error" | "end",
    listener: (...args: unknown[]) => void,
  ): unknown;
  removeListener?(
    event: "ready" | "error" | "end",
    listener: (...args: unknown[]) => void,
  ): unknown;
}

export type TemplateTwinMappingSaveRateLimitResult =
  | { allowed: true }
  | {
      allowed: false;
      reason: "limited";
      retryAfterSec: number;
      resetAtMs: number;
      limitType: string;
    }
  | {
      allowed: false;
      reason: "unavailable";
      retryAfterSec: number;
    };

/**
 * Atomically checks every fixed window, then increments all of them only when
 * all would allow the request. Redis TIME is the clock authority, so every app
 * replica returns the same reset instant and a skewed web-process clock cannot
 * shorten Retry-After. Keys always have a TTL and share a Redis Cluster hash
 * tag, although today's task-scoped Redis is a standalone instance.
 */
const CONSUME_MAPPING_SAVE_SLOT_LUA = String.raw`
local redisTime = redis.call("TIME")
local nowMs = (tonumber(redisTime[1]) * 1000) + math.floor(tonumber(redisTime[2]) / 1000)
local latestResetAtMs = 0
local latestBlockedIndex = 0

for index = 1, #KEYS do
  local limit = tonumber(ARGV[((index - 1) * 2) + 1])
  local windowMs = tonumber(ARGV[((index - 1) * 2) + 2])
  local count = tonumber(redis.call("GET", KEYS[index]) or "0")
  local ttlMs = redis.call("PTTL", KEYS[index])

  if ttlMs <= 0 then
    count = 0
    ttlMs = windowMs
  end

  if count >= limit then
    local resetAtMs = nowMs + ttlMs
    if resetAtMs > latestResetAtMs then
      latestResetAtMs = resetAtMs
      latestBlockedIndex = index
    end
  end
end

if latestBlockedIndex > 0 then
  return {0, latestResetAtMs, latestBlockedIndex, nowMs}
end

for index = 1, #KEYS do
  local windowMs = tonumber(ARGV[((index - 1) * 2) + 2])
  local ttlMs = redis.call("PTTL", KEYS[index])

  if ttlMs <= 0 then
    redis.call("SET", KEYS[index], "1", "PX", windowMs)
  else
    redis.call("INCR", KEYS[index])
  end
end

return {1, 0, 0, nowMs}
`;

function digest(value: string): string {
  return createHash("sha256").update(value).digest("hex").slice(0, 32);
}

function publicUrlIdentity(raw: string | undefined): string {
  if (!raw) return "unset";
  try {
    const parsed = new URL(raw);
    return `${parsed.protocol}//${parsed.hostname}:${parsed.port || "default"}${parsed.pathname}`;
  } catch {
    return "invalid";
  }
}

function databaseIdentity(raw: string | undefined): string {
  if (!raw) return "unset";
  try {
    const parsed = new URL(raw);
    return `${parsed.hostname}:${parsed.port || "default"}${parsed.pathname}`;
  } catch {
    return "invalid";
  }
}

function redisIdentity(raw: string | undefined): string {
  if (!raw) return "default";
  try {
    const parsed = new URL(raw);
    return `${parsed.protocol}//${parsed.hostname}:${parsed.port || "default"}${parsed.pathname}`;
  } catch {
    return "invalid";
  }
}

/**
 * The digest keeps credentials and internal resource names out of Redis keys.
 * APP_VERSION gives an audited staging deployment its exact-head scope, while
 * the public origin and isolated database identities distinguish two tasks
 * running the same SHA. Replicas of one deployment resolve the same scope.
 */
function deploymentScope(env: RateLimitEnvironment): string {
  return digest(
    JSON.stringify({
      appVersion: env.APP_VERSION?.trim() || "unversioned",
      environment:
        env.TEMPLATE_TWIN_STAGING_QA_ENVIRONMENT?.trim() ||
        env.APP_ENV?.trim() ||
        env.NODE_ENV?.trim() ||
        "unknown",
      publicOrigin: publicUrlIdentity(
        env.AUTH_URL ||
          env.NEXTAUTH_URL ||
          env.NEXT_PUBLIC_TRANSCRIBE_MD_APP_URL,
      ),
      database: databaseIdentity(env.DATABASE_URL),
      redis: redisIdentity(env.REDIS_URL),
    }),
  );
}

function redisKeys(userId: string, env: RateLimitEnvironment): string[] {
  const scope = deploymentScope(env);
  const user = digest(userId);
  const hashTag = `{${scope}:${user}}`;
  return TEMPLATE_TWIN_MAPPING_SAVE_WINDOWS.map(
    (window) =>
      `rate-limit:template-twin:mapping-save:v1:${hashTag}:${window.label}`,
  );
}

/**
 * The shared ioredis client intentionally disables its offline queue, so a
 * command issued during the initial TCP handshake is rejected immediately.
 * Mapping saves wait only for that bounded cold-start handshake. An actual
 * outage still fails closed and never falls back to process memory.
 */
async function waitForRedisReady(
  redis: TemplateTwinMappingSaveRedisClient,
): Promise<void> {
  if (redis.status === undefined || redis.status === "ready") return;
  if (!redis.once || !redis.removeListener) {
    throw new Error("Redis client cannot report readiness");
  }

  await new Promise<void>((resolve, reject) => {
    let settled = false;
    const finish = (error?: Error) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      redis.removeListener?.("ready", onReady);
      redis.removeListener?.("error", onFailure);
      redis.removeListener?.("end", onFailure);
      if (error) reject(error);
      else resolve();
    };
    const onReady = () => finish();
    const onFailure = () => finish(new Error("Redis did not become ready"));
    const timer = setTimeout(
      () => finish(new Error("Redis readiness timed out")),
      REDIS_READY_WAIT_MS,
    );

    redis.once?.("ready", onReady);
    redis.once?.("error", onFailure);
    redis.once?.("end", onFailure);
    // Close the event-registration race if ioredis became ready between the
    // function's first status read and the listeners above.
    if (redis.status === "ready") finish();
  });
}

function parseRedisReply(raw: unknown):
  | { allowed: true }
  | {
      allowed: false;
      resetAtMs: number;
      nowMs: number;
      windowIndex: number;
    }
  | null {
  if (!Array.isArray(raw) || raw.length !== 4) return null;
  const values = raw.map((value) => Number(value));
  if (values.some((value) => !Number.isSafeInteger(value))) return null;
  const [allowed, resetAtMs, windowIndex, nowMs] = values as [
    number,
    number,
    number,
    number,
  ];
  if (allowed === 1 && resetAtMs === 0 && windowIndex === 0 && nowMs > 0) {
    return { allowed: true };
  }
  if (
    allowed === 0 &&
    resetAtMs > nowMs &&
    nowMs > 0 &&
    windowIndex >= 1 &&
    windowIndex <= TEMPLATE_TWIN_MAPPING_SAVE_WINDOWS.length
  ) {
    return { allowed: false, resetAtMs, nowMs, windowIndex };
  }
  return null;
}

export async function checkTemplateTwinMappingSaveRateLimit(
  userId: string,
  options: {
    redis?: TemplateTwinMappingSaveRedisClient;
    env?: RateLimitEnvironment;
  } = {},
): Promise<TemplateTwinMappingSaveRateLimitResult> {
  if (!userId.trim()) {
    return {
      allowed: false,
      reason: "unavailable",
      retryAfterSec: REDIS_FAILURE_RETRY_SECONDS,
    };
  }

  const env = options.env ?? process.env;
  const keys = redisKeys(userId, env);
  const args = TEMPLATE_TWIN_MAPPING_SAVE_WINDOWS.flatMap((window) => [
    String(window.limit),
    String(window.windowMs),
  ]);

  try {
    const redis = options.redis ?? getRedis();
    await waitForRedisReady(redis);
    const raw = await redis.eval(
      CONSUME_MAPPING_SAVE_SLOT_LUA,
      keys.length,
      ...keys,
      ...args,
    );
    const parsed = parseRedisReply(raw);
    if (!parsed) throw new Error("invalid Redis rate-limit response");
    if (parsed.allowed) return parsed;

    const window = TEMPLATE_TWIN_MAPPING_SAVE_WINDOWS[parsed.windowIndex - 1];
    if (!window) throw new Error("invalid Redis rate-limit window");
    return {
      allowed: false,
      reason: "limited",
      retryAfterSec: Math.max(
        1,
        Math.ceil((parsed.resetAtMs - parsed.nowMs) / SECOND_MS),
      ),
      resetAtMs: parsed.resetAtMs,
      limitType: window.label,
    };
  } catch {
    // Never include a Redis error, URL, key, or user identifier here. A Redis
    // outage must fail closed without leaking task credentials into logs.
    console.error(
      "[template-twin-mapping-rate-limit] Redis check failed; mapping save denied.",
    );
    return {
      allowed: false,
      reason: "unavailable",
      retryAfterSec: REDIS_FAILURE_RETRY_SECONDS,
    };
  }
}

/** Route-handler adapter. Returns null only after Redis atomically reserves a slot. */
export async function templateTwinMappingSaveRateLimitOrError(
  userId: string,
): Promise<NextResponse | null> {
  const result = await checkTemplateTwinMappingSaveRateLimit(userId);
  if (result.allowed) return null;

  if (result.reason === "limited") {
    return NextResponse.json(
      {
        ok: false,
        code: "RATE_LIMITED",
        error:
          "Mapping saves are temporarily limited. Your draft is safe; retry when the countdown reaches zero.",
        retryAfterSec: result.retryAfterSec,
        limitType: result.limitType,
        resetAtIso: new Date(result.resetAtMs).toISOString(),
      },
      {
        status: 429,
        headers: {
          "Cache-Control": "no-store, private",
          "Retry-After": String(result.retryAfterSec),
        },
      },
    );
  }

  return NextResponse.json(
    {
      ok: false,
      code: "RATE_LIMIT_UNAVAILABLE",
      error:
        "Mapping saves are temporarily unavailable because the safety limiter could not be verified. Your draft is safe; retry shortly.",
      retryAfterSec: result.retryAfterSec,
    },
    {
      status: 503,
      headers: {
        "Cache-Control": "no-store, private",
        "Retry-After": String(result.retryAfterSec),
      },
    },
  );
}
