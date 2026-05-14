// ============================================================================
// withRetry — unit tests
// ----------------------------------------------------------------------------
// Pins the policy locked in 2026-05-14:
//   - 3 attempts default, configurable
//   - FULL JITTER backoff (random between 0 and base*2^attempt, capped)
//   - isTransient: 429 + 5xx + Anthropic overloaded_error/rate_limit_error
//     + OpenAI rate_limit_exceeded + Node network codes
//   - Retry-After respected (seconds OR HTTP-date), capped at maxDelayMs
//   - Non-transient errors throw immediately, no retry
//   - After maxAttempts, throws the last error
//   - onRetry telemetry hook fires before delay sleep
//
// Uses vi.useFakeTimers() so the test suite runs in <1 second despite
// the helper's setTimeout-based backoff.
// ============================================================================

import {
  afterEach,
  beforeEach,
  describe,
  expect,
  it,
  vi,
} from 'vitest';

import {
  defaultIsTransient,
  withRetry,
  type RetryAttemptInfo,
} from '../retry';

beforeEach(() => {
  vi.useFakeTimers();
});

afterEach(() => {
  vi.useRealTimers();
});

/** Drives the helper's delay sleep with fake timers. The helper's
 *  setTimeout is the only async checkpoint we can't satisfy by simply
 *  resolving promises — `vi.runAllTimersAsync()` runs them in
 *  promise-microtask order, which is what we want here. */
async function flushTimers(): Promise<void> {
  await vi.runAllTimersAsync();
}

describe('withRetry — happy path', () => {
  it('returns immediately on first-attempt success (no retry, no delay)', async () => {
    const fn = vi.fn().mockResolvedValue('ok');

    const result = await withRetry(fn);

    expect(result).toBe('ok');
    expect(fn).toHaveBeenCalledTimes(1);
  });

  it('passes through plain values + reference types', async () => {
    const payload = { utterances: [], confidence: 0.9 };
    const fn = vi.fn().mockResolvedValue(payload);

    const result = await withRetry(fn);

    expect(result).toBe(payload);
  });
});

describe('withRetry — transient retry path', () => {
  it('retries once on a transient 503, succeeds on the second attempt', async () => {
    let calls = 0;
    const fn = vi.fn().mockImplementation(async () => {
      calls += 1;
      if (calls === 1) {
        const err: Error & { status: number } = Object.assign(
          new Error('Service Unavailable'),
          { status: 503 }
        );
        throw err;
      }
      return 'recovered';
    });

    const promise = withRetry(fn);
    await flushTimers();
    const result = await promise;

    expect(result).toBe('recovered');
    expect(fn).toHaveBeenCalledTimes(2);
  });

  it('retries up to maxAttempts-1 times before throwing the last error', async () => {
    const finalErr: Error & { status: number } = Object.assign(
      new Error('Bad Gateway #3'),
      { status: 502 }
    );
    const fn = vi
      .fn()
      .mockRejectedValueOnce(
        Object.assign(new Error('502 #1'), { status: 502 })
      )
      .mockRejectedValueOnce(
        Object.assign(new Error('502 #2'), { status: 502 })
      )
      .mockRejectedValueOnce(finalErr);

    // Attach the rejection assertion BEFORE flushing timers — the
    // expect.rejects handler immediately wires .catch on the
    // returned promise, which suppresses Vitest's "unhandled
    // rejection" warning when fake timers race the inner await.
    const expectPromise = expect(
      withRetry(fn, { maxAttempts: 3 })
    ).rejects.toBe(finalErr);
    await flushTimers();
    await expectPromise;

    expect(fn).toHaveBeenCalledTimes(3);
  });

  it('respects custom maxAttempts (5 attempts → 4 retries)', async () => {
    const fn = vi.fn().mockImplementation(async () => {
      throw Object.assign(new Error('rate limited'), { status: 429 });
    });

    const expectPromise = expect(
      withRetry(fn, { maxAttempts: 5 })
    ).rejects.toThrow(/rate limited/);
    await flushTimers();
    await expectPromise;

    expect(fn).toHaveBeenCalledTimes(5);
  });

  it('maxAttempts=1 → never retries (effectively bypass)', async () => {
    const fn = vi.fn().mockImplementation(async () => {
      throw Object.assign(new Error('503'), { status: 503 });
    });

    await expect(withRetry(fn, { maxAttempts: 1 })).rejects.toThrow(/503/);
    expect(fn).toHaveBeenCalledTimes(1);
  });
});

