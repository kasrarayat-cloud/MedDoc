// ============================================================================
// @meddoc/ai — Transcription orchestrator (PR-L resilience)
// ----------------------------------------------------------------------------
// Single entry point for batch transcription with provider fallback:
//
//   1. Try Deepgram nova-3-medical (primary — best clinical-domain
//      quality + speaker diarization).
//   2. On a transient/server failure (5xx, network blip, timeout),
//      fall back to OpenAI Whisper. Returns a result tagged
//      `provider: 'deepgram-batch' | 'whisper-fallback'` so Layer 2/3
//      can flag the visit for review.
//   3. On a permanent 4xx (bad audio MIME, file corrupt, etc.),
//      DON'T fall back — a different provider won't fix bad input.
//      Re-throw so the worker surfaces a `reviewReason` to the visit.
//
// KILL-SWITCH (2026-06-10, fail-closed) — the cross-provider hop in
// step 2 ships raw patient AUDIO to OpenAI, which requires a
// countersigned BAA (none on file — see docs/BAA_CHECKLIST.md). The
// fallback is therefore GATED behind `args.allowCrossProviderFallback`,
// which is fail-closed: ONLY `=== true` enables it; absent/false/
// anything-else = disabled. When disabled and a fallback WOULD have
// fired (transient Deepgram failure, audio fits), the orchestrator
// throws `CrossProviderFallbackDisabledError` instead of calling
// OpenAI — the worker catches it, emits a suppressed-fallback audit
// row, and fails the visit into the DLQ (retryable). The eligibility
// check (permanent-4xx / oversize) and Deepgram's own internal retries
// are unchanged — only the cross-provider hop is gated.
//
// PR-L NOTE — direction inversion from the task brief:
// The brief described "OpenAI Whisper → Deepgram" fallback. Reality
// (verified at PR-L time): the project has been Deepgram-only since
// T-M4 — there's no Whisper to fall back FROM. The actual resilience
// upgrade is Deepgram-PRIMARY → Whisper-FALLBACK (inverse of brief).
// Per memory #16, surfaced + shipped the inverted direction.
//
// PR-L FOUNDATION SCOPE: this orchestrator + the underlying
// whisper-batch module are the building blocks. Wiring this into
// Layer-1 (apps/transcribe-md/src/worker/layers/01-transcribe.ts)
// + the schema field that records which provider produced a given
// transcript is a follow-up PR (incremental rollout — let the
// orchestrator land in isolation first so its tests can pin the
// fallback shape before the worker depends on it).
// ============================================================================

import {
  deepgramBatchTranscribe,
  type DeepgramBatchArgs,
  type DeepgramBatchResult,
} from './deepgram-batch';
import {
  whisperBatchTranscribe,
  isPermanent4xxError,
  WHISPER_MAX_BYTES,
  type WhisperBatchResult,
} from './whisper-batch';
import { deepgramBatchCostCents } from './pricing';
import type { AiLogContext } from './types';

/** Re-exported helper used by the orchestrator's success-shape. The
 *  underlying pricing helper rounds to cents per Deepgram's published
 *  unit cost; the orchestrator just calls it. */
const deepgramBatchCostCentsHelper = deepgramBatchCostCents;

/** PR-L follow-up: stream-with-fallback-buffer source. The Deepgram
 *  primary path uses the stream (preserves T-M18.2's streaming
 *  optimization — never buffers the full audio in worker RAM). When
 *  fallback fires, the orchestrator calls toBuffer() to materialize
 *  the audio for Whisper (which only accepts multipart Buffer).
 *
 *  Callers (Layer-1) implement toBuffer() by re-opening the MinIO
 *  source + draining — the original stream above has been consumed
 *  by the failed Deepgram attempt, so a fresh open is required.
 */
export interface TranscribeStreamSource {
  stream: ReadableStream<Uint8Array>;
  sizeBytes: number;
  toBuffer: () => Promise<Buffer>;
}

export type TranscribeAudioSource = Buffer | TranscribeStreamSource;

/** Tag the orchestrator stamps on every result so downstream Layer
 *  2/3 + the audit trail know which provider produced this transcript.
 *  `whisper-fallback` is the canary value: any visit carrying this
 *  tag was processed during a Deepgram outage and may warrant extra
 *  review (Whisper doesn't diarize, so speaker labels are absent). */
export type TranscriptionProvider =
  | 'deepgram-batch'
  | 'whisper-fallback';

