// ============================================================================
// DLQ + main queue jobId BullMQ-legality regression guards (2026-05-12).
// ----------------------------------------------------------------------------
// PR #223 fixed half of the G10 finding (queue name colon rejection) but
// the Kasra stuck-visit incident surfaced the other half: BullMQ ALSO
// rejects job IDs containing ':' with `Error: Custom Id cannot contain :`.
// Pre-fix, `enqueueDlq()` composed `${originalQueue}:${originalJobId}` as
// the jobId — every dead-lettered job since PR-L failed to enqueue with
// a one-line worker log + no DLQ row.
//
// This test pins:
//   1. enqueueDlq() now uses '--' as the separator (no colons anywhere)
//   2. enqueueProcessVisit() removes a prior terminal-state job before
//      enqueueing so a same-minute retry isn't silently deduped against
//      a dead-failed job (the actual Kasra stuck-visit mechanism)
// ============================================================================

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  queueAdd: vi.fn().mockResolvedValue({ id: 'job-ok' }),
  redisErrorOn: vi.fn(),
  getJob: vi.fn(),
  jobRemove: vi.fn(),
  jobGetState: vi.fn(),
}));

vi.mock('bullmq', () => ({
  Queue: class {
    add = mocks.queueAdd;
    getJob = mocks.getJob;
  },
}));

vi.mock('ioredis', () => ({
  default: class {
    on = mocks.redisErrorOn;
  },
}));

vi.mock('@meddoc/ai', () => ({ redactPhi: (s: string) => s }));

import {
  enqueueDlq,
  enqueueProcessVisit,
  QUEUE_NAME,
} from '@/lib/queue';

