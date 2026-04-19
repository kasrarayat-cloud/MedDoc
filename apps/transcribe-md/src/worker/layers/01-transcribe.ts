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

import prisma from '@meddoc/db';
import { deepgramBatchTranscribe } from '@meddoc/ai';
import { downloadAudio } from '@/lib/minio';

export interface Layer1Input {
  visitId: string;
  practiceId: string;
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

  // Download once. For files > ~250MB this is the hot path; a streaming
  // variant is a T-M4.5 optimisation.
  const audio = await downloadAudio(input.audioKey);

  const attempt = async () =>
    deepgramBatchTranscribe({
      practiceId: input.practiceId,
      visitId: input.visitId,
      purpose: 'tm_transcribe',
      audio,
      mimeType: input.audioMimeType!,
    });

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

  await prisma.transcribeVisit.update({
    where: { id: input.visitId },
    data: {
      transcriptRaw: result.raw as unknown as object,
      transcriptText: result.transcript,
      audioDurationSec: result.durationSec,
    },
  });

  return {
    durationSec: result.durationSec,
    utteranceCount: result.utterances.length,
    speakerCount: speakerIds.size || 1,
  };
}