describe('withRetry — non-transient errors throw immediately', () => {
  it('400 throws on first attempt, no retry', async () => {
    const err = Object.assign(new Error('Bad Request'), { status: 400 });
    const fn = vi.fn().mockRejectedValue(err);

    await expect(withRetry(fn)).rejects.toBe(err);
    expect(fn).toHaveBeenCalledTimes(1);
  });

  it('401 unauthorized — never retry', async () => {
    const err = Object.assign(new Error('Unauthorized'), { status: 401 });
    const fn = vi.fn().mockRejectedValue(err);

    await expect(withRetry(fn)).rejects.toBe(err);
    expect(fn).toHaveBeenCalledTimes(1);
  });

  it('422 unprocessable — never retry (malformed request body)', async () => {
    const err = Object.assign(new Error('Unprocessable Entity'), { status: 422 });
    const fn = vi.fn().mockRejectedValue(err);

    await expect(withRetry(fn)).rejects.toBe(err);
    expect(fn).toHaveBeenCalledTimes(1);
  });

  it('plain Error without status — non-transient, no retry', async () => {
    const fn = vi.fn().mockRejectedValue(new Error('Validation failed'));

    await expect(withRetry(fn)).rejects.toThrow('Validation failed');
    expect(fn).toHaveBeenCalledTimes(1);
  });

  it('custom isTransient override is honored', async () => {
    const fn = vi.fn().mockImplementation(async () => {
      throw new Error('custom');
    });
    // Force all errors to be transient → should retry to exhaustion.
    const expectPromise = expect(
      withRetry(fn, { maxAttempts: 2, isTransient: () => true })
    ).rejects.toThrow('custom');
    await flushTimers();
    await expectPromise;

    expect(fn).toHaveBeenCalledTimes(2);
  });
});

describe('withRetry — onRetry telemetry', () => {
  it('fires once per retry (NOT on terminal failure, NOT on success)', async () => {
    const onRetry = vi.fn();
    const fn = vi
      .fn()
      .mockRejectedValueOnce(
        Object.assign(new Error('1'), { status: 503 })
      )
      .mockRejectedValueOnce(
        Object.assign(new Error('2'), { status: 503 })
      )
      .mockResolvedValueOnce('ok');

    const promise = withRetry(fn, { maxAttempts: 3, onRetry });
    await flushTimers();
    await promise;

    expect(onRetry).toHaveBeenCalledTimes(2);
    expect(onRetry.mock.calls[0][0]).toMatchObject({
      attempt: 1,
      maxAttempts: 3,
    });
    expect(onRetry.mock.calls[1][0]).toMatchObject({
      attempt: 2,
      maxAttempts: 3,
    });
  });

  it('carries the actual error + delay in the telemetry payload', async () => {
    const onRetry = vi.fn();
    const errOne = Object.assign(new Error('first'), { status: 503 });
    const fn = vi
      .fn()
      .mockRejectedValueOnce(errOne)
      .mockResolvedValueOnce('ok');

    const promise = withRetry(fn, { onRetry });
    await flushTimers();
    await promise;

    const info = onRetry.mock.calls[0][0] as RetryAttemptInfo;
    expect(info.error).toBe(errOne);
    expect(info.delayMs).toBeGreaterThanOrEqual(0);
    expect(info.delayMs).toBeLessThanOrEqual(30_000);
  });

  it('telemetry hook errors do NOT break retry', async () => {
    const onRetry = vi.fn(() => {
      throw new Error('logger blew up');
    });
    const fn = vi
      .fn()
      .mockRejectedValueOnce(
        Object.assign(new Error('503'), { status: 503 })
      )
      .mockResolvedValueOnce('ok');

    const promise = withRetry(fn, { onRetry });
    await flushTimers();

    await expect(promise).resolves.toBe('ok');
    expect(fn).toHaveBeenCalledTimes(2);
  });
});

describe('withRetry — Retry-After header', () => {
  it('honors numeric Retry-After (seconds) when present', async () => {
    const err = Object.assign(new Error('rate limited'), {
      status: 429,
      headers: { 'retry-after': '2' },
    });
    const fn = vi
      .fn()
      .mockRejectedValueOnce(err)
      .mockResolvedValueOnce('ok');
    const onRetry = vi.fn();

    const promise = withRetry(fn, { onRetry });
    await flushTimers();
    await promise;

    const info = onRetry.mock.calls[0][0] as RetryAttemptInfo;
    expect(info.delayMs).toBe(2000); // 2 seconds → 2000 ms
  });

  it('caps Retry-After at maxDelayMs (do NOT wait 60s)', async () => {
    const err = Object.assign(new Error('rate limited'), {
      status: 429,
      headers: { 'retry-after': '60' }, // 60s
    });
    const fn = vi
      .fn()
      .mockRejectedValueOnce(err)
      .mockResolvedValueOnce('ok');
    const onRetry = vi.fn();

    const promise = withRetry(fn, { onRetry, maxDelayMs: 5_000 }); // 5s cap
    await flushTimers();
    await promise;

    const info = onRetry.mock.calls[0][0] as RetryAttemptInfo;
    expect(info.delayMs).toBe(5_000); // capped
  });

  it('falls back to computed backoff when Retry-After is unparseable', async () => {
    const err = Object.assign(new Error('rate limited'), {
      status: 429,
      headers: { 'retry-after': 'gobbledygook' },
    });
    const fn = vi
      .fn()
      .mockRejectedValueOnce(err)
      .mockResolvedValueOnce('ok');
    const onRetry = vi.fn();

    const promise = withRetry(fn, {
      onRetry,
      baseDelayMs: 100,
      maxDelayMs: 30_000,
    });
    await flushTimers();
    await promise;

    const info = onRetry.mock.calls[0][0] as RetryAttemptInfo;
    // Computed backoff = random(0, 100 * 2^0) = random(0, 100)
    expect(info.delayMs).toBeGreaterThanOrEqual(0);
    expect(info.delayMs).toBeLessThanOrEqual(100);
  });

  it('handles Headers-instance shape (err.response.headers.get)', async () => {
    const headers = new Headers({ 'Retry-After': '3' });
    const err = Object.assign(new Error('rate limited'), {
      status: 429,
      response: { headers },
    });
    const fn = vi
      .fn()
      .mockRejectedValueOnce(err)
      .mockResolvedValueOnce('ok');
    const onRetry = vi.fn();

    const promise = withRetry(fn, { onRetry });
    await flushTimers();
    await promise;

    const info = onRetry.mock.calls[0][0] as RetryAttemptInfo;
    expect(info.delayMs).toBe(3000);
  });
});

