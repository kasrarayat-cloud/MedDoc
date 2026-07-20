// ============================================================================
// Stuck-visit watchdog tests (2026-05-12).
// ----------------------------------------------------------------------------
// Pins the per-minute sweep's force-fail semantics. Mocks @meddoc/db so
// the test can simulate visits in each of the 6 in-flight statuses +
// QUEUED (the latter must NOT be touched — that's the
// stale-visit-cleanup sweep's job).
// ============================================================================

import { beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  findMany: vi.fn(),
  txFindUnique: vi.fn(),
  txUpdateMany: vi.fn(),
  txQueryRaw: vi.fn(),
  runTransaction: vi.fn(),
  enqueueAudit: vi.fn(),
  logInfo: vi.fn(),
  logError: vi.fn(),
}));

vi.mock('@meddoc/db', () => ({
  default: {
    transcribeVisit: {
      findMany: mocks.findMany,
    },
  },
}));

vi.mock('@/lib/db/transaction-retry', () => ({
  runSerializableTransactionWithRetry: mocks.runTransaction,
}));
vi.mock('@/lib/template-twin/audit-outbox', () => ({
  enqueueIdempotentTemplateTwinAudit: mocks.enqueueAudit,
}));
vi.mock('@/lib/log', () => ({
  log: {
    info: mocks.logInfo,
    error: mocks.logError,
    warn: vi.fn(),
  },
}));

import { runStuckVisitWatchdog } from '@/worker/cleanup/stuck-visit-watchdog';

const ORDINARY_MARKERS = {
  patient: { externalId: null },
  noteTemplate: {
    templateKind: 'structured',
    templateTwinCompiledVersion: null,
  },
  templateTwinFill: null,
  templateTwinSyntheticQaRun: null,
  templateTwinSyntheticQaAdmission: null,
  templateTwinProviderExecutions: [],
} as const;

type Candidate = ReturnType<typeof ordinaryCandidate>;

function ordinaryCandidate(overrides: Record<string, unknown> = {}) {
  return {
    id: 'cmp_stuck_1',
    status: 'POLISHING',
    userId: 'u1',
    user: { practiceId: 'p1' },
    processingStartedAt: new Date(Date.now() - 20 * 60 * 1000),
    ...ORDINARY_MARKERS,
    ...overrides,
  };
}

function lockedCandidate(candidate: Candidate) {
  return {
    id: candidate.id,
    status: candidate.status,
    processingStartedAt: candidate.processingStartedAt,
    patient: candidate.patient,
    noteTemplate: candidate.noteTemplate,
    templateTwinFill: candidate.templateTwinFill,
    templateTwinSyntheticQaRun: candidate.templateTwinSyntheticQaRun,
    templateTwinSyntheticQaAdmission:
      candidate.templateTwinSyntheticQaAdmission,
    templateTwinProviderExecutions: candidate.templateTwinProviderExecutions,
  };
}

function setCandidates(candidates: Candidate[]) {
  const byId = new Map(candidates.map((candidate) => [candidate.id, candidate]));
  mocks.findMany.mockResolvedValueOnce(candidates);
  mocks.txFindUnique.mockImplementation(
    async (args: { where: { id: string } }) => {
      const candidate = byId.get(args.where.id);
      return candidate ? lockedCandidate(candidate) : null;
    },
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  mocks.findMany.mockResolvedValue([]);
  mocks.txFindUnique.mockResolvedValue(null);
  mocks.txUpdateMany.mockResolvedValue({ count: 1 });
  mocks.txQueryRaw.mockResolvedValue([{ id: 'locked-row' }]);
  mocks.enqueueAudit.mockResolvedValue('CREATED');
  mocks.runTransaction.mockImplementation(
    async (input: { transaction: (tx: unknown) => Promise<unknown> }) =>
      input.transaction({
        transcribeVisit: {
          findUnique: mocks.txFindUnique,
          updateMany: mocks.txUpdateMany,
        },
        $queryRaw: mocks.txQueryRaw,
      }),
  );
});

describe('runStuckVisitWatchdog — empty result', () => {
  it('returns scanned=0 / rescued=0 when no stuck visits exist', async () => {
    const result = await runStuckVisitWatchdog();
    expect(result).toEqual({ scanned: 0, rescued: 0, errors: 0 });
    expect(mocks.findMany).toHaveBeenCalledTimes(1);
    expect(mocks.txUpdateMany).not.toHaveBeenCalled();
    expect(mocks.enqueueAudit).not.toHaveBeenCalled();
  });
});

