// ============================================================================
// Scribe live-stream concurrency lock (spec §13)
// ----------------------------------------------------------------------------
// "Rate limit per clinician (max 1 concurrent live stream)." Enforced at WS
// accept time with SET NX EX. The value stored is the visitId so a retry
// from the same visit (same tab reload) can reclaim the lock without
// bouncing — the server checks "same visit or reject".
//
// TTL = 4h (max realistic live visit duration). If a process crashes and
// leaves the lock, it auto-expires. Release is best-effort via a Lua CAS
// so we never release a lock acquired by someone else.
// ============================================================================

import type IORedis from 'ioredis';

const LOCK_TTL_SECONDS = 4 * 3600;

export function liveLockKey(userId: string): string {
  return `scribe:live:user:${userId}`;
}

/**
 * Try to acquire the per-user live lock. Returns true if acquired or if
 * the caller already holds the lock for this visit.
 */
export async function acquireLiveLock(
  redis: IORedis,
  userId: string,
  visitId: string
): Promise<boolean> {
  const key = liveLockKey(userId);
  const ok = await redis.set(key, visitId, 'EX', LOCK_TTL_SECONDS, 'NX');
  if (ok === 'OK') return true;
  // Already held — reclaim iff it's the same visit.
  const current = await redis.get(key);
  return current === visitId;
}

/**
 * Release the lock only if we still hold it for this visit. Prevents a
 * late release from one WS session from releasing a newer session's lock.
 */
export async function releaseLiveLock(
  redis: IORedis,
  userId: string,
  visitId: string
): Promise<void> {
  const script = `
    if redis.call("get", KEYS[1]) == ARGV[1] then
      return redis.call("del", KEYS[1])
    else
      return 0
    end
  `;
  await redis.eval(script, 1, liveLockKey(userId), visitId);
}
