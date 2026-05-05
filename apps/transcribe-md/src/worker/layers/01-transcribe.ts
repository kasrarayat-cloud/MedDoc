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
import { deepgramBatchTranscribe } from '@meddoc/ai';
import { statAudio, streamAudio } from '@/lib/minio';
import { MEDICATION_KEYTERMS } from '@/lib/deepgram-vocabulary';
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

  // T-M18.2 A7: stream MinIO → fetch → Deepgram instead of buffering
  // the whole audio. Each retry opens a fresh stream (HTTP requests
  // can't replay a consumed ReadableStream).
  const attempt = async () => {
    const stat = await statAudio(input.audioKey);
    if (!stat || typeof stat.size !== 'number') {
      throw new Error(`[L1] audio object missing or has no size: ${input.audioKey}`);
    }
    const nodeStream = await streamAudio(input.audioKey);
    // Cast — the minio SDK types the stream as a generic Readable;
    // `Readable.toWeb()` yields the ReadableStream<Uint8Array> fetch
    // needs.
    const webStream = Readable.toWeb(nodeStream) as ReadableStream<Uint8Array>;
    return deepgramBatchTranscribe({
      practiceId: input.practiceId,
      visitId: input.visitId,
      userId: input.userId,
      purpose: 'tm_transcribe',
      audio: { stream: webStream, sizeBytes: stat.size },
      mimeType: input.audioMimeType!,
      // Phase-2 voice batch 1: boost the medication lexicon so
      // near-homophones decode as the drug name rather than an
      // invented word. See src/lib/deepgram-vocabulary.ts.
      keyterms: MEDICATION_KEYTERMS,
    });
  };

  let result;
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

  const speakerIds = new Set<number>();
  for (const u of result.utterances) {
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
  const audioStats = computeAudioConfidenceStats(result.utterances);
  const lowConfFlag = audioStats ? shouldFlagForReview(audioStats) : false;

  await prisma.transcribeVisit.update({
    where: { id: input.visitId },
    data: {
      transcriptRaw: result.raw as unknown as object,
      transcriptText: result.transcript,
      audioDurationSec: result.durationSec,
      audioConfidenceStats: (audioStats ?? null) as unknown as object,
      ...(lowConfFlag
        ? {
            needsReview: true,
            reviewReason: `Audio confidence is below threshold (median ${audioStats!.median.toFixed(2)}, ${audioStats!.lowConfPct.toFixed(0)}% of utterances < ${LOW_CONFIDENCE_THRESHOLD}). Recommend manual review or re-record.`,
          }
        : {}),
    },
  });

  return {
    durationSec: result.durationSec,
    utteranceCount: result.utterances.length,
    speakerCount: speakerIds.size || 1,
  };
}