describe('runStuckVisitWatchdog — single stuck visit', () => {
  it('transitions the visit + writes the audit row', async () => {
    const startedAt = new Date(Date.now() - 20 * 60 * 1000); // 20 min ago
    setCandidates([
      ordinaryCandidate({
        id: 'cmp_stuck_1',
        status: 'POLISHING',
        userId: 'u1',
        user: { practiceId: 'p1' },
        processingStartedAt: startedAt,
      }),
    ]);

    const result = await runStuckVisitWatchdog();

    expect(result.scanned).toBe(1);
    expect(result.rescued).toBe(1);
    expect(result.errors).toBe(0);

    // Updates with the FAILED + transient pair + a reviewReason that
    // names the prev status so visit-failed-view can derive layer-
    // aware copy.
    expect(mocks.txUpdateMany).toHaveBeenCalledTimes(1);
    const updateArgs = mocks.txUpdateMany.mock.calls[0][0];
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
    expect(mocks.enqueueAudit).toHaveBeenCalledTimes(1);
    const auditArgs = mocks.enqueueAudit.mock.calls[0][1];
    expect(auditArgs.action).toBe('VISIT_PROCESSING_TIMEOUT');
    expect(auditArgs.targetId).toBe('cmp_stuck_1');
    expect(auditArgs.metadata.prevStatus).toBe('POLISHING');
    expect(auditArgs.metadata.elapsedMin).toBe(20);
    expect(auditArgs.metadata.thresholdMin).toBe(15);
  });
});

describe('runStuckVisitWatchdog — race with the worker (Prisma updateMany count=0)', () => {
  it('does NOT count as rescued when the worker won the race', async () => {
    setCandidates([
      ordinaryCandidate({
        id: 'cmp_race',
        status: 'POLISHING',
        userId: 'u1',
        user: { practiceId: 'p1' },
        processingStartedAt: new Date(Date.now() - 20 * 60 * 1000),
      }),
    ]);
    mocks.txUpdateMany.mockResolvedValueOnce({ count: 0 });

    const result = await runStuckVisitWatchdog();
    expect(result.scanned).toBe(1);
    expect(result.rescued).toBe(0);
    expect(result.errors).toBe(0);

    // No audit row when the rescue didn't fire — the row's actual
    // outcome is whatever the worker just wrote.
    expect(mocks.enqueueAudit).not.toHaveBeenCalled();
  });
});

describe('runStuckVisitWatchdog — outbox write failure', () => {
  it('does not report a rescue when the atomic audit write aborts the transaction', async () => {
    setCandidates([
      ordinaryCandidate({
        id: 'cmp_audit_fail',
        status: 'TRANSCRIBING',
        userId: 'u1',
        user: { practiceId: 'p1' },
        processingStartedAt: new Date(Date.now() - 18 * 60 * 1000),
      }),
    ]);
    mocks.enqueueAudit.mockRejectedValueOnce(new Error('outbox unavailable'));

    const result = await runStuckVisitWatchdog();
    expect(result.rescued).toBe(0);
    expect(result.errors).toBe(1);
    expect(mocks.txUpdateMany).toHaveBeenCalledTimes(1);
    expect(mocks.enqueueAudit).toHaveBeenCalledTimes(1);
    expect(mocks.logInfo).not.toHaveBeenCalled();
  });
});

describe('runStuckVisitWatchdog — Prisma update throw', () => {
  it('counts as error, not rescued', async () => {
    setCandidates([
      ordinaryCandidate({
        id: 'cmp_db_error',
        status: 'EXTRACTING',
        userId: 'u1',
        user: { practiceId: 'p1' },
        processingStartedAt: new Date(Date.now() - 30 * 60 * 1000),
      }),
    ]);
    mocks.txUpdateMany.mockRejectedValueOnce(new Error('connection refused'));

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

    setCandidates([
      ordinaryCandidate({
        id: 'a',
        status: 'TRANSCRIBING',
        userId: 'u',
        user: { practiceId: 'p' },
        processingStartedAt: startedAtMin(16),
      }),
      ordinaryCandidate({
        id: 'b',
        status: 'EXTRACTING',
        userId: 'u',
        user: { practiceId: 'p' },
        processingStartedAt: startedAtMin(22),
      }),
      ordinaryCandidate({
        id: 'c',
        status: 'POLISHING',
        userId: 'u',
        user: { practiceId: 'p' },
        processingStartedAt: startedAtMin(45),
      }),
      ordinaryCandidate({
        id: 'd',
        status: 'AUTOMATING',
        userId: 'u',
        user: { practiceId: 'p' },
        processingStartedAt: startedAtMin(180),
      }),
    ]);

    const result = await runStuckVisitWatchdog({ now });
    expect(result.scanned).toBe(4);
    expect(result.rescued).toBe(4);

    const reasons = mocks.txUpdateMany.mock.calls.map(
      (call) => call[0].data.reviewReason,
    );
    expect(reasons[0]).toMatch(/was TRANSCRIBING for 16 min/);
    expect(reasons[1]).toMatch(/was EXTRACTING for 22 min/);
    expect(reasons[2]).toMatch(/was POLISHING for 45 min/);
    expect(reasons[3]).toMatch(/was AUTOMATING for 180 min/);
  });
});

describe('runStuckVisitWatchdog — configurable threshold', () => {
  it('honors an override threshold (e.g. 10 min for tighter dev environments)', async () => {
    setCandidates([
      ordinaryCandidate({
        id: 'cmp_tight',
        status: 'CRITIQUING',
        userId: 'u',
        user: { practiceId: 'p' },
        processingStartedAt: new Date(Date.now() - 11 * 60 * 1000),
      }),
    ]);
    const result = await runStuckVisitWatchdog({ thresholdMs: 10 * 60 * 1000 });
    expect(result.rescued).toBe(1);
    const audit = mocks.enqueueAudit.mock.calls[0][1];
    expect(audit.metadata.thresholdMin).toBe(10);
  });
});
