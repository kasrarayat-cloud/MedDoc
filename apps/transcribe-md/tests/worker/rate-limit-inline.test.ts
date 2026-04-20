// ============================================================================
// Unit tests for T-M16.2 inline rate limiter
// ============================================================================

import { afterEach, describe, expect, it } from 'vitest';

import {
  __resetForTests,
  clientIpFromRequest,
  tryConsume,
} from '@/lib/rate-limit-inline';

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
