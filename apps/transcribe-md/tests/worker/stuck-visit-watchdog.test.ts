// ============================================================================
// Stuck-visit watchdog tests (2026-05-12).
// ----------------------------------------------------------------------------
// Pins the per-minute sweep's force-fail semantics. Mocks @meddoc/db so
// the test can simulate visits in each of the 6 in-flight statuses +
// QUEUED (the latter must NOT be touched — that's the
// stale-visit-cleanup sweep's job).
// ============================================================================

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  findMany: vi.fn(),
  updateMany: vi.fn(),
  logAudit: vi.fn(),
}));

vi.mock('@meddoc/db', () => ({
  default: {
    transcribeVisit: {
      findMany: mocks.findMany,
      updateMany: mocks.updateMany,
    },
  },
}));

vi.mock('@/lib/audit', () => ({ logAudit: mocks.logAudit }));

import { runStuckVisitWatchdog } from '@/worker/cleanup/stuck-visit-watchdog';

beforeEach(() => {
  vi.clearAllMocks();
  mocks.findMany.mockResolvedValue([]);
  mocks.updateMany.mockResolvedValue({ count: 1 });
  mocks.logAudit.mockResolvedValue(undefined);
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe('runStuckVisitWatchdog — empty result', () => {
  it('returns scanned=0 / rescued=0 when no stuck visits exist', async () => {
    const result = await runStuckVisitWatchdog();
    expect(result).toEqual({ scanned: 0, rescued: 0, errors: 0 });
    expect(mocks.findMany).toHaveBeenCalledTimes(1);
    expect(mocks.updateMany).not.toHaveBeenCalled();
    expect(mocks.logAudit).not.toHaveBeenCalled();
  });
});

describe('runStuckVisitWatchdog — single stuck visit', () => {
  it('transitions the visit + writes the audit row', async () => {
    const startedAt = new Date(Date.now() - 20 * 60 * 1000); // 20 min ago
    mocks.findMany.mockResolvedValueOnce([
      {
        id: 'cmp_stuck_1',
        status: 'POLISHING',
        userId: 'u1',
        user: { practiceId: 'p1' },
        processingStartedAt: startedAt,
      },
    ]);

    const result = await runStuckVisitWatchdog();

    expect(result.scanned).toBe(1);
    expect(result.rescued).toBe(1);
    expect(result.errors).toBe(0);

    // Updates with the FAILED + transient pair + a reviewReason that
    // names the prev status so visit-failed-view can derive layer-
    // aware copy.
    expect(mocks.updateMany).toHaveBeenCalledTimes(1);
    const updateArgs = mocks.updateMany.mock.calls[0][0];
    expect(updateArgs.data.status).toBe('FAILED');
    expect(updateArgs.data.failureCategory).toBe('transient');
    expect(updateArgs.data.needsReview).toBe(true);
    expect(updateArgs.data.reviewReason).toMatch(/was POLISHING for 20 min/);
    expect(updateArgs.data.reviewReason).toMatch(/retry to reprocess/i);

    // Race-guard WHERE clause prevents clobbering a row the worker
    // just transitioned.
    expect(updateArgs.where.id).toBe('cmp_stuck_1');
    expect(updateArgs.where.status).toBeDefined();
    expect(updateArgs.where.processingStartedAt).toBeDefined();

    // Audit row carries forensics metadata.
    expect(mocks.logAudit).toHaveBeenCalledTimes(1);
    const auditArgs = mocks.logAudit.mock.calls[0][0];
    expect(auditArgs.action).toBe('VISIT_PROCESSING_TIMEOUT');
    expect(auditArgs.targetId).toBe('cmp_stuck_1');
    expect(auditArgs.metadata.prevStatus).toBe('POLISHING');
    expect(auditArgs.metadata.elapsedMin).toBe(20);
    expect(auditArgs.metadata.thresholdMin).toBe(15);
  });
});

describe('runStuckVisitWatchdog — race with the worker (Prisma updateMany count=0)', () => {
  it('does NOT count as rescued when the worker won the race', async () => {
    mocks.findMany.mockResolvedValueOnce([
      {
        id: 'cmp_race',
        status: 'POLISHING',
        userId: 'u1',
        user: { practiceId: 'p1' },
        processingStartedAt: new Date(Date.now() - 20 * 60 * 1000),
      },
    ]);
    mocks.updateMany.mockResolvedValueOnce({ count: 0 });

    const result = await runStuckVisitWatchdog();
    expect(result.scanned).toBe(1);
    expect(result.rescued).toBe(0);
    expect(result.errors).toBe(0);

    // No audit row when the rescue didn't fire — the row's actual
    // outcome is whatever the worker just wrote.
    expect(mocks.logAudit).not.toHaveBeenCalled();
  });
});

describe('runStuckVisitWatchdog — audit-row write failure', () => {
  it('still counts as rescued; logs the audit-gap as a non-fatal error', async () => {
    mocks.findMany.mockResolvedValueOnce([
      {
        id: 'cmp_audit_fail',
        status: 'TRANSCRIBING',
        userId: 'u1',
        user: { practiceId: 'p1' },
        processingStartedAt: new Date(Date.now() - 18 * 60 * 1000),
      },
    ]);
    mocks.logAudit.mockRejectedValueOnce(
      new Error('headers was called outside a request scope'),
    );

    const result = await runStuckVisitWatchdog();
    expect(result.rescued).toBe(1);
    expect(result.errors).toBe(1);
  });
});

describe('runStuckVisitWatchdog — Prisma update throw', () => {
  it('counts as error, not rescued', async () => {
    mocks.findMany.mockResolvedValueOnce([
      {
        id: 'cmp_db_error',
        status: 'EXTRACTING',
        userId: 'u1',
        user: { practiceId: 'p1' },
        processingStartedAt: new Date(Date.now() - 30 * 60 * 1000),
      },
    ]);
    mocks.updateMany.mockRejectedValueOnce(new Error('connection refused'));

    const result = await runStuckVisitWatchdog();
    expect(result.rescued).toBe(0);
    expect(result.errors).toBe(1);
  });
});

describe('runStuckVisitWatchdog — multiple stuck visits across statuses', () => {
  it('rescues each independently + scopes the reviewReason to the actual prev status', async () => {
    const now = new Date(Date.UTC(2026, 4, 12, 22, 0, 0));
    const startedAtMin = (mins: number) =>
      new Date(now.getTime() - mins * 60 * 1000);

    mocks.findMany.mockResolvedValueOnce([
      { id: 'a', status: 'TRANSCRIBING', userId: 'u', user: { practiceId: 'p' }, processingStartedAt: startedAtMin(16) },
      { id: 'b', status: 'EXTRACTING', userId: 'u', user: { practiceId: 'p' }, processingStartedAt: startedAtMin(22) },
      { id: 'c', status: 'POLISHING', userId: 'u', user: { practiceId: 'p' }, processingStartedAt: startedAtMin(45) },
      { id: 'd', status: 'AUTOMATING', userId: 'u', user: { practiceId: 'p' }, processingStartedAt: startedAtMin(180) },
    ]);

    const result = await runStuckVisitWatchdog({ now });
    expect(result.scanned).toBe(4);
    expect(result.rescued).toBe(4);

    const reasons = mocks.updateMany.mock.calls.map((c) => c[0].data.reviewReason);
    expect(reasons[0]).toMatch(/was TRANSCRIBING for 16 min/);
    expect(reasons[1]).toMatch(/was EXTRACTING for 22 min/);
    expect(reasons[2]).toMatch(/was POLISHING for 45 min/);
    expect(reasons[3]).toMatch(/was AUTOMATING for 180 min/);
  });
});

describe('runStuckVisitWatchdog — configurable threshold', () => {
  it('honors an override threshold (e.g. 10 min for tighter dev environments)', async () => {
    mocks.findMany.mockResolvedValueOnce([
      {
        id: 'cmp_tight',
        status: 'CRITIQUING',
        userId: 'u',
        user: { practiceId: 'p' },
        processingStartedAt: new Date(Date.now() - 11 * 60 * 1000),
      },
    ]);
    const result = await runStuckVisitWatchdog({ thresholdMs: 10 * 60 * 1000 });
    expect(result.rescued).toBe(1);
    const audit = mocks.logAudit.mock.calls[0][0];
    expect(audit.metadata.thresholdMin).toBe(10);
  });
});
