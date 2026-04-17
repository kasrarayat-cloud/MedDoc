// ============================================================================
// apps/scribe — BullMQ queue handles
// ----------------------------------------------------------------------------
// Single queue `scribe` with per-job-name fan-out:
//   - API routes (upload-complete) → enqueue `transcribe_batch`
//   - transcribe-batch worker      → enqueue `finalize_visit`
//   - finalize-visit worker (M2)   → generates SOAP, done
// ============================================================================

import IORedis, { type RedisOptions } from 'ioredis';
import { Queue } from 'bullmq';

const redisUrl = process.env.REDIS_URL?.trim() || 'redis://redis:6379';

let connection: IORedis | null = null;
let scribeQueue: Queue | null = null;

function getConnection(): IORedis {
  if (connection) return connection;
  // BullMQ requires maxRetriesPerRequest=null on the shared connection
  // (otherwise blocking commands throw after the retry limit).
  const opts: RedisOptions = { maxRetriesPerRequest: null };
  connection = new IORedis(redisUrl, opts);
  connection.on('error', (err) => {
    console.error('[scribe-queue] redis error:', err);
  });
  return connection;
}

export const JOB_TRANSCRIBE_BATCH = 'transcribe_batch';
export const JOB_FINALIZE_VISIT = 'finalize_visit';

export interface TranscribeBatchPayload {
  visitId: string;
  audioObjectKey: string;
  sourceFileName: string;
}

export interface FinalizeVisitPayload {
  visitId: string;
}

export function getScribeQueue(): Queue {
  if (scribeQueue) return scribeQueue;
  scribeQueue = new Queue('scribe', {
    connection: getConnection(),
    defaultJobOptions: {
      attempts: 3,
      backoff: { type: 'exponential', delay: 5_000 },
      removeOnComplete: { count: 500, age: 24 * 3600 },
      removeOnFail: { count: 500 },
    },
  });
  return scribeQueue;
}

export function getSharedRedisConnection(): IORedis {
  return getConnection();
}
