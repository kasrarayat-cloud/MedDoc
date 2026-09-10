// ============================================================================
// ADMIN-6 — PRACTICE ARCHIVE AS ONE DECLARED, RESTORABLE ACT (+ door D2)
// ----------------------------------------------------------------------------
// The claims, each with the arm that would red if it stopped being true:
//
//   1. DESIGN A — the archive writes the PRACTICE ROW AND ITS AUDIT ROW, and
//      nothing else. No `users` write of any kind, on archive or on restore, so
//      neither users trigger fires and a restore returns every member exactly
//      as they were. (The byte-identical `users` table is proven on a real
//      Postgres by `scripts/proofs/admin6-archive-restore-proof.ts`.)
//   2. It refuses BY NAME — own practice, a platform administrator inside, a
//      visit still processing, an actor it cannot find — and writes nothing
//      when it does.
//   3. It never refuses a RESTORE for those reasons: #310(b), never strand.
//   4. The audit row is written in the transaction: a failed audit insert
//      FAILS the act instead of being swallowed.
//   5. D2 — `validateSession` returns null for a member of an archived
//      practice, and the same session is admitted once the practice is restored.
// ============================================================================
import { beforeEach, describe, expect, it, vi } from 'vitest';

type AuditArg = {
  data: {
    action: string;
    targetType?: string;
    targetId?: string;
    practiceId?: string;
    metadata: {
      changed: Record<string, { from: unknown; to: unknown }>;
      reason: string | null;
      members?: Record<string, unknown>[];
    };
  };
};

const h = vi.hoisted(() => {
  const w = () => vi.fn(async (_a: unknown): Promise<unknown> => ({}));
  const tx = {
    $queryRaw: vi.fn(async (_s: TemplateStringsArray, ..._v: unknown[]): Promise<unknown[]> => []),
    practice: {
      findUnique: vi.fn(async (_a: unknown): Promise<unknown> => null),
      update: vi.fn(async (_a: { where: { id: string }; data: Record<string, unknown> }) => ({})),
    },
    // ⚠️ EVERY USER WRITE METHOD IS PRESENT, SO A DESIGN-B REGRESSION (suspend
    // the members) would CALL one rather than throw "not a function" — and the
    // arm below asserts none was called. A missing method would make the arm
    // pass for the wrong reason: the act would crash, not refrain.
    user: {
      findUnique: vi.fn(async (_a: unknown): Promise<unknown> => null),
      findMany: vi.fn(async (_a: unknown): Promise<unknown[]> => []),
      update: w(),
      updateMany: w(),
      upsert: w(),
      create: w(),
      delete: w(),
      deleteMany: w(),
    },
    transcribeVisit: {
      findMany: vi.fn(async (_a: { where: Record<string, unknown> }): Promise<unknown[]> => []),
    },
    auditLog: { create: vi.fn(async (_a: AuditArg) => ({})) },
  };
  const transaction = vi.fn(
    async (fn: (t: typeof tx) => unknown, _opts?: { isolationLevel?: string }) => fn(tx),
  );
  const userSession = {
    findUnique: vi.fn(async (_a: unknown): Promise<unknown> => null),
    update: vi.fn(async (_a: unknown) => ({})),
    deleteMany: vi.fn(async (_a: unknown) => ({})),
  };
  return { tx, transaction, userSession };
});

vi.mock('@meddoc/db', () => ({
  default: { $transaction: h.transaction, userSession: h.userSession },
}));
// The route's gate is the existing `/admin` stack; here it hands straight
// through so the arm measures the ROUTE's mapping and nothing else.
vi.mock('@/lib/admin-api-gate', () => ({
  adminApi:
    (routeKey: string, handler: (req: Request, ctx: unknown) => unknown) =>
    (req: Request) =>
      handler(req, { session: { user: { id: 'u_admin' } }, routeKey }),
}));

import { IN_FLIGHT_VISIT_STATUSES, updatePractice } from '../practice-write';
import { validateSession } from '../../../../../packages/auth/src/user-session';
import { PATCH } from '../../app/api/admin/practices/[id]/route';