describe('withRetry — provider-specific shapes (defaultIsTransient)', () => {
  it('Anthropic overloaded_error → transient', () => {
    const err = {
      status: 529,
      error: { error: { type: 'overloaded_error', message: '...' } },
    };
    expect(defaultIsTransient(err)).toBe(true);
  });

  it('Anthropic rate_limit_error → transient', () => {
    const err = {
      status: 429,
      error: { error: { type: 'rate_limit_error', message: '...' } },
    };
    expect(defaultIsTransient(err)).toBe(true);
  });

  it('Anthropic invalid_request_error → NON-transient', () => {
    const err = {
      status: 400,
      error: { error: { type: 'invalid_request_error', message: '...' } },
    };
    expect(defaultIsTransient(err)).toBe(false);
  });

  it('OpenAI rate_limit_exceeded → transient', () => {
    const err = { code: 'rate_limit_exceeded', message: 'rate-limited' };
    expect(defaultIsTransient(err)).toBe(true);
  });

  it('OpenAI 5xx → transient (via status check)', () => {
    const err = { status: 502, code: 'server_error' };
    expect(defaultIsTransient(err)).toBe(true);
  });

  it('Node ECONNRESET → transient', () => {
    const err = Object.assign(new Error('socket hang up'), {
      code: 'ECONNRESET',
    });
    expect(defaultIsTransient(err)).toBe(true);
  });

  it('Node ETIMEDOUT → transient', () => {
    const err = Object.assign(new Error('timeout'), { code: 'ETIMEDOUT' });
    expect(defaultIsTransient(err)).toBe(true);
  });

  it('Node ECONNREFUSED → transient', () => {
    const err = Object.assign(new Error('connection refused'), {
      code: 'ECONNREFUSED',
    });
    expect(defaultIsTransient(err)).toBe(true);
  });

  it('undici fetch failure (TypeError with .cause network code) → transient', () => {
    const cause = Object.assign(new Error('socket hang up'), {
      code: 'ECONNRESET',
    });
    const err = Object.assign(new TypeError('fetch failed'), { cause });
    expect(defaultIsTransient(err)).toBe(true);
  });

  it('AbortError → transient (timeout fired mid-flight)', () => {
    const err = Object.assign(new Error('aborted'), { name: 'AbortError' });
    expect(defaultIsTransient(err)).toBe(true);
  });

  it('null / non-object errors → non-transient', () => {
    expect(defaultIsTransient(null)).toBe(false);
    expect(defaultIsTransient(undefined)).toBe(false);
    expect(defaultIsTransient('boom')).toBe(false);
    expect(defaultIsTransient(42)).toBe(false);
  });

  it('plain Error without status/code → non-transient', () => {
    expect(defaultIsTransient(new Error('validation failed'))).toBe(false);
  });
});

describe('withRetry — backoff bounds', () => {
  it('full-jitter delay never exceeds maxDelayMs', async () => {
    const onRetry = vi.fn();
    const fn = vi
      .fn()
      .mockRejectedValueOnce(
        Object.assign(new Error('1'), { status: 503 })
      )
      .mockRejectedValueOnce(
        Object.assign(new Error('2'), { status: 503 })
      )
      .mockResolvedValueOnce('ok');

    const promise = withRetry(fn, {
      onRetry,
      baseDelayMs: 100,
      maxDelayMs: 200,
    });
    await flushTimers();
    await promise;

    // Both retries should respect the cap (computed = random(0, min(200, 100 * 2^attempt))).
    expect(onRetry.mock.calls[0][0].delayMs).toBeLessThanOrEqual(200);
    expect(onRetry.mock.calls[1][0].delayMs).toBeLessThanOrEqual(200);
  });
});
