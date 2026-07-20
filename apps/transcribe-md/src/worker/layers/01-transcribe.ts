// ============================================================================
// Layer 1 — Deepgram batch transcription (T-M4)
// ----------------------------------------------------------------------------
// Downloads the uploaded audio from MinIO, hands it to Deepgram's
// /v1/listen endpoint with nova-3-medical + diarize + utterances +
// smart_format + paragraphs + punctuate, persists the full response +
// a flattened transcript + the audio duration.
//
// One retry on 5xx. 4xx fails immediately with a helpful reviewReason
// so the clinician sees why (bad content type, corrupt file, etc).
// ============================================================================

import { Readable } from "node:stream";

import { updateTemplateTwinSyntheticQaClaimBoundVisit } from "@/worker/staging-qa-mutation-fence";
// PR-L follow-up: swap direct Deepgram call → transcribe() orchestrator.
// transcribe() = Deepgram primary + Whisper fallback on transient
// failures. Result tagged provider='deepgram-batch' or 'whisper-fallback'
// so the visit row + audit trail record which provider produced
// transcript. See packages/ai/src/transcribe.ts header for the full
// fallback semantics + the foundation-scope rationale (PR #162).
import {
  withRetry,
  CrossProviderFallbackDisabledError,
  type TranscribeResult,
  type RetryAttemptInfo,
} from "@meddoc/ai";
import { runTemplateTwinOwnedTranscribe } from "@/lib/template-twin/provider-ownership";
import { statAudio, streamAudio } from "@/lib/minio";
import {
  isWhisperFallbackEnabled,
  WHISPER_FALLBACK_FLAG,
} from "@/worker/transcription-fallback-flag";
// 2026-05-13 Issues #202 + #206 — keyterms are now scoped per-visit
// via the builder rather than a single global list. See
// `buildKeytermsForVisit` for the composition rules.
import { buildKeytermsForVisit } from "@/lib/deepgram-keyterm-builder";
import { CONFUSED_DRUG_NAMES_FLAT } from "@/lib/confused-drug-names";
import { logWorkerAudit } from "@/worker/worker-audit";
import {
  computeAudioConfidenceStats,
  shouldFlagForReview,
  LOW_CONFIDENCE_THRESHOLD,
} from "./audio-confidence";

export interface Layer1Input {
  visitId: string;
  practiceId: string;
  userId: string | null;
  audioKey: string;
  audioMimeType: string | null;
  /** 2026-05-12 interpreter-mode flag from the visit row. When true,
   *  L1 switches from nova-3-medical (English-only) to nova-3 with
   *  `detect_language: true` + `language: multi` so the multilingual
   *  Spanish/English audio of an interpreted visit gets captured
   *  instead of producing the fragmentary English-only transcript the
   *  Sylvia incident surfaced. */
  interpreterMode?: boolean;
  /** 2026-05-13 Issues #202 + #206 — visit specialty used to scope the
   *  Deepgram keyterm list. Pulled from `transcribe_visits.specialty`
   *  by the worker. Free-text — the builder normalizes internally. */
  specialty?: string | null;
}

export interface Layer1Output {
  durationSec: number;
  utteranceCount: number;
  /** Count of distinct speaker IDs Deepgram returned (Layer 2 reads
   *  this to know how many roles to assign). */
  speakerCount: number;
  /** 2026-05-12 interpreter-mode: IETF language tag Deepgram detected
   *  (e.g. 'en', 'es', 'multi') on visits where interpreterMode was
   *  set. Undefined on standard English visits. worker.ts persists
   *  this to transcribe_visits.detectedLanguage. */
  detectedLanguage?: string;
}

const BACKOFF_MS = 2_000;

