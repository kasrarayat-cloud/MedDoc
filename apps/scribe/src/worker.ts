// ============================================================================
// apps/scribe — BullMQ worker entrypoint
// ----------------------------------------------------------------------------
// Runs as a separate container (scribe-worker) per spec §14. Connects to
// the shared Redis, pulls jobs off the `scribe` queue, dispatches by
// name to transcribe_batch or finalize_visit handlers.
//
// Dev: `npm run worker -w scribe` or `tsx apps/scribe/src/worker.ts`
// Prod: container runs `tsx apps/scribe/src/worker.ts` as its CMD.
// ============================================================================

import 'dotenv/config';
import { Worker, type Job } from 'bullmq';
import {
  JOB_FINALIZE_VISIT,
  JOB_TRANSCRIBE_BATCH,
  getSharedRedisConnection,
  type FinalizeVisitPayload,
  type TranscribeBatchPayload,
} from '@/lib/queue';
import { runTranscribeBatch } from '@/server/workers/transcribe-batch';
import { runFinalizeVisit } from '@/server/workers/finalize-visit';

const CONCURRENCY = Number(process.env.SCRIBE_WORKER_CONCURRENCY ?? 2);

async function processJob(job: Job): Promise<void> {
  const started = Date.now();
  console.log(`[worker] ${job.name} start visit=${(job.data as { visitId?: string }).visitId ?? '?'}`);
  try {
    switch (job.name) {
      case JOB_TRANSCRIBE_BATCH:
        await runTranscribeBatch(job.data as TranscribeBatchPayload);
        break;
      case JOB_FINALIZE_VISIT:
        await runFinalizeVisit(job.data as FinalizeVisitPayload);
        break;
      default:
        throw new Error(`Unknown job name: ${job.name}`);
    }
    console.log(`[worker] ${job.name} ok in ${Date.now() - started}ms`);
  } catch (err) {
    console.error(`[worker] ${job.name} FAILED:`, err);
    throw err; // BullMQ retry policy handles this.
  }
}

const worker = new Worker('scribe', processJob, {
  connection: getSharedRedisConnection(),
  concurrency: CONCURRENCY,
});

worker.on('error', (err) => {
  console.error('[worker] unexpected error:', err);
});

function shutdown(signal: string): void {
  console.log(`[worker] ${signal} — draining and shutting down…`);
  void worker.close().then(() => process.exit(0));
}
process.on('SIGTERM', () => shutdown('SIGTERM'));
process.on('SIGINT', () => shutdown('SIGINT'));

console.log(
  `[worker] ready, concurrency=${CONCURRENCY}, queue=scribe (${Object.values({
    JOB_TRANSCRIBE_BATCH,
    JOB_FINALIZE_VISIT,
  }).join(', ')})`
);
