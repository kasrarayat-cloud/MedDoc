// ============================================================================
// apps/transcribe-md — BullMQ worker entrypoint (T-M4)
// ----------------------------------------------------------------------------
// Runs as a separate container (transcribe-md-worker in docker-compose).
// Connects to the shared Redis, pulls jobs off the `transcribe-md` queue,
// drives each visit through the 6-layer pipeline (Deepgram → speaker
// roles → entities → SOAP draft → self-critique → polish).
//
// Dev:  `npm run worker -w transcribe-md`
// Prod: container CMD runs `tsx src/worker.ts`
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
import {
  runLayer2SpeakerRoles,
  type SpeakerMap,
} from '@/worker/layers/02-speaker-roles';
import {
  runLayer3ExtractEntities,
  buildRoleLabeledTranscript,
} from '@/worker/layers/03-extract-entities';
import { runLayer4GenerateSoap } from '@/worker/layers/04-generate-soap';
import { runLayer5SelfCritique } from '@/worker/layers/05-self-critique';
import { runLayer6Polish } from '@/worker/layers/06-polish';

const CONCURRENCY = Number.parseInt(
  process.env.TRANSCRIBE_MD_WORKER_CONCURRENCY ?? '2',
  10
);

async function processVisit(job: Job<ProcessVisitPayload>): Promise<void> {
  const { visitId } = job.data;

  // Read the visit + user's practice once; we need practiceId on every
  // AiCall for cost attribution + eventual per-practice unit economics.
  const visit = await prisma.transcribeVisit.findUnique({
    where: { id: visitId },
    select: {
      id: true,
      userId: true,
      audioKey: true,
      audioMimeType: true,
      specialty: true,
      inputMode: true,
      user: { select: { practiceId: true } },
    },
  });
  if (!visit) throw new Error(`Visit ${visitId} not found`);
  if (!visit.audioKey) throw new Error(`Visit ${visitId} has no audioKey`);
  if (visit.inputMode !== 'audio_upload') {
    throw new Error(
      `Visit ${visitId} inputMode is "${visit.inputMode}" — this queue only handles audio_upload.`
    );
  }

  const practiceId = visit.user.practiceId;
  const startedAt = new Date();

  await prisma.transcribeVisit.update({
    where: { id: visitId },
    data: {
      status: TranscribeVisitStatus.TRANSCRIBING,
      processingStartedAt: startedAt,
      // Clear any prior-run review flag so a retry starts clean. Layers
      // will re-set it if they find new reasons.
      needsReview: false,
      reviewReason: null,
    },
  });

  try {
    // ── L1: Deepgram ──
    await runLayer1Transcribe({
      visitId,
      practiceId,
      audioKey: visit.audioKey,
      audioMimeType: visit.audioMimeType,
    });

    // Re-read transcriptRaw for downstream layers. It's been persisted
    // by L1 so we can trust it.
    const withTranscript = await prisma.transcribeVisit.findUnique({
      where: { id: visitId },
      select: { transcriptRaw: true },
    });
    const raw = withTranscript?.transcriptRaw as
      | DeepgramBatchResponse
      | null
      | undefined;
    const utterances: DeepgramUtterance[] = raw?.results?.utterances ?? [];

    // ── L2: Speaker roles ──
    await prisma.transcribeVisit.update({
      where: { id: visitId },
      data: { status: TranscribeVisitStatus.EXTRACTING },
    });
    const { speakerMap } = await runLayer2SpeakerRoles({
      visitId,
      practiceId,
      utterances,
    });

    // ── L3: Entity extraction ──
    const entities = await runLayer3ExtractEntities({
      visitId,
      practiceId,
      utterances,
      speakerMap,
    });

    const roleLabeledTranscript = buildRoleLabeledTranscript(
      utterances,
      speakerMap as SpeakerMap
    );

    // ── L4: SOAP draft ──
    await prisma.transcribeVisit.update({
      where: { id: visitId },
      data: { status: TranscribeVisitStatus.DRAFTING },
    });
    const soapDraft = await runLayer4GenerateSoap({
      visitId,
      practiceId,
      specialty: visit.specialty,
      roleLabeledTranscript,
      entities,
    });

    // ── L5: Self-critique ──
    await prisma.transcribeVisit.update({
      where: { id: visitId },
      data: { status: TranscribeVisitStatus.CRITIQUING },
    });
    const critique = await runLayer5SelfCritique({
      visitId,
      practiceId,
      specialty: visit.specialty,
      soapDraft,
      roleLabeledTranscript,
      entities,
    });

    // ── L6: Polish ──
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

    // ── Done. Sum per-layer costs from ai_calls into the visit-level
    //       total so /settings → usage can read one column. ──
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
              : 'Unknown error during audio processing. Try again or contact support.',
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