const { tx } = h;
const TARGET = { id: 'prac_T', name: 'Target', slug: 'target', isActive: true };
const ACTOR = { practiceId: 'prac_ADMIN', email: 'admin@example.invalid' };
const MEMBER = (id: string, extra: Record<string, unknown> = {}) => ({
  id,
  role: 'DOCTOR',
  practiceRole: 'CLINICIAN',
  products: ['TRANSCRIBE_MD'],
  isActive: true,
  deactivatedAt: null,
  suspendedAt: null,
  softDeletedAt: null,
  forceLogoutAt: null,
  ...extra,
});
const MEMBERS = [
  MEMBER('u_owner', { practiceRole: 'OWNER' }),
  MEMBER('u_susp', { suspendedAt: new Date('2026-09-01T00:00:00Z') }),
  MEMBER('u_deact', { isActive: false, deactivatedAt: new Date('2026-08-01T00:00:00Z'), practiceRole: 'TECH' }),
];
const USER_WRITES = ['update', 'updateMany', 'upsert', 'create', 'delete', 'deleteMany'] as const;

function archive(patch: Record<string, unknown> = { isActive: false }) {
  return updatePractice({ practiceId: 'prac_T', patch, actorUserId: 'u_admin', reason: 'closing' });
}

function expectNothingWritten() {
  expect(tx.practice.update, 'the practice row was written despite the refusal').not.toHaveBeenCalled();
  expect(tx.auditLog.create, 'an audit row was written for an act that did not happen').not.toHaveBeenCalled();
}

beforeEach(() => {
  vi.clearAllMocks();
  tx.$queryRaw.mockResolvedValue([TARGET]);
  tx.user.findUnique.mockResolvedValue(ACTOR);
  tx.user.findMany.mockResolvedValue(MEMBERS);
  tx.transcribeVisit.findMany.mockResolvedValue([]);
});

describe('ADMIN-6 — the archive act, positive control first', () => {
  it('POSITIVE CONTROL — an ordinary archive succeeds and writes the practice + ONE audit row', async () => {
    const r = await archive();
    expect(r.ok, `the act refused an ordinary archive — every refusal arm below is vacuous: ${JSON.stringify(r)}`).toBe(true);
    expect(tx.practice.update).toHaveBeenCalledTimes(1);
    expect(tx.practice.update.mock.calls[0]![0]).toEqual({ where: { id: 'prac_T' }, data: { isActive: false } });
    expect(tx.auditLog.create).toHaveBeenCalledTimes(1);
  });

  it('⚠️ one READ COMMITTED transaction, and the practice is read FOR UPDATE', async () => {
    await archive();
    expect(h.transaction).toHaveBeenCalledTimes(1);
    expect(h.transaction.mock.calls[0]![1]).toEqual({ isolationLevel: 'ReadCommitted' });
    const sql = tx.$queryRaw.mock.calls[0]![0].join('?');
    expect(sql).toMatch(/FROM practices WHERE id = \? FOR UPDATE/);
  });

  it('⚠️ the audit row NAMES its target, carries from/to and the reason, and a member snapshot of IDS ONLY', async () => {
    await archive();
    const row = tx.auditLog.create.mock.calls[0]![0].data;
    expect(row.action).toBe('PRACTICE_ARCHIVED');
    expect(row.targetType).toBe('Practice');
    expect(row.targetId).toBe('prac_T');
    expect(row.practiceId).toBe('prac_T');
    expect(row.metadata.changed).toEqual({ isActive: { from: true, to: false } });
    expect(row.metadata.reason).toBe('closing');
    const members = row.metadata.members!;
    expect(members.map((m) => m.id)).toEqual(['u_owner', 'u_susp', 'u_deact']);
    // the lifecycle state a restore will be compared against
    expect(members[1]!.suspendedAt).toBe('2026-09-01T00:00:00.000Z');
    expect(members[2]!.isActive).toBe(false);
    // ⚠️ NO PHI, NO PII — the snapshot never carries a name or an email
    for (const m of members) {
      expect(Object.keys(m)).not.toContain('email');
      expect(Object.keys(m)).not.toContain('name');
    }
  });
});

