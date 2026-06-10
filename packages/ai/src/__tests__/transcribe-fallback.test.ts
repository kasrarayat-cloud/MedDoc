// ============================================================================
// transcribe.ts orchestrator — Deepgram primary + Whisper fallback (PR-L)
// ----------------------------------------------------------------------------
// Pin the orchestrator's fallback semantics:
//
//   - Deepgram succeeds → result tagged `provider: 'deepgram-batch'`,
//     fallbackUsed=false. No Whisper call fires.
//   - Deepgram throws a 5xx / network error → Whisper is invoked +
//     result tagged `provider: 'whisper-fallback'`, fallbackUsed=true,
//     primaryError populated.
//   - Deepgram throws a permanent 4xx (bad audio) → orchestrator
//     re-throws the original error. Whisper is NOT invoked (a
//     different provider won't fix bad input).
//   - Audio > WHISPER_MAX_BYTES + Deepgram fails → orchestrator
//     re-throws the original error. Whisper is NOT invoked (the
//     fallback would 4xx on size pre-network).
// ============================================================================

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  deepgramBatch: vi.fn(),
  whisperBatch: vi.fn(),
}));

vi.mock('../deepgram-batch', () => ({
  deepgramBatchTranscribe: mocks.deepgramBatch,
  // Re-export the types so transcribe.ts compiles.
  DEFAULT_BATCH_MODEL: 'nova-3-medical',
}));

vi.mock('../whisper-batch', async () => {
  const real = await vi.importActual<
    typeof import('../whisper-batch')
  >('../whisper-batch');
  return {
    ...real,
    whisperBatchTranscribe: mocks.whisperBatch,
  };
});

import { transcribe, CrossProviderFallbackDisabledError } from '../transcribe';

const baseArgs = {
  practiceId: 'p1',
  visitId: 'v1',
  userId: 'u1',
  purpose: 'transcribe' as const,
  audio: Buffer.from(new Uint8Array(1024)), // 1 KB synthetic
  mimeType: 'audio/mpeg',
  // The cross-provider Whisper fallback is fail-closed (kill-switch).
  // These mechanism tests exercise the ENABLED path, so opt in
  // explicitly. The disabled path has its own describe block below.
  allowCrossProviderFallback: true,
};

