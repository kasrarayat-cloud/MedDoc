// ============================================================================
// POST /api/visits/[id]/icd-codes/decision — F8-S1's server gates.
// ----------------------------------------------------------------------------
// Prisma / auth / audit are mocked; the DECISION LOGIC is real
// (`lib/icd-decisions.ts` is imported, not stubbed), so these arms measure the
// shipped predicate rather than a re-implementation of it.
//
// The claims, stated so they can be broken:
//   1. a SIGNED visit refuses, server-side, and writes nothing
//   2. a code the suggester never proposed refuses, and writes nothing
//   3. the happy path writes the map AND the audit row — the row is READ BACK,
//      because `logAudit` is fire-and-forget and its failure is invisible by
//      construction
//   4. the audit metadata carries the CODE and nothing that can hold patient
//      context — asserted by exact key set, not by absence of one field
//   5. a NO-OP writes nothing and audits nothing
//   6. each intent maps to its OWN label; CLEARED is a real event
// ============================================================================

import { beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  findFirst: vi.fn(),
  updateMany: vi.fn(),
  queryRaw: vi.fn(),
  transaction: vi.fn(),
  auth: vi.fn(),
  logAudit: vi.fn(),
}));

vi.mock('next/server', () => {
  class FakeNextResponse {
    status: number;
    headers = new Map<string, string>();
    body: unknown;
    constructor(body: unknown, init?: { status?: number }) {
      this.body = body;
      this.status = init?.status ?? 200;
    }
    async json() {
      return this.body;
    }
    static json(body: unknown, init?: { status?: number }) {
      return new FakeNextResponse(body, init);
    }
  }
  return { NextResponse: FakeNextResponse };
});

vi.mock('@meddoc/db', () => {
  const prisma: Record<string, unknown> = {
    transcribeVisit: { findFirst: mocks.findFirst, updateMany: mocks.updateMany },
    // The row lock. Recorded so the arms below can assert it was taken, and
    // taken FIRST — a lock acquired after the read protects nothing.
    $queryRaw: mocks.queryRaw,
    // Interactive transaction: the callback receives the same client, so every
    // call the route makes through `tx` lands on these same spies.
    $transaction: (fn: unknown) => {
      mocks.transaction();
      return typeof fn === 'function'
        ? (fn as (tx: unknown) => unknown)(prisma)
        : Promise.all(fn as never);
    },
  };
  return { default: prisma, prisma };
});
vi.mock('@/lib/auth', () => ({ getSession: mocks.auth }));
vi.mock('@/lib/nextauth', () => ({ auth: mocks.auth }));
vi.mock('@/lib/audit', () => ({ logAudit: mocks.logAudit }));
vi.mock('@meddoc/ai', () => ({ redactPhi: (x: unknown) => x }));
vi.mock('@/lib/log', () => ({
  log: { warn: vi.fn(), info: vi.fn(), error: vi.fn() },
}));

import type { NextRequest } from 'next/server';
import { TranscribeVisitStatus } from '@prisma/client';

import { POST } from '../route';

const DOCTOR = 'doc-1';
const PRACTICE = 'p1';
const VISIT = 'visit-1';

const ICD = {
  codes: [
    { code: 'K21.00', description: 'GERD with esophagitis', evidence_quote: 'q1', confidence: 0.93 },
    { code: 'I10', description: 'Essential hypertension', evidence_quote: 'q2', confidence: 0.81 },
  ],
};

function visitRow(over: Record<string, unknown> = {}) {
  return {
    id: VISIT,
    status: TranscribeVisitStatus.READY,
    deletedAt: null,
    archivedAt: null,
    signedAt: null,
    icdCodes: ICD,
    icdDecisions: null,
    ...over,
  };
}

function call(body: unknown) {
  const req = { json: async () => body } as unknown as NextRequest;
  return POST(req, { params: Promise.resolve({ id: VISIT }) });
}

/** The response shape these arms read. `body` is the FakeNextResponse field. */
type Res = { status: number; body: Record<string, unknown> };

