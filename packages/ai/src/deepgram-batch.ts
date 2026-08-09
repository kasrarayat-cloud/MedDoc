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
import { readDeepgramRequestId } from './vendor-request-id';
import { isMockEnabled, mockDeepgramBatch } from './mock';
import { deepgramBatchCostCents } from './pricing';
import { withRetry, type RetryAttemptInfo } from './retry';
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
  /** 2026-05-12 interpreter-mode: request Deepgram to detect the
   *  spoken language(s) and switch to a multilingual model internally.
   *  Used in conjunction with `language: 'multi'` for code-switching
   *  audio (e.g., Spanish patient + English doctor + interpreter).
   *  When true, the returned `DeepgramBatchResult.detectedLanguage`
   *  carries the IETF tag Deepgram inferred. */
  detectLanguage?: boolean;
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
  /** 2026-05-12 interpreter-mode: IETF language tag Deepgram detected
   *  when `detectLanguage: true` was requested. Examples: 'en' (English
   *  only), 'es' (Spanish only), 'multi' (code-switching). Undefined
   *  when detection wasn't requested or the response didn't carry it. */
  detectedLanguage?: string;
}

/**
 * Public entry point — wraps the underlying transcribe call in
 * `withRetry` (full-jitter backoff, default 2 attempts) for transient
 * Deepgram failures. FIND-P1-006 (2026-05-14): non-L1 callers (eval
 * harness, regression baseline) used to get zero retries on Deepgram
 * 5xx; this gives them the same safety net as the worker path.
 *
 * The L1 worker layer ALSO retries this call (via its own withRetry).
 * For pilot scale that double-retry is acceptable; the helper's
 * `defaultIsTransient` predicate matches both layers' intent.
 *
 * Throws on 4xx (permanent input error) or after retries exhaust.
 */
