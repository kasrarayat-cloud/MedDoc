import "server-only";

import IORedis from "ioredis";

let client: IORedis | null = null;
let errorReported = false;

export function getAuthRateLimitRedis(): IORedis {
  // ioredis cannot reconnect a client after retryStrategy terminates and its
  // lifecycle reaches `end`. Retaining that terminal singleton would make a
  // transient startup/network failure deny authentication until the process
  // restarts. Replace it only on a later request; non-terminal states continue
  // to fail closed in ensureAuthRateLimitRedisReady below.
  if (client?.status === "end") {
    client = null;
    errorReported = false;
  }
  if (client) return client;
  const redisUrl = process.env.REDIS_URL?.trim() || "redis://redis:6379";
  const nextClient = new IORedis(redisUrl, {
    lazyConnect: true,
    enableOfflineQueue: false,
    maxRetriesPerRequest: 1,
    connectTimeout: 1_500,
    commandTimeout: 1_500,
    retryStrategy: () => null,
  });
  client = nextClient;
  nextClient.on("error", () => {
    // An ended instance may emit after a later request has installed its
    // replacement. Stale lifecycle events must not alter the active client's
    // log-suppression state.
    if (client !== nextClient) return;
    if (!errorReported) {
      errorReported = true;
      console.error("[auth-rate-limit] shared authority unavailable");
    }
  });
  nextClient.on("ready", () => {
    if (client !== nextClient) return;
    errorReported = false;
  });
  return nextClient;
}

export async function ensureAuthRateLimitRedisReady(): Promise<IORedis> {
  const redis = getAuthRateLimitRedis();
  if (redis.status === "wait") await redis.connect();
  if (redis.status !== "ready") {
    throw new Error("Shared authentication rate-limit authority unavailable.");
  }
  return redis;
}

export function __resetAuthRateLimitRedisForTests(): void {
  client?.disconnect(false);
  client = null;
  errorReported = false;
}
