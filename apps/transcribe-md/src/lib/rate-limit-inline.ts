// ============================================================================
// In-memory per-IP rate limiter (T-M16.2)
// ----------------------------------------------------------------------------
// TODO(T-M16.3): replace with the shared rate-limit module. This
// implementation has two known limitations that are acceptable for
// T-M16.2 scope but NOT for a horizontally-scaled deployment:
//
//   1. State lives in the Node process — a worker restart resets
//      every bucket. On this single-VPS setup that's a restart-per-
//      deploy window of relief for attackers, which is annoying but
//      not exploitable in practice.
//   2. State doesn't cross containers. The transcribe-md app runs as
//      one replica today, so this is a non-issue. When we scale to
//      two replicas behind the same Caddy, the limit becomes 2×
//      whatever we configured — move to Redis-backed limiting then.
//
// Used by /api/auth/forgot-password and /api/auth/resend-verification
// to cap per-IP request rate. Other routes will gain rate-limit in
// T-M16.3 via the shared module.
// ============================================================================

interface Bucket {
  count: number;
  resetAt: number;
}

const buckets = new Map<string, Bucket>();

export interface RateLimitResult {
  allowed: boolean;
  /** Seconds until the bucket resets. Use as the Retry-After header
   *  value when allowed=false. */
  retryAfterSec: number;
}

/** Consume one slot in the named bucket. If the bucket is full or
 *  expired, this call resets it (fresh window) OR rejects, depending
 *  on which came first. */
export function tryConsume(
  key: string,
  limit: number,
  windowMs: number
): RateLimitResult {
  const now = Date.now();
  const existing = buckets.get(key);

  if (!existing || existing.resetAt <= now) {
    buckets.set(key, { count: 1, resetAt: now + windowMs });
    // Opportunistic sweep so the map doesn't grow without bound.
    if (buckets.size > 2048) pruneExpired(now);
    return { allowed: true, retryAfterSec: 0 };
  }

  if (existing.count >= limit) {
    return {
      allowed: false,
      retryAfterSec: Math.max(1, Math.ceil((existing.resetAt - now) / 1000)),
    };
  }

  existing.count += 1;
  return { allowed: true, retryAfterSec: 0 };
}

function pruneExpired(now: number): void {
  for (const [key, bucket] of buckets.entries()) {
    if (bucket.resetAt <= now) buckets.delete(key);
  }
}

/** Visible-for-tests: reset all state. NEVER call from production code. */
export function __resetForTests(): void {
  buckets.clear();
}

// ---------------------------------------------------------------------------
// Helper: extract a client IP from the request. Caddy sets X-Forwarded-For
// and X-Real-IP; the first value in XFF is the originating client.
// ---------------------------------------------------------------------------

export function clientIpFromRequest(req: Request): string {
  const xff = req.headers.get('x-forwarded-for');
  if (xff) {
    const first = xff.split(',')[0]?.trim();
    if (first) return first;
  }
  return req.headers.get('x-real-ip') || 'unknown';
}
