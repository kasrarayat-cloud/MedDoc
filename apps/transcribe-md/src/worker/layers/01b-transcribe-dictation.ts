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

import prisma from '@meddoc/db';
import { deepgramBatchTranscribe } from '@meddoc/ai';
import { downloadAudio } from '@/lib/minio';

export interface Layer1bInput {
  visitId: string;
  practiceId: string;
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
  const audio = await downloadAudio(input.dictationAudioKey);

  const attempt = async () =>
    deepgramBatchTranscribe({
      practiceId: input.practiceId,
      visitId: input.visitId,
      purpose: 'tm_transcribe',
      audio,
      mimeType: input.dictationMimeType,
      // Options below intentionally differ from Layer 1: single speaker
      // → no diarize, and we don't need utterance boundaries since the
      // downstream layers treat the transcript as one block.
      options: {
        diarize: false,
        utterances: false,
      },
    });

  let result;
  try {
    result = await attempt();
  } catch (err) {
    const status = (err as { status?: number }).status;
    if (status && status >= 400 && status < 500) throw err;
    await new Promise((r) => setTimeout(r, BACKOFF_MS));
    result = await attempt();
  }

  await prisma.transcribeVisit.update({
    where: { id: input.visitId },
    data: {
      transcriptRaw: result.raw as unknown as object,
      transcriptText: result.transcript,
      dictationDurationSec: result.durationSec,
    },
  });

  return { durationSec: result.durationSec, transcript: result.transcript };
}
