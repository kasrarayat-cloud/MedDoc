// ============================================================================
// Layer 1' — Single-speaker Deepgram transcription (T-M5)
// ----------------------------------------------------------------------------
// For voice_dictation. Same Deepgram backend as Layer 1 but with diarize +
// utterances turned OFF — the doctor is the only speaker, and downstream
// layers treat the whole text as one block rather than a dialogue.
//
// Writes transcriptRaw + transcriptText (same columns Layer 1 uses) so
// the Pipeline tab + Layer 3 see the same shape, plus dictationDurationSec
// for the cost math + UI replay duration hint.
// ============================================================================

import { Readable } from "node:stream";

import { updateTemplateTwinSyntheticQaClaimBoundVisit } from "@/worker/staging-qa-mutation-fence";
// PR-L follow-up — same orchestrator swap as L1; dictation now also
// gets Whisper fallback when Deepgram has a transient outage. The
// dictation path is single-speaker so there are no diarization
// concerns on the fallback branch — Whisper produces the same flat
// text Deepgram does (with `diarize: false`).
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
// via the builder rather than a single global list.
import { buildKeytermsForVisit } from "@/lib/deepgram-keyterm-builder";
import { CONFUSED_DRUG_NAMES_FLAT } from "@/lib/confused-drug-names";
import { logWorkerAudit } from "@/worker/worker-audit";
import {
  computeAudioConfidenceStats,
  shouldFlagForReview,
  LOW_CONFIDENCE_THRESHOLD,
} from "./audio-confidence";

export interface Layer1bInput {
  visitId: string;
  practiceId: string;
  userId: string | null;
  dictationAudioKey: string;
  dictationMimeType: string;
  /** 2026-05-12 interpreter-mode flag from the visit row. When true,
   *  the dictation path switches to nova-3 + detect_language=true +
   *  language=multi. Note that L1b is a SINGLE-SPEAKER dictation path
   *  (diarize: false), so interpreter mode on L1b is unusual — most
   *  interpreted visits land on L1 (audio_upload) or the live-recorder
   *  L1b that the Sylvia incident hit. We still honor the flag for
   *  symmetry so a doctor who dictates a code-switching summary gets
   *  the multilingual model. */
  interpreterMode?: boolean;
  /** 2026-05-13 Issues #202 + #206 — visit specialty used to scope
   *  the Deepgram keyterm list. Free-text from
   *  `transcribe_visits.specialty`; the builder normalizes. */
  specialty?: string | null;
}

export interface Layer1bOutput {
  durationSec: number;
  transcript: string;
  /** 2026-05-12 interpreter-mode: detected IETF language tag, surfaces
   *  on visits where interpreterMode was true. Undefined otherwise. */
  detectedLanguage?: string;
}

const BACKOFF_MS = 2_000;

