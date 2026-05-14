// ============================================================================
// withRetry — shared transient-error retry helper for @meddoc/ai
// ----------------------------------------------------------------------------
// FIND-P1-006 / -007 / -008 / -009 (comprehensive-audit 2026-05-14):
// Multiple transcription / model call sites had ad-hoc retry blocks (or
// none). The audit clustered them as one bundle. This helper is the
// shared shape they all flow into.
//
// Policy (Kasra, 2026-05-14):
//   - Jitter: FULL JITTER. delay = random(0, min(maxDelayMs, base * 2^attempt))
//     The AWS-recommended pattern for thundering-herd resilience — pure
//     randomization is less correlated than additive jitter, which matters
//     when many workers retry simultaneously on a regional provider blip.
//   - Default budget: 3 attempts (configurable per call site).
//   - isTransient: 429 + 5xx + ECONNRESET / ETIMEDOUT / ECONNREFUSED /
//     EAI_AGAIN + Anthropic "overloaded_error"/"rate_limit_error" + OpenAI
//     "rate_limit_exceeded" + OpenAI 5xx.
//   - Retry-After: honored when present, parsed as seconds OR HTTP-date.
//     Capped at maxDelayMs (default 30s) so a server-set retry of 60s
//     can't block the worker pipeline indefinitely.
//   - Telemetry hook: onRetry({attempt, error, delayMs}) — caller wires
//     this to structured logging. NO PHI in the payload; this helper
//     never logs anything on its own.
//
// The helper is intentionally NOT coupled to worker/error-categorize.ts —
// that one classifies errors into transient/permanent/provider_down for
// fail-fast decisions; this one decides "should we retry RIGHT NOW".
// The classes overlap but are not identical (e.g., provider_down →
// don't retry, treat as transient locally).
// ============================================================================

/** Options for `withRetry`. All fields optional; defaults are tuned for
 *  the transcription + model-client call sites. */
export interface RetryOptions {
  /** Total attempts including the first. `1` = no retry. Default `3`. */
  maxAttempts?: number;
  /** Base delay for exponential backoff in milliseconds. Default `500`. */
  baseDelayMs?: number;
  /** Hard cap on any computed delay (including Retry-After). Default
   *  `30000` (30s). Prevents a server-set huge Retry-After from blocking
   *  worker concurrency indefinitely. */
  maxDelayMs?: number;
  /** Predicate that decides if a thrown error is worth retrying. Default
   *  is `defaultIsTransient` (429 + 5xx + network + structured
   *  Anthropic/OpenAI error types). */
  isTransient?: (err: unknown) => boolean;
  /** Telemetry hook called once per retry, AFTER the decision to retry
   *  but BEFORE the delay sleep. Caller is responsible for any logging;
   *  the helper never logs on its own. */
  onRetry?: (info: RetryAttemptInfo) => void;
}

export interface RetryAttemptInfo {
  /** 1-based attempt number that JUST FAILED. So `attempt=1` means the
   *  first attempt failed and a retry is about to happen. */
  attempt: number;
  /** Total `maxAttempts` so the caller can log "1 of 3". */
  maxAttempts: number;
  /** The thrown error from the failed attempt. */
  error: unknown;
  /** Delay in ms before the next attempt (after jitter + Retry-After
   *  cap). */
  delayMs: number;
}

/** Default retry predicate. Matches the union of provider error shapes
 *  the QuillMD AI stack actually sees in production. */
export function defaultIsTransient(err: unknown): boolean {
  if (err === null || typeof err !== 'object') return false;
  const obj = err as Record<string, unknown>;

  // HTTP status — many SDKs hang it on .status / .statusCode / .response.status.
  const status = readStatus(obj);
  if (typeof status === 'number') {
    if (status === 429) return true;
    if (status === 408) return true; // request timeout
    if (status >= 500 && status < 600) return true;
    // 4xx (except 408/429) is non-transient — bad input, bad auth, etc.
    if (status >= 400 && status < 500) return false;
  }

  // Anthropic SDK structured error: { error: { error: { type: '...' } } }
  // overloaded_error: 529 surge; rate_limit_error: hit token/req budget
  const anthropicType = readNestedString(obj, ['error', 'error', 'type']);
  if (
    anthropicType === 'overloaded_error' ||
    anthropicType === 'rate_limit_error'
  ) {
    return true;
  }

  // OpenAI SDK structured error: { code: 'rate_limit_exceeded', ... }
  // The SDK also throws RateLimitError / APIError with .code populated.
  const openaiCode = typeof obj.code === 'string' ? obj.code : null;
  if (openaiCode === 'rate_limit_exceeded') return true;

  // Node fetch / OS network errors — error.code on AggregateError or
  // SystemError. fetch may also throw a TypeError('fetch failed') with
  // .cause carrying the SystemError; check both depths.
  const nodeCode = readNetworkCode(obj);
  if (nodeCode) {
    switch (nodeCode) {
      case 'ECONNRESET':
      case 'ETIMEDOUT':
      case 'ECONNREFUSED':
      case 'ENETUNREACH':
      case 'EAI_AGAIN':
      case 'EPIPE':
      case 'UND_ERR_SOCKET':
        return true;
    }
  }

  // AbortError mid-flight (timeout fired while waiting on the wire) —
  // retryable. Caller's own timeout still bounds the total.
  const errName = typeof obj.name === 'string' ? obj.name : null;
  if (errName === 'AbortError' || errName === 'TimeoutError') return true;

  // Plain fetch-failure TypeError from undici — usually wraps a network
  // error in .cause.
  if (errName === 'TypeError' && readNetworkCode(obj)) return true;

  return false;
}

