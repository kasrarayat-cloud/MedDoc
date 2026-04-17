// ============================================================================
// In-memory per-user rate limiter
// ----------------------------------------------------------------------------
// Protects expensive endpoints (OpenAI calls, anything billable) from an
// authenticated user making abusive volumes. NOT a DDoS shield — that's
// Caddy's job and requires real network-layer throttling.
//
// Algorithm: fixed-window counter. Each (userId, bucket) tracks a count
// and the start of its current window. When a request arrives:
//   - If the window expired, reset.
//   - If count < limit, increment and allow.
//   - Otherwise deny and return seconds until the window rolls.
//
// Limitations:
//   - In-memory: resets on deploy, doesn't coordinate across app instances.
//     Move to Redis / Upstash when you scale to >1 app container.
//   - Fixed-window (not sliding): a user can theoretically burst 2x the
//     limit across a window boundary. Good enough for stopping abuse,
//     not perfect fairness.
// ============================================================================

interface WindowEntry {
  count: number;
  windowStart: number; // epoch ms
}

const buckets = new Map<string, WindowEntry>();

export interface RateLimitResult {
  ok: boolean;
  /** Number of requests used in the current window. */
  count: number;
  /** Configured max per window. */
  limit: number;
  /** Seconds until the window resets (when ok is false). */
  retryAfterSeconds: number;
}

export interface RateLimitRule {
  /** Bucket name for this rule. Separate buckets have separate counters. */
  bucket: string;
  /** Max requests per window. */
  limit: number;
  /** Window length in seconds. */
  windowSeconds: number;
}

/**
 * Check whether the user is under their rate-limit for this bucket, and
 * increment the counter if so. Returns `{ ok: false, retryAfterSeconds }`
 * when they've blown through the limit — the caller should return HTTP 429.
 */
export function checkRateLimit(
  userId: string,
  rule: RateLimitRule
): RateLimitResult {
  const key = `${rule.bucket}:${userId}`;
  const now = Date.now();
  const windowMs = rule.windowSeconds * 1000;

  const existing = buckets.get(key);

  if (!existing || now - existing.windowStart >= windowMs) {
    // New window
    buckets.set(key, { count: 1, windowStart: now });
    return {
      ok: true,
      count: 1,
      limit: rule.limit,
      retryAfterSeconds: 0,
    };
  }

  if (existing.count < rule.limit) {
    existing.count += 1;
    return {
      ok: true,
      count: existing.count,
      limit: rule.limit,
      retryAfterSeconds: 0,
    };
  }

  // Over limit
  const elapsed = now - existing.windowStart;
  const retryAfterSeconds = Math.max(1, Math.ceil((windowMs - elapsed) / 1000));
  return {
    ok: false,
    count: existing.count,
    limit: rule.limit,
    retryAfterSeconds,
  };
}

// ----------------------------------------------------------------------------
// Preset rules — centralized so we can tune without chasing call sites.
// ----------------------------------------------------------------------------
//
// TRANSCRIBE: 30/min is roughly one continuous dictation. A clinician
// doing 20 patients in a morning averages well under this; an abusive
// client hitting the endpoint in a loop trips quickly.
//
// DOC_EDITOR: text-completion is cheaper than audio but can still burn
// tokens; 60/min is generous for normal interactive editing.
export const RATE_LIMITS = {
  transcribe: { bucket: 'transcribe', limit: 30, windowSeconds: 60 },
  docEditor: { bucket: 'doc-editor', limit: 60, windowSeconds: 60 },
  // TTS: voice mode plays one short utterance per assistant turn. 60/min
  // covers an animated multi-turn dialogue with headroom; abusive loops
  // (each call costs $0.015/min of audio) trip quickly.
  tts: { bucket: 'tts', limit: 60, windowSeconds: 60 },
} satisfies Record<string, RateLimitRule>;
