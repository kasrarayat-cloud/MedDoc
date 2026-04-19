// ============================================================================
// apps/transcribe-md — BullMQ worker entrypoint (T-M4 + T-M5)
// ----------------------------------------------------------------------------
// Runs as a separate container (transcribe-md-worker). Pulls jobs off the
// shared `transcribe-md` queue and drives each visit through the pipeline.
//
// Pipeline branches by visit.inputMode:
//   audio_upload    → L1 (diarize) + L2 + L3 (conversation) + L4 + L5 + L6
//   voice_dictation → L1' (single-speaker) + L3 (dictation) + L4 + L5 + L6
//   text_notes      →                         L3 (text)     + L4 + L5 + L6
//
// Layers 4-6 are mode-agnostic: they consume (entities, contextText) and
// produce SOAP draft → critique → polish. That uniformity is the point —
// the doctor gets the same output quality regardless of input shape.
// ============================================================================

import 'dotenv/config';
import { Worker, type Job } from 'bullmq';
import prisma from '@meddoc/db';
import { TranscribeVisitStatus } from '@prisma/client';
import type { DeepgramBatchResponse, DeepgramUtterance } from '@meddoc/ai';

import {
  QUEUE_NAME,
  JOB_PROCESS_VISIT,
  getSharedRedisConnection,
  type ProcessVisitPayload,
} from '@/lib/queue';
import { ensureBucket } from '@/lib/minio';
import { runLayer1Transcribe } from '@/worker/layers/01-transcribe';
import { runLayer1bTranscribeDictation } from '@/worker/layers/01b-transcribe-dictation';
import {
  runLayer2SpeakerRoles,
  type SpeakerMap,
} from '@/worker/layers/02-speaker-roles';
import { runLayer3ExtractEntities } from '@/worker/layers/03-extract-entities';
import { runLayer4GenerateSoap } from '@/worker/layers/04-generate-soap';
import { runLayer5SelfCritique } from '@/worker/layers/05-self-critique';
import { runLayer6Polish } from '@/worker/layers/06-polish';

const CONCURRENCY = Number.parseInt(
  process.env.TRANSCRIBE_MD_WORKER_CONCURRENCY ?? '2',
  10
);

