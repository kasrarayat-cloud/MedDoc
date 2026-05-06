// ============================================================================
// /admin/queues — BullMQ queue health dashboard (PR-L)
// ----------------------------------------------------------------------------
// SUPER_ADMIN-gated read-only view of:
//   - transcribe-md (visit pipeline, 3 attempts then DLQ)
//   - transcribe-md-cleanup (MinIO orphan / stale visit / retention sweeps)
//   - dlq:permanent-failures (PR-L — exhausted-retry sink; no consumer)
//
// Auth gate inherits from apps/transcribe-md/src/app/admin/layout.tsx
// (SUPER_ADMIN product entitlement + ≤12-hour session freshness).
// Non-SUPER_ADMIN users see notFound() — same posture as the rest of
// /admin/*.
//
// PR-L scope: dashboard is READ-ONLY this PR. Re-enqueue / clear /
// drop actions on DLQ jobs are a v2 concern (write paths need their
// own audit-row instrumentation + confirmation UX).
// ============================================================================

import type { Metadata } from 'next';

import {
  QUEUE_NAME,
  CLEANUP_QUEUE_NAME,
  DLQ_QUEUE_NAME,
  getCleanupQueue,
  getDlqQueue,
  getTranscribeMdQueue,
} from '@/lib/queue';
import type { Queue } from 'bullmq';

export const metadata: Metadata = { title: 'Queues · Admin · QuillMD' };
export const dynamic = 'force-dynamic';
export const revalidate = 0;

interface QueueRow {
  name: string;
  description: string;
  counts: {
    waiting: number;
    active: number;
    completed: number;
    failed: number;
    delayed: number;
    paused: number;
  };
  /** Total = waiting + active + delayed + paused (the "live" depth).
   *  failed is shown separately because BullMQ keeps a rolling buffer
   *  of failed jobs even after the retry budget is exhausted. */
  liveDepth: number;
}

/** Read counts for a queue. BullMQ's getJobCounts is cheap (Redis
 *  HLEN/LLEN per status). If Redis is unhappy we surface zeros + a
 *  visible warning rather than crashing the page. */
async function readQueueRow(
  queue: Queue,
  description: string
): Promise<QueueRow & { error?: string }> {
  try {
    const counts = await queue.getJobCounts(
      'waiting',
      'active',
      'completed',
      'failed',
      'delayed',
      'paused'
    );
    const c = {
      waiting: counts.waiting ?? 0,
      active: counts.active ?? 0,
      completed: counts.completed ?? 0,
      failed: counts.failed ?? 0,
      delayed: counts.delayed ?? 0,
      paused: counts.paused ?? 0,
    };
    return {
      name: queue.name,
      description,
      counts: c,
      liveDepth: c.waiting + c.active + c.delayed + c.paused,
    };
  } catch (err) {
    return {
      name: queue.name,
      description,
      counts: {
        waiting: 0,
        active: 0,
        completed: 0,
        failed: 0,
        delayed: 0,
        paused: 0,
      },
      liveDepth: 0,
      error: err instanceof Error ? err.message : String(err),
    };
  }
}

interface DlqJobPreview {
  id: string;
  originalQueue: string;
  originalJobId: string | null;
  originalJobName: string;
  lastError: string;
  exhaustedAt: string;
  totalAttempts: number;
  visitId: string | null;
}

/** Fetch the most-recent DLQ jobs so the operator can see what failed
 *  + paste the originalJobId into a console for forensics. PR-L scope:
 *  read-only. The "retry" button + bulk-clear actions are v2 work. */
async function readDlqJobs(): Promise<DlqJobPreview[] | { error: string }> {
  try {
    const queue = getDlqQueue();
    // BullMQ's getJobs returns arrays of Job<TPayload>; the DLQ uses
    // DlqJobPayload so each .data carries the structured failure info.
    const jobs = await queue.getJobs(
      ['waiting', 'completed', 'failed', 'delayed'],
      0,
      24, // 25 most recent
      false
    );
    return jobs.map((job) => {
      const data = job.data as {
        originalQueue?: string;
        originalJobId?: string | null;
        originalJobName?: string;
        lastError?: string;
        exhaustedAt?: string;
        totalAttempts?: number;
        originalPayload?: { visitId?: string };
      };
      return {
        id: job.id ?? '?',
        originalQueue: data.originalQueue ?? '?',
        originalJobId: data.originalJobId ?? null,
        originalJobName: data.originalJobName ?? '?',
        lastError: (data.lastError ?? '?').slice(0, 240),
        exhaustedAt: data.exhaustedAt ?? '?',
        totalAttempts: data.totalAttempts ?? 0,
        visitId: data.originalPayload?.visitId ?? null,
      };
    });
  } catch (err) {
    return { error: err instanceof Error ? err.message : String(err) };
  }
}