describe('ADMIN-6 — DESIGN A: the practice row is the ONLY write', () => {
  it.each([
    ['archive', { isActive: false }, true],
    ['restore', { isActive: true }, false],
  ])('⚠️ %s writes NO users row of any kind', async (_n, patch, currentlyActive) => {
    tx.$queryRaw.mockResolvedValue([{ ...TARGET, isActive: currentlyActive }]);
    const r = await archive(patch);
    expect(r.ok).toBe(true);
    for (const m of USER_WRITES) {
      expect(tx.user[m], `tx.user.${m} was called — the members were written, which is design B`).not.toHaveBeenCalled();
    }
  });
});

describe('ADMIN-6 — the archive refuses BY NAME, and writes nothing when it does', () => {
  it('⚠️ own_practice — the actor would lock themselves out', async () => {
    tx.user.findUnique.mockResolvedValue({ ...ACTOR, practiceId: 'prac_T' });
    const r = await archive();
    expect(r).toMatchObject({ ok: false, reason: 'own_practice' });
    expectNothingWritten();
  });

  it('⚠️ practice_has_super_admin — by the PRODUCTS array, which is what the /admin gate reads', async () => {
    tx.user.findMany.mockResolvedValue([...MEMBERS, MEMBER('u_sa', { products: ['TRANSCRIBE_MD', 'SUPER_ADMIN'] })]);
    const r = await archive();
    expect(r).toMatchObject({ ok: false, reason: 'practice_has_super_admin' });
    if (!r.ok) expect(r.detail).toContain('u_sa');
    expectNothingWritten();
  });

  it('⚠️ practice_has_super_admin — by the legacy ROLE too (fail-closed on either spelling)', async () => {
    tx.user.findMany.mockResolvedValue([...MEMBERS, MEMBER('u_role', { role: 'SUPER_ADMIN' })]);
    const r = await archive();
    expect(r).toMatchObject({ ok: false, reason: 'practice_has_super_admin' });
    expectNothingWritten();
  });

  it('⚠️ visits_in_flight — and the query covers BOTH tenancies and every in-flight status', async () => {
    tx.transcribeVisit.findMany.mockResolvedValue([{ id: 'v_1', status: 'DRAFTING' }]);
    const r = await archive();
    expect(r).toMatchObject({ ok: false, reason: 'visits_in_flight' });
    if (!r.ok) expect(r.detail).toContain('v_1(DRAFTING)');
    expectNothingWritten();
    const where = tx.transcribeVisit.findMany.mock.calls[0]![0].where as {
      status: { in: string[] };
      OR: Record<string, unknown>[];
    };
    expect(where.status.in.sort()).toEqual([...IN_FLIGHT_VISIT_STATUSES].sort());
    expect(where.OR).toEqual([{ practiceId: 'prac_T' }, { user: { practiceId: 'prac_T' } }]);
  });

  it('⚠️ actor_unknown — "is this their own practice?" with no actor is not "no"', async () => {
    tx.user.findUnique.mockResolvedValue(null);
    const r = await archive();
    expect(r).toMatchObject({ ok: false, reason: 'actor_unknown' });
    expectNothingWritten();
  });

  it('the in-flight set is DERIVED — every status except the three a visit rests in', () => {
    expect([...IN_FLIGHT_VISIT_STATUSES].sort()).toEqual(
      ['AUTOMATING', 'CRITIQUING', 'DRAFTING', 'EXTRACTING', 'POLISHING', 'QUEUED', 'TRANSCRIBING'].sort(),
    );
    for (const settled of ['READY', 'FAILED', 'SIGNED']) {
      expect(IN_FLIGHT_VISIT_STATUSES).not.toContain(settled);
    }
  });
});

describe('ADMIN-6 — a RESTORE is never refused for the archive\'s reasons (#310(b): never strand)', () => {
  it('⚠️ restore succeeds even with the actor inside, a platform admin inside, and a visit in flight', async () => {
    tx.$queryRaw.mockResolvedValue([{ ...TARGET, isActive: false }]);
    tx.user.findUnique.mockResolvedValue({ ...ACTOR, practiceId: 'prac_T' });
    tx.user.findMany.mockResolvedValue([...MEMBERS, MEMBER('u_sa', { products: ['SUPER_ADMIN'] })]);
    tx.transcribeVisit.findMany.mockResolvedValue([{ id: 'v_1', status: 'QUEUED' }]);
    const r = await archive({ isActive: true });
    expect(r.ok, `a restore was refused — an archive would then be a one-way door: ${JSON.stringify(r)}`).toBe(true);
    const row = tx.auditLog.create.mock.calls[0]![0].data;
    expect(row.action).toBe('PRACTICE_RESTORED');
    expect(row.metadata.changed).toEqual({ isActive: { from: false, to: true } });
  });
});

