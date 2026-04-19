// ============================================================================
// apps/transcribe-md — BullMQ queue handles (T-M4)
// ----------------------------------------------------------------------------
// Single queue `transcribe-md` with one job name today (`process_visit`).
// Both the upload API route (enqueue) and the worker container (consume)
// import this module, so the job-name + payload shape live in one place.
// ============================================================================

import IORedis, { type RedisOptions } from 'ioredis';
import { Queue } from 'bullmq';

const redisUrl = process.env.REDIS_URL?.trim() || 'redis://redis:6379';

let connection: IORedis | null = null;
let transcribeMdQueue: Queue | null = null;

function getConnection(): IORedis {
  if (connection) return connection;
  // BullMQ requires maxRetriesPerRequest=null on the shared connection
  // (otherwise blocking commands throw after the retry limit).
  const opts: RedisOptions = { maxRetriesPerRequest: null };
  connection = new IORedis(redisUrl, opts);
  connection.on('error', (err) => {
    console.error('[transcribe-md-queue] redis error:', err);
  });
  return connection;
}

export const QUEUE_NAME = 'transcribe-md';
export const JOB_PROCESS_VISIT = 'process_visit';

export interface ProcessVisitPayload {
  visitId: string;
  userId: string;
}

export function getTranscribeMdQueue(): Queue<ProcessVisitPayload> {
  if (transcribeMdQueue) return transcribeMdQueue as Queue<ProcessVisitPayload>;
  transcribeMdQueue = new Queue<ProcessVisitPayload>(QUEUE_NAME, {
    connection: getConnection(),
    defaultJobOptions: {
      // 3 attempts with exp backoff — recoverable network blips at
      // Deepgram/Anthropic shouldn't poison the job. A 4th attempt is
      // almost always a real pipeline bug.
      attempts: 3,
      backoff: { type: 'exponential', delay: 5_000 },
      removeOnComplete: { count: 500, age: 24 * 3600 },
      removeOnFail: { count: 500 },
    },
    // T-M11: per-attempt hard cap lives in worker.ts (not here) —
    // BullMQ v5's DefaultJobOptions doesn't have a `timeout` field.
    // The worker wraps processVisit() in Promise.race against a
    // 15-minute timer so a stuck Anthropic / Deepgram / Prisma call
    // fails the attempt instead of occupying a worker slot forever.
  });
  return transcribeMdQueue as Queue<ProcessVisitPayload>;
}

export function getSharedRedisConnection(): IORedis {
  return getConnection();
}
