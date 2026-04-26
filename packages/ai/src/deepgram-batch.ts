// ============================================================================
// @meddoc/ai — Deepgram batch transcription (T-M4)
// ----------------------------------------------------------------------------
// The live client in ./deepgram.ts handles real-time audio from scribe's
// WebSocket sidecar. This module is the prerecorded counterpart that the
// TranscribeMD audio-upload pipeline needs: one POST to /v1/listen with
// the uploaded file as the request body.
//
// Options are locked here (diarize, utterances, punctuate, smart_format,
// paragraphs, nova-3-medical) so per-caller overrides can't degrade
// accuracy. This matches the "pipeline quality is non-negotiable" posture
// of T-M4.
// ============================================================================

import { logAiCall } from './log';
import { isMockEnabled, mockDeepgramBatch } from './mock';
import { deepgramBatchCostCents } from './pricing';
import type { AiLogContext } from './types';
import { logApiUsage, buildDeepgramUsage } from './api-usage';

const DEEPGRAM_BATCH_URL = 'https://api.deepgram.com/v1/listen';
export const DEFAULT_BATCH_MODEL = 'nova-3-medical';

export interface DeepgramBatchOptions {
  /** Speaker diarization. Defaults true (conversation transcripts).
   *  Set false for single-speaker dictation. */
  diarize?: boolean;
  /** Utterance segmentation. Defaults true — Layer 2/3 read these for
   *  role assignment + evidence quoting. Turn off for dictation where
   *  the whole transcript is treated as one block. */
  utterances?: boolean;
}

export interface DeepgramBatchStreamSource {
  /** Web ReadableStream — Node Readable should be converted via
   *  `Readable.toWeb(nodeReadable)`. */
  stream: ReadableStream<Uint8Array>;
  /** Object size in bytes. Required because Deepgram /v1/listen
   *  rejects chunked-transfer bodies; fetch needs Content-Length. */
  sizeBytes: number;
}

export interface DeepgramBatchArgs extends AiLogContext {
  /** Raw audio. Pass a Buffer for small/legacy paths, or a
   *  `{ stream, sizeBytes }` pair for the T-M18.2 streaming path
   *  that never buffers the whole file in the worker's memory. */
  audio: Buffer | DeepgramBatchStreamSource;
  /** MIME type from the upload (audio/mpeg, audio/mp4, audio/wav, etc).
   *  Deepgram accepts Content-Type and auto-detects encoding/sample-rate,
   *  which is what the live path also relies on. */
  mimeType: string;
  /** Override the default nova-3-medical model. Almost never needed. */
  model?: string;
  /** IETF language tag. Defaults to en. */
  language?: string;
  /** Network timeout in ms. Long by default — a 45 min recording takes
   *  Deepgram ~60s wall-clock to process. */
  timeoutMs?: number;
  /** T-M5 opt-outs for single-speaker dictation. Undefined = current
   *  Layer 1 conversation defaults (diarize+utterances on). */
  options?: DeepgramBatchOptions;
  /** Phase-2 voice batch 1 — Nova-3 `keyterm` prompting. Raises the
   *  prior on these tokens so near-homophone medications decode as
   *  the drug name instead of an invented word ("abirrobing" →
   *  "ibuprofen"). Passed as repeated ?keyterm= URL params. Callers
   *  (e.g. the TranscribeMD worker) supply the medication lexicon
   *  from apps/transcribe-md/src/lib/deepgram-vocabulary.ts.
   *  SDK @4.11.3 docs: https://developers.deepgram.com/docs/keyterm */
  keyterms?: readonly string[];
}

export interface DeepgramWord {
  word: string;
  start: number;
  end: number;
  confidence: number;
  speaker?: number;
  punctuated_word?: string;
}

export interface DeepgramUtterance {
  start: number;
  end: number;
  confidence: number;
  channel: number;
  transcript: string;
  words: DeepgramWord[];
  speaker?: number;
  id?: string;
}

export interface DeepgramParagraph {
  speaker: number;
  num_words: number;
  start: number;
  end: number;
  sentences: { text: string; start: number; end: number }[];
}

export interface DeepgramBatchResponse {
  metadata?: {
    duration?: number;
    channels?: number;
    request_id?: string;
    sha256?: string;
    [k: string]: unknown;
  };
  results?: {
    channels?: Array<{
      alternatives?: Array<{
        transcript?: string;
        confidence?: number;
        words?: DeepgramWord[];
        paragraphs?: {
          transcript?: string;
          paragraphs?: DeepgramParagraph[];
        };
      }>;
    }>;
    utterances?: DeepgramUtterance[];
  };
  [k: string]: unknown;
}

export interface DeepgramBatchResult {
  /** The full JSON response, persisted to TranscribeVisit.transcriptRaw. */
  raw: DeepgramBatchResponse;
  /** Flattened channel[0].alternatives[0].transcript for display/search. */
  transcript: string;
  /** Utterances with diarized speaker tags. Layer 2 reads this. */
  utterances: DeepgramUtterance[];
  /** Duration in whole seconds. Used for cost math + UI ETA hints. */
  durationSec: number;
}

/**
 * One-shot batch transcription. Throws on 4xx/5xx. Caller is responsible
 * for retry policy (L1 wraps this with one network retry on 5xx).
 */