export async function deepgramBatchTranscribe(
  args: DeepgramBatchArgs
): Promise<DeepgramBatchResult> {
  return withRetry(() => deepgramBatchTranscribeOnce(args), {
    maxAttempts: 2,
    baseDelayMs: 1000,
    onRetry: (info: RetryAttemptInfo) => {
      // Structured telemetry — NO PHI in payload, just operational shape.
      // The error.status (or .code) is enough to debug post-mortem
      // without surfacing audio metadata or transcripts.
      const err = info.error as { status?: number; code?: string };
      console.warn(
        '[deepgram-batch] retrying',
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

/**
 * Internal single-attempt transcribe. Renamed from `deepgramBatchTranscribe`
 * during FIND-P1-006 closure; the public wrapper above adds retry. Throws
 * on 4xx/5xx.
 */
async function deepgramBatchTranscribeOnce(
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
  const wantDetectLanguage = args.options?.detectLanguage ?? false;
  // Deepgram rejects `language` + `detect_language=true` together; we
  // drop the explicit language tag when detection is on so the model
  // chooses based on the audio itself. The result carries the inferred
  // tag back via `metadata.detected_language`.
  const baseParams: Record<string, string> = {
    model,
    diarize: String(wantDiarize),
    punctuate: 'true',
    smart_format: 'true',
    paragraphs: 'true',
    utterances: String(wantUtterances),
    filler_words: 'false',
  };
  if (wantDetectLanguage) {
    baseParams.detect_language = 'true';
    // `language=multi` opts the model into code-switching mode.
    baseParams.language = 'multi';
  } else {
    baseParams.language = language;
    baseParams.detect_language = 'false';
  }
  const params = new URLSearchParams(baseParams);
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
    // ── B1-b step 1 — DEEPGRAM ID SEMANTICS, SITE 1 OF 2. STATED, NOT SKIPPED.
    // The ruling said to include the two remaining sites "if they are the same
    // shape; if they are not, state that vendor's id semantics explicitly."
    // They are not, and the two differ from each other:
    //
    //   THIS SITE — `fetch` itself threw (timeout / DNS / connection reset).
    //   There is NO response object in scope, and on a TIMEOUT the request may
    //   never have reached Deepgram at all. `requestId` is therefore genuinely
    //   absent, not merely uncaptured, and NULL here is the honest value.
    //
    // Deepgram's id lives in the BODY (`metadata.request_id`), unlike Anthropic
    // and OpenAI which expose it as a non-enumerable property on a parsed SDK
    // response. This caller uses raw `fetch`, so there is no SDK to populate one.
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
    // ── B1-b step 1 — DEEPGRAM ID SEMANTICS, SITE 2 OF 2.
    //
    //   THIS SITE — Deepgram ANSWERED, with a non-2xx. A response exists, and
    //   an id very likely exists WITH it — but not where `readDeepgramRequestId`
    //   looks. That reader parses `metadata.request_id` out of a JSON body, and
    //   an error body is read as TEXT two lines above (deliberately, and capped
    //   at 500 chars) because Deepgram's error bodies are not the batch schema.
    //   The id on this path is carried by the `dg-request-id` RESPONSE HEADER.
    //
    // ⚠️ CAPTURING IT IS DELIBERATELY NOT DONE HERE. Reading a header is a new
    // third id-source shape, and the failure paths are B2's item by name ("wire
    // the failure paths into the durable table"). Step 1's job is to stop the
    // SIZING being fabricated, and the sizing counts SUCCESS rows — so widening
    // into B2 here would buy nothing this ruling asked for and would leave B2
    // half-done under another item's name. Recorded in RELAY.md as B2's input,
    // with the header named, so B2 does not have to rediscover it.
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

  // (Pre-existing variable name `firstChannel` here actually refers to
  // alternatives[0]; the surrounding code has used the misnomer for
  // multiple releases. Kept as-is to minimize diff surface.)
  const firstChannel = raw.results?.channels?.[0]?.alternatives?.[0];
  const transcript = (firstChannel?.transcript ?? '').trim();
  const utterances = raw.results?.utterances ?? [];
  const durationSec = Math.round(raw.metadata?.duration ?? 0);
  // 2026-05-12 interpreter-mode: Deepgram returns the inferred language
  // when `detect_language` was requested. Per the Deepgram response
  // shape the tag lives at THE CHANNEL OBJECT level (not the
  // alternative — see https://developers.deepgram.com/docs/language-
  // detection). We check the channel first, then fall back to the
  // alternative (some response shapes carry it there), then metadata,
  // before giving up with undefined. Keeps `detectedLanguage` safe
  // against future Deepgram payload reshuffles.
  const channelObj = raw.results?.channels?.[0] as
    | { detected_language?: unknown }
    | undefined;
  const altObj = firstChannel as { detected_language?: unknown } | undefined;
  const metaObj = raw.metadata as { detected_language?: unknown } | undefined;
  const detectedLanguage =
    typeof channelObj?.detected_language === 'string'
      ? (channelObj.detected_language as string)
      : typeof altObj?.detected_language === 'string'
        ? (altObj.detected_language as string)
        : typeof metaObj?.detected_language === 'string'
          ? (metaObj.detected_language as string)
          : undefined;

  // B1-a — Deepgram's own correlation id. It was ALREADY here, in `raw`, and
  // already durable: the whole response is persisted to
  // `transcribe_visits.transcriptRaw` (jsonb). So the id has been stored this
  // entire time in a PHI-bearing column nobody can bill from. Reading it into
  // a queryable column is B1-a; getting it OUT of `transcriptRaw` is not.
  const vendorRequestId = readDeepgramRequestId(raw);

  logAiCall({
    ...args,
    provider: 'deepgram',
    model,
    promptHash,
    latencyMs,
    costUsdCents: deepgramBatchCostCents(durationSec),
    success: true,
    requestId: vendorRequestId,
  });

  logApiUsage(
    buildDeepgramUsage(
      {
        // B0: a REAL vendor call — see UnitsSource.
        unitsSource: 'vendor',
        userId: args.userId ?? null,
        practiceId: args.practiceId,
        visitId: args.visitId ?? null,
        // B1-a: `?? undefined`, never `?? randomUUID()` — see anthropic.ts.
        requestId: vendorRequestId ?? undefined,
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
    detectedLanguage,
  };
}
