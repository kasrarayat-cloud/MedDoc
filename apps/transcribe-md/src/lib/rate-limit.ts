// ============================================================================
// Per-user + per-IP rate limiter — evolution of T-M16.2's inline helper
// ----------------------------------------------------------------------------
// Fixed-window counters keyed by a composite `<bucket>:<identifier>`
// string where identifier is either a userId (authed routes) or an IP
// (unauthed routes). Named rule presets in `RATE_LIMITS` are the SSOT
// for every limit the app applies — tuning one number in one place
// is always enough.
//
// Scope (T-M16.3):
//   • apps/transcribe-md only. meddoc-pro keeps its own
//     apps/meddoc-pro/src/lib/rate-limit.ts for now — it works, its
//     API shape differs, and porting its 9 callers adds risk with no
//     visible benefit.
//   • TODO(later): once the two modules prove convergent under real
//     load, lift the shared surface into packages/ratelimit and
//     migrate both sides. Not this milestone.
//
// Limitations carried over from T-M16.2's inline version — still
// acceptable at single-VPS scale:
//   1. In-memory state resets on worker restart.
//   2. Buckets don't cross containers (single transcribe-md replica
//      today — revisit when we horizontally scale).
// ============================================================================

import { NextResponse } from 'next/server';

interface Bucket {
  count: number;
  resetAt: number;
}

const buckets = new Map<string, Bucket>();

export interface RateLimitResult {
  allowed: boolean;
  /** Seconds until the bucket resets. Safe to use directly as the
   *  Retry-After header value when allowed=false. */
  retryAfterSec: number;
}

export interface RateLimitRule {
  /** Bucket name shared across all identifiers under this rule. */
  bucket: string;
  /** Max requests per window. */
  limit: number;
  /** Window length in milliseconds. */
  windowMs: number;
}

// ---------------------------------------------------------------------------
// Named presets — the app's rate-limit catalog
// ---------------------------------------------------------------------------
//
//   AUTH_EMAIL:    forgot-password, reset-password, resend-verification,
//                  verify-email, confirm-email. Per-IP. Shared bucket
//                  across all five endpoints so an attacker mixing them
//                  can't bypass by round-robin.
//
//   LOGIN:         login action. Per-IP, NOT per-email — per-email would
//                  leak account existence on the second attempt.
//
//   SIGNUP:        signup action. Per-IP. Stops automated signup farms.
//
//   UPLOAD:        audio + dictation + text-pipeline kickoff endpoints.
//                  Per-user. Each upload burns real Deepgram / Anthropic
//                  cost — this is the cost shield.
//
//   CLIENT_ERRORS: /api/client-errors sink. Per-IP. Generous limit
//                  because legit users can trip React errors in
//                  bursts; anti-abuse not anti-user.
//
//   SETTINGS:      change-password, change-email, delete-account,
//                  export-data. Per-user. Lower than UPLOAD because
//                  these shouldn't be called often.
//
const HOUR_MS = 60 * 60 * 1000;

export const RATE_LIMITS = {
  AUTH_EMAIL:    { bucket: 'auth-email',    limit: 5,  windowMs: HOUR_MS },
  LOGIN:         { bucket: 'login',         limit: 10, windowMs: HOUR_MS },
  SIGNUP:        { bucket: 'signup',        limit: 5,  windowMs: HOUR_MS },
  UPLOAD:        { bucket: 'upload',        limit: 20, windowMs: HOUR_MS },
  CLIENT_ERRORS: { bucket: 'client-errors', limit: 30, windowMs: HOUR_MS },
  SETTINGS:      { bucket: 'settings',      limit: 10, windowMs: HOUR_MS },
} satisfies Record<string, RateLimitRule>;

// ---------------------------------------------------------------------------
// Low-level primitive — unchanged signature from T-M16.2.
// ---------------------------------------------------------------------------

/** Consume one slot in the named bucket. If the bucket expired OR is
 *  new, this call resets it (fresh window). If full, rejects. */
export function tryConsume(
  key: string,
  limit: number,
  windowMs: number
): RateLimitResult {
  const now = Date.now();
  const existing = buckets.get(key);

  if (!existing || existing.resetAt <= now) {
    buckets.set(key, { count: 1, resetAt: now + windowMs });
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

export function __resetForTests(): void {
  buckets.clear();
}

// ---------------------------------------------------------------------------
// High-level helpers — the shape every caller should prefer.
// ---------------------------------------------------------------------------

/** Check a rule against an identifier (userId or IP). Returns the raw
 *  result so callers that aren't in a Next route handler (server
 *  actions) can build their own rejection shape. */
export function checkRateLimit(
  rule: RateLimitRule,
  identifier: string
): RateLimitResult {
  return tryConsume(
    `${rule.bucket}:${identifier}`,
    rule.limit,
    rule.windowMs
  );
}

/** Route-handler-friendly one-shot: check the limit, return a
 *  429 NextResponse if exceeded, null if OK. Pattern:
 *
 *    const blocked = rateLimitOr429(RATE_LIMITS.UPLOAD, userId);
 *    if (blocked) return blocked;
 *    // ... continue request handling ...
 */
export function rateLimitOr429(
  rule: RateLimitRule,
  identifier: string
): NextResponse | null {
  const rl = checkRateLimit(rule, identifier);
  if (rl.allowed) return null;
  return NextResponse.json(
    { error: 'Too many requests. Try again later.' },
    {
      status: 429,
      headers: { 'Retry-After': String(rl.retryAfterSec) },
    }
  );
}

// ---------------------------------------------------------------------------
// IP extraction — works in both NextRequest / fetch Request context
// (route handlers) and server-action context (where only Headers is
// easily available via next/headers).
// ---------------------------------------------------------------------------

/** Extract a client IP from a Headers object. Used by server actions. */
export function clientIpFromHeaders(headers: Headers): string {
  const xff = headers.get('x-forwarded-for');
  if (xff) {
    const first = xff.split(',')[0]?.trim();
    if (first) return first;
  }
  return headers.get('x-real-ip') || 'unknown';
}

/** Shortcut for route handlers. */
export function clientIpFromRequest(req: Request): string {
  return clientIpFromHeaders(req.headers);
}