beforeEach(() => {
  vi.clearAllMocks();
  mocks.deepgramBatch.mockResolvedValue({
    raw: { stub: true },
    transcript: 'hello world from deepgram',
    utterances: [],
    durationSec: 60,
  });
  mocks.whisperBatch.mockResolvedValue({
    provider: 'whisper',
    transcript: 'hello world from whisper',
    durationSec: 60,
    segments: [],
    language: 'en',
    costCents: 1,
  });
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe('transcribe() — Deepgram primary success path', () => {
  it('returns provider=deepgram-batch + fallbackUsed=false on Deepgram success', async () => {
    const result = await transcribe(baseArgs);

    expect(result.provider).toBe('deepgram-batch');
    expect(result.fallbackUsed).toBe(false);
    expect(result.transcript).toBe('hello world from deepgram');
    expect(mocks.deepgramBatch).toHaveBeenCalledTimes(1);
    expect(mocks.whisperBatch).not.toHaveBeenCalled();
  });

  it('does NOT fire Whisper when Deepgram succeeds (cost guard)', async () => {
    await transcribe(baseArgs);
    expect(mocks.whisperBatch).not.toHaveBeenCalled();
  });
});

describe('transcribe() — Whisper fallback path', () => {
  it('falls back to Whisper on Deepgram 5xx', async () => {
    const err500 = Object.assign(new Error('deepgram 502'), { status: 502 });
    mocks.deepgramBatch.mockRejectedValueOnce(err500);

    const result = await transcribe(baseArgs);

    expect(result.provider).toBe('whisper-fallback');
    expect(result.fallbackUsed).toBe(true);
    expect(result.primaryError?.status).toBe(502);
    expect(result.transcript).toBe('hello world from whisper');
    expect(mocks.whisperBatch).toHaveBeenCalledTimes(1);
  });

  it('falls back to Whisper on Deepgram network error (no status)', async () => {
    mocks.deepgramBatch.mockRejectedValueOnce(new Error('ECONNRESET'));

    const result = await transcribe(baseArgs);

    expect(result.provider).toBe('whisper-fallback');
    expect(result.fallbackUsed).toBe(true);
    expect(result.primaryError?.message).toContain('ECONNRESET');
    expect(mocks.whisperBatch).toHaveBeenCalledTimes(1);
  });

  it('falls back to Whisper on Deepgram 408 timeout (recoverable 4xx)', async () => {
    const err408 = Object.assign(new Error('timeout'), { status: 408 });
    mocks.deepgramBatch.mockRejectedValueOnce(err408);

    const result = await transcribe(baseArgs);

    expect(result.provider).toBe('whisper-fallback');
    expect(result.fallbackUsed).toBe(true);
  });

  it('falls back to Whisper on Deepgram 429 rate-limit (recoverable 4xx)', async () => {
    const err429 = Object.assign(new Error('rate limited'), { status: 429 });
    mocks.deepgramBatch.mockRejectedValueOnce(err429);

    const result = await transcribe(baseArgs);

    expect(result.provider).toBe('whisper-fallback');
    expect(result.fallbackUsed).toBe(true);
  });
});

describe('transcribe() — permanent 4xx skips fallback', () => {
  it('re-throws Deepgram 400 (bad audio) without firing Whisper', async () => {
    const err400 = Object.assign(new Error('unsupported MIME'), { status: 400 });
    mocks.deepgramBatch.mockRejectedValueOnce(err400);

    await expect(transcribe(baseArgs)).rejects.toThrow(/unsupported MIME/);
    expect(mocks.whisperBatch).not.toHaveBeenCalled();
  });

  it('re-throws Deepgram 415 (unsupported media type) without firing Whisper', async () => {
    const err415 = Object.assign(new Error('unsupported media'), {
      status: 415,
    });
    mocks.deepgramBatch.mockRejectedValueOnce(err415);

    await expect(transcribe(baseArgs)).rejects.toThrow(/unsupported media/);
    expect(mocks.whisperBatch).not.toHaveBeenCalled();
  });

  it('re-throws Deepgram 401 (auth failure) without firing Whisper', async () => {
    // Auth misconfiguration shouldn't cascade to spending money on the
    // fallback path — better to surface the deployment issue.
    const err401 = Object.assign(new Error('bad api key'), { status: 401 });
    mocks.deepgramBatch.mockRejectedValueOnce(err401);

    await expect(transcribe(baseArgs)).rejects.toThrow(/bad api key/);
    expect(mocks.whisperBatch).not.toHaveBeenCalled();
  });
});

describe('transcribe() — audio-size guard', () => {
  it('skips fallback when audio > 25 MB (Whisper would 4xx pre-network)', async () => {
    const oversize = Buffer.from(new Uint8Array(26 * 1024 * 1024));
    mocks.deepgramBatch.mockRejectedValueOnce(
      Object.assign(new Error('deepgram 503'), { status: 503 })
    );

    await expect(
      transcribe({ ...baseArgs, audio: oversize })
    ).rejects.toThrow(/deepgram 503/);
    expect(mocks.whisperBatch).not.toHaveBeenCalled();
  });
});

describe('transcribe() — both providers fail', () => {
  it('re-throws the Whisper error when both fail', async () => {
    mocks.deepgramBatch.mockRejectedValueOnce(
      Object.assign(new Error('deepgram down'), { status: 503 })
    );
    mocks.whisperBatch.mockRejectedValueOnce(
      Object.assign(new Error('whisper down'), { status: 503 })
    );

    await expect(transcribe(baseArgs)).rejects.toThrow(/whisper down/);
    expect(mocks.deepgramBatch).toHaveBeenCalledTimes(1);
    expect(mocks.whisperBatch).toHaveBeenCalledTimes(1);
  });
});

describe('transcribe() — cross-provider fallback kill-switch (fail-closed)', () => {
  it('does NOT call OpenAI on a Deepgram 5xx when fallback is disabled — throws CrossProviderFallbackDisabledError', async () => {
    const err503 = Object.assign(new Error('deepgram 503'), { status: 503 });
    mocks.deepgramBatch.mockRejectedValueOnce(err503);

    await expect(
      transcribe({ ...baseArgs, allowCrossProviderFallback: false })
    ).rejects.toBeInstanceOf(CrossProviderFallbackDisabledError);
    // The whole point: raw audio never reaches OpenAI.
    expect(mocks.whisperBatch).not.toHaveBeenCalled();
  });

  it('carries the primary Deepgram error on the thrown error (for the audit row)', async () => {
    const err502 = Object.assign(new Error('deepgram 502'), { status: 502 });
    mocks.deepgramBatch.mockRejectedValueOnce(err502);

    await expect(
      transcribe({ ...baseArgs, allowCrossProviderFallback: false })
    ).rejects.toMatchObject({
      name: 'CrossProviderFallbackDisabledError',
      code: 'CROSS_PROVIDER_FALLBACK_DISABLED',
      primaryError: { status: 502 },
    });
    expect(mocks.whisperBatch).not.toHaveBeenCalled();
  });

  it('blocks the fallback on a Deepgram network error (no status) when disabled', async () => {
    mocks.deepgramBatch.mockRejectedValueOnce(new Error('ECONNRESET'));

    await expect(
      transcribe({ ...baseArgs, allowCrossProviderFallback: false })
    ).rejects.toBeInstanceOf(CrossProviderFallbackDisabledError);
    expect(mocks.whisperBatch).not.toHaveBeenCalled();
  });

  it('FAIL-CLOSED by default: omitting the flag entirely also blocks the fallback', async () => {
    const { allowCrossProviderFallback, ...noFlag } = baseArgs;
    void allowCrossProviderFallback;
    mocks.deepgramBatch.mockRejectedValueOnce(
      Object.assign(new Error('deepgram 503'), { status: 503 })
    );

    await expect(transcribe(noFlag)).rejects.toBeInstanceOf(
      CrossProviderFallbackDisabledError
    );
    expect(mocks.whisperBatch).not.toHaveBeenCalled();
  });

  it('a permanent 4xx still re-throws the ORIGINAL Deepgram error (eligibility precedes the kill-switch), no fallback error', async () => {
    const err400 = Object.assign(new Error('unsupported MIME'), { status: 400 });
    mocks.deepgramBatch.mockRejectedValueOnce(err400);

    // Disabled flag must NOT mask a permanent input error as a
    // kill-switch error — the worker still needs the real reason.
    await expect(
      transcribe({ ...baseArgs, allowCrossProviderFallback: false })
    ).rejects.toThrow(/unsupported MIME/);
    expect(mocks.whisperBatch).not.toHaveBeenCalled();
  });
});