/** Wraps `fn` with retry-on-transient-failure. See module docstring for
 *  policy. */
export async function withRetry<T>(
  fn: () => Promise<T>,
  options?: RetryOptions
): Promise<T> {
  const maxAttempts = options?.maxAttempts ?? 3;
  const baseDelayMs = options?.baseDelayMs ?? 500;
  const maxDelayMs = options?.maxDelayMs ?? 30_000;
  const isTransient = options?.isTransient ?? defaultIsTransient;
  const onRetry = options?.onRetry;

  let lastErr: unknown;
  for (let attempt = 1; attempt <= maxAttempts; attempt++) {
    try {
      return await fn();
    } catch (err) {
      lastErr = err;
      if (attempt === maxAttempts || !isTransient(err)) {
        throw err;
      }

      // Compute delay. Retry-After (if present and parseable) wins over
      // computed backoff, capped at maxDelayMs either way.
      const retryAfterMs = readRetryAfter(err);
      const expBackoffCap = Math.min(
        maxDelayMs,
        baseDelayMs * 2 ** (attempt - 1)
      );
      const computedDelay = Math.floor(Math.random() * expBackoffCap);
      const delayMs =
        retryAfterMs !== null
          ? Math.min(maxDelayMs, retryAfterMs)
          : computedDelay;

      if (onRetry) {
        try {
          onRetry({ attempt, maxAttempts, error: err, delayMs });
        } catch {
          // Telemetry hook failures must never break retry logic.
        }
      }

      if (delayMs > 0) {
        await new Promise((r) => setTimeout(r, delayMs));
      }
    }
  }
  // Unreachable — loop above either returns on success or throws on the
  // final attempt. Throw for type safety.
  throw lastErr;
}

// ----------------------------------------------------------------------------
// Internal helpers
// ----------------------------------------------------------------------------

function readStatus(obj: Record<string, unknown>): number | undefined {
  for (const key of ['status', 'statusCode']) {
    const v = obj[key];
    if (typeof v === 'number' && Number.isFinite(v)) return v;
  }
  const resp = obj.response;
  if (resp && typeof resp === 'object') {
    const rstatus = (resp as Record<string, unknown>).status;
    if (typeof rstatus === 'number' && Number.isFinite(rstatus)) return rstatus;
  }
  return undefined;
}

function readNestedString(
  obj: Record<string, unknown>,
  path: string[]
): string | null {
  let current: unknown = obj;
  for (const key of path) {
    if (current === null || typeof current !== 'object') return null;
    current = (current as Record<string, unknown>)[key];
  }
  return typeof current === 'string' ? current : null;
}

function readNetworkCode(obj: Record<string, unknown>): string | null {
  const direct = obj.code;
  if (typeof direct === 'string') return direct;
  const cause = obj.cause;
  if (cause && typeof cause === 'object') {
    const causeCode = (cause as Record<string, unknown>).code;
    if (typeof causeCode === 'string') return causeCode;
  }
  return null;
}

/** Parse Retry-After header from an error's headers bag. Accepts both
 *  seconds (integer string) and HTTP-date formats. Returns milliseconds
 *  or null. */
function readRetryAfter(err: unknown): number | null {
  if (err === null || typeof err !== 'object') return null;
  const obj = err as Record<string, unknown>;

  const rawHeader = findHeader(obj, 'retry-after');
  if (rawHeader === null) return null;

  // Numeric seconds — most common shape from rate-limit responses.
  const seconds = Number(rawHeader);
  if (Number.isFinite(seconds) && seconds >= 0) {
    return Math.floor(seconds * 1000);
  }

  // HTTP-date — rare but spec-allowed.
  const dateMs = Date.parse(rawHeader);
  if (Number.isFinite(dateMs)) {
    const delta = dateMs - Date.now();
    return delta > 0 ? delta : 0;
  }

  return null;
}

/** Look for a header value in the shapes SDKs use:
 *    err.headers['retry-after']
 *    err.response.headers['retry-after']
 *    err.response.headers.get('retry-after')  (Headers instance)
 */
function findHeader(
  obj: Record<string, unknown>,
  name: string
): string | null {
  const lowerName = name.toLowerCase();

  const tryBag = (bag: unknown): string | null => {
    if (bag === null || typeof bag !== 'object') return null;
    // Headers instance — has .get()
    if (typeof (bag as { get?: unknown }).get === 'function') {
      const v = (bag as { get: (k: string) => string | null }).get(lowerName);
      return typeof v === 'string' ? v : null;
    }
    // Plain object: try the name as-is and lowercased.
    const asObj = bag as Record<string, unknown>;
    for (const key of Object.keys(asObj)) {
      if (key.toLowerCase() === lowerName) {
        const v = asObj[key];
        if (typeof v === 'string') return v;
        if (Array.isArray(v) && typeof v[0] === 'string') return v[0];
      }
    }
    return null;
  };

  const fromTop = tryBag(obj.headers);
  if (fromTop !== null) return fromTop;

  const resp = obj.response;
  if (resp && typeof resp === 'object') {
    const fromResp = tryBag((resp as Record<string, unknown>).headers);
    if (fromResp !== null) return fromResp;
  }

  return null;
}
