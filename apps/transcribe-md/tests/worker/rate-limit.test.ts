// ============================================================================
// Unit tests for rate-limit module (T-M16.2 inline → T-M16.3 evolution
// → 2026-05-13 multi-window rules)
// ----------------------------------------------------------------------------
// Covers the tryConsume primitive, the clientIp helpers, the named
// RATE_LIMITS presets, the checkRateLimit wrapper (multi-window
// semantics), and the rateLimitOr429 route-handler shortcut.
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
  type RateLimitRule,
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
  it('exposes every preset required by the call sites', () => {
    // Authoritative list — bumped 2026-05-13 to add PATIENT_READ /
    // PATIENT_CREATE / PATIENT_OPS so the patient-CRUD surface no
    // longer shares a 10/hour bucket with `change-password`.
    expect(Object.keys(RATE_LIMITS).sort()).toEqual([
      'AUTH_EMAIL',
      'CLIENT_ERRORS',
      'LOGIN',
      'PATIENT_CREATE',
      'PATIENT_OPS',
      'PATIENT_READ',
      'SETTINGS',
      'SIGNUP',
      'UPLOAD',
      'VISIT_OPS',
    ]);
  });

  it('every preset has a sane bucket + at least one window with positive limit + ≥1s window', () => {
    for (const [name, rule] of Object.entries(RATE_LIMITS)) {
      expect(rule.bucket, `${name}.bucket`).toBeTruthy();
      expect(rule.windows.length, `${name}.windows`).toBeGreaterThan(0);
      for (const win of rule.windows) {
        expect(win.limit, `${name}.windows[i].limit`).toBeGreaterThan(0);
        expect(win.windowMs, `${name}.windows[i].windowMs`).toBeGreaterThanOrEqual(1000);
      }
    }
  });

  it('no preset declares two windows with the same windowMs (would collapse onto one counter)', () => {
    // Bucket keys are `${bucket}:${windowMs}:${identifier}`. Two
    // windows with the same windowMs would share the same key and
    // silently double-increment the same counter, making the second
    // window's limit dead. Catch this at build-time-equivalent
    // (test-time).
    for (const [name, rule] of Object.entries(RATE_LIMITS)) {
      const seen = new Set<number>();
      for (const win of rule.windows) {
        expect(
          seen.has(win.windowMs),
          `${name} has duplicate windowMs ${win.windowMs}`,
        ).toBe(false);
        seen.add(win.windowMs);
      }
    }
  });

  it('PATIENT_CREATE meets the clinical-reality brief (60/h, 20/5min, 10/30s)', () => {
    // Pins the operator-brief numbers so a future tightening doesn't
    // silently re-introduce the Kasra-morning-rounds regression.
    const limits = RATE_LIMITS.PATIENT_CREATE.windows.map(
      (w) => ({ limit: w.limit, windowMs: w.windowMs }),
    );
    expect(limits).toContainEqual({ limit: 10, windowMs: 30 * 1000 });
    expect(limits).toContainEqual({ limit: 20, windowMs: 5 * 60 * 1000 });
    expect(limits).toContainEqual({ limit: 60, windowMs: 60 * 60 * 1000 });
  });
});