export async function deepgramBatchTranscribe(
  args: DeepgramBatchArgs
): Promise<DeepgramBatchResult> {
  // T-M10: MOCK_AI_CALLS short-circuit. See packages/ai/src/mock.ts.
  if (isMockEnabled()) {
    return mockDeepgramBatch();
  }

  const apiKey = process.env.DEEPGRAM_API_KEY;
  if (!apiKey) {
    throw new Error('DEEPGRAM_API_KEY is not set.');
  }

  const model =
    args.model ?? process.env.DEEPGRAM_MODEL?.trim() ?? DEFAULT_BATCH_MODEL;
  const language = args.language ?? 'en';

  const wantDiarize = args.options?.diarize ?? true;
  const wantUtterances = args.options?.utterances ?? true;
  const params = new URLSearchParams({
    model,
    language,
    diarize: String(wantDiarize),
    punctuate: 'true',
    smart_format: 'true',
    paragraphs: 'true',
    utterances: String(wantUtterances),
    filler_words: 'false',
    detect_language: 'false',
  });
  // Phase-2 voice: append one ?keyterm= per entry. Deepgram accepts
  // the repeated-param form; URLSearchParams.append preserves order.
  // No-op when the caller omits keyterms.
  for (const term of args.keyterms ?? []) {
    const trimmed = term.trim();
    if (trimmed.length > 0) params.append('keyterm', trimmed);
  }
  const url = `${DEEPGRAM_BATCH_URL}?${params.toString()}`;
  const started = Date.now();

  // T-M18.2 A7: source type drives two parallel paths.
  //   Buffer  → legacy in-memory body (small payloads, export-path
  //             callers that already had the bytes)
  //   stream  → forward the MinIO stream directly into fetch, with
  //             Content-Length preset so Deepgram doesn't reject
  //             the chunked-transfer variant.
  let sizeBytes: number;
  let body: BodyInit;
  let isStreamed: boolean;
  if (args.audio instanceof Uint8Array) {
    isStreamed = false;
    sizeBytes = args.audio.byteLength;
    body = args.audio as unknown as BodyInit;
  } else {
    isStreamed = true;
    sizeBytes = args.audio.sizeBytes;
    body = args.audio.stream as unknown as BodyInit;
  }

  // promptHash carries "batch:<bytes>" as a size marker — we deliberately
  // never hash audio content (PHI).
  const promptHash = `batch:${sizeBytes}b`;

  const timeoutMs = args.timeoutMs ?? 10 * 60 * 1000; // 10 min ceiling.
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);

  let res: Response;
  try {
    // Node 22's fetch accepts Buffer and ReadableStream at runtime.
    // TS 5.6 narrowed BlobPart/BodyInit; cast to BodyInit — Node does
    // the right thing at runtime. For the streaming path we pass
    // `duplex: 'half'` (required by Node fetch when body is a stream).
    res = await fetch(url, {
      method: 'POST',
      headers: {
        Authorization: `Token ${apiKey}`,
        'Content-Type': args.mimeType,
        'Content-Length': String(sizeBytes),
      },
      body,
      signal: controller.signal,
      ...(isStreamed
        ? ({ duplex: 'half' } as { duplex: 'half' })
        : {}),
    });
  } catch (err) {
    clearTimeout(timer);
    const latencyMs = Date.now() - started;
    logAiCall({
      ...args,
      provider: 'deepgram',
      model,
      promptHash,
      latencyMs,
      success: false,
      errorCode:
        err instanceof Error && err.name === 'AbortError'
          ? 'TIMEOUT'
          : 'NETWORK_ERROR',
    });
    throw err;
  }
  clearTimeout(timer);

  const latencyMs = Date.now() - started;

  if (!res.ok) {
    let body = '';
    try {
      body = (await res.text()).slice(0, 500);
    } catch {
      body = '(body read failed)';
    }
    logAiCall({
      ...args,
      provider: 'deepgram',
      model,
      promptHash,
      latencyMs,
      success: false,
      errorCode: `HTTP_${res.status}`,
    });
    const err = new Error(
      `Deepgram batch failed: HTTP ${res.status} ${res.statusText} ${body}`
    ) as Error & { status?: number };
    err.status = res.status;
    throw err;
  }

  const raw = (await res.json()) as DeepgramBatchResponse;

  const firstChannel = raw.results?.channels?.[0]?.alternatives?.[0];
  const transcript = (firstChannel?.transcript ?? '').trim();
  const utterances = raw.results?.utterances ?? [];
  const durationSec = Math.round(raw.metadata?.duration ?? 0);

  logAiCall({
    ...args,
    provider: 'deepgram',
    model,
    promptHash,
    latencyMs,
    costUsdCents: deepgramBatchCostCents(durationSec),
    success: true,
  });

  logApiUsage(
    buildDeepgramUsage(
      {
        userId: args.userId ?? null,
        practiceId: args.practiceId,
        visitId: args.visitId ?? null,
        metadata: { purpose: args.purpose, latencyMs, model },
      },
      durationSec
    )
  );

  return {
    raw,
    transcript,
    utterances,
    durationSec,
  };
}