export async function runLayer1bTranscribeDictation(
  input: Layer1bInput,
): Promise<Layer1bOutput> {
  // T-M18.2 A7 + PR-L: stream MinIO → orchestrator. The fresh
  // toBuffer() callback re-opens the MinIO object on the rare
  // fallback path so Whisper's multipart upload has a Buffer.
  const stat = await statAudio(input.dictationAudioKey);
  if (!stat || typeof stat.size !== "number") {
    throw new Error(
      `[L1b] dictation audio missing or has no size: ${input.dictationAudioKey}`,
    );
  }
  const nodeStream = await streamAudio(input.dictationAudioKey);
  const webStream = Readable.toWeb(nodeStream) as ReadableStream<Uint8Array>;

  // 2026-05-13 Issues #202 + #206 — per-visit keyterm composition
  // with ISMP confused-drug-names safety floor (PR-2).
  // Interpreter mode skips this (model swap to nova-3 general).
  const built = input.interpreterMode
    ? null
    : buildKeytermsForVisit({
        specialty: input.specialty,
        safetyFloor: CONFUSED_DRUG_NAMES_FLAT,
      });

  // 2026-06-10 kill-switch (audit 4.2): fail-closed gate on the
  // Deepgram→Whisper hop (ships raw audio to non-BAA'd OpenAI).
  const allowCrossProviderFallback = isWhisperFallbackEnabled();

  const attempt = async () => {
    return runTemplateTwinOwnedTranscribe({
      operation: "L1B_TRANSCRIBE",
      operationVersion: "deepgram-batch-l1b-v1",
      audioIdentity: {
        objectKey: input.dictationAudioKey,
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
          toBuffer: async () => {
            const fresh = await streamAudio(input.dictationAudioKey);
            const chunks: Buffer[] = [];
            for await (const chunk of fresh) {
              chunks.push(Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk));
            }
            return Buffer.concat(chunks);
          },
        },
        mimeType: input.dictationMimeType,
        deepgram: input.interpreterMode
          ? {
              // 2026-05-12 interpreter-mode (Sylvia incident follow-up):
              // switch to multilingual nova-3 + language detection.
              // Dictation stays single-speaker (diarize off) so the
              // utterances pipeline behaves identically downstream.
              model: "nova-3",
              options: {
                diarize: false,
                utterances: false,
                detectLanguage: true,
              },
            }
          : {
              // Single-speaker dictation — disable diarize + utterances.
              // Whisper has no equivalent toggles (it just transcribes), so
              // the fallback path produces functionally the same flat text.
              options: { diarize: false, utterances: false },
              // 2026-05-13 Issues #202 + #206 — scoped per-visit keyterms.
              keyterms: built?.keyterms ?? [],
            },
      },
    });
  };

  // FIND-P1-009 (2026-05-14): same shape as L1's FIND-P1-008 fix —
  // shared `withRetry` with full-jitter backoff. Preserves the prior
  // 2-attempt semantic; the jitter change decorrelates dictation-mode
  // retries from conversation-mode retries when both workers hit a
  // Deepgram outage simultaneously.
  let result: TranscribeResult;
  try {
    result = await withRetry(attempt, {
      maxAttempts: 2,
      baseDelayMs: BACKOFF_MS,
      onRetry: (info: RetryAttemptInfo) => {
        const err = info.error as { status?: number; code?: string };
        console.warn(
          "[layer-01b-transcribe-dictation] retrying",
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
    // 2026-06-10 kill-switch (audit 4.2): same suppressed-fallback audit
    // as L1, scoped to L1b. Deepgram failed + Whisper was eligible but
    // the cross-provider hop is disabled → audit + re-throw → DLQ. Raw
    // dictation audio never leaves to OpenAI.
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
          layer: "L1b",
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

  // Round 3 quality fix-pack Q0-5 (audit Findings 02.5 + 07.3) —
  // dictation also runs through Deepgram's batch endpoint, so the
  // same low-confidence detection applies. Note that L1b currently
  // requests `utterances: false`, so result.utterances is empty and
  // the helper returns null (we deliberately keep dictation parity
  // with the helper contract). When a future PR enables utterances
  // for dictation, the same wiring fires automatically.
  // PR-L: same discriminated-union handling as L1.
  const utterances =
    result.raw.kind === "deepgram" ? result.raw.data.utterances : [];
  const audioStats = computeAudioConfidenceStats(utterances);
  const lowConfFlag = audioStats ? shouldFlagForReview(audioStats) : false;

  const transcriptRaw =
    result.raw.kind === "deepgram"
      ? result.raw.data.raw
      : { kind: "whisper", segments: result.raw.data.segments };

  // PR-L: dictation is single-speaker so there's no diarization gap
  // on the fallback path; the transcript is still usable. We still
  // surface a softer review note so the doctor knows the route the
  // recording took (helps explain stylistic differences after the
  // fact).
  const fallbackReviewReason = result.fallbackUsed
    ? `Dictation transcribed by ${result.provider} (Whisper fallback) — primary Deepgram failed${result.primaryError?.message ? ` with: ${result.primaryError.message.slice(0, 120)}` : ""}. Verify the transcript before signing.`
    : null;

  await updateTemplateTwinSyntheticQaClaimBoundVisit({
    visitId: input.visitId,
    userId: input.userId ?? "",
    practiceId: input.practiceId,
    data: {
      transcriptRaw: transcriptRaw as unknown as object,
      transcriptText: result.transcript,
      dictationDurationSec: result.durationSec,
      audioConfidenceStats: (audioStats ?? null) as unknown as object,
      transcriptionProvider: result.provider,
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

  // PR-L canary — same audit row L1 emits, scoped to L1b.
  if (result.fallbackUsed) {
    await logWorkerAudit({
      action: "TRANSCRIPTION_PROVIDER_FALLBACK",
      targetType: "TranscribeVisit",
      targetId: input.visitId,
      userId: input.userId,
      practiceId: input.practiceId,
      metadata: {
        layer: "L1b",
        primaryProvider: "deepgram-batch",
        fallbackProvider: result.provider,
        primaryError: result.primaryError?.message ?? null,
        primaryStatus: result.primaryError?.status ?? null,
        durationSec: result.durationSec,
      },
    });
  }

  // Persist keyterm composition for audit attribution. Synthetic staging
  // awaits and claim-fences this write so detached telemetry cannot outlive a
  // reclaimed delivery. Failures remain non-load-bearing for ordinary visits.
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
      // Non-load-bearing for the visit.
    }
  }

  return {
    durationSec: result.durationSec,
    transcript: result.transcript,
    detectedLanguage: input.interpreterMode
      ? (result.language ?? undefined)
      : undefined,
  };
}