beforeEach(() => {
  vi.clearAllMocks();
  mocks.queueAdd.mockResolvedValue({ id: 'job-ok' });
  mocks.getJob.mockResolvedValue(null);
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe('enqueueDlq — jobId is BullMQ-legal (no colons)', () => {
  it('uses "--" as the queue/jobId separator', async () => {
    await enqueueDlq({
      originalQueue: 'transcribe-md',
      originalJobId: 'visit-cmp31iojc-retry-29643593',
      originalJobName: 'process_visit',
      originalPayload: { visitId: 'cmp31iojc' },
      lastError: '529 overloaded',
      exhaustedAt: '2026-05-12T19:53:38.000Z',
      totalAttempts: 3,
    });

    const [, , opts] = mocks.queueAdd.mock.calls[0];
    expect(opts.jobId).toBe('transcribe-md--visit-cmp31iojc-retry-29643593');
    expect(opts.jobId).not.toMatch(/:/);
  });

  it('falls back to "null" suffix when originalJobId is missing — still no colons', async () => {
    await enqueueDlq({
      originalQueue: 'transcribe-md',
      originalJobId: null,
      originalJobName: 'process_visit',
      originalPayload: {},
      lastError: 'whatever',
      exhaustedAt: new Date().toISOString(),
      totalAttempts: 3,
    });

    const [, , opts] = mocks.queueAdd.mock.calls[0];
    expect(opts.jobId).toBe('transcribe-md--null');
    expect(opts.jobId).not.toMatch(/:/);
  });

  it('regression guard — no DLQ jobId can ever contain ":"', async () => {
    // Cross-check shape across a spread of plausible inputs.
    const fixtures = [
      'transcribe-md',
      'transcribe-md-cleanup',
      'queue-with-many-segments',
    ];
    for (const originalQueue of fixtures) {
      mocks.queueAdd.mockClear();
      await enqueueDlq({
        originalQueue,
        originalJobId: 'visit-abc-123',
        originalJobName: 'process_visit',
        originalPayload: {},
        lastError: 'meh',
        exhaustedAt: new Date().toISOString(),
        totalAttempts: 3,
      });
      const [, , opts] = mocks.queueAdd.mock.calls[0];
      expect(opts.jobId, `${originalQueue}`).not.toMatch(/:/);
    }
  });
});

describe('enqueueProcessVisit — removes prior terminal job before enqueue', () => {
  it('removes a prior FAILED job with the same jobId (the Kasra stuck-visit fix)', async () => {
    const remove = vi.fn().mockResolvedValue(undefined);
    const getState = vi.fn().mockResolvedValue('failed');
    mocks.getJob.mockResolvedValueOnce({ remove, getState });

    await enqueueProcessVisit('cmp_v1', 'u1', { retry: true });

    expect(mocks.getJob).toHaveBeenCalledTimes(1);
    expect(getState).toHaveBeenCalledTimes(1);
    expect(remove).toHaveBeenCalledTimes(1);
    expect(mocks.queueAdd).toHaveBeenCalledTimes(1);
    const [, , opts] = mocks.queueAdd.mock.calls[0];
    expect(opts.jobId).toMatch(/^visit-cmp_v1-retry-\d+$/);
  });

  it('removes a prior COMPLETED job with the same jobId', async () => {
    const remove = vi.fn().mockResolvedValue(undefined);
    const getState = vi.fn().mockResolvedValue('completed');
    mocks.getJob.mockResolvedValueOnce({ remove, getState });

    await enqueueProcessVisit('cmp_v2', 'u1', {});

    expect(remove).toHaveBeenCalledTimes(1);
    expect(mocks.queueAdd).toHaveBeenCalledTimes(1);
  });

  it('does NOT remove a prior ACTIVE job (preserves double-click idempotency)', async () => {
    const remove = vi.fn().mockResolvedValue(undefined);
    const getState = vi.fn().mockResolvedValue('active');
    mocks.getJob.mockResolvedValueOnce({ remove, getState });

    await enqueueProcessVisit('cmp_v3', 'u1', { retry: true });

    expect(getState).toHaveBeenCalledTimes(1);
    expect(remove).not.toHaveBeenCalled();
    // Re-enqueue still fires; BullMQ's silent-no-op on jobId collision
    // protects the in-flight job (T-M16.4 contract preserved).
    expect(mocks.queueAdd).toHaveBeenCalledTimes(1);
  });

  it('does NOT remove a prior WAITING job (preserves double-click idempotency)', async () => {
    const remove = vi.fn();
    const getState = vi.fn().mockResolvedValue('waiting');
    mocks.getJob.mockResolvedValueOnce({ remove, getState });

    await enqueueProcessVisit('cmp_v4', 'u1', { retry: true });
    expect(remove).not.toHaveBeenCalled();
  });

  it('does NOT remove a prior DELAYED job (preserves backoff state)', async () => {
    const remove = vi.fn();
    const getState = vi.fn().mockResolvedValue('delayed');
    mocks.getJob.mockResolvedValueOnce({ remove, getState });

    await enqueueProcessVisit('cmp_v5', 'u1', { retry: true });
    expect(remove).not.toHaveBeenCalled();
  });

  it('falls through to add() if the BullMQ inspect call throws (best-effort)', async () => {
    mocks.getJob.mockRejectedValueOnce(new Error('redis connection lost'));

    // Should not bubble — the add() runs and add()'s own dedup logic
    // handles the symptom if a colliding job exists.
    await expect(enqueueProcessVisit('cmp_v6', 'u1', { retry: true })).resolves.toBeUndefined();
    expect(mocks.queueAdd).toHaveBeenCalledTimes(1);
  });
});

describe('enqueueProcessVisit — main queue jobId is BullMQ-legal', () => {
  it('initial enqueue jobId contains no colons or whitespace', async () => {
    await enqueueProcessVisit('cmp_v_init', 'u1');
    const [, , opts] = mocks.queueAdd.mock.calls[0];
    expect(opts.jobId).not.toMatch(/[:\s]/);
  });

  it('retry enqueue jobId contains no colons or whitespace', async () => {
    await enqueueProcessVisit('cmp_v_retry', 'u1', { retry: true });
    const [, , opts] = mocks.queueAdd.mock.calls[0];
    expect(opts.jobId).not.toMatch(/[:\s]/);
  });
});

describe('QUEUE_NAME sanity check (pre-existing, regression guard)', () => {
  it('QUEUE_NAME is BullMQ-legal', () => {
    expect(QUEUE_NAME).not.toMatch(/[:\s]/);
  });
});