export interface TranscribeArgs extends AiLogContext {
  /** Audio source. Buffer = always-buffered shape (small files,
   *  legacy callers, tests). TranscribeStreamSource = stream-first
   *  shape that preserves T-M18.2's RAM optimization on the
   *  Deepgram primary path; the orchestrator calls toBuffer() only
   *  when fallback fires.
   *  Files > 25 MB skip Whisper fallback (per WHISPER_MAX_BYTES);
   *  a Deepgram failure on those surfaces. */
  audio: TranscribeAudioSource;
  /** MIME type — both providers auto-detect from this. */
  mimeType: string;
  /** IETF language tag. Defaults to 'en'. */
  language?: string;
  /** Pass-through to Deepgram primary call: keyterm prompts, etc. */
  deepgram?: Pick<DeepgramBatchArgs, 'options' | 'keyterms' | 'model' | 'timeoutMs' | 'maxAttempts'>;
  /** Pass-through to Whisper fallback call. */
  whisper?: { model?: string; timeoutMs?: number };
  /** Kill-switch for the cross-provider (Deepgram → OpenAI Whisper)
   *  fallback. FAIL-CLOSED: the cross-provider hop fires ONLY when this
   *  is exactly `true`. Absent / `false` / any other value = disabled,
   *  in which case an otherwise-eligible Deepgram failure throws
   *  {@link CrossProviderFallbackDisabledError} instead of shipping raw
   *  patient audio to OpenAI (which needs a countersigned BAA). The
   *  worker resolves this from `TRANSCRIBE_MD_WHISPER_FALLBACK_ENABLED`. */
  allowCrossProviderFallback?: boolean;
}

/** Unified result shape regardless of which provider succeeded. */
export interface TranscribeResult {
  /** Which provider produced this transcript. Layer 2/3 + the audit
   *  log read this — `whisper-fallback` flags the visit for review. */
  provider: TranscriptionProvider;
  /** Flattened transcript text. */
  transcript: string;
  /** Duration in seconds. */
  durationSec: number;
  /** Detected (or supplied) language. */
  language: string;
  /** Approximate cost stamp (cents). */
  costCents: number;
  /** Whether the primary call failed before this result was produced.
   *  When true, Layer 2/3 should treat downstream confidence
   *  thresholds with extra suspicion (the fallback provider has no
   *  speaker diarization). */
  fallbackUsed: boolean;
  /** Error from the primary attempt (only set when fallbackUsed=true).
   *  Captured for the audit trail; ops surfaces this in admin dashboards. */
  primaryError?: { message: string; status?: number };
  /** Raw provider result. Layer 2/3 read provider-specific fields
   *  (Deepgram utterances vs Whisper segments) via the discriminated
   *  union below. */
  raw:
    | { kind: 'deepgram'; data: DeepgramBatchResult }
    | { kind: 'whisper'; data: WhisperBatchResult };
}

/** Audio byte size — works for both Buffer + TranscribeStreamSource. */
function audioByteLength(source: TranscribeAudioSource): number {
  return Buffer.isBuffer(source) ? source.byteLength : source.sizeBytes;
}

/** Thrown when a cross-provider Whisper fallback WAS eligible (transient
 *  Deepgram failure, audio fits) but the fail-closed kill-switch
 *  (`allowCrossProviderFallback !== true`) blocked it. The worker
 *  catches this to emit a suppressed-fallback audit row and fail the
 *  visit into the DLQ — raw patient audio is NEVER sent to OpenAI.
 *
 *  Deliberately does NOT expose an HTTP `.status`: that keeps the L1
 *  `withRetry` from re-attempting (the job-level BullMQ retry already
 *  gives Deepgram fresh attempts) and lets `categorizeError` fall to
 *  its generous `transient` default so the visit stays retryable. The
 *  underlying primary error rides on `primaryError` for the audit. */
export class CrossProviderFallbackDisabledError extends Error {
  readonly code = 'CROSS_PROVIDER_FALLBACK_DISABLED';
  readonly primaryError: { message: string; status?: number };
  constructor(
    primaryError: { message: string; status?: number },
    options?: { cause?: unknown }
  ) {
    super(
      `Cross-provider transcription fallback is disabled (kill-switch); ` +
        `primary Deepgram transcription failed` +
        `${primaryError.status ? ` [${primaryError.status}]` : ''}: ${primaryError.message}`,
      options
    );
    this.name = 'CrossProviderFallbackDisabledError';
    this.primaryError = primaryError;
  }
}

/** Decide whether to attempt fallback after a primary failure.
 *
 *  Skip fallback when:
 *    - The error is a permanent 4xx from Deepgram (bad audio /
 *      unsupported MIME / corrupt file). Whisper would 4xx too.
 *    - The audio exceeds WHISPER_MAX_BYTES (25 MB). Whisper would
 *      reject pre-network; surface the original Deepgram error.
 *
 *  Otherwise (5xx, 408, 429, network failure, timeout) → fallback.
 */