export async function runLayer1Transcribe(
  input: Layer1Input,
): Promise<Layer1Output> {
  if (!input.audioMimeType) {
    throw new Error("[L1] audioMimeType is missing — cannot contact Deepgram.");
  }

  // T-M18.2 A7 + PR-L: open the audio source once. The orchestrator
  // uses the stream for the Deepgram primary attempt; if that fails
  // and Whisper fallback fires, toBuffer() re-opens the MinIO stream
  // + drains (the original was already consumed by the failed
  // primary). Streaming on the happy path; ~30 MB peak RAM only on
  // the rare fallback case.
  const stat = await statAudio(input.audioKey);
  if (!stat || typeof stat.size !== "number") {
    throw new Error(
      `[L1] audio object missing or has no size: ${input.audioKey}`,
    );
  }
  const nodeStream = await streamAudio(input.audioKey);
  const webStream = Readable.toWeb(nodeStream) as ReadableStream<Uint8Array>;

  // Compose per-visit keyterm list. Interpreter mode skips this
  // entirely (model swaps to nova-3 general which doesn't accept
  // keyterm bias the same way); see the deepgram branch below.
  //
  // PR-2 (Issues #202 + #206): the ISMP confused-drug-names ride as
  // the always-loaded safety floor. The Implanon → insulin
  // substitution from Issue #206 is the seed case for the floor;
  // the T-cluster (Trulicity/Tradjenta/Toujeo/Tresiba/Tanzeum) is
  // the highest-density ISMP confusion cluster in QuillMD's
  // endocrine wedge.
  const built = input.interpreterMode
    ? null
    : buildKeytermsForVisit({
        specialty: input.specialty,
        safetyFloor: CONFUSED_DRUG_NAMES_FLAT,
      });

  // 2026-06-10 kill-switch (audit 4.2): the Deepgram→Whisper hop ships
  // raw audio to OpenAI (no BAA). Fail-closed — resolve the gate from
  // env per-run so the orchestrator only crosses providers when the
  // operator has explicitly enabled it post-BAA.
  const allowCrossProviderFallback = isWhisperFallbackEnabled();

  const attempt = async () => {
    return runTemplateTwinOwnedTranscribe({
      operation: "L1_TRANSCRIBE",
      operationVersion: "deepgram-batch-l1-v1",
      audioIdentity: {
        objectKey: input.audioKey,
        objectEtag: stat.etag ?? null,
        sizeBytes: stat.size,
        lastModifiedIso: stat.lastModified?.toISOString() ?? null,
      },
      args: {
        practiceId: input.practiceId,
        visitId: input.visitId,
        userId: input.userId,
        purpose: "tm_transcribe",
        allowCrossProviderFallback,
        audio: {
          stream: webStream,
          sizeBytes: stat.size,
          // Re-open + drain on fallback. Buffer.concat with a typed
          // chunks list keeps the conversion small + explicit.
          toBuffer: async () => {
            const fresh = await streamAudio(input.audioKey);
            const chunks: Buffer[] = [];
            for await (const chunk of fresh) {
              chunks.push(Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk));
            }
            return Buffer.concat(chunks);
          },
        },
        mimeType: input.audioMimeType!,
        deepgram: input.interpreterMode
          ? {
              // 2026-05-12 interpreter-mode (Sylvia incident follow-up):
              // nova-3-medical is English-only; running it on a mixed-
              // language interpreted visit produces a fragmentary
              // transcript with only the doctor's English questions.
              // Switching to nova-3 general + detect_language=true +
              // language=multi captures the code-switching audio.
              // Domain-specific keyterm biasing is lost (Nova-3 general
              // doesn't accept it the same way) — accepted trade-off
              // since we'd rather have the full transcript with weaker
              // drug-name handling than a half-conversation with strong
              // medical bias.
              model: "nova-3",
              options: {
                detectLanguage: true,
                // The 2-speaker hint is wrong for interpreter visits
                // (doctor + patient + interpreter = 3 voices). Deepgram
                // diarization handles N speakers natively; this just
                // matches the SOAP-side expectation downstream.
              },
            }
          : {
              // 2026-05-13 Issues #202 + #206 — keyterms composed per-visit
              // from core + specialty + (PR-2 safety floor). Persisted to
              // transcribe_visits.keytermsApplied below so a future
              // transcription regression can be attributed to the exact
              // keyterm set that ran.
              keyterms: built?.keyterms ?? [],
            },
      },
    });
  };

  // FIND-P1-008 (2026-05-14): replaced inline retry+setTimeout with the
  // shared `withRetry` helper. 2 attempts (1 retry) preserves the prior
  // semantic. Full-jitter backoff is the policy change — pure
  // randomization within [0, baseDelayMs * 2^attempt] decorrelates
  // retries across concurrent workers, avoiding a thundering-herd on a
  // Deepgram region's recovery.
  // `defaultIsTransient` skips 4xx (except 408/429), matching the prior
  // "4xx is terminal" guard; it ALSO skips plain Error-without-status,
  // which used to retry — more correct: a no-status throw is almost
  // always a code bug, not a transient API failure.
  let result: TranscribeResult;
  try {
    result = await withRetry(attempt, {
      maxAttempts: 2,
      baseDelayMs: BACKOFF_MS,
      onRetry: (info: RetryAttemptInfo) => {
        const err = info.error as { status?: number; code?: string };
        console.warn(
          "[layer-01-transcribe] retrying",
          JSON.stringify({
            attempt: info.attempt,
            maxAttempts: info.maxAttempts,
            delayMs: info.delayMs,
            status: err?.status ?? null,
            code: err?.code ?? null,
          }),
        );
      },
    });
  } catch (err) {
    // 2026-06-10 kill-switch (audit 4.2): Deepgram failed and a Whisper
    // fallback WAS eligible, but the cross-provider hop is disabled. Emit
    // a suppressed-fallback audit row so operators can see how often a
    // real Deepgram failure would have shipped audio to OpenAI, then
    // re-throw — the worker's outer catch fails the visit into the DLQ
    // (retryable). Raw audio never leaves to OpenAI. Fire-and-forget,
    // matching the success-fallback audit below.
    if (err instanceof CrossProviderFallbackDisabledError) {
      await logWorkerAudit({
        action: "TRANSCRIPTION_PROVIDER_FALLBACK",
        targetType: "TranscribeVisit",
        targetId: input.visitId,
        userId: input.userId,
        practiceId: input.practiceId,
        success: false,
        errorCode: "CROSS_PROVIDER_FALLBACK_DISABLED",
        metadata: {
          layer: "L1",
          suppressed: true,
          reason: "fallback_disabled",
          flag: WHISPER_FALLBACK_FLAG,
          primaryProvider: "deepgram-batch",
          wouldHaveUsed: "whisper-fallback",
          primaryError: err.primaryError.message ?? null,
          primaryStatus: err.primaryError.status ?? null,
        },
      });
    }
    throw err;
  }

  // PR-L: discriminated-union of provider raw shape. Deepgram path
  // gives us speaker labels + per-utterance confidence; Whisper has
  // segments + no diarization. Layer 2 reads `result.raw.kind` to
  // decide which extraction path to run.
  const utterances =
    result.raw.kind === "deepgram" ? result.raw.data.utterances : [];
  const speakerIds = new Set<number>();
  for (const u of utterances) {
    if (typeof u.speaker === "number") speakerIds.add(u.speaker);
  }

  // Round 3 quality fix-pack Q0-5 (audit Findings 02.5 + 07.3) —
  // aggregate Deepgram per-utterance confidence into a single visit-
  // level signal. When the audio is mostly low-confidence (median
  // below 0.55 OR more than 30% of utterances under 0.6), flip
  // needsReview so the doctor sees the warning before signing AND
  // surface the structured stats column so L4 + L5 can hedge their
  // language. Don't HALT — produce the SOAP, but make sure the
  // doctor knows the audio fidelity wasn't great.
  // PR-L: only Deepgram returns the per-utterance confidence Layer-1
  // depends on; Whisper has segment-level scores in a different
  // shape. When fallback fires, audioStats is null and the visit is
  // auto-flagged for review via the fallback-detection branch below.
  const audioStats = computeAudioConfidenceStats(utterances);
  const lowConfFlag = audioStats ? shouldFlagForReview(audioStats) : false;

  // Persist the provider-specific raw response into transcriptRaw.
  // Deepgram path stores its full /v1/listen response (Layer 2 reads
  // utterances + speakers from this); Whisper path stores the
  // verbose_json shape (segments + duration). The column is JSON,
  // so the discriminator is preserved end-to-end.
  const transcriptRaw =
    result.raw.kind === "deepgram"
      ? result.raw.data.raw
      : { kind: "whisper", segments: result.raw.data.segments };

  // PR-L: when Whisper fallback fired, auto-flag the visit for
  // review (Whisper doesn't diarize, so Layer 2 can't assign
  // doctor/patient roles — every visit on this path needs a human
  // pass). The lowConfFlag branch above already handles a separate
  // signal; both can apply.
  const fallbackReviewReason = result.fallbackUsed
    ? `Transcription fell back to ${result.provider} (Whisper) — primary Deepgram failed${result.primaryError?.message ? ` with: ${result.primaryError.message.slice(0, 120)}` : ""}. Speaker diarization is unavailable; please review the transcript before signing.`
    : null;

  await updateTemplateTwinSyntheticQaClaimBoundVisit({
    visitId: input.visitId,
    userId: input.userId ?? "",
    practiceId: input.practiceId,
    data: {
      transcriptRaw: transcriptRaw as unknown as object,
      transcriptText: result.transcript,
      audioDurationSec: result.durationSec,
      audioConfidenceStats: (audioStats ?? null) as unknown as object,
      transcriptionProvider: result.provider,
      // 2026-05-12 interpreter-mode: persist Deepgram's detected language
      // tag so the future soft-banner reprocess flow can read it on
      // English-only-mode visits to detect a non-English mis-classification.
      // Only write when interpreterMode requested detection — non-interpreter
      // visits keep the column at its default (null) value.
      ...(input.interpreterMode && result.language
        ? { detectedLanguage: result.language }
        : {}),
      ...(fallbackReviewReason
        ? { needsReview: true, reviewReason: fallbackReviewReason }
        : lowConfFlag
          ? {
              needsReview: true,
              reviewReason: `Audio confidence is below threshold (median ${audioStats!.median.toFixed(2)}, ${audioStats!.lowConfPct.toFixed(0)}% of utterances < ${LOW_CONFIDENCE_THRESHOLD}). Recommend manual review or re-record.`,
            }
          : {}),
    },
  });

  // PR-L canary: Whisper-fallback gets a permanent audit row so
  // operators see the rate over time in /admin/queues + audit_logs.
  // Fire-and-forget — audit failures must never block the pipeline
  // (logAudit is internally try/wrapped per the file's contract).
  if (result.fallbackUsed) {
    // Worker context — no Next.js request lifecycle, so pass
    // userId + practiceId explicitly (otherwise logAudit's session
    // resolution returns null + the row gets the 'clinic_main'
    // sentinel practice).
    await logWorkerAudit({
      action: "TRANSCRIPTION_PROVIDER_FALLBACK",
      targetType: "TranscribeVisit",
      targetId: input.visitId,
      userId: input.userId,
      practiceId: input.practiceId,
      metadata: {
        layer: "L1",
        primaryProvider: "deepgram-batch",
        fallbackProvider: result.provider,
        primaryError: result.primaryError?.message ?? null,
        primaryStatus: result.primaryError?.status ?? null,
        durationSec: result.durationSec,
      },
    });
  }

  // Persist the keyterm metadata so a future transcription regression
  // can be attributed to the exact composition that ran. Staging awaits and
  // claim-fences it so detached telemetry cannot outlive a reclaim. Skipped for
  // interpreter-mode runs (the metadata is null there — model swap).
  if (built?.metadata) {
    try {
      await updateTemplateTwinSyntheticQaClaimBoundVisit({
        visitId: input.visitId,
        userId: input.userId ?? "",
        practiceId: input.practiceId,
        data: {
          keytermsApplied: built.metadata as unknown as object,
        },
      });
    } catch {
      // Audit-attribution metadata is not load-bearing for the
      // visit — never block on it. The pipeline proceeds.
    }
  }

  return {
    durationSec: result.durationSec,
    utteranceCount: utterances.length,
    speakerCount: speakerIds.size || 1,
    // result.language carries the Deepgram-detected tag on interpreter-
    // mode visits ('en', 'es', 'multi'); on standard visits it's just
    // the supplied 'en'. worker.ts persists this to transcribe_visits
    // .detectedLanguage so the soft-banner reprocess flow can surface
    // misclassified English-only-mode visits as needing interpreter mode.
    detectedLanguage:
      input.interpreterMode && result.language && result.language !== "en"
        ? result.language
        : input.interpreterMode
          ? (result.language ?? undefined)
          : undefined,
  };
}