describe('ADMIN-6 — the audit row is part of the act', () => {
  it('⚠️ a failed audit insert FAILS the act — it is not swallowed the way logAudit swallows', async () => {
    tx.auditLog.create.mockRejectedValueOnce(new Error('insert into audit_logs failed'));
    await expect(archive()).rejects.toThrow('insert into audit_logs failed');
  });
});

describe('ADMIN-6 — the route maps the archive refusals to 409', () => {
  it.each([
    ['own_practice', () => tx.user.findUnique.mockResolvedValue({ ...ACTOR, practiceId: 'prac_T' })],
    ['visits_in_flight', () => tx.transcribeVisit.findMany.mockResolvedValue([{ id: 'v', status: 'QUEUED' }])],
  ])('⚠️ %s → 409, with the reason by name', async (reason, arrange) => {
    arrange();
    const res = await PATCH(
      new Request('http://x/api/admin/practices/prac_T', {
        method: 'PATCH',
        body: JSON.stringify({ isActive: false }),
      }) as never,
    );
    expect(res.status).toBe(409);
    expect(((await res.json()) as { error: string }).error).toBe(reason);
  });

  it('and a successful archive is 200', async () => {
    const res = await PATCH(
      new Request('http://x/api/admin/practices/prac_T', {
        method: 'PATCH',
        body: JSON.stringify({ isActive: false, reason: 'closing' }),
      }) as never,
    );
    expect(res.status).toBe(200);
  });
});

// ─── D2 — the per-request door ──────────────────────────────────────────────
const sessionRow = (practice: unknown) => ({
  id: 'us_1',
  createdAt: new Date(Date.now() - 60_000),
  expiresAt: new Date(Date.now() + 60 * 60 * 1000),
  user: { isActive: true, suspendedAt: null, softDeletedAt: null, forceLogoutAt: null, practice },
});

describe('ADMIN-6a D2 — validateSession ends every session of an archived practice', () => {
  it('POSITIVE CONTROL — a member of an ACTIVE practice keeps their session', async () => {
    h.userSession.findUnique.mockResolvedValue(sessionRow({ isActive: true }));
    expect(await validateSession('tok')).not.toBeNull();
  });

  it('⚠️ a member of an ARCHIVED practice gets null — the session ends on its next request', async () => {
    h.userSession.findUnique.mockResolvedValue(sessionRow({ isActive: false }));
    expect(await validateSession('tok'), 'an archived practice still admits its members').toBeNull();
  });

  it('⚠️ …and is admitted again once the practice is RESTORED, with nothing else changed', async () => {
    h.userSession.findUnique.mockResolvedValueOnce(sessionRow({ isActive: false }));
    expect(await validateSession('tok')).toBeNull();
    h.userSession.findUnique.mockResolvedValueOnce(sessionRow({ isActive: true }));
    expect(await validateSession('tok'), 'restore did not re-admit the member').not.toBeNull();
  });

  it('⚠️ FAIL-CLOSED — a session row whose practice did not load is refused, not admitted', async () => {
    h.userSession.findUnique.mockResolvedValue(sessionRow(undefined));
    expect(await validateSession('tok')).toBeNull();
  });

  it('⚠️ the door LOADS the practice through the predicate\'s own select', async () => {
    h.userSession.findUnique.mockResolvedValue(sessionRow({ isActive: true }));
    await validateSession('tok');
    const arg = h.userSession.findUnique.mock.calls[0]![0] as {
      include: { user: { select: { practice?: { select: Record<string, true> } } } };
    };
    expect(arg.include.user.select.practice).toEqual({ select: { isActive: true } });
  });
});
