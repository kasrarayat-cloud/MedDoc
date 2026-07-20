// ============================================================================
// @meddoc/ai — OpenAI Whisper batch transcription (PR-L resilience)
// ----------------------------------------------------------------------------
// Fallback transcription provider for when Deepgram batch is degraded
// or rate-limiting. Deepgram nova-3-medical is the primary path
// (better clinical-domain quality); Whisper is the resilience backstop
// so a single-vendor outage doesn't take down the pipeline.
//
// Whisper API (POST /v1/audio/transcriptions) accepts up to 25MB per
// request. Larger files (>25MB ≈ 30+ min of mp3) are rejected with a
// 400; the orchestrator in `transcribe.ts` treats that as permanent
// and surfaces to the visit `reviewReason` rather than retrying.
//
// Auth: OPENAI_API_KEY env var (same key the LLM layers use).
//
// Cost / instrumentation: per-minute usage event via buildWhisperUsage()
// + AiCall row via logAiCall() with provider='openai' (the AiCall
// table's ModelProvider enum doesn't include 'whisper' — Whisper IS
// OpenAI; the per-provider rollups distinguish via the api_usage_events
// table where the granular `provider: 'whisper'` lives).
// ============================================================================

import OpenAI from 'openai';

import { logAiCall } from './log';
import { PRICING } from './api-usage';
import { withRetry, type RetryAttemptInfo } from './retry';
import type { AiLogContext } from './types';
import { logApiUsage, buildWhisperUsage } from './api-usage';
import {
  TEMPLATE_TWIN_SYNTHETIC_QA_TRANSCRIPT,
  syntheticQaFixtureForProviderCall,
} from './synthetic-qa-context';

export const DEFAULT_WHISPER_MODEL = 'whisper-1';

/** Max upload size Whisper accepts. Files larger than this are
 *  rejected by the API with HTTP 400; we check ahead of time so the
 *  orchestrator can classify the failure as permanent without
 *  touching the network. */
export const WHISPER_MAX_BYTES = 25 * 1024 * 1024;

export interface WhisperBatchArgs extends AiLogContext {
  /** Raw audio bytes. Whisper API multipart upload caps at 25 MB —
   *  see WHISPER_MAX_BYTES. */
  audio: Buffer;
  /** MIME type from the upload (audio/mpeg, audio/mp4, audio/wav). */
  mimeType: string;
  /** Filename for the multipart part. Whisper uses the extension to
   *  pick the decoder; default is `audio.bin`. */
  filename?: string;
  /** Override the default whisper-1 model. Almost never needed. */
  model?: string;
  /** IETF language tag. Whisper auto-detects when omitted. */
  language?: string;
  /** Network timeout in ms. Default 5 min — Whisper batches a 30 min
   *  file in ~30s wall-clock. */
  timeoutMs?: number;
  /** Server-owned authorization fence run immediately before network egress. */
  beforeProviderAttempt?: () => Promise<void>;
  /** Matching fence run after network response or failure. */
  afterProviderAttempt?: () => Promise<void>;
}

/** Word-level segment from Whisper's verbose_json response. */
export interface WhisperSegment {
  id: number;
  start: number;
  end: number;
  text: string;
  avg_logprob: number;
  /** 0..1 — Whisper's no-speech probability for this segment. The
   *  Deepgram-equivalent confidence flag uses (1 - no_speech_prob). */
  no_speech_prob: number;
  /** Compression ratio — > 2.4 indicates likely-hallucination. The
   *  orchestrator can flag low-quality segments via this. */
  compression_ratio: number;
  /** Average temperature used during decoding for this segment. */
  temperature: number;
}

export interface WhisperBatchResponse {
  text: string;
  language: string;
  duration: number;
  segments: WhisperSegment[];
}

