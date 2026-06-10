// ============================================================================
// Typed errors — @meddoc/ai (FIND-P1-010).
// ----------------------------------------------------------------------------
// Shared error classes that the model-client / Anthropic / worker stack can
// instanceof-check rather than scraping `err.message` strings. Generic
// `new Error(...)` was load-bearing in three places before this module:
//
//   1. anthropic.ts threw `Error('Anthropic response was not valid JSON: ...')`
//      on a parse-fail; the model-client retry loop matched it by
//      `err.message.startsWith('Anthropic response was not valid JSON')`.
//   2. The same parse-fail propagated up to the worker outer catch as a
//      generic Error, surfacing as the user-facing "Processing failed"
//      reviewReason — not a doctor-actionable hint that the model output
//      was malformed.
//   3. categorizeError couldn't classify it without the same string match,
//      so a body that would NEVER parse still got "transient" + BullMQ retry.
//
// Replacing the generic throws with typed errors gives the retry loop +
// worker outer catch + categorizeError a clean instanceof gate.
// ============================================================================

/** Thrown when the Anthropic API returns content that can't be parsed as
 *  the requested JSON shape — typically a model regression where the
 *  response includes prose ("Sure! Here's the JSON...") around the
 *  payload, or trailing garbage after a closing brace.
 *
 *  Behavior contract:
 *    - The model-client retry loop (`modelClient.complete`) retries up to
 *      MAX_RETRIES on this error class. Each retry appends the malformed
 *      body to `retryContext` so the next prompt can self-correct.
 *    - After retry exhaustion, the error propagates up to the worker
 *      outer catch. `categorizeError` classifies it as `permanent` so
 *      BullMQ does NOT burn additional attempts on a body that won't ever
 *      parse — the visit fails fast with a doctor-actionable reviewReason.
 *    - Marked NON-transient for the `withRetry` helper at
 *      `packages/ai/src/retry.ts` too (defaultIsTransient returns false
 *      because the error has no HTTP status / SDK code, and the `name`
 *      doesn't match the transient short-list).
 *
 *  PHI guard: `rawTextSlice` is capped at 200 chars + scrubbed at log
 *  emission sites (logAiCall, worker-sentry beforeSend). The raw model
 *  output can include patient content quoted from the upstream
 *  transcript/SOAP, so callers must not log `.rawTextSlice` to operator-
 *  visible surfaces (admin UI, /admin/queues, public Sentry) without
 *  redactPhi first.
 */
export class ModelOutputMalformedError extends Error {
  readonly rawTextSlice: string;
  readonly parseError: unknown;
  readonly attempt?: number;

  constructor(
    rawText: string,
    parseError: unknown,
    options?: { attempt?: number }
  ) {
    // Cap at 200 chars — diagnostic snippet, not the whole body.
    const slice = (rawText ?? '').slice(0, 200);
    // Preserve the legacy message prefix so callers that match on
    // `err.message.startsWith('Anthropic response was not valid JSON')`
    // (model-client.ts pre-FIND-P1-010) continue to work during the
    // migration window. The instanceof check is the source of truth.
    const parseMessage =
      parseError instanceof Error ? parseError.message : String(parseError);
    super(`Anthropic response was not valid JSON: ${parseMessage}`);
    this.name = 'ModelOutputMalformedError';
    this.rawTextSlice = slice;
    this.parseError = parseError;
    this.attempt = options?.attempt;
  }
}

/**
 *  Thrown when Anthropic returns `stop_reason: 'refusal'` — the model
 *  declined to generate (content-policy / safety). A refusal is
 *  deterministic for the same input, so `categorizeError` maps it
 *  PERMANENT (by `name`) to avoid burning the BullMQ retry budget; the
 *  worker fails the visit into the DLQ with a clear reason + an
 *  `AI_REFUSAL` audit row. The note-format preview catches it and
 *  degrades (it must never block parse/save/activate).
 *
 *  PHI-safe: carries only the model id + purpose — NO model output /
 *  transcript content.
 */
export class AnthropicRefusalError extends Error {
  readonly code = 'AI_REFUSAL';
  readonly model: string;
  readonly purpose?: string;

  constructor(model: string, purpose?: string) {
    super(
      `Anthropic declined to generate (stop_reason=refusal)` +
        `${purpose ? ` for purpose=${purpose}` : ''} on model ${model}.`
    );
    this.name = 'AnthropicRefusalError';
    this.model = model;
    this.purpose = purpose;
  }
}
