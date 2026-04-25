// ============================================================================
// Redis singleton for meddoc-pro
// ----------------------------------------------------------------------------
// Phase 1B: needed by the admin SSE stream (subscribe channel) and by
// logAudit() (publish channel). Mirrors apps/transcribe-md/src/lib/queue.ts's
// `getSharedRedisConnection()` shape so both apps end up on the same
// pattern when they need bare Redis (no BullMQ).
//
// Connection options match the BullMQ-side requirements
// (maxRetriesPerRequest: null, enableReadyCheck: false) so this single
// client can be reused as a BullMQ connection later without
// re-architecting.
// ============================================================================

import IORedis, { type RedisOptions } from 'ioredis';

let connection: IORedis | null = null;

function buildConnection(): IORedis {
  // Default points at the docker-compose `redis` service hostname,
  // not localhost. The container env doesn't set REDIS_URL by default;
  // hardcoding the service name keeps this self-healing without a
  // compose edit. Override via REDIS_URL when running outside Docker.
  const redisUrl =
    process.env.REDIS_URL?.trim() || 'redis://redis:6379';
  const opts: RedisOptions = {
    maxRetriesPerRequest: null,
    enableReadyCheck: false,
  };
  const client = new IORedis(redisUrl, opts);
  client.on('error', (err) => {
    // Avoid stack-trace spam — Redis errors are common transient
    // states. Retain ONE log per error message so a flapping
    // connection doesn't poison stdout.
    console.error('[redis] connection error:', err.message);
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

/** Channel used for admin-dashboard SSE streaming. Both apps
 *  publish to it from logAudit() after a successful DB write; the
 *  meddoc-pro /api/admin/stream/activity endpoint subscribes and
 *  forwards each message to connected admin clients. */
export const ADMIN_AUDIT_STREAM_CHANNEL = 'admin:audit-stream';
