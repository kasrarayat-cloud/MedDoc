// ============================================================================
// parseRateLimit — 429-response parser
// ----------------------------------------------------------------------------
// Server side: rateLimitOr429 (apps/transcribe-md/src/lib/rate-limit.ts)
// emits { error, retryAfterSec, limitType } in the body + `Retry-After`
// header. Client side: parseRateLimit reads either with sensible
// fallbacks so the UI's countdown never crashes on an unexpected
// shape (e.g., proxy stripped both, or future server version drift).
// ============================================================================

import { describe, expect, it } from 'vitest';

import { parseRateLimit } from '@/lib/parse-rate-limit';

function mkRes(headers: Record<string, string> = {}, status = 429): Response {
  return new Response(null, { status, headers });
}

describe('parseRateLimit', () => {
  it('prefers body.retryAfterSec when present', () => {
    const res = mkRes({ 'Retry-After': '99' });
    const r = parseRateLimit(res, { retryAfterSec: 23, limitType: 'burst_30s' });
    expect(r).toEqual({ retryAfterSec: 23, limitType: 'burst_30s' });
  });

  it('falls back to Retry-After header when body omits retryAfterSec', () => {
    const res = mkRes({ 'Retry-After': '17' });
    const r = parseRateLimit(res, { limitType: 'sustained_5min' });
    expect(r).toEqual({ retryAfterSec: 17, limitType: 'sustained_5min' });
  });

  it('falls back to default 30s when both body + header are missing', () => {
    const res = mkRes({});
    const r = parseRateLimit(res, {});
    expect(r.retryAfterSec).toBe(30);
    expect(r.limitType).toBeNull();
  });

  it('rejects body.retryAfterSec of 0 or negative (likely a bug; uses fallback)', () => {
    const res = mkRes({ 'Retry-After': '12' });
    const r = parseRateLimit(res, { retryAfterSec: 0 });
    expect(r.retryAfterSec).toBe(12);
  });

  it('rejects body.retryAfterSec of wrong type (uses fallback)', () => {
    const res = mkRes({ 'Retry-After': '12' });
    const r = parseRateLimit(res, { retryAfterSec: 'soon' as unknown });
    expect(r.retryAfterSec).toBe(12);
  });

  it('uses ceil() on fractional body values', () => {
    const res = mkRes({});
    const r = parseRateLimit(res, { retryAfterSec: 5.4 });
    expect(r.retryAfterSec).toBe(6);
  });

  it('rejects non-numeric Retry-After header (uses default)', () => {
    const res = mkRes({ 'Retry-After': 'tomorrow' });
    const r = parseRateLimit(res, {});
    expect(r.retryAfterSec).toBe(30);
  });

  it('handles null body without crashing', () => {
    const res = mkRes({ 'Retry-After': '7' });
    const r = parseRateLimit(res, null);
    expect(r).toEqual({ retryAfterSec: 7, limitType: null });
  });

  it('handles undefined body without crashing', () => {
    const res = mkRes({});
    const r = parseRateLimit(res, undefined);
    expect(r.retryAfterSec).toBe(30);
  });

  it('ignores empty-string limitType in body', () => {
    const res = mkRes({});
    const r = parseRateLimit(res, { retryAfterSec: 8, limitType: '' });
    expect(r.limitType).toBeNull();
  });
});
