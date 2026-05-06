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

import { Readable } from 'node:stream';

import prisma from '@meddoc/db';
// PR-L follow-up: swap direct Deepgram call → transcribe() orchestrator.
// transcribe() = Deepgram primary + Whisper fallback on transient
// failures. Result tagged provider='deepgram-batch' or 'whisper-fallback'
// so the visit row + audit trail record which provider produced
// transcript. See packages/ai/src/transcribe.ts header for the full
// fallback semantics + the foundation-scope rationale (PR #162).
import { transcribe, type TranscribeResult } from '@meddoc/ai';
import { statAudio, streamAudio } from '@/lib/minio';
// Q2 fix-pack — keyterm coverage now spans medications + anatomy + labs
// + procedures + common diagnoses. See `CLINICAL_KEYTERMS`.
import { CLINICAL_KEYTERMS } from '@/lib/deepgram-vocabulary';
import { logAudit } from '@/lib/audit';
import {
  computeAudioConfidenceStats,
  shouldFlagForReview,
  LOW_CONFIDENCE_THRESHOLD,
} from './audio-confidence';

export interface Layer1Input {
  visitId: string;
  practiceId: string;
  userId: string | null;
  audioKey: string;
  audioMimeType: string | null;
}

export interface Layer1Output {
  durationSec: number;
  utteranceCount: number;
  /** Count of distinct speaker IDs Deepgram returned (Layer 2 reads
   *  this to know how many roles to assign). */
  speakerCount: number;
}

const BACKOFF_MS = 2_000;

export async function runLayer1Transcribe(
  input: Layer1Input
): Promise<Layer1Output> {
  if (!input.audioMimeType) {
    throw new Error('[L1] audioMimeType is missing — cannot contact Deepgram.');
  }

  // T-M18.2 A7 + PR-L: open the audio source once. The orchestrator
  // uses the stream for the Deepgram primary attempt; if that fails
  // and Whisper fallback fires, toBuffer() re-opens the MinIO stream
  // + drains (the original was already consumed by the failed
  // primary). Streaming on the happy path; ~30 MB peak RAM only on
  // the rare fallback case.
  const stat = await statAudio(input.audioKey);
  if (!stat || typeof stat.size !== 'number') {
    throw new Error(`[L1] audio object missing or has no size: ${input.audioKey}`);
  }
  const nodeStream = await streamAudio(input.audioKey);
  const webStream = Readable.toWeb(nodeStream) as ReadableStream<Uint8Array>;

  const attempt = async () => {
    return transcribe({
      practiceId: input.practiceId,
      visitId: input.visitId,
      userId: input.userId,
      purpose: 'tm_transcribe',
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
      deepgram: {
        // Q2 fix-pack — biases nova-3-medical across the full clinical
        // surface: medications (drug-name homophones) + anatomy + labs
        // + procedures + common diagnoses. See `CLINICAL_KEYTERMS`.
        keyterms: CLINICAL_KEYTERMS,
      },
    });
  };

  let result: TranscribeResult;
  try {
    result = await attempt();
  } catch (err) {
    // Retry once on 5xx / network blips. 4xx (bad file, bad mime) is
    // terminal and the catch in worker.ts will surface it as a
    // reviewReason on the visit.
    const status = (err as { status?: number }).status;
    if (status && status >= 400 && status < 500) throw err;
    await new Promise((r) => setTimeout(r, BACKOFF_MS));
    result = await attempt();
  }

  // PR-L: discriminated-union of provider raw shape. Deepgram path
  // gives us speaker labels + per-utterance confidence; Whisper has
  // segments + no diarization. Layer 2 reads `result.raw.kind` to
  // decide which extraction path to run.
  const utterances =
    result.raw.kind === 'deepgram' ? result.raw.data.utterances : [];
  const speakerIds = new Set<number>();
  for (const u of utterances) {
    if (typeof u.speaker === 'number') speakerIds.add(u.speaker);
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
    result.raw.kind === 'deepgram'
      ? result.raw.data.raw
      : { kind: 'whisper', segments: result.raw.data.segments };

  // PR-L: when Whisper fallback fired, auto-flag the visit for
  // review (Whisper doesn't diarize, so Layer 2 can't assign
  // doctor/patient roles — every visit on this path needs a human
  // pass). The lowConfFlag branch above already handles a separate
  // signal; both can apply.
  const fallbackReviewReason = result.fallbackUsed
    ? `Transcription fell back to ${result.provider} (Whisper) — primary Deepgram failed${result.primaryError?.message ? ` with: ${result.primaryError.message.slice(0, 120)}` : ''}. Speaker diarization is unavailable; please review the transcript before signing.`
    : null;

  await prisma.transcribeVisit.update({
    where: { id: input.visitId },
    data: {
      transcriptRaw: transcriptRaw as unknown as object,
      transcriptText: result.transcript,
      audioDurationSec: result.durationSec,
      audioConfidenceStats: (audioStats ?? null) as unknown as object,
      transcriptionProvider: result.provider,
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
    void logAudit({
      action: 'TRANSCRIPTION_PROVIDER_FALLBACK',
      targetType: 'TranscribeVisit',
      targetId: input.visitId,
      userId: input.userId,
      practiceId: input.practiceId,
      metadata: {
        layer: 'L1',
        primaryProvider: 'deepgram-batch',
        fallbackProvider: result.provider,
        primaryError: result.primaryError?.message ?? null,
        primaryStatus: result.primaryError?.status ?? null,
        durationSec: result.durationSec,
      },
    });
  }

  return {
    durationSec: result.durationSec,
    utteranceCount: utterances.length,
    speakerCount: speakerIds.size || 1,
  };
}
