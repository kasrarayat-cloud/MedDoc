// ============================================================================
// B1-a GATE — the vendor's request id survives the trip from the SDK response
// to the log payload, and the trap that would have eaten it is PINNED.
// ----------------------------------------------------------------------------
// ⚠️ WHAT MAKES THIS SUITE WORTH READING IS THE NEGATIVE CONTROL, NOT THE
// HAPPY PATH. `readAnthropicRequestId` is four lines and would pass its happy
// path just as well if it were written with a spread. The reason it is not, and
// the reason it must never be "simplified" into one, is asserted here directly:
// a spread copy of the very same object returns null.
//
// Without that arm this file would be decoration. A test that only proves
// direct access works cannot tell you that the alternative fails — and the
// alternative is what a future reader will reach for.
//
// Every fixture below is built with the SDK's OWN idiom, copied from the
// installed @anthropic-ai/sdk 0.85.0 (`internal/parse.js:55`):
//
//     Object.defineProperty(value, '_request_id', {
//       value: response.headers.get('request-id'),
//       enumerable: false,
//     });
//
// so the shape under test is the shape production receives, not a convenient
// stand-in that happens to be enumerable.
// ============================================================================

import { describe, expect, it, vi } from 'vitest';

import { readAnthropicRequestId, readDeepgramRequestId } from './vendor-request-id';

/** Build a response the way the Anthropic SDK does — non-enumerable. */
function sdkResponse(requestId: string | null): Record<string, unknown> {
  const value: Record<string, unknown> = {
    id: 'msg_01ABC',
    content: [{ type: 'text', text: 'hello' }],
    usage: { input_tokens: 10, output_tokens: 5 },
  };
  return Object.defineProperty(value, '_request_id', {
    value: requestId,
    enumerable: false,
  });
}

describe('readAnthropicRequestId', () => {
  it('reads the vendor id off a real SDK-shaped response', () => {
    expect(readAnthropicRequestId(sdkResponse('req_011CQ8xyz'))).toBe('req_011CQ8xyz');
  });

  // ── THE ARM THAT JUSTIFIES THE WHOLE FILE ───────────────────────────────
  it('NEGATIVE CONTROL: a spread copy loses the id — proving the trap is real', () => {
    const response = sdkResponse('req_011CQ8xyz');

    // Same object, three idioms anyone would reach for first. All three drop a
    // non-enumerable property silently — no throw, no warning, just undefined.
    expect(readAnthropicRequestId({ ...response })).toBeNull();
    expect(readAnthropicRequestId(Object.assign({}, response))).toBeNull();
    expect(readAnthropicRequestId(JSON.parse(JSON.stringify(response)))).toBeNull();

    // And the direct read still works on the original, so the nulls above are
    // the copies' fault and not a broken matcher.
    expect(readAnthropicRequestId(response)).toBe('req_011CQ8xyz');
  });

  it('confirms the property really is non-enumerable (pins the SDK contract)', () => {
    const response = sdkResponse('req_011CQ8xyz');
    expect(Object.keys(response)).not.toContain('_request_id');
    expect(JSON.stringify(response)).not.toContain('req_011CQ8xyz');
  });

  it('returns null — never a fabricated id — when the vendor sent no header', () => {
    // `headers.get('request-id')` returns null for an absent header, so this
    // is a real production shape, not a hypothetical.
    expect(readAnthropicRequestId(sdkResponse(null))).toBeNull();
  });

  it('returns null for junk input rather than throwing', () => {
    expect(readAnthropicRequestId(null)).toBeNull();
    expect(readAnthropicRequestId(undefined)).toBeNull();
    expect(readAnthropicRequestId('a string')).toBeNull();
    expect(readAnthropicRequestId({})).toBeNull();
    // Present but the wrong type, and present but empty — both are "no id".
    expect(readAnthropicRequestId({ _request_id: 42 })).toBeNull();
    expect(readAnthropicRequestId({ _request_id: '' })).toBeNull();
  });
});

describe('readDeepgramRequestId', () => {
  it('reads metadata.request_id off a batch response', () => {
    expect(
      readDeepgramRequestId({
        metadata: { duration: 12.5, request_id: 'dg_9f3c-4b21' },
        results: {},
      }),
    ).toBe('dg_9f3c-4b21');
  });

  it('returns null when the id is absent, rather than fabricating one', () => {
    expect(readDeepgramRequestId({ metadata: { duration: 12.5 } })).toBeNull();
    expect(readDeepgramRequestId({ results: {} })).toBeNull();
    expect(readDeepgramRequestId({ metadata: null })).toBeNull();
    expect(readDeepgramRequestId({ metadata: 'not-an-object' })).toBeNull();
    expect(readDeepgramRequestId(null)).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// THE WIRING — that the id reaches the WRITE PAYLOAD, not just the reader.
// ---------------------------------------------------------------------------
// ⚠️ `logAiCall` is FIRE-AND-FORGET (`void prisma.aiCall.create(...).catch(…)`),
// which is deliberate — a failed telemetry write must never break a clinical
// call. The standing rule for that shape is that it is proved only by something
// that READS THE WRITE BACK, so these assert the payload handed to the client
// rather than trusting that a function which cannot fail loudly did its job.
//
// ⚠️ AND THE SUPPRESSION ARM IS NOT OPTIONAL. `ai_calls` is real-vendor-only
// (B0 Q1), so `logAiCall` returns early under mock. A suite that only ran with
// the flag off would pass identically if the early return were deleted.

describe('logAiCall — the id reaches the create payload', () => {
  async function loadWithMocks(mockEnabled: boolean) {
    vi.resetModules();
    const create = vi.fn().mockResolvedValue({});
    vi.doMock('@meddoc/db', () => ({ default: { aiCall: { create } } }));
    vi.doMock('./mock', () => ({ isMockEnabled: () => mockEnabled }));
    const { logAiCall } = await import('./log');
    return { logAiCall, create };
  }

  const BASE = {
    practiceId: 'prac_1',
    purpose: 'soap' as const,
    provider: 'anthropic' as const,
    model: 'claude-sonnet-5',
    promptHash: 'abc123',
    latencyMs: 900,
    success: true,
  };

  it('persists the vendor id verbatim', async () => {
    const { logAiCall, create } = await loadWithMocks(false);
    logAiCall({ ...BASE, requestId: 'req_011CQ8xyz' });
    expect(create).toHaveBeenCalledTimes(1);
    expect(create.mock.calls[0][0].data.requestId).toBe('req_011CQ8xyz');
  });

  it('writes NULL — not a fabricated id — when the vendor gave none', async () => {
    const { logAiCall, create } = await loadWithMocks(false);
    logAiCall({ ...BASE, requestId: null });
    expect(create.mock.calls[0][0].data.requestId).toBeNull();

    // Omitted entirely is the same fact, and must reach the same value.
    const second = await loadWithMocks(false);
    second.logAiCall({ ...BASE });
    expect(second.create.mock.calls[0][0].data.requestId).toBeNull();
  });

  it('writes NOTHING under mock — ai_calls stays real-vendor-only (B0 Q1)', async () => {
    const { logAiCall, create } = await loadWithMocks(true);
    logAiCall({ ...BASE, requestId: 'req_011CQ8xyz' });
    expect(create).not.toHaveBeenCalled();
  });
});
