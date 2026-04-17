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
// M7 — Sentry init must precede every other import that might throw so
// early-boot errors still get captured. No-op when SENTRY_DSN_* is unset.
import '../sentry.server.config';
import { Worker, type Job } from 'bullmq';
import {
  JOB_FINALIZE_VISIT,
  JOB_RETENTION_PURGE,
  JOB_TRANSCRIBE_BATCH,
  getScribeQueue,
  getSharedRedisConnection,
  type FinalizeVisitPayload,
  type RetentionPurgePayload,
  type TranscribeBatchPayload,
} from '@/lib/queue';
import { runTranscribeBatch } from '@/server/workers/transcribe-batch';
import { runFinalizeVisit } from '@/server/workers/finalize-visit';
import { runRetentionPurge } from '@/server/workers/retention-purge';

const CONCURRENCY = Number(process.env.SCRIBE_WORKER_CONCURRENCY ?? 2);
/** M7 — daily 02:00 UTC. Env override for ops tuning without a rebuild. */
const RETENTION_CRON = process.env.RETENTION_PURGE_CRON?.trim() || '0 2 * * *';

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
      case JOB_RETENTION_PURGE:
        await runRetentionPurge(job.data as RetentionPurgePayload);
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

/**
 * Register the daily retention scan at boot. BullMQ deduplicates
 * repeatable jobs by (name + pattern + jobId), so re-registration on
 * every worker boot is a no-op. Set RETENTION_PURGE_ENABLED=false in
 * an emergency to prevent the cron from firing (the live-purge flag
 * gates the destructive path inside the handler separately).
 */
async function registerRepeatableJobs(): Promise<void> {
  if ((process.env.RETENTION_PURGE_ENABLED ?? 'true').toLowerCase() === 'false') {
    console.log('[worker] retention_purge cron disabled by RETENTION_PURGE_ENABLED=false');
    return;
  }
  await getScribeQueue().add(
    JOB_RETENTION_PURGE,
    {} satisfies RetentionPurgePayload,
    {
      repeat: { pattern: RETENTION_CRON },
      jobId: 'retention_purge_daily',
      removeOnComplete: { count: 30, age: 7 * 24 * 3600 },
      removeOnFail: { count: 30 },
    }
  );
  console.log(`[worker] registered retention_purge repeatable pattern="${RETENTION_CRON}"`);
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

void registerRepeatableJobs().catch((err) => {
  console.error('[worker] repeatable registration failed:', err);
});

console.log(
  `[worker] ready, concurrency=${CONCURRENCY}, queue=scribe (${Object.values({
    JOB_TRANSCRIBE_BATCH,
    JOB_FINALIZE_VISIT,
    JOB_RETENTION_PURGE,
  }).join(', ')})`
);