export default async function AdminQueuesPage() {
  // The auth/SUPER_ADMIN gate is the parent layout's responsibility.
  // Reaching here means the request already passed those checks.
  const [pipelineRow, cleanupRow, dlqRow, dlqJobs] = await Promise.all([
    readQueueRow(
      getTranscribeMdQueue(),
      'Visit pipeline (Layer 1-8). 3 attempts with exponential backoff; exhausted jobs go to DLQ.'
    ),
    readQueueRow(
      getCleanupQueue(),
      'MinIO orphan sweep + stale-visit cleanup + audio retention sweep. 1 attempt; failures retry on next schedule.'
    ),
    readQueueRow(
      getDlqQueue(),
      'PR-L dead-letter queue. No consumer — accumulates exhausted jobs for operator review.'
    ),
    readDlqJobs(),
  ]);

  return (
    <main
      style={{
        padding: '32px 24px 80px',
        minHeight: '60vh',
        background: 'var(--color-linear-bg)',
        color: 'var(--color-linear-text)',
      }}
    >
      <h1
        style={{
          margin: 0,
          fontFamily: 'var(--font-sans)',
          fontSize: 22,
          fontWeight: 500,
          letterSpacing: '-0.012em',
          marginBottom: 6,
        }}
      >
        Queue health
      </h1>
      <p
        style={{
          margin: 0,
          fontSize: 13,
          color: 'var(--color-linear-text-3)',
          marginBottom: 28,
        }}
      >
        BullMQ queue depth + dead-letter contents. Read-only view (PR-L). Retry / clear actions land in a follow-up.
      </p>

      <section style={{ marginBottom: 32 }}>
        <h2
          style={{
            margin: 0,
            fontFamily: 'var(--font-mono)',
            fontSize: 11,
            fontWeight: 500,
            letterSpacing: '0.07em',
            textTransform: 'uppercase',
            color: 'var(--color-linear-text-3)',
            marginBottom: 10,
          }}
        >
          Queues
        </h2>
        <table
          style={{
            width: '100%',
            borderCollapse: 'collapse',
            fontFamily: 'var(--font-mono)',
            fontSize: 12,
          }}
        >
          <thead>
            <tr style={{ textAlign: 'left', color: 'var(--color-linear-text-3)' }}>
              <th style={{ padding: '8px 10px', borderBottom: '1px solid var(--color-linear-hairline)' }}>queue</th>
              <th style={{ padding: '8px 10px', borderBottom: '1px solid var(--color-linear-hairline)' }}>waiting</th>
              <th style={{ padding: '8px 10px', borderBottom: '1px solid var(--color-linear-hairline)' }}>active</th>
              <th style={{ padding: '8px 10px', borderBottom: '1px solid var(--color-linear-hairline)' }}>delayed</th>
              <th style={{ padding: '8px 10px', borderBottom: '1px solid var(--color-linear-hairline)' }}>failed</th>
              <th style={{ padding: '8px 10px', borderBottom: '1px solid var(--color-linear-hairline)' }}>completed (rolling)</th>
            </tr>
          </thead>
          <tbody>
            {[pipelineRow, cleanupRow, dlqRow].map((row) => (
              <tr key={row.name}>
                <td style={{ padding: '8px 10px', borderBottom: '1px solid var(--color-linear-hairline)' }}>
                  <div style={{ color: 'var(--color-linear-text)', fontWeight: 500 }}>{row.name}</div>
                  <div style={{ color: 'var(--color-linear-text-3)', fontSize: 11, fontFamily: 'var(--font-sans)', marginTop: 2 }}>
                    {row.description}
                  </div>
                  {row.error && (
                    <div style={{ color: 'var(--color-linear-danger)', fontSize: 11, marginTop: 4 }}>
                      read-error: {row.error.slice(0, 140)}
                    </div>
                  )}
                </td>
                <td style={{ padding: '8px 10px', borderBottom: '1px solid var(--color-linear-hairline)' }}>{row.counts.waiting}</td>
                <td style={{ padding: '8px 10px', borderBottom: '1px solid var(--color-linear-hairline)' }}>{row.counts.active}</td>
                <td style={{ padding: '8px 10px', borderBottom: '1px solid var(--color-linear-hairline)' }}>{row.counts.delayed}</td>
                <td
                  style={{
                    padding: '8px 10px',
                    borderBottom: '1px solid var(--color-linear-hairline)',
                    color: row.counts.failed > 0 ? 'var(--color-linear-warning)' : undefined,
                  }}
                >
                  {row.counts.failed}
                </td>
                <td style={{ padding: '8px 10px', borderBottom: '1px solid var(--color-linear-hairline)' }}>{row.counts.completed}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <section>
        <h2
          style={{
            margin: 0,
            fontFamily: 'var(--font-mono)',
            fontSize: 11,
            fontWeight: 500,
            letterSpacing: '0.07em',
            textTransform: 'uppercase',
            color: 'var(--color-linear-text-3)',
            marginBottom: 10,
          }}
        >
          Recent dead-letter jobs (last 25)
        </h2>
        {Array.isArray(dlqJobs) ? (
          dlqJobs.length === 0 ? (
            <div
              style={{
                padding: '24px 20px',
                border: '1px solid var(--color-linear-hairline)',
                borderRadius: 8,
                background: 'var(--color-linear-surface-1)',
                color: 'var(--color-linear-text-3)',
                fontSize: 13,
              }}
            >
              No permanently-failed jobs. The visit pipeline is healthy.
            </div>
          ) : (
            <table
              style={{
                width: '100%',
                borderCollapse: 'collapse',
                fontFamily: 'var(--font-mono)',
                fontSize: 12,
              }}
            >
              <thead>
                <tr style={{ textAlign: 'left', color: 'var(--color-linear-text-3)' }}>
                  <th style={{ padding: '8px 10px', borderBottom: '1px solid var(--color-linear-hairline)' }}>exhausted at</th>
                  <th style={{ padding: '8px 10px', borderBottom: '1px solid var(--color-linear-hairline)' }}>visit / job</th>
                  <th style={{ padding: '8px 10px', borderBottom: '1px solid var(--color-linear-hairline)' }}>attempts</th>
                  <th style={{ padding: '8px 10px', borderBottom: '1px solid var(--color-linear-hairline)' }}>last error</th>
                </tr>
              </thead>
              <tbody>
                {dlqJobs.map((j) => (
                  <tr key={j.id}>
                    <td style={{ padding: '8px 10px', borderBottom: '1px solid var(--color-linear-hairline)', whiteSpace: 'nowrap' }}>
                      {j.exhaustedAt}
                    </td>
                    <td style={{ padding: '8px 10px', borderBottom: '1px solid var(--color-linear-hairline)' }}>
                      <div style={{ color: 'var(--color-linear-text)' }}>
                        {j.visitId ? `visit ${j.visitId}` : `job ${j.originalJobId ?? '?'}`}
                      </div>
                      <div style={{ color: 'var(--color-linear-text-3)', fontSize: 11 }}>
                        {j.originalQueue} · {j.originalJobName}
                      </div>
                    </td>
                    <td style={{ padding: '8px 10px', borderBottom: '1px solid var(--color-linear-hairline)' }}>
                      {j.totalAttempts}/{j.totalAttempts}
                    </td>
                    <td
                      style={{
                        padding: '8px 10px',
                        borderBottom: '1px solid var(--color-linear-hairline)',
                        color: 'var(--color-linear-warning)',
                        maxWidth: 480,
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                      }}
                    >
                      {j.lastError}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )
        ) : (
          <div style={{ color: 'var(--color-linear-danger)', fontSize: 12 }}>
            DLQ read failed: {dlqJobs.error}
          </div>
        )}
      </section>

      <p
        style={{
          marginTop: 32,
          fontSize: 11,
          color: 'var(--color-linear-text-3)',
        }}
      >
        v1 read-only view. Retry / clear actions are v2. Names: <code>{QUEUE_NAME}</code>,{' '}
        <code>{CLEANUP_QUEUE_NAME}</code>, <code>{DLQ_QUEUE_NAME}</code>.
      </p>
    </main>
  );
}