describe('checkRateLimit — multi-window semantics', () => {
  it('allows under-limit identifiers', () => {
    const r = checkRateLimit(RATE_LIMITS.LOGIN, 'ip-check-1');
    expect(r.allowed).toBe(true);
  });

  it('isolates buckets by identifier', () => {
    // LOGIN is a single-window rule (10/hr).
    for (let i = 0; i < 10; i++) {
      checkRateLimit(RATE_LIMITS.LOGIN, 'ip-check-2');
    }
    // Another IP on the same rule still gets a fresh window.
    expect(checkRateLimit(RATE_LIMITS.LOGIN, 'ip-check-3').allowed).toBe(true);
  });

  it('isolates buckets by rule', () => {
    for (let i = 0; i < 10; i++) {
      checkRateLimit(RATE_LIMITS.LOGIN, 'ip-check-4');
    }
    // Same identifier but different rule = different bucket.
    expect(checkRateLimit(RATE_LIMITS.SIGNUP, 'ip-check-4').allowed).toBe(true);
  });

  it('PATIENT_CREATE accepts 10 sequential creates within the 30s burst window', () => {
    // The exact morning-rounds workflow Kasra reproduced: doctor
    // creates patients back-to-back. Under the new 10/30s burst,
    // 10 consecutive creates must all succeed.
    for (let i = 0; i < 10; i++) {
      const r = checkRateLimit(RATE_LIMITS.PATIENT_CREATE, 'doc-1');
      expect(r.allowed, `create #${i + 1}`).toBe(true);
    }
  });

  it('PATIENT_CREATE rejects an 11th request inside the 30s burst window', () => {
    for (let i = 0; i < 10; i++) checkRateLimit(RATE_LIMITS.PATIENT_CREATE, 'doc-2');
    const r = checkRateLimit(RATE_LIMITS.PATIENT_CREATE, 'doc-2');
    expect(r.allowed).toBe(false);
    expect(r.limitType).toBe('burst_30s');
    // The burst window is 30s, so retryAfterSec should be <= 30.
    expect(r.retryAfterSec).toBeGreaterThan(0);
    expect(r.retryAfterSec).toBeLessThanOrEqual(30);
  });

  it('PATIENT_CREATE returns the LONGEST retryAfterSec across windows when multiple fail', () => {
    // Synthesize a rule with two tripped windows — verify the
    // sustained-5min window's retryAfterSec wins over the burst.
    const rule: RateLimitRule = {
      bucket: 'multi-test',
      windows: [
        { limit: 1, windowMs: 30_000, label: 'short' },
        { limit: 1, windowMs: 300_000, label: 'long' },
      ],
    };
    checkRateLimit(rule, 'id-1'); // first call consumes both windows
    const r = checkRateLimit(rule, 'id-1'); // second call trips both
    expect(r.allowed).toBe(false);
    expect(r.limitType).toBe('long');
    expect(r.retryAfterSec).toBeGreaterThan(30);
  });

  it('PATIENT_READ tolerates the patient-picker bursty-search workflow (30 calls in 30s)', () => {
    // Debounced search + open-picker + post-create refresh can fire
    // 3+ reads per second; verify the 30/30s burst doesn't trip a
    // legit workflow.
    for (let i = 0; i < 30; i++) {
      const r = checkRateLimit(RATE_LIMITS.PATIENT_READ, 'doc-3');
      expect(r.allowed, `read #${i + 1}`).toBe(true);
    }
    // 31st in the burst window trips.
    expect(checkRateLimit(RATE_LIMITS.PATIENT_READ, 'doc-3').allowed).toBe(false);
  });

  it('PATIENT_READ and PATIENT_CREATE counters are independent (key by bucket name)', () => {
    // The pre-2026-05-13 bug: patient list GET + patient POST + fuzzy-
    // match all shared the SETTINGS bucket. Verify that's gone — even
    // exhausting PATIENT_READ leaves PATIENT_CREATE untouched.
    for (let i = 0; i < 30; i++) checkRateLimit(RATE_LIMITS.PATIENT_READ, 'doc-4');
    expect(checkRateLimit(RATE_LIMITS.PATIENT_READ, 'doc-4').allowed).toBe(false);
    expect(checkRateLimit(RATE_LIMITS.PATIENT_CREATE, 'doc-4').allowed).toBe(true);
  });

  it('windows are independently keyed (burst expiry doesn\'t reset the sustained window)', async () => {
    // Two-window synthetic rule with a short burst so the test runs
    // fast: burst=2/200ms, sustained=3/60s. Confirms the per-window
    // bucket key includes windowMs — the burst counter expiring must
    // NOT accidentally release the 60s counter.
    //
    // 200ms is deliberately wider than a worst-case CI cold-start
    // V8 hiccup; tighter values (30ms etc.) would flake under GC.
    const rule: RateLimitRule = {
      bucket: 'win-isolation',
      windows: [
        { limit: 2, windowMs: 200, label: 'burst' },
        { limit: 3, windowMs: 60_000, label: 'sustained' },
      ],
    };
    // Two successful calls fill both windows to (2, 2).
    expect(checkRateLimit(rule, 'id-7').allowed).toBe(true);
    expect(checkRateLimit(rule, 'id-7').allowed).toBe(true);
    // Third call: burst is at 2/2 — REJECTED by burst. Critically,
    // peek-then-commit means sustained's count stays at 2 (not 3) —
    // a partial commit would have leaked a slot here.
    const blocked = checkRateLimit(rule, 'id-7');
    expect(blocked.allowed).toBe(false);
    expect(blocked.limitType).toBe('burst');
    // Wait past the burst window. Sustained still has 2 consumed.
    await new Promise((r) => setTimeout(r, 250));
    // One more call succeeds (burst reset, sustained 2→3).
    expect(checkRateLimit(rule, 'id-7').allowed).toBe(true);
    // Next call is now rejected by SUSTAINED (3/3), not burst —
    // proving sustained's counter was preserved across the burst
    // window's reset.
    const r = checkRateLimit(rule, 'id-7');
    expect(r.allowed).toBe(false);
    expect(r.limitType).toBe('sustained');
  });
});

describe('rateLimitOr429', () => {
  it('returns null when the limit is not exceeded', () => {
    expect(rateLimitOr429(RATE_LIMITS.SIGNUP, 'ip-or429-1')).toBeNull();
  });

  it('returns a 429 NextResponse with Retry-After + structured body when exceeded', async () => {
    for (let i = 0; i < 5; i++) {
      rateLimitOr429(RATE_LIMITS.SIGNUP, 'ip-or429-2');
    }
    const res = rateLimitOr429(RATE_LIMITS.SIGNUP, 'ip-or429-2');
    expect(res).not.toBeNull();
    expect(res?.status).toBe(429);
    expect(res?.headers.get('Retry-After')).toMatch(/^\d+$/);
    const body = await res?.json();
    expect(body).toMatchObject({
      error: expect.stringContaining('faster than the system allows'),
      retryAfterSec: expect.any(Number),
    });
    // limitType is set when a window has a label (all our presets do)
    expect(body.limitType).toBe('hourly');
  });

  it('body retryAfterSec matches the Retry-After header value', async () => {
    for (let i = 0; i < 10; i++) {
      rateLimitOr429(RATE_LIMITS.PATIENT_CREATE, 'doc-or429-3');
    }
    const res = rateLimitOr429(RATE_LIMITS.PATIENT_CREATE, 'doc-or429-3');
    const body = await res?.json();
    expect(String(body.retryAfterSec)).toBe(res?.headers.get('Retry-After'));
  });
});