beforeEach(() => {
  vi.clearAllMocks();
  mocks.auth.mockResolvedValue({
    user: { id: DOCTOR, email: 'doc@test.dev', practiceId: PRACTICE },
  });
  mocks.findFirst.mockResolvedValue(visitRow());
  mocks.updateMany.mockResolvedValue({ count: 1 });
  mocks.queryRaw.mockResolvedValue([{ id: VISIT }]);
});

// ── THE LOCK ───────────────────────────────────────────────────────────────
// ⚠️ `icdDecisions` is a WHOLE-COLUMN overwrite built from a value the request
// read. Two accepts in flight at once would each read the map, each add one
// entry, and the second write would silently drop the first — F5-h's class
// ("read fresh, written stale"), already paid for once on the E/M blob.
describe('⚠️ the read-modify-write runs under a ROW LOCK', () => {
  it('locks the PRACTICE-SCOPED row, and locks it BEFORE reading', async () => {
    await call({ code: 'K21.00', decision: 'accepted' });
    expect(mocks.transaction).toHaveBeenCalledTimes(1);
    expect(mocks.queryRaw).toHaveBeenCalledTimes(1);

    // The tagged-template call arrives as (strings, ...values).
    const [strings, ...values] = mocks.queryRaw.mock.calls[0] as [string[], ...unknown[]];
    const sql = strings.join('?');
    expect(sql).toMatch(/FOR UPDATE/i);
    expect(sql).toMatch(/"transcribe_visits"/);
    // Parameterised, never interpolated — the values travel separately.
    expect(values).toEqual([VISIT, PRACTICE]);
    expect(sql).not.toContain(VISIT);

    // ⚠️ ORDER IS THE WHOLE POINT. A lock taken after the read protects
    // nothing, and a test that only asserts "both were called" is green on
    // exactly that defect.
    expect(mocks.queryRaw.mock.invocationCallOrder[0]).toBeLessThan(
      mocks.findFirst.mock.invocationCallOrder[0],
    );
    expect(mocks.queryRaw.mock.invocationCallOrder[0]).toBeLessThan(
      mocks.updateMany.mock.invocationCallOrder[0],
    );
  });

  it('EVERY GATE runs inside the lock, not only the write', async () => {
    // A visit signed between a gate read and the write would otherwise take a
    // decision AFTER its signature — the freeze bypassed by a race.
    mocks.findFirst.mockResolvedValue(visitRow({ signedAt: new Date() }));
    const res = (await call({ code: 'K21.00', decision: 'accepted' })) as unknown as Res;
    expect(res.status).toBe(409);
    expect(mocks.queryRaw).toHaveBeenCalledTimes(1);
    expect(mocks.queryRaw.mock.invocationCallOrder[0]).toBeLessThan(
      mocks.findFirst.mock.invocationCallOrder[0],
    );
  });

  it('the audit row is emitted only when the write COMMITTED', async () => {
    // `logAudit` is fire-and-forget; attaching it inside a transaction that has
    // already resolved is how a row goes missing. It fires after, and only on
    // a real change.
    await call({ code: 'K21.00', decision: 'accepted' });
    expect(mocks.logAudit).toHaveBeenCalledTimes(1);
    expect(mocks.logAudit.mock.invocationCallOrder[0]).toBeGreaterThan(
      mocks.updateMany.mock.invocationCallOrder[0],
    );
  });
});

