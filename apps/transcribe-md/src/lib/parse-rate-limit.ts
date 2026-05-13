// ============================================================================
// parseRateLimit — read 429 response shape produced by rateLimitOr429
// ----------------------------------------------------------------------------
// The server enriches the 429 body with { error, retryAfterSec, limitType }
// (see `apps/transcribe-md/src/lib/rate-limit.ts`). This helper does the
// resilient client-side parse:
//   1. Prefer `retryAfterSec` from the body (server's authoritative value).
//   2. Fall back to the `Retry-After` HTTP header if the body is empty.
//   3. Fall back to a sensible default if neither parses (e.g., a proxy
//      stripped both for some reason — shouldn't happen, but the UI
//      shouldn't crash if it does).
//
// Callers should ONLY invoke this on a 429 response. The function does
// NOT consume the body (it's already consumed by the caller's earlier
// `.json()` parse); pass the already-parsed body through.
// ============================================================================

export interface ParsedRateLimit {
  retryAfterSec: number;
  limitType: string | null;
}

const DEFAULT_RETRY_SEC = 30;

interface RateLimitBody {
  retryAfterSec?: unknown;
  limitType?: unknown;
}

export function parseRateLimit(
  res: Response,
  body: RateLimitBody | null | undefined,
): ParsedRateLimit {
  // 1. Body value.
  if (body && typeof body.retryAfterSec === 'number' && body.retryAfterSec > 0) {
    return {
      retryAfterSec: Math.ceil(body.retryAfterSec),
      limitType:
        typeof body.limitType === 'string' && body.limitType.length > 0
          ? body.limitType
          : null,
    };
  }
  // 2. Header value.
  const headerVal = res.headers.get('Retry-After');
  if (headerVal) {
    const n = Number.parseInt(headerVal, 10);
    if (Number.isFinite(n) && n > 0) {
      return {
        retryAfterSec: n,
        limitType:
          body && typeof body.limitType === 'string' && body.limitType.length > 0
            ? body.limitType
            : null,
      };
    }
  }
  // 3. Sensible fallback.
  return { retryAfterSec: DEFAULT_RETRY_SEC, limitType: null };
}