function shouldFallback(args: TranscribeArgs, err: unknown): boolean {
  if (audioByteLength(args.audio) > WHISPER_MAX_BYTES) return false;
  if (isPermanent4xxError(err)) return false;
  return true;
}

/** Single-call orchestrator. Always succeeds via Deepgram OR Whisper
 *  OR throws (when both fail, or when the primary fails permanently
 *  + fallback isn't allowed for this audio). */
export async function transcribe(
  args: TranscribeArgs
): Promise<TranscribeResult> {
  let primaryError: { message: string; status?: number } | undefined;

  // ── Primary: Deepgram nova-3-medical ──
  try {
    // deepgramBatchTranscribe natively accepts Buffer | { stream,
    // sizeBytes }; our TranscribeStreamSource adds the toBuffer()
    // materializer used only on the fallback path. Strip toBuffer
    // before forwarding so the deepgram call doesn't see an
    // unrecognized field.
    const dgAudio: Buffer | { stream: ReadableStream<Uint8Array>; sizeBytes: number } =
      Buffer.isBuffer(args.audio)
        ? args.audio
        : { stream: args.audio.stream, sizeBytes: args.audio.sizeBytes };
    const deepgram = await deepgramBatchTranscribe({
      practiceId: args.practiceId,
      visitId: args.visitId,
      userId: args.userId,
      purpose: args.purpose,
      audio: dgAudio,
      mimeType: args.mimeType,
      language: args.language,
      ...(args.deepgram ?? {}),
    });
    // DeepgramBatchResult exposes transcript + durationSec but not
    // language or costCents — compute the cost via the same pricing
    // helper Layer-1 already uses (deepgramBatchCostCents lives in
    // pricing.ts), and treat language as the supplied arg or 'en'
    // since Deepgram nova-3-medical doesn't return a separate
    // detected-language field on the batch path.
    return {
      provider: 'deepgram-batch',
      transcript: deepgram.transcript,
      durationSec: deepgram.durationSec,
      // 2026-05-12 interpreter-mode: prefer Deepgram's detected language
      // when present (returned only when the caller set
      // options.detectLanguage=true). Falls back to the caller-supplied
      // language or 'en' on visits that didn't request detection.
      language: deepgram.detectedLanguage ?? args.language ?? 'en',
      costCents: deepgramBatchCostCentsHelper(deepgram.durationSec),
      fallbackUsed: false,
      raw: { kind: 'deepgram', data: deepgram },
    };
  } catch (err) {
    primaryError = {
      message: err instanceof Error ? err.message : String(err),
      status:
        typeof err === 'object' && err !== null && 'status' in err
          ? (err as { status?: number }).status
          : undefined,
    };
    if (!shouldFallback(args, err)) {
      // Permanent failure or audio too large for Whisper — re-throw
      // the original error so the worker surfaces it to the visit.
      throw err;
    }
    // Fallback IS eligible for this transient failure — but is the
    // cross-provider hop allowed? FAIL-CLOSED: only an explicit
    // `=== true` opt-in (env-driven in the worker) lets raw patient
    // audio reach OpenAI. Otherwise throw a typed error so the worker
    // emits a suppressed-fallback audit + DLQs the visit. Never silent,
    // never OpenAI.
    if (args.allowCrossProviderFallback !== true) {
      throw new CrossProviderFallbackDisabledError(primaryError, { cause: err });
    }
  }

  // ── Fallback: OpenAI Whisper ──
  // Reaching here means: primary failed, fallback allowed, audio fits.
  // Whisper's multipart upload requires a Buffer — materialize the
  // stream source via toBuffer() if needed. Layer-1 implements
  // toBuffer() by re-opening the MinIO source (the original stream
  // was consumed by the Deepgram primary attempt).
  const whisperAudio: Buffer = Buffer.isBuffer(args.audio)
    ? args.audio
    : await args.audio.toBuffer();
  const whisper = await whisperBatchTranscribe({
    practiceId: args.practiceId,
    visitId: args.visitId,
    userId: args.userId,
    purpose: args.purpose,
    audio: whisperAudio,
    mimeType: args.mimeType,
    language: args.language,
    ...(args.whisper ?? {}),
  });

  return {
    provider: 'whisper-fallback',
    transcript: whisper.transcript,
    durationSec: whisper.durationSec,
    language: whisper.language,
    costCents: whisper.costCents,
    fallbackUsed: true,
    primaryError,
    raw: { kind: 'whisper', data: whisper },
  };
}
