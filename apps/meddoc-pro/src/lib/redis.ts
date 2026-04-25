// ============================================================================
// Redis singleton for meddoc-pro
// ----------------------------------------------------------------------------
// Phase 1B: needed by the admin SSE stream (subscribe channel) and by
// logAudit() (publish channel). Mirrors apps/transcribe-md/src/lib/queue.ts's
// `getSharedRedisConnection()` shape so both apps end up on the same
// pattern when they need bare Redis (no BullMQ).
//
// Phase 1B v2 — fail-fast options. The original v1 used
// `maxRetriesPerRequest: null` which caused publishes to queue
// indefinitely while the singleton was reconnecting; combined with the
// fire-and-forget chain in logAudit() this held NextAuth's response
// open ~60s after a successful sign-in. The new options drop commands
// the moment the connection isn't ready, so an unreachable Redis
// degrades to "no live SSE fan-out" rather than blocking the request
// path. The audit_logs row is the durable source of truth either way.
// ============================================================================

import IORedis, { type RedisOptions } from 'ioredis';

let connection: IORedis | null = null;

function buildConnection(): IORedis {
  // Default points at the docker-compose `redis` service hostname.
  // Override via REDIS_URL when running outside Docker.
  const redisUrl =
    process.env.REDIS_URL?.trim() || 'redis://redis:6379';
  const opts: RedisOptions = {
    maxRetriesPerRequest: 0,
    enableReadyCheck: false,
    enableOfflineQueue: false,
    retryStrategy: () => null,
    lazyConnect: true,
  };
  const client = new IORedis(redisUrl, opts);
  client.on('error', (err) => {
    // err.message can be empty on socket-level errors — fall back to
    // err.code so we don't emit naked colons into stdout.
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const detail = err.message || (err as any).code || 'unknown';
    console.error('[redis] connection error:', detail);
  });
  return client;
}

/** Returns a singleton ioredis client. Lazy — only opens a socket
 *  on first call. Callers must NOT close this client; let the
 *  runtime hold it open across requests. */
export function getRedis(): IORedis {
  if (!connection) connection = buildConnection();
  return connection;
}

/** True when the singleton has a live connection that's accepting
 *  commands. Callers in the request path should gate their publishes
 *  on this — a degraded Redis must never delay the response. */
export function isRedisReady(): boolean {
  if (!connection) return false;
  return connection.status === 'ready';
}

/** Channel used for admin-dashboard SSE streaming. Both apps
 *  publish to it from logAudit() after a successful DB write; the
 *  meddoc-pro /api/admin/stream/activity endpoint subscribes and
 *  forwards each message to connected admin clients. */
export const ADMIN_AUDIT_STREAM_CHANNEL = 'admin:audit-stream';