describe('the happy path — and it is asserted FIRST so every refusal below has a control', () => {
  it('accepts a suggested code: writes the map, returns the projection', async () => {
    const res = (await call({ code: 'K21.00', decision: 'accepted' })) as unknown as Res;
    expect(res.status).toBe(200);
    expect(res.body.ok).toBe(true);
    expect(res.body.changed).toBe(true);

    expect(mocks.updateMany).toHaveBeenCalledTimes(1);
    const args = mocks.updateMany.mock.calls[0][0] as {
      where: Record<string, unknown>;
      data: { icdDecisions: Record<string, { state: string; byUserId: string }> };
    };
    // Practice-scoped write — T5's wall, asserted rather than assumed.
    expect(args.where).toMatchObject({ id: VISIT, practiceId: PRACTICE });
    expect(args.data.icdDecisions['K21.00'].state).toBe('accepted');
    expect(args.data.icdDecisions['K21.00'].byUserId).toBe(DOCTOR);

    expect(res.body.summary).toEqual({ suggested: 2, accepted: 1, needsReview: 1 });
  });

  it('READS THE AUDIT ROW BACK — action, target, and the exact metadata key set', async () => {
    await call({ code: 'K21.00', decision: 'accepted' });
    expect(mocks.logAudit).toHaveBeenCalledTimes(1);
    const row = mocks.logAudit.mock.calls[0][0] as {
      action: string;
      targetType: string;
      targetId: string;
      metadata: Record<string, unknown>;
    };
    expect(row.action).toBe('ICD_CODE_ACCEPTED');
    expect(row.targetType).toBe('transcribe_visit');
    expect(row.targetId).toBe(VISIT);

    // ⚠️ EXACT KEY SET, not "does not contain description". A future field
    // carrying patient context would satisfy a negative assertion about one
    // name and fail this one. `07a-icd-coding.ts:471-473` already records that
    // the AI-emitted description can include patient context.
    expect(Object.keys(row.metadata).sort()).toEqual(['code', 'fromState', 'toState']);
    expect(row.metadata).toEqual({ code: 'K21.00', fromState: null, toState: 'accepted' });
  });

  it('each intent writes its OWN label — CLEARED is a real event', async () => {
    const cases: Array<[string, string, unknown]> = [
      ['accepted', 'ICD_CODE_ACCEPTED', null],
      ['rejected', 'ICD_CODE_REJECTED', null],
      [
        'cleared',
        'ICD_CODE_DECISION_CLEARED',
        { 'K21.00': { state: 'accepted', at: '2026-08-25T10:00:00.000Z', byUserId: DOCTOR } },
      ],
    ];
    for (const [decision, label, stored] of cases) {
      vi.clearAllMocks();
      mocks.auth.mockResolvedValue({
        user: { id: DOCTOR, email: 'doc@test.dev', practiceId: PRACTICE },
      });
      mocks.updateMany.mockResolvedValue({ count: 1 });
      mocks.findFirst.mockResolvedValue(visitRow({ icdDecisions: stored }));

      const res = (await call({ code: 'K21.00', decision })) as unknown as Res;
      expect(res.status, `${decision} did not succeed`).toBe(200);
      expect(res.body.changed, `${decision} was a no-op`).toBe(true);
      expect(mocks.logAudit.mock.calls[0][0].action).toBe(label);
    }
  });

  it('a differently-cased code resolves, and the audit row records the NORMALISED code', async () => {
    await call({ code: ' k21.00 ', decision: 'rejected' });
    expect(mocks.updateMany).toHaveBeenCalledTimes(1);
    expect(mocks.logAudit.mock.calls[0][0].metadata.code).toBe('K21.00');
  });
});

describe('⚠️ THE FREEZE — a signed visit refuses, server-side', () => {
  it.each([
    ['signedAt set', { signedAt: new Date('2026-08-25T09:00:00.000Z') }],
    ['status SIGNED', { status: TranscribeVisitStatus.SIGNED }],
  ])('%s → 409 VISIT_LOCKED, and NOTHING is written', async (_label, over) => {
    mocks.findFirst.mockResolvedValue(visitRow(over));
    const res = (await call({ code: 'K21.00', decision: 'accepted' })) as unknown as Res;
    expect(res.status).toBe(409);
    expect(res.body.code).toBe('VISIT_LOCKED');
    expect(mocks.updateMany).not.toHaveBeenCalled();
    expect(mocks.logAudit).not.toHaveBeenCalled();
  });
});

