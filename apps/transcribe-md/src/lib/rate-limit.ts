// ============================================================================
// Per-user + per-IP rate limiter — evolution of T-M16.2's inline helper
// ----------------------------------------------------------------------------
// Fixed-window counters keyed by a composite `<bucket>:<windowMs>:<identifier>`
// string where identifier is either a userId (authed routes) or an IP
// (unauthed routes). Named rule presets in `RATE_LIMITS` are the SSOT
// for every limit the app applies — tuning one number in one place
// is always enough.
//
// 2026-05-13 — multi-window rules. A rule now declares an array of
// `{ limit, windowMs }` checks; ALL must pass for the request to be
// allowed. This lets a single rule combine a short burst window (e.g.,
// 10/30s) with a sustained-volume window (e.g., 60/hour) without
// needing two named rules at the call site. Each window owns its own
// counter (keyed by windowMs), so they're truly independent.
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
// See `docs/KNOWN_ISSUES.md` KI-4 for the trigger-to-revisit list
// and the Redis-backed fix path.
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
  /** When allowed=false, which window tripped — useful for client
   *  diagnostics and the 429 body. `undefined` when allowed=true. */
  limitType?: string;
}

export interface RateLimitWindow {
  /** Max requests in this window. */
  limit: number;
  /** Window length in milliseconds. */
  windowMs: number;
  /** Optional label exposed on 429 responses (e.g., `burst_30s`,
   *  `sustained_5min`, `hourly`). Defaults to `${windowMs}ms`. */
  label?: string;
}

export interface RateLimitRule {
  /** Bucket name shared across all identifiers under this rule. */
  bucket: string;
  /** One or more windows. ALL must pass for the request to be
   *  allowed. Each window has an independent counter. */
  windows: RateLimitWindow[];
}

// ---------------------------------------------------------------------------
// Window-builder shorthands — keeps preset definitions readable.
// ---------------------------------------------------------------------------

const SEC = 1000;
const MIN = 60 * SEC;
const HOUR = 60 * MIN;

const w = (label: string, limit: number, windowMs: number): RateLimitWindow => ({
  limit,
  windowMs,
  label,
});

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
//                  cost — this is the cost shield. Clinical reality:
//                  10-15 audio uploads per morning rounds, 50 over a
//                  full clinical day; burst tolerates batch-import.
//
//   CLIENT_ERRORS: /api/client-errors sink. Per-IP. Generous limit
//                  because legit users can trip React errors in
//                  bursts; anti-abuse not anti-user.
//
//   SETTINGS:      change-password, change-email, delete-account,
//                  export-data, account-recovery surfaces. Per-user.
//                  Genuinely-low-frequency operations; tight limit OK.
//
//   PATIENT_READ:  GET /api/patients (search), POST /api/patients/
//                  fuzzy-match (duplicate check), GET /api/patients/
//                  [id]. Per-user. High-volume because the patient
//                  picker debounces a GET per keystroke + fires
//                  fuzzy-match on every new-patient attempt.
//
//   PATIENT_CREATE: POST /api/patients. Per-user. Clinical reality:
//                  AM rounds in a busy primary-care practice creates
//                  10-15 new patients in 30 min; burst tolerates
//                  back-to-back creation; hourly caps a runaway
//                  script. Numbers match the operator brief.
//
//   PATIENT_OPS:   PATCH/PUT/DELETE on /api/patients/[id]. Per-user.
//                  Tighter than CREATE — destructive ops shouldn't
//                  fire in tight loops in real workflows.
//
//   VISIT_OPS:     visit-management mutations (delete/archive/restore/
//                  edit/retry). Per-user. Already in clinical-realism
//                  range; tightened bursts to catch scripted misuse.
//
export const RATE_LIMITS = {
  AUTH_EMAIL: {
    bucket: 'auth-email',
    windows: [w('hourly', 5, HOUR)],
  },
  LOGIN: {
    bucket: 'login',
    windows: [w('hourly', 10, HOUR)],
  },
  SIGNUP: {
    bucket: 'signup',
    windows: [w('hourly', 5, HOUR)],
  },
  UPLOAD: {
    bucket: 'upload',
    windows: [
      w('burst_30s', 5, 30 * SEC),
      w('sustained_5min', 15, 5 * MIN),
      w('hourly', 50, HOUR),
    ],
  },
  CLIENT_ERRORS: {
    bucket: 'client-errors',
    windows: [w('hourly', 30, HOUR)],
  },
  SETTINGS: {
    bucket: 'settings',
    windows: [w('hourly', 10, HOUR)],
  },
  PATIENT_READ: {
    bucket: 'patient-read',
    windows: [
      w('burst_30s', 30, 30 * SEC),
      w('sustained_5min', 60, 5 * MIN),
      w('hourly', 200, HOUR),
    ],
  },
  PATIENT_CREATE: {
    bucket: 'patient-create',
    windows: [
      w('burst_30s', 10, 30 * SEC),
      w('sustained_5min', 20, 5 * MIN),
      w('hourly', 60, HOUR),
    ],
  },
  PATIENT_OPS: {
    bucket: 'patient-ops',
    windows: [
      w('sustained_5min', 20, 5 * MIN),
      w('hourly', 60, HOUR),
    ],
  },
  VISIT_OPS: {
    bucket: 'visit-ops',
    windows: [
      w('burst_30s', 10, 30 * SEC),
      w('hourly', 60, HOUR),
    ],
  },
} satisfies Record<string, RateLimitRule>;

