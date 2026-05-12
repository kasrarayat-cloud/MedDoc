// ============================================================================
// PR-L — DLQ enqueue logic
// ----------------------------------------------------------------------------
// The worker's `failed` event handler (in src/worker.ts) checks
// `job.attemptsMade === job.opts.attempts` and calls enqueueDlq()
// with the original payload + last-error metadata. This test pins
// the call SHAPE — the metadata an operator reads in the
// /admin/queues bull-board dashboard depends on these fields.
//
// We can't trivially boot real BullMQ inside the test process (it
// needs Redis); instead we exercise the lib/queue.enqueueDlq()
// surface against a mocked Queue.add and assert the field shape +
// jobId-derivation rule (no duplicate DLQ rows on a re-fired
// failed-event during worker restart).
// ============================================================================

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  queueAdd: vi.fn().mockResolvedValue({ id: 'dlq-job-1' }),
  redisErrorOn: vi.fn(),
}));

// Mock bullmq's Queue + ioredis at the module boundary so importing
// queue.ts doesn't open real network connections. Both are used via
// `new ClassName(...)` in queue.ts; vi's mock implementations need
// to be class-shaped (constructor-callable) — using a class
// expression rather than vi.fn() does the trick.
vi.mock('bullmq', () => ({
  Queue: class {
    add = mocks.queueAdd;
  },
}));

vi.mock('ioredis', () => ({
  default: class {
    on = mocks.redisErrorOn;
  },
}));

vi.mock('@meddoc/ai', () => ({
  redactPhi: (s: string) => s,
}));

import { enqueueDlq, DLQ_QUEUE_NAME, QUEUE_NAME } from '@/lib/queue';

beforeEach(() => {
  vi.clearAllMocks();
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe('enqueueDlq — payload shape (PR-L)', () => {
  const basePayload = {
    originalQueue: QUEUE_NAME,
    originalJobId: 'visit-abc-29033710',
    originalJobName: 'process_visit',
    originalPayload: { visitId: 'cmot_test_visit', userId: 'user_1' },
    lastError: 'Layer 3 entity-extraction timed out after 15m',
    exhaustedAt: '2026-05-06T12:34:56.000Z',
    totalAttempts: 3,
  };

  it('forwards the full payload to Queue.add as data', async () => {
    await enqueueDlq(basePayload);

    expect(mocks.queueAdd).toHaveBeenCalledTimes(1);
    const [jobName, data] = mocks.queueAdd.mock.calls[0];
    expect(jobName).toBe('permanent-failure');
    expect(data).toMatchObject({
      originalQueue: QUEUE_NAME,
      originalJobId: 'visit-abc-29033710',
      originalJobName: 'process_visit',
      lastError: expect.stringContaining('timed out'),
      exhaustedAt: '2026-05-06T12:34:56.000Z',
      totalAttempts: 3,
    });
  });

  it('preserves the original job payload (visitId / userId) for operator-side replay', async () => {
    await enqueueDlq(basePayload);

    const [, data] = mocks.queueAdd.mock.calls[0];
    expect(data.originalPayload).toEqual({
      visitId: 'cmot_test_visit',
      userId: 'user_1',
    });
  });

  it("derives jobId from origin queue + job id (idempotent on duplicate `failed` events)", async () => {
    await enqueueDlq(basePayload);

    const [, , opts] = mocks.queueAdd.mock.calls[0];
    expect(opts.jobId).toBe(`${QUEUE_NAME}:visit-abc-29033710`);
  });

  it('falls back to "null" suffix when the original jobId is missing', async () => {
    await enqueueDlq({ ...basePayload, originalJobId: null });

    const [, , opts] = mocks.queueAdd.mock.calls[0];
    expect(opts.jobId).toBe(`${QUEUE_NAME}:null`);
  });

  it('uses the canonical DLQ queue name', () => {
    // Sanity — the dashboard's bull-board adapter mounts queues by
    // name. If this constant ever drifts the dashboard goes blank.
    // Renamed 2026-05-12 from `dlq:permanent-failures` (the colon
    // caused BullMQ to reject the queue at construction time, which
    // silently dropped every dead-lettered job — deep-audit G10).
    expect(DLQ_QUEUE_NAME).toBe('dlq-permanent-failures');
  });

  it('queue name contains no characters BullMQ rejects (no :, no whitespace)', () => {
    // Regression guard for G10. BullMQ throws "Queue name cannot
    // contain :" at `new Queue(name, …)` if the name has a colon.
    // Whitespace is also rejected. Keep this assertion as a hard
    // pre-commit on any future rename.
    expect(DLQ_QUEUE_NAME).not.toMatch(/[:\s]/);
  });
});

describe('enqueueDlq — error propagation (PR-L)', () => {
  it('rejects with the underlying Queue.add error so the worker can log it', async () => {
    mocks.queueAdd.mockRejectedValueOnce(new Error('redis connection lost'));

    await expect(
      enqueueDlq({
        originalQueue: QUEUE_NAME,
        originalJobId: 'x',
        originalJobName: 'process_visit',
        originalPayload: {},
        lastError: 'meh',
        exhaustedAt: new Date().toISOString(),
        totalAttempts: 3,
      })
    ).rejects.toThrow(/redis connection lost/);
  });
});