describe('the suggested set is the authority', () => {
  it('a code the suggester never proposed → 409, and NOTHING is written', async () => {
    const res = (await call({ code: 'Z99.9', decision: 'accepted' })) as unknown as Res;
    expect(res.status).toBe(409);
    expect(res.body.code).toBe('ICD_CODE_NOT_SUGGESTED');
    expect(mocks.updateMany).not.toHaveBeenCalled();
    expect(mocks.logAudit).not.toHaveBeenCalled();
  });

  it('a visit with NO codes at all refuses every decision', async () => {
    mocks.findFirst.mockResolvedValue(visitRow({ icdCodes: null }));
    const res = (await call({ code: 'K21.00', decision: 'accepted' })) as unknown as Res;
    expect(res.status).toBe(409);
    expect(res.body.code).toBe('ICD_CODE_NOT_SUGGESTED');
  });
});

describe('a NO-OP is not an event', () => {
  it('re-asserting the stored state writes nothing and audits nothing', async () => {
    mocks.findFirst.mockResolvedValue(
      visitRow({
        icdDecisions: {
          'K21.00': { state: 'accepted', at: '2026-08-25T10:00:00.000Z', byUserId: DOCTOR },
        },
      }),
    );
    const res = (await call({ code: 'K21.00', decision: 'accepted' })) as unknown as Res;
    expect(res.status).toBe(200);
    expect(res.body.changed).toBe(false);
    expect(mocks.updateMany).not.toHaveBeenCalled();
    expect(mocks.logAudit).not.toHaveBeenCalled();
  });
});

describe('the ordinary gates', () => {
  it('no session → 401', async () => {
    mocks.auth.mockResolvedValue(null);
    const res = (await call({ code: 'K21.00', decision: 'accepted' })) as unknown as Res;
    expect(res.status).toBe(401);
  });

  it('a session with no practice → 401', async () => {
    mocks.auth.mockResolvedValue({ user: { id: DOCTOR, email: 'd@t.dev' } });
    const res = (await call({ code: 'K21.00', decision: 'accepted' })) as unknown as Res;
    expect(res.status).toBe(401);
  });

  it.each([
    ['an unknown decision', { code: 'K21.00', decision: 'maybe' }],
    ['a missing code', { decision: 'accepted' }],
    ['an over-long code', { code: 'K21.0000000000', decision: 'accepted' }],
  ])('%s → 400 INVALID_REQUEST', async (_label, body) => {
    const res = (await call(body)) as unknown as Res;
    expect(res.status).toBe(400);
    expect(res.body.code).toBe('INVALID_REQUEST');
    expect(mocks.updateMany).not.toHaveBeenCalled();
  });

  it('a visit outside the practice → 404, never 403', async () => {
    // The read is practice-scoped, so a foreign visit simply is not found.
    // 404 over 403 is this codebase's standing choice — never leak existence.
    mocks.findFirst.mockResolvedValue(null);
    const res = (await call({ code: 'K21.00', decision: 'accepted' })) as unknown as Res;
    expect(res.status).toBe(404);
  });

  it.each([
    ['deleted', { deletedAt: new Date() }],
    ['archived', { archivedAt: new Date() }],
  ])('a %s visit → 400 VISIT_NOT_ACTIVE', async (_label, over) => {
    mocks.findFirst.mockResolvedValue(visitRow(over));
    const res = (await call({ code: 'K21.00', decision: 'accepted' })) as unknown as Res;
    expect(res.status).toBe(400);
    expect(res.body.code).toBe('VISIT_NOT_ACTIVE');
  });

  it('a visit still in the pipeline → 409 VISIT_NOT_READY', async () => {
    // L7a has not settled, so `icdCodes` is still moving under any decision
    // made against it.
    mocks.findFirst.mockResolvedValue(
      visitRow({ status: TranscribeVisitStatus.DRAFTING }),
    );
    const res = (await call({ code: 'K21.00', decision: 'accepted' })) as unknown as Res;
    expect(res.status).toBe(409);
    expect(res.body.code).toBe('VISIT_NOT_READY');
  });
});
