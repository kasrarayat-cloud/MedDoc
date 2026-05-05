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

import { Readable } from 'node:stream';

import prisma from '@meddoc/db';
import { deepgramBatchTranscribe } from '@meddoc/ai';
import { statAudio, streamAudio } from '@/lib/minio';
import {
  computeAudioConfidenceStats,
  shouldFlagForReview,
  LOW_CONFIDENCE_THRESHOLD,
} from './audio-confidence';

export interface Layer1bInput {
  visitId: string;
  practiceId: string;
  userId: string | null;
  dictationAudioKey: string;
  dictationMimeType: string;
}

export interface Layer1bOutput {
  durationSec: number;
  transcript: string;
}

const BACKOFF_MS = 2_000;

export async function runLayer1bTranscribeDictation(
  input: Layer1bInput
): Promise<Layer1bOutput> {
  // T-M18.2 A7: stream MinIO → fetch instead of buffering.
  const attempt = async () => {
    const stat = await statAudio(input.dictationAudioKey);
    if (!stat || typeof stat.size !== 'number') {
      throw new Error(
        `[L1b] dictation audio missing or has no size: ${input.dictationAudioKey}`
      );
    }
    const nodeStream = await streamAudio(input.dictationAudioKey);
    const webStream = Readable.toWeb(nodeStream) as ReadableStream<Uint8Array>;
    return deepgramBatchTranscribe({
      practiceId: input.practiceId,
      visitId: input.visitId,
      userId: input.userId,
      purpose: 'tm_transcribe',
      audio: { stream: webStream, sizeBytes: stat.size },
      mimeType: input.dictationMimeType,
      // Options below intentionally differ from Layer 1: single speaker
      // → no diarize, and we don't need utterance boundaries since the
      // downstream layers treat the transcript as one block.
      options: {
        diarize: false,
        utterances: false,
      },
    });
  };

  let result;
  try {
    result = await attempt();
  } catch (err) {
    const status = (err as { status?: number }).status;
    if (status && status >= 400 && status < 500) throw err;
    await new Promise((r) => setTimeout(r, BACKOFF_MS));
    result = await attempt();
  }

  // Round 3 quality fix-pack Q0-5 (audit Findings 02.5 + 07.3) —
  // dictation also runs through Deepgram's batch endpoint, so the
  // same low-confidence detection applies. Note that L1b currently
  // requests `utterances: false`, so result.utterances is empty and
  // the helper returns null (we deliberately keep dictation parity
  // with the helper contract). When a future PR enables utterances
  // for dictation, the same wiring fires automatically.
  const audioStats = computeAudioConfidenceStats(result.utterances);
  const lowConfFlag = audioStats ? shouldFlagForReview(audioStats) : false;

  await prisma.transcribeVisit.update({
    where: { id: input.visitId },
    data: {
      transcriptRaw: result.raw as unknown as object,
      transcriptText: result.transcript,
      dictationDurationSec: result.durationSec,
      audioConfidenceStats: (audioStats ?? null) as unknown as object,
      ...(lowConfFlag
        ? {
            needsReview: true,
            reviewReason: `Audio confidence is below threshold (median ${audioStats!.median.toFixed(2)}, ${audioStats!.lowConfPct.toFixed(0)}% of utterances < ${LOW_CONFIDENCE_THRESHOLD}). Recommend manual review or re-record.`,
          }
        : {}),
    },
  });

  return { durationSec: result.durationSec, transcript: result.transcript };
}