export interface WhisperBatchResult {
  /** Provider tag for downstream classification + auditing. */
  provider: 'whisper';
  /** Flattened transcript (Whisper's `text` field). */
  transcript: string;
  /** Total duration in seconds (Whisper's `duration` field). */
  durationSec: number;
  /** Per-segment timing + confidence info. Layer 2/3 consume these
   *  the same way they consume Deepgram utterances. */
  segments: WhisperSegment[];
  /** Detected (or supplied) IETF language tag. */
  language: string;
  /** Approximate cost in cents based on duration × Whisper unit cost. */
  costCents: number;
}

/** Build the OpenAI client. Lazy + cached so test environments that
 *  set OPENAI_API_KEY late don't get burned by import-time evaluation. */
let cachedClient: OpenAI | null = null;
function getOpenAIClient(): OpenAI {
  if (cachedClient) return cachedClient;
  const apiKey = process.env.OPENAI_API_KEY;
  if (!apiKey || apiKey.length === 0) {
    throw new Error(
      'whisper-batch: OPENAI_API_KEY env var unset. The fallback path requires it.'
    );
  }
  cachedClient = new OpenAI({ apiKey });
  return cachedClient;
}

/** Test-only hook: lets unit tests inject a stub OpenAI client without
 *  having to mock the entire module. Production calls use the cached
 *  lazy client; tests use this to avoid network. */
export function __setOpenAIClientForTests(c: OpenAI | null): void {
  cachedClient = c;
}

/** Convert duration in seconds to cost in cents using PRICING.whisper.
 *  Mirrors the inline math buildWhisperUsage uses. */
function whisperBatchCostCents(audioDurationSec: number): number {
  const minutes = audioDurationSec / 60;
  return Math.round(minutes * PRICING.whisper * 100);
}

/** Permanent-failure classifier — the orchestrator skips Whisper
 *  fallback when Deepgram returns a permanent 4xx (the audio itself
 *  is bad; a different provider won't fix it). Used by `transcribe.ts`. */
export function isPermanent4xxError(err: unknown): boolean {
  if (typeof err !== 'object' || err === null) return false;
  const e = err as { status?: number; statusCode?: number };
  const status = e.status ?? e.statusCode;
  if (typeof status === 'number') {
    // 408 (timeout) + 429 (rate limit) are RECOVERABLE 4xx — caller
    // should still try the fallback. Everything else 4xx is permanent.
    if (status === 408 || status === 429) return false;
    if (status >= 400 && status < 500) return true;
  }
  return false;
}

/** Whisper batch transcription. Throws on:
 *   - missing OPENAI_API_KEY (config error)
 *   - audio > WHISPER_MAX_BYTES (permanent — orchestrator surfaces)
 *   - Whisper API 4xx (mostly permanent; 408/429 are transient)
 *   - Network failure (transient — caller can retry)
 *
 *  FIND-P1-007 (2026-05-14): Whisper is the load-bearing fallback when
 *  Deepgram fails. Wrapped in `withRetry` (full-jitter, 2 attempts) so
 *  a transient OpenAI 5xx during the Deepgram-failed path doesn't
 *  produce hard FAILED state with no automatic recovery.
 *
 *  Returns a `WhisperBatchResult` with the transcript + timing +
 *  cost stamp on success.
 */
export async function whisperBatchTranscribe(
  args: WhisperBatchArgs
): Promise<WhisperBatchResult> {
  // A staging visit may reach this function when the ordinary Deepgram
  // orchestrator evaluates its fallback branch. Keep the provider boundary
  // closed here as defense in depth: exact visit/practice context returns the
  // reviewed transcript without reading audio or constructing an OpenAI
  // client; mismatched context throws instead of falling through live.
  if (syntheticQaFixtureForProviderCall(args)) {
    return {
      provider: 'whisper',
      transcript: TEMPLATE_TWIN_SYNTHETIC_QA_TRANSCRIPT,
      durationSec: 0,
      segments: [],
      language: args.language ?? 'en',
      costCents: 0,
    };
  }
  return withRetry(() => whisperBatchTranscribeOnce(args), {
    maxAttempts: 2,
    baseDelayMs: 1000,
    onRetry: (info: RetryAttemptInfo) => {
      const err = info.error as {
        status?: number;
        code?: string;
        type?: string;
      };
      console.warn(
        '[whisper-batch] retrying',
        JSON.stringify({
          attempt: info.attempt,
          maxAttempts: info.maxAttempts,
          delayMs: info.delayMs,
          status: err?.status ?? null,
          code: err?.code ?? null,
        })
      );
    },
  });
}

