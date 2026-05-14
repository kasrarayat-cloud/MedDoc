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

/** Q2 follow-up — Anthropic SDK errors. The SDK throws BadRequestError
 *  / AuthenticationError / PermissionDeniedError / NotFoundError for
 *  structured 4xx responses. The body shape is:
 *    { type: 'error', error: { type: <api-error-type>, message: <text> } }
 *  with api-error-type ∈ {'invalid_request_error',
 *  'authentication_error', 'permission_error', 'not_found_error',
 *  'request_too_large', …}. All of these are permanent — the same
 *  wire payload will fail identically every time; retry only burns
 *  the BullMQ attempt budget without a chance of success.
 *
 *  Caught the temperature-deprecation 400 in production (Opus 4.7
 *  rejected `temperature`); pre-fix the categorizer treated it as
 *  transient and the worker burned 6 attempts on it. */
const PERMANENT_API_ERROR_TYPES = new Set([
  'invalid_request_error',
  'authentication_error',
  'permission_error',
  'not_found_error',
  'request_too_large',
]);

function isPermanent4xxApiError(err: unknown): boolean {
  if (err === null || typeof err !== 'object') return false;
  const obj = err as Record<string, unknown>;
  const status = obj.status;
  if (typeof status !== 'number' || status < 400 || status >= 500) return false;
  // The SDK's parsed body lives at err.error; the API's nested error
  // type is err.error.error.type.
  const body = obj.error as Record<string, unknown> | undefined;
  const inner = body?.error as Record<string, unknown> | undefined;
  const apiErrorType = inner?.type;
  if (typeof apiErrorType !== 'string') return false;
  return PERMANENT_API_ERROR_TYPES.has(apiErrorType);
}

/** Match patterns that mean "this input will never process correctly,
 *  no matter how many times we retry". Conservative on purpose — when
 *  in doubt, treat as transient.
 *
 *  Deepgram-specific note: a 400 from Deepgram with a config error
 *  ("Keyterm limit exceeded", "Invalid model", etc.) is permanent —
 *  the same audio + same wire config will fail identically on every
 *  retry. We pattern-match those explicitly because the generic
 *  "isLikelyTransient" path treats most non-5xx as transient by
 *  default, and burning 3 BullMQ attempts on a config bug just
 *  triples the noise. */
function isPermanentInputError(msg: string, err: unknown): boolean {
  if (err instanceof Error && err.constructor?.name === 'ZodError') return true;
  // Round 3 PR-D — A06-P0-001 empty-transcript guard. PipelineRejectError
  // is thrown by the deterministic pipeline-entry guards (audio too
  // short, transcript too short). Same audio means same outcome —
  // BullMQ retries cannot help. Mark permanent so the worker's
  // shouldFailNow short-circuit fires immediately.
  if (err instanceof Error && err.name === 'PipelineRejectError') return true;
  // FIND-P1-010 (2026-05-14) — model returned non-JSON after the
  // model-client retry exhausted. The body won't parse on the next
  // BullMQ retry either (Claude doesn't see prior responses across
  // BullMQ attempts; the only retry-context that helped lived inside
  // the model-client loop, which already burned its budget). Mark
  // permanent so shouldFailNow fires and the visit fails fast with
  // a clearer reviewReason rather than burning two more attempts.
  if (err instanceof Error && err.name === 'ModelOutputMalformedError') return true;
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
  // Deepgram 4xx config errors — permanent because they're driven by
  // wire-config (keyterm budget, model name, sample rate) rather than
  // the audio itself.
  if (
    /keyterm (limit )?exceeded/.test(lower) ||
    /maximum number of (tokens|keyterms)/.test(lower) ||
    /invalid keyterm/.test(lower) ||
    /invalid model/.test(lower) ||
    /unsupported (codec|encoding|sample[- ]?rate)/.test(lower)
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
  // Q2 follow-up: Anthropic 4xx structured errors (invalid_request,
  // auth, permission, not_found, request_too_large) are also
  // permanent. Same wire payload will fail identically on retry.
  if (isPermanent4xxApiError(err)) return 'permanent';
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