// ---------------------------------------------------------------------------
// Low-level primitive — unchanged signature from T-M16.2. Independent
// counters per `key`. Callers that want multi-window semantics should
// use checkRateLimit instead.
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

/** Non-mutating peek — would `tryConsume(key, limit)` allow the next
 *  request? Used by checkRateLimit's two-phase commit so a multi-
 *  window rule can reject without partially consuming the windows
 *  that WOULD have allowed it. Doesn't need windowMs because it
 *  doesn't create a fresh bucket — only inspects state set by a
 *  prior tryConsume. */
function peekConsume(key: string, limit: number): RateLimitResult {
  const now = Date.now();
  const existing = buckets.get(key);
  if (!existing || existing.resetAt <= now) {
    return { allowed: true, retryAfterSec: 0 };
  }
  if (existing.count >= limit) {
    return {
      allowed: false,
      retryAfterSec: Math.max(1, Math.ceil((existing.resetAt - now) / 1000)),
    };
  }
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
 *  actions) can build their own rejection shape.
 *
 *  Multi-window semantics: every window must pass for the request to
 *  be allowed. Two-phase: peek every window first (no mutation); if
 *  ALL would allow, commit by calling tryConsume on each. This way
 *  rejection by ANY window doesn't accidentally consume slots in the
 *  windows that would have allowed it.
 *
 *  When multiple windows would reject, we return the LONGEST
 *  retryAfterSec — the client must wait that long for the rule as a
 *  whole to clear.
 */
export function checkRateLimit(
  rule: RateLimitRule,
  identifier: string
): RateLimitResult {
  // TEST-ONLY bypass. The E2E suite drives many signups/uploads from a SINGLE
  // runner IP, which trips these per-IP limits and makes the CI gate flaky.
  // Gated on an EXPLICIT opt-in env that exists ONLY in the throwaway qa/CI
  // stack (docker-compose.qa.yml) — NEVER in the production env — the same
  // posture as EMAIL_AUTO_CONFIRM_ALLOW_IN_PROD. Unset (the default) ⇒ every
  // window is enforced exactly as before, so production rate-limiting is
  // unchanged. This is the central choke point: actionRateLimitOrError (signup)
  // and rateLimitOr429 (API routes) both funnel through here.
  if (process.env.RATE_LIMIT_DISABLED === 'true') {
    return { allowed: true, retryAfterSec: 0 };
  }

  let worstRejection: RateLimitResult | null = null;
  // Phase 1 — peek every window. Track the LONGEST retryAfterSec
  // across all rejecting windows.
  for (const win of rule.windows) {
    const key = `${rule.bucket}:${win.windowMs}:${identifier}`;
    const r = peekConsume(key, win.limit);
    if (r.allowed) continue;
    const label = win.label ?? `${win.windowMs}ms`;
    if (
      !worstRejection ||
      r.retryAfterSec > worstRejection.retryAfterSec
    ) {
      worstRejection = {
        allowed: false,
        retryAfterSec: r.retryAfterSec,
        limitType: label,
      };
    }
  }
  if (worstRejection) return worstRejection;
  // Phase 2 — every window would allow; commit consumption. JS is
  // single-threaded so there's no race between peek and consume
  // within this synchronous call.
  for (const win of rule.windows) {
    const key = `${rule.bucket}:${win.windowMs}:${identifier}`;
    tryConsume(key, win.limit, win.windowMs);
  }
  return { allowed: true, retryAfterSec: 0 };
}

/** Route-handler-friendly one-shot: check the limit, return a
 *  429 NextResponse if exceeded, null if OK. Pattern:
 *
 *    const blocked = rateLimitOr429(RATE_LIMITS.UPLOAD, userId);
 *    if (blocked) return blocked;
 *    // ... continue request handling ...
 *
 *  2026-05-13: the 429 body now carries `retryAfterSec` + `limitType`
 *  so the client can render a countdown without parsing the header.
 */
export function rateLimitOr429(
  rule: RateLimitRule,
  identifier: string
): NextResponse | null {
  const rl = checkRateLimit(rule, identifier);
  if (rl.allowed) return null;
  return NextResponse.json(
    {
      error: "You're working faster than the system allows — please pause briefly and retry.",
      retryAfterSec: rl.retryAfterSec,
      limitType: rl.limitType ?? null,
    },
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