/** Internal single-attempt Whisper transcribe. Renamed from
 *  `whisperBatchTranscribe` during FIND-P1-007 closure. */
async function whisperBatchTranscribeOnce(
  args: WhisperBatchArgs
): Promise<WhisperBatchResult> {
  const t0 = Date.now();
  const model = args.model ?? DEFAULT_WHISPER_MODEL;
  // logAiCall requires a non-empty promptHash; transcription has no
  // prompt — use a stable sentinel so per-provider rollups still
  // group correctly.
  const PROMPT_HASH_SENTINEL = 'whisper-batch:audio';

  if (args.audio.byteLength > WHISPER_MAX_BYTES) {
    const err = new Error(
      `whisper-batch: audio is ${args.audio.byteLength} bytes; max ${WHISPER_MAX_BYTES} bytes (Whisper API cap).`
    );
    (err as { status?: number }).status = 400;
    throw err;
  }

  const client = getOpenAIClient();
  // OpenAI SDK's audio.transcriptions.create accepts a File-like.
  // Build a Blob (web-platform Blob is available in Node 18+ via
  // node:buffer) so we don't have to write to /tmp.
  //
  // TS strict: Buffer + Uint8Array's typed-array buffer field is
  // ArrayBufferLike, but BlobPart wants ArrayBufferView<ArrayBuffer>.
  // Slice copies the bytes into a fresh ArrayBuffer (not Shared),
  // which both satisfies the type and detaches the Blob from the
  // caller's buffer (slightly safer for concurrent use).
  const detached = args.audio.buffer.slice(
    args.audio.byteOffset,
    args.audio.byteOffset + args.audio.byteLength
  ) as ArrayBuffer;
  const blob = new Blob([new Uint8Array(detached)], { type: args.mimeType });
  const file = new File([blob], args.filename ?? 'audio.bin', {
    type: args.mimeType,
  });

  let response: WhisperBatchResponse;
  await args.beforeProviderAttempt?.();
  try {
    response = (await client.audio.transcriptions.create(
      {
        file,
        model,
        language: args.language,
        response_format: 'verbose_json',
      },
      {
        timeout: args.timeoutMs ?? 5 * 60 * 1000,
        ...(args.beforeProviderAttempt || args.afterProviderAttempt
          ? { maxRetries: 0 }
          : {}),
      },
    )) as unknown as WhisperBatchResponse;
  } catch (err) {
    void logAiCall({
      ...args,
      provider: 'openai',
      model,
      promptHash: PROMPT_HASH_SENTINEL,
      latencyMs: Date.now() - t0,
      success: false,
      errorCode:
        typeof err === 'object' && err !== null && 'status' in err
          ? String((err as { status?: number }).status ?? 'unknown')
          : 'unknown',
    });
    throw err;
  } finally {
    await args.afterProviderAttempt?.();
  }

  const durationSec = response.duration ?? 0;
  const costCents = whisperBatchCostCents(durationSec);

  void logAiCall({
    ...args,
    provider: 'openai',
    model,
    promptHash: PROMPT_HASH_SENTINEL,
    latencyMs: Date.now() - t0,
    success: true,
    costUsdCents: costCents,
  });

  // logApiUsage is fire-and-forget (returns void) — no .catch needed.
  logApiUsage(buildWhisperUsage(args, durationSec));

  return {
    provider: 'whisper',
    transcript: response.text,
    durationSec,
    segments: response.segments ?? [],
    language: response.language ?? args.language ?? 'en',
    costCents,
  };
}
