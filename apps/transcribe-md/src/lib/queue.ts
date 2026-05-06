// ============================================================================
// apps/transcribe-md — BullMQ queue handles (T-M4)
// ----------------------------------------------------------------------------
// Single queue `transcribe-md` with one job name today (`process_visit`).
// Both the upload API route (enqueue) and the worker container (consume)
// import this module, so the job-name + payload shape live in one place.
// ============================================================================

import IORedis, { type RedisOptions } from 'ioredis';
import { Queue } from 'bullmq';
import { redactPhi } from '@meddoc/ai';

const redisUrl = process.env.REDIS_URL?.trim() || 'redis://redis:6379';

let connection: IORedis | null = null;
let transcribeMdQueue: Queue | null = null;
let cleanupQueue: Queue | null = null;
let dlqQueue: Queue | null = null;

function getConnection(): IORedis {
  if (connection) return connection;
  // BullMQ requires maxRetriesPerRequest=null on the shared connection
  // (otherwise blocking commands throw after the retry limit).
  const opts: RedisOptions = { maxRetriesPerRequest: null };
  connection = new IORedis(redisUrl, opts);
  connection.on('error', (err) => {
    // T-M18.3 A17: redactPhi guard — the ioredis error is almost never
    // PHI-shaped, but the pipeline sometimes passes payloads through
    // the command arg trace on failures, so err.message could leak a
    // patient name or email on a rare shape. Cheap insurance.
    console.error(
      '[transcribe-md-queue] redis error:',
      redactPhi(err instanceof Error ? err.message : err)
    );
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

// ---------------------------------------------------------------------------
// T-M16.4: shared enqueue helper with per-minute jobId idempotency.
// ---------------------------------------------------------------------------
//
// BullMQ dedupes on jobId — `add()` with an existing jobId is a silent
// no-op (returns the existing Job). Before T-M16.4 the three upload
// routes each used `jobId: visit-<id>-<Date.now()>` which is unique per
// millisecond → a double-click within the same second enqueued twice.
//
// Per-minute suffix gives:
//   - Double-click within 60s → same jobId → BullMQ dedupes, no extra
//     pipeline run.
//   - Intentional retry > 60s later → different jobId → new run.
//
// `retry` variant carries a separate suffix so the retry endpoint can
// re-enqueue a visit whose initial job is still sitting in BullMQ's
// completed/failed buffer under the 24h age limit.

export interface EnqueueVisitOpts {
  /** True for POST /api/visits/[id]/retry. Keeps the jobId namespace
   *  separate from initial enqueues so a retry-within-the-same-minute
   *  isn't deduped against an active initial job. */
  retry?: boolean;
}

export async function enqueueProcessVisit(
  visitId: string,
  userId: string,
  opts: EnqueueVisitOpts = {}
): Promise<void> {
  const minute = Math.floor(Date.now() / 60_000);
  const jobId = opts.retry
    ? `visit-${visitId}-retry-${minute}`
    : `visit-${visitId}-${minute}`;
  await getTranscribeMdQueue().add(
    JOB_PROCESS_VISIT,
    { visitId, userId },
    { jobId }
  );
}

// ---------------------------------------------------------------------------
// T-M12: separate queue for scheduled MinIO orphan cleanup. Kept apart
// from the main pipeline queue so a long-running sweep (hundreds of
// deletes) can't block visit processing. Only instantiated when the
// worker enables cleanup — so a web container that never opts in
// doesn't accidentally create a Redis queue structure.
// ---------------------------------------------------------------------------
export const CLEANUP_QUEUE_NAME = 'transcribe-md-cleanup';
export const JOB_MINIO_ORPHAN_CLEANUP = 'minio_orphan_cleanup';
/** T-M17.3: daily sweep of abandoned-QUEUED drafts + expired trash.
 *  Shares the cleanup queue so a single BullMQ Worker processes both
 *  kinds of job. */
export const JOB_STALE_VISIT_CLEANUP = 'stale_visit_cleanup';
/** T-M18.1 A3: daily audio-retention sweep. Purges audioKey +
 *  dictationAudioKey on SIGNED visits past AUDIO_RETENTION_DAYS.
 *  Transcripts + SOAP stay — the 7-year clinical-record retention
 *  window is separate from the 180-day audio window. */
export const JOB_RETENTION_SWEEP = 'retention_sweep';

export function getCleanupQueue(): Queue {
  if (cleanupQueue) return cleanupQueue;
  cleanupQueue = new Queue(CLEANUP_QUEUE_NAME, {
    connection: getConnection(),
    defaultJobOptions: {
      // Cleanup is eventually consistent — if a scheduled run fails,
      // the next scheduled invocation retries the whole sweep from
      // scratch. No in-job retries; they'd just double the time spent.
      attempts: 1,
      removeOnComplete: { count: 50, age: 7 * 24 * 3600 },
      removeOnFail: { count: 50 },
    },
  });
  return cleanupQueue;
}

// ---------------------------------------------------------------------------
// PR-L: Dead Letter Queue — `dlq:permanent-failures`.
// ---------------------------------------------------------------------------
// Jobs that exhaust their retry budget on the main queues land here
// with their original payload + last-error metadata. The DLQ has NO
// automatic consumer — it accumulates until a human (admin) decides
// what to do (re-enqueue / fix / drop). This sits behind the
// SUPER_ADMIN-gated /admin/queues bull-board dashboard so an operator
// can see depth + retry / discard from the UI.
//
// Worker-side wiring (apps/transcribe-md/src/worker.ts): the worker's
// `failed` event handler checks `job.attemptsMade === job.opts.attempts`
// and calls enqueueDlq() with the job's original payload + the last
// error message. This handler doesn't itself retry — by the time the
// failed event fires, BullMQ has already exhausted the retry budget.
// ---------------------------------------------------------------------------

export const DLQ_QUEUE_NAME = 'dlq:permanent-failures';

export interface DlqJobPayload {
  /** Source queue the failed job came from (e.g. 'transcribe-md'). */
  originalQueue: string;
  /** BullMQ job id of the failed job. */
  originalJobId: string | null;
  /** Job name (e.g. 'process_visit'). */
  originalJobName: string;
  /** The job's `data` payload at the time it failed. May contain
   *  `visitId` etc. PHI guard: callers strip raw text fields before
   *  enqueueing — admin-side viewing is intentional but limited to
   *  identifiers + status. */
  originalPayload: unknown;
  /** Last `failedReason` BullMQ recorded (string-coerced error). */
  lastError: string;
  /** ISO-8601 timestamp of when the retry budget was exhausted. */
  exhaustedAt: string;
  /** Total attempts the original job was allowed (e.g. 3 for
   *  transcribe-md, 1 for cleanup). Operator reads this in the UI to
   *  understand whether the retry budget was generous or stingy. */
  totalAttempts: number;
}

export function getDlqQueue(): Queue<DlqJobPayload> {
  if (dlqQueue) return dlqQueue as Queue<DlqJobPayload>;
  dlqQueue = new Queue<DlqJobPayload>(DLQ_QUEUE_NAME, {
    connection: getConnection(),
    defaultJobOptions: {
      // DLQ jobs are themselves never retried — they're already
      // failed-permanently records. removeOnComplete:false so the
      // operator sees the full history; cap on count so an
      // unbounded DLQ doesn't fill Redis.
      attempts: 1,
      removeOnComplete: false,
      removeOnFail: false,
    },
  });
  return dlqQueue as Queue<DlqJobPayload>;
}

/** Enqueue a permanently-failed job into the DLQ. The worker's
 *  `failed` event handler calls this when `attemptsMade ===
 *  job.opts.attempts` (final retry exhausted). The DLQ job's id is
 *  derived from the original job id so re-attempts on the same
 *  payload don't pile up duplicate DLQ entries. */
export async function enqueueDlq(payload: DlqJobPayload): Promise<void> {
  await getDlqQueue().add('permanent-failure', payload, {
    // Stable id keyed on origin queue + job id avoids duplicates if
    // the same exhausted job's failed-event fires twice (rare but
    // possible during worker restarts mid-event).
    jobId: `${payload.originalQueue}:${payload.originalJobId ?? 'null'}`,
  });
}
