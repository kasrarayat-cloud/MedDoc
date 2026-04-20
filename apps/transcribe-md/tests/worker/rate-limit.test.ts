// ============================================================================
// Unit tests for rate-limit module (T-M16.2 inline → T-M16.3 evolution)
// ----------------------------------------------------------------------------
// Covers the tryConsume primitive, the clientIp helpers, the named
// RATE_LIMITS presets, the checkRateLimit wrapper, and the
// rateLimitOr429 route-handler shortcut.
// ============================================================================

import { afterEach, describe, expect, it } from 'vitest';

import {
  RATE_LIMITS,
  __resetForTests,
  checkRateLimit,
  clientIpFromHeaders,
  clientIpFromRequest,
  rateLimitOr429,
  tryConsume,
} from '@/lib/rate-limit';

afterEach(() => {
  __resetForTests();
});

describe('tryConsume — bucket behavior', () => {
  it('allows the first N requests within the window', () => {
    for (let i = 0; i < 5; i++) {
      const r = tryConsume('ip-1', 5, 60_000);
      expect(r.allowed).toBe(true);
    }
  });

  it('rejects the N+1th request with a sensible retryAfterSec', () => {
    for (let i = 0; i < 5; i++) tryConsume('ip-1', 5, 60_000);
    const r = tryConsume('ip-1', 5, 60_000);
    expect(r.allowed).toBe(false);
    expect(r.retryAfterSec).toBeGreaterThan(0);
    expect(r.retryAfterSec).toBeLessThanOrEqual(60);
  });

  it('buckets are isolated by key', () => {
    for (let i = 0; i < 5; i++) tryConsume('ip-1', 5, 60_000);
    const other = tryConsume('ip-2', 5, 60_000);
    expect(other.allowed).toBe(true);
  });

  it('window expiry resets the bucket', async () => {
    for (let i = 0; i < 5; i++) tryConsume('ip-3', 5, 10);
    // Wait past the 10ms window
    await new Promise((r) => setTimeout(r, 15));
    const r = tryConsume('ip-3', 5, 60_000);
    expect(r.allowed).toBe(true);
  });
});

describe('clientIpFromRequest', () => {
  function mkReq(headers: Record<string, string>): Request {
    return new Request('http://x', { headers });
  }

  it('prefers the first value in X-Forwarded-For', () => {
    expect(
      clientIpFromRequest(
        mkReq({ 'x-forwarded-for': '1.2.3.4, 10.0.0.1' })
      )
    ).toBe('1.2.3.4');
  });

  it('falls back to X-Real-IP when XFF is absent', () => {
    expect(
      clientIpFromRequest(mkReq({ 'x-real-ip': '9.9.9.9' }))
    ).toBe('9.9.9.9');
  });

  it('returns "unknown" when no proxy headers are present', () => {
    expect(clientIpFromRequest(mkReq({}))).toBe('unknown');
  });

  it('ignores whitespace-only XFF', () => {
    expect(
      clientIpFromRequest(
        mkReq({ 'x-forwarded-for': '   ', 'x-real-ip': '4.4.4.4' })
      )
    ).toBe('4.4.4.4');
  });
});

describe('clientIpFromHeaders — server-action path', () => {
  it('parses a Headers object the same way as a Request', () => {
    const h = new Headers({ 'x-forwarded-for': '8.8.8.8, 10.0.0.5' });
    expect(clientIpFromHeaders(h)).toBe('8.8.8.8');
  });
});

describe('RATE_LIMITS presets', () => {
  it('has all 6 expected named rules', () => {
    expect(Object.keys(RATE_LIMITS).sort()).toEqual([
      'AUTH_EMAIL',
      'CLIENT_ERRORS',
      'LOGIN',
      'SETTINGS',
      'SIGNUP',
      'UPLOAD',
    ]);
  });

  it('every preset has a sane bucket + positive limit + hour-ish window', () => {
    for (const [name, rule] of Object.entries(RATE_LIMITS)) {
      expect(rule.bucket, `${name}.bucket`).toBeTruthy();
      expect(rule.limit, `${name}.limit`).toBeGreaterThan(0);
      expect(rule.windowMs, `${name}.windowMs`).toBeGreaterThanOrEqual(60_000);
    }
  });
});

describe('checkRateLimit', () => {
  it('allows under-limit identifiers', () => {
    const r = checkRateLimit(RATE_LIMITS.LOGIN, 'ip-check-1');
    expect(r.allowed).toBe(true);
  });

  it('isolates buckets by identifier', () => {
    for (let i = 0; i < RATE_LIMITS.LOGIN.limit; i++) {
      checkRateLimit(RATE_LIMITS.LOGIN, 'ip-check-2');
    }
    // Another IP on the same rule still gets a fresh window.
    expect(checkRateLimit(RATE_LIMITS.LOGIN, 'ip-check-3').allowed).toBe(true);
  });

  it('isolates buckets by rule', () => {
    for (let i = 0; i < RATE_LIMITS.LOGIN.limit; i++) {
      checkRateLimit(RATE_LIMITS.LOGIN, 'ip-check-4');
    }
    // Same identifier but different rule = different bucket.
    expect(checkRateLimit(RATE_LIMITS.SIGNUP, 'ip-check-4').allowed).toBe(true);
  });
});

describe('rateLimitOr429', () => {
  it('returns null when the limit is not exceeded', () => {
    expect(rateLimitOr429(RATE_LIMITS.SIGNUP, 'ip-or429-1')).toBeNull();
  });

  it('returns a 429 NextResponse with Retry-After when exceeded', async () => {
    for (let i = 0; i < RATE_LIMITS.SIGNUP.limit; i++) {
      rateLimitOr429(RATE_LIMITS.SIGNUP, 'ip-or429-2');
    }
    const res = rateLimitOr429(RATE_LIMITS.SIGNUP, 'ip-or429-2');
    expect(res).not.toBeNull();
    expect(res?.status).toBe(429);
    expect(res?.headers.get('Retry-After')).toMatch(/^\d+$/);
    const body = await res?.json();
    expect(body).toEqual({ error: 'Too many requests. Try again later.' });
  });
});
