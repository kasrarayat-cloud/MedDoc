// ============================================================================
// Worker error categorization (commit 2 of fix/voice-retry-robustness).
// ----------------------------------------------------------------------------
// Sorts a caught pipeline error into one of three buckets so the worker's
// FAILED branch can decide whether to fail-fast (skipping BullMQ's
// auto-retry budget) and the UI can render a category-specific copy.
//
//   transient      — a network blip / 5xx / timeout. Worth retrying.
//   permanent      — input is wrong (corrupt audio, unsupported format,
//                    Zod validation, etc). No amount of retry helps.
//   provider_down  — same upstream provider has thrown 5xx repeatedly
//                    in the last PROVIDER_WINDOW_MS. UI tells the
//                    doctor to wait it out.
//
// Pure module — only side effect is the small in-memory ring of
// provider-failure timestamps used to detect provider_down. The
// worker is a single Node process today (concurrency=2), so the
// ring stays accurate without Redis. A cluster move means moving
// this counter to Redis or accepting per-instance accuracy.
// ============================================================================

export type ErrorCategory = 'transient' | 'permanent' | 'provider_down';

type Provider = 'deepgram' | 'anthropic' | 'openai' | 'minio' | 'unknown';

// Look-back window for the "same provider keeps 5xx-ing" heuristic.
// 60s matches the spec — long enough to catch a real outage, short
// enough that one bad request doesn't poison the bucket for an hour.
const PROVIDER_WINDOW_MS = 60_000;

// How many 5xx hits inside the window flip a provider to "down".
// Three keeps a single transient blip from triggering "service is
// down" copy.
const PROVIDER_DOWN_THRESHOLD = 3;

// Stamps of recent 5xx hits per provider. Trimmed lazily on every
// record / read so it doesn't grow unbounded.
const providerFailures = new Map<Provider, number[]>();

function recordProviderFailure(provider: Provider): void {
  if (provider === 'unknown') return;
  const now = Date.now();
  const cutoff = now - PROVIDER_WINDOW_MS;
  const stamps = (providerFailures.get(provider) ?? []).filter(
    (t) => t > cutoff
  );
  stamps.push(now);
  providerFailures.set(provider, stamps);
}

function isProviderDown(provider: Provider): boolean {
  if (provider === 'unknown') return false;
  const cutoff = Date.now() - PROVIDER_WINDOW_MS;
  const stamps = (providerFailures.get(provider) ?? []).filter(
    (t) => t > cutoff
  );
  // Keep the trimmed array — saves work on the next call.
  providerFailures.set(provider, stamps);
  return stamps.length >= PROVIDER_DOWN_THRESHOLD;
}

/** Test-only — let the suite reset the in-memory ring between cases. */
export function _resetProviderFailuresForTesting(): void {
  providerFailures.clear();
}

// ----------------------------------------------------------------------------
// Heuristics
// ----------------------------------------------------------------------------

function getMessage(err: unknown): string {
  if (err instanceof Error) return err.message ?? '';
  if (typeof err === 'string') return err;
  return '';
}

/** HTTP status if the thrown thing exposes one. Many SDKs hang it on
 *  `.status`, `.statusCode`, or `.response.status`. We don't trust
 *  any single shape — try them in order and return undefined if none
 *  match. */
function getStatus(err: unknown): number | undefined {
  if (err === null || typeof err !== 'object') return undefined;
  const obj = err as Record<string, unknown>;
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

function getProvider(err: unknown): Provider {
  const msg = getMessage(err).toLowerCase();
  if (/deepgram/.test(msg)) return 'deepgram';
  if (/anthropic|claude/.test(msg)) return 'anthropic';
  if (/openai|gpt/.test(msg)) return 'openai';
  if (/minio|s3/.test(msg)) return 'minio';
  // Fall back to error class names that some SDKs use.
  const ctorName =
    err instanceof Error
      ? err.constructor?.name?.toLowerCase() ?? ''
      : '';
  if (ctorName.includes('deepgram')) return 'deepgram';
  if (ctorName.includes('anthropic')) return 'anthropic';
  if (ctorName.includes('openai')) return 'openai';
  return 'unknown';
}

/** Match patterns that mean "this input will never process correctly,
 *  no matter how many times we retry". Conservative on purpose — when
 *  in doubt, treat as transient. */
function isPermanentInputError(msg: string, err: unknown): boolean {
  if (err instanceof Error && err.constructor?.name === 'ZodError') return true;
  const lower = msg.toLowerCase();
  if (
    /unsupported( (audio|file))? format/.test(lower) ||
    /unrecognized( (audio|file))? format/.test(lower) ||
    /file (is )?too short/.test(lower) ||
    /audio (is )?too short/.test(lower) ||
    /audio (file )?(is )?(corrupt|malformed|invalid)/.test(lower) ||
    /no audio (data |stream )?detected/.test(lower) ||
    /empty audio/.test(lower) ||
    /could not (decode|parse) audio/.test(lower) ||
    /zero[- ]?byte/.test(lower)
  ) {
    return true;
  }
  return false;
}

/** Match patterns that look transient — a connection blip or a 5xx
 *  from a remote service. */
function isLikelyTransient(msg: string, status: number | undefined): boolean {
  if (typeof status === 'number' && status >= 500 && status < 600) return true;
  // 408 (request timeout) and 429 (rate-limited) are transient too —
  // BullMQ's exp backoff is a fine response.
  if (status === 408 || status === 429) return true;
  const lower = msg.toLowerCase();
  return (
    /\betimedout\b/.test(lower) ||
    /\bekonn?reset\b/.test(lower) ||
    /\beconnreset\b/.test(lower) ||
    /\beconnrefused\b/.test(lower) ||
    /\benetunreach\b/.test(lower) ||
    /\beai_again\b/.test(lower) ||
    /\beagain\b/.test(lower) ||
    /\babort(ed)?\b/.test(lower) ||
    /timeout(ed)?\b/.test(lower) ||
    /socket hang up/.test(lower) ||
    /network error/.test(lower) ||
    /fetch failed/.test(lower)
  );
}

/** Categorize a caught error into transient / permanent / provider_down.
 *  Side effect: records the timestamp of this error against its
 *  provider so subsequent calls within PROVIDER_WINDOW_MS can detect
 *  a sustained outage. */
export function categorizeError(err: unknown): ErrorCategory {
  const msg = getMessage(err);
  const status = getStatus(err);

  // Permanent first — a Zod / format error doesn't get to be
  // "transient" just because it happens to also include the word
  // "timeout" somewhere in the message.
  if (isPermanentInputError(msg, err)) return 'permanent';

  const transient = isLikelyTransient(msg, status);
  if (transient) {
    const provider = getProvider(err);
    recordProviderFailure(provider);
    return isProviderDown(provider) ? 'provider_down' : 'transient';
  }

  // Default: be generous and treat unknowns as transient. A real
  // permanent bug deserves an explicit pattern above.
  return 'transient';
}
