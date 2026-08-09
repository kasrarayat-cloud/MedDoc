// ============================================================================
// @meddoc/ai — vendor request-id readers
// ----------------------------------------------------------------------------
// B1-a. One place where a vendor's own correlation id is lifted off a response,
// because the two vendors hide it in two different ways and BOTH of them punish
// the obvious code.
//
// ⚠️ ANTHROPIC'S `_request_id` IS NON-ENUMERABLE. THIS IS THE WHOLE REASON THIS
// FILE EXISTS, AND IT IS THE SILENT-NO-OP CLASS EXACTLY.
//
// Verified against the INSTALLED SDK (@anthropic-ai/sdk 0.85.0), not against a
// claim — `internal/parse.js:55`:
//
//     Object.defineProperty(value, '_request_id', {
//       value: response.headers.get('request-id'),
//       enumerable: false,
//     });
//
// A non-enumerable property is dropped, WITH NO ERROR, by every idiom anyone
// would reach for first:
//
//     { ...response }          → gone
//     Object.assign({}, resp)  → gone
//     JSON.parse(JSON.stringify(resp)) → gone
//
// So a builder written as `ctx.requestId ?? randomUUID()` fed from a spread copy
// would mint a fresh UUID on every call, look completely implemented, and meter
// nothing. `readAnthropicRequestId` therefore reads by DIRECT PROPERTY ACCESS,
// and its test asserts the negative control — that a spread copy loses it — so
// the trap itself is pinned rather than merely avoided today.
//
// ⚠️ AND IT CAN BE `null` ON A GENUINELY SUCCESSFUL CALL. The value is whatever
// `headers.get('request-id')` returned, and `get` returns `null` for an absent
// header. "The vendor was called" and "the vendor told us its request id" are
// two different facts, which is why every column fed from here is NULLABLE and
// why nothing in this file invents a substitute.
//
// ⚠️ THIS IS A DEPENDENCY-SENSITIVE FILE. The property is SDK-internal (leading
// underscore, non-enumerable) and PR #421 proposes 0.85.0 → 0.115.0. If that
// bump lands, re-read `internal/parse.js` before trusting this — the unit test
// pins the SHAPE we depend on, so a change in it should surface there first.
// ============================================================================

/**
 * Anthropic: lift `_request_id` off an SDK response.
 *
 * Returns the vendor's id, or `null` when the vendor did not supply one.
 * NEVER fabricates — a fabricated id is indistinguishable from a real one
 * afterwards, which is the fail-open shape the `unitsSource` ruling exists to
 * prevent (RULINGS.md 2026-08-08, "A provenance column's DEFAULT must never be
 * the TRUSTED value").
 */
export function readAnthropicRequestId(response: unknown): string | null {
  if (!response || typeof response !== 'object') return null;
  // Direct property access — see the header. Do NOT refactor this into a
  // destructure off a copied object; the copy does not carry the property.
  const id = (response as { _request_id?: unknown })._request_id;
  return typeof id === 'string' && id.length > 0 ? id : null;
}

/**
 * OpenAI: lift `_request_id` off an SDK response.
 *
 * ⚠️ SAME TRAP, SECOND VENDOR, DIFFERENT HEADER — which is exactly why this is
 * its own function rather than a call to `readAnthropicRequestId`. The body is
 * identical today. The EVIDENCE behind it is not, and a shared function would
 * have one header comment pinning one SDK while silently carrying two.
 *
 * Verified against the INSTALLED SDK (openai 6.34.0), `internal/parse.js:55`:
 *
 *     Object.defineProperty(value, '_request_id', {
 *       value: response.headers.get('x-request-id'),
 *       enumerable: false,
 *     });
 *
 * Note the header is `x-request-id` here and bare `request-id` at Anthropic.
 * Neither function reads a header directly — both read the property the SDK
 * has already populated — but the difference is recorded because the day one
 * SDK changes its header is the day these stop being interchangeable, and a
 * reader who found them merged would have no way to notice.
 *
 * B1-b step 1. Returns the vendor's id, or `null` when the vendor did not
 * supply one. NEVER fabricates — same contract as the Anthropic reader.
 */
export function readOpenAIRequestId(response: unknown): string | null {
  if (!response || typeof response !== 'object') return null;
  // Direct property access — non-enumerable, see the header. Do NOT refactor
  // this into a destructure off a copied object; the copy loses it silently.
  const id = (response as { _request_id?: unknown })._request_id;
  return typeof id === 'string' && id.length > 0 ? id : null;
}

/**
 * Deepgram: lift `metadata.request_id` off a batch response.
 *
 * Plain enumerable JSON — no defineProperty trap here. It is read through this
 * function anyway so that both vendors' ids arrive at the meter by the same
 * named route, and so the "returns null rather than inventing" contract is
 * stated once for both.
 *
 * ⚠️ It was ALREADY being persisted, in the wrong column: the full response is
 * written to `transcribe_visits.transcriptRaw` (jsonb) — a PHI-bearing column —
 * so the id has been durable and unqueryable this whole time. Reading it here
 * does not change that; moving it out of `transcriptRaw` is not B1-a's item.
 */
export function readDeepgramRequestId(response: unknown): string | null {
  if (!response || typeof response !== 'object') return null;
  const metadata = (response as { metadata?: unknown }).metadata;
  if (!metadata || typeof metadata !== 'object') return null;
  const id = (metadata as { request_id?: unknown }).request_id;
  return typeof id === 'string' && id.length > 0 ? id : null;
}