async function processVisit(job: Job<ProcessVisitPayload>): Promise<void> {
  const { visitId } = job.data;

  const visit = await prisma.transcribeVisit.findUnique({
    where: { id: visitId },
    select: {
      id: true,
      userId: true,
      audioKey: true,
      audioMimeType: true,
      dictationAudioKey: true,
      rawTextInput: true,
      specialty: true,
      inputMode: true,
      user: { select: { practiceId: true } },
    },
  });
  if (!visit) throw new Error(`Visit ${visitId} not found`);

  const practiceId = visit.user.practiceId;
  const startedAt = new Date();

  // Per-mode input validation. Keeps the branch bodies below simple.
  if (visit.inputMode === 'audio_upload') {
    if (!visit.audioKey)
      throw new Error(`Visit ${visitId} has no audioKey (audio_upload mode).`);
    if (!visit.audioMimeType)
      throw new Error(`Visit ${visitId} has no audioMimeType.`);
  } else if (visit.inputMode === 'voice_dictation') {
    if (!visit.dictationAudioKey)
      throw new Error(`Visit ${visitId} has no dictationAudioKey.`);
  } else if (visit.inputMode === 'text_notes') {
    if (!visit.rawTextInput?.trim())
      throw new Error(`Visit ${visitId} has no rawTextInput.`);
  } else {
    throw new Error(`Unknown inputMode: ${visit.inputMode}`);
  }

  // text_notes skips TRANSCRIBING — nothing to transcribe.
  const initialStatus =
    visit.inputMode === 'text_notes'
      ? TranscribeVisitStatus.EXTRACTING
      : TranscribeVisitStatus.TRANSCRIBING;

  await prisma.transcribeVisit.update({
    where: { id: visitId },
    data: {
      status: initialStatus,
      processingStartedAt: startedAt,
      needsReview: false,
      reviewReason: null,
    },
  });

  try {
    // -------------------------------------------------------------------
    // Per-mode input stage — produces (entities, contextText).
    // -------------------------------------------------------------------
    let entities: Awaited<ReturnType<typeof runLayer3ExtractEntities>>['entities'];
    let contextText: string;

    if (visit.inputMode === 'audio_upload') {
      // L1 — Deepgram with diarize on.
      await runLayer1Transcribe({
        visitId,
        practiceId,
        audioKey: visit.audioKey!,
        audioMimeType: visit.audioMimeType!,
      });
      const withTranscript = await prisma.transcribeVisit.findUnique({
        where: { id: visitId },
        select: { transcriptRaw: true },
      });
      const raw = withTranscript?.transcriptRaw as
        | DeepgramBatchResponse
        | null
        | undefined;
      const utterances: DeepgramUtterance[] = raw?.results?.utterances ?? [];

      // L2 — speaker roles.
      await prisma.transcribeVisit.update({
        where: { id: visitId },
        data: { status: TranscribeVisitStatus.EXTRACTING },
      });
      const { speakerMap } = await runLayer2SpeakerRoles({
        visitId,
        practiceId,
        utterances,
      });

      // L3 — conversation entities.
      const l3 = await runLayer3ExtractEntities({
        visitId,
        practiceId,
        mode: 'conversation',
        utterances,
        speakerMap: speakerMap as SpeakerMap,
      });
      entities = l3.entities;
      contextText = l3.contextText;
    } else if (visit.inputMode === 'voice_dictation') {
      // L1' — single-speaker Deepgram.
      const l1b = await runLayer1bTranscribeDictation({
        visitId,
        practiceId,
        dictationAudioKey: visit.dictationAudioKey!,
        // Dictations come from browser MediaRecorder → webm/opus.
        // Deepgram auto-detects encoding from the Content-Type header.
        dictationMimeType:
          process.env.TRANSCRIBE_MD_DICTATION_MIME ?? 'audio/webm',
      });

      // L3 — dictation entities.
      await prisma.transcribeVisit.update({
        where: { id: visitId },
        data: { status: TranscribeVisitStatus.EXTRACTING },
      });
      const l3 = await runLayer3ExtractEntities({
        visitId,
        practiceId,
        mode: 'dictation',
        dictationText: l1b.transcript,
      });
      entities = l3.entities;
      contextText = l3.contextText;
    } else {
      // text_notes — no transcription step.
      const l3 = await runLayer3ExtractEntities({
        visitId,
        practiceId,
        mode: 'text',
        rawText: visit.rawTextInput!,
      });
      entities = l3.entities;
      contextText = l3.contextText;
    }

    // -------------------------------------------------------------------
    // Layers 4-6 — mode-agnostic.
    // -------------------------------------------------------------------
    await prisma.transcribeVisit.update({
      where: { id: visitId },
      data: { status: TranscribeVisitStatus.DRAFTING },
    });
    const soapDraft = await runLayer4GenerateSoap({
      visitId,
      practiceId,
      specialty: visit.specialty,
      roleLabeledTranscript: contextText,
      entities,
    });

    await prisma.transcribeVisit.update({
      where: { id: visitId },
      data: { status: TranscribeVisitStatus.CRITIQUING },
    });
    const critique = await runLayer5SelfCritique({
      visitId,
      practiceId,
      specialty: visit.specialty,
      soapDraft,
      roleLabeledTranscript: contextText,
      entities,
    });

    await prisma.transcribeVisit.update({
      where: { id: visitId },
      data: { status: TranscribeVisitStatus.POLISHING },
    });
    await runLayer6Polish({
      visitId,
      practiceId,
      soapDraft,
      critique,
    });

    // Sum per-layer costs from ai_calls into the visit-level total.
    const costRows = await prisma.aiCall.findMany({
      where: { visitId },
      select: { costUsdCents: true },
    });
    const totalCents = costRows.reduce(
      (sum: number, r: { costUsdCents: number | null }) =>
        sum + (r.costUsdCents ?? 0),
      0
    );

    await prisma.transcribeVisit.update({
      where: { id: visitId },
      data: {
        status: TranscribeVisitStatus.READY,
        processingFinishedAt: new Date(),
        processingCostCents: totalCents,
      },
    });
  } catch (err) {
    console.error(`[transcribe-md-worker] visit ${visitId} failed:`, err);
    await prisma.transcribeVisit
      .update({
        where: { id: visitId },
        data: {
          status: TranscribeVisitStatus.FAILED,
          processingFinishedAt: new Date(),
          needsReview: true,
          reviewReason:
            err instanceof Error
              ? err.message.slice(0, 500)
              : 'Unknown error during processing. Try again or contact support.',
        },
      })
      .catch((writeErr: unknown) => {
        console.error(
          '[transcribe-md-worker] failed to write FAILED state:',
          writeErr
        );
      });
    throw err;
  }
}

async function main() {
  console.log('[transcribe-md-worker] booting…');
  await ensureBucket();
  console.log('[transcribe-md-worker] bucket ready');

  const worker = new Worker<ProcessVisitPayload>(
    QUEUE_NAME,
    async (job) => {
      if (job.name !== JOB_PROCESS_VISIT) {
        throw new Error(`Unknown job name: ${job.name}`);
      }
      await processVisit(job);
    },
    {
      connection: getSharedRedisConnection(),
      concurrency: CONCURRENCY,
    }
  );

  worker.on('completed', (job) => {
    console.log(`[transcribe-md-worker] job ${job.id} visit ${job.data.visitId} OK`);
  });
  worker.on('failed', (job, err) => {
    console.error(
      `[transcribe-md-worker] job ${job?.id} visit ${job?.data.visitId} FAILED:`,
      err
    );
  });

  console.log(
    `[transcribe-md-worker] listening on queue "${QUEUE_NAME}" concurrency=${CONCURRENCY}`
  );
}

main().catch((err) => {
  console.error('[transcribe-md-worker] fatal:', err);
  process.exit(1);
});
