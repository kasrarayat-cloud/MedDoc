/**
 * PROMO DOOR 3 OF 3 — THE REACTIVATION GRANT, DRIVEN.
 * ----------------------------------------------------------------------------
 * `gate-b7s3c-three-doors` reads this door's SOURCE: it calls the one writer,
 * it audits, it invents no key and no amount. What a source read cannot see is
 * the property that decides whether the door is safe at all:
 *
 *   ⚠️ THE GRANT RUNS AFTER THE LOCK TRANSACTION COMMITS, AND OUTSIDE IT.
 *
 * A collision (`already_granted`, the ORDINARY case — most reactivations are
 * into already-funded practices) aborts the Postgres transaction it runs in,
 * and COMMIT on an aborted transaction is silently a ROLLBACK. Inside the lock
 * transaction, that would un-reactivate the person and report success. So this
 * file runs the door with a transaction that RECORDS when it is open, and a
 * grant that records whether it was called inside it.
 */
import { beforeEach, describe, expect, it, vi } from 'vitest';

const { prisma, wouldOrphanMember, logAudit, withPracticeLock, grantPromoCredit, events } = vi.hoisted(
  () => ({
    prisma: {
      user: { findUnique: vi.fn(), update: vi.fn() },
      $transaction: vi.fn(),
    },
    wouldOrphanMember: vi.fn(),
    logAudit: vi.fn(),
    withPracticeLock: vi.fn(),
    grantPromoCredit: vi.fn(),
    events: [] as string[],
  }),
);

vi.mock('@/lib/admin-api-gate', () => ({
  adminApi:
    (_key: string, handler: (req: unknown, ctx: unknown) => unknown) =>
    (req: unknown) =>
      // The ACTING admin's session names a DIFFERENT practice, so an audit row
      // attributed to the session rather than the target is visible.
      handler(req, { session: { user: { id: 'admin-1', email: 'a@x', practiceId: 'admin-practice' } } }),
}));
vi.mock('@meddoc/db', () => ({ default: prisma }));
vi.mock('@/lib/audit', () => ({ logAudit }));
vi.mock('@/lib/last-owner-invariant', () => ({ wouldOrphanMember, withPracticeLock }));
vi.mock('@meddoc/ai/billing-grant', () => ({ grantPromoCredit }));

import { POST } from '../[id]/reactivate/route';

const TARGET = 'target-9';
const DEACTIVATED = {
  id: TARGET,
  email: 't@x.com',
  practiceId: 'prac-7',
  practiceRole: 'CLINICIAN',
  isActive: false,
  deactivatedAt: new Date('2026-09-01T00:00:00Z'),
  softDeletedAt: null,
};

const req = (body: unknown = {}) =>
  ({ url: `https://x/api/admin/users/${TARGET}/reactivate`, json: async () => body }) as unknown as Request;

let inTx = false;
let grantSawTx: boolean | null = null;

beforeEach(() => {
  vi.clearAllMocks();
  events.length = 0;
  inTx = false;
  grantSawTx = null;
  prisma.user.findUnique.mockResolvedValue({ ...DEACTIVATED });
  prisma.user.update.mockImplementation(async () => {
    events.push('write');
    return {};
  });
  withPracticeLock.mockImplementation(async (_tx: unknown, _p: string, write: () => Promise<unknown>) => write());
  prisma.$transaction.mockImplementation(async (fn: (tx: unknown) => unknown) => {
    inTx = true;
    events.push('tx:open');
    try {
      const out = await fn({ user: prisma.user });
      events.push('tx:commit');
      return out;
    } finally {
      inTx = false;
    }
  });
  wouldOrphanMember.mockResolvedValue({ wouldOrphan: false });
  grantPromoCredit.mockImplementation(async () => {
    grantSawTx = inTx;
    events.push('grant');
    return { granted: true, ledgerEntryId: 'le-1', amountMicroUsd: 10_000_000n, balanceAfter: 10_000_000n, seq: 1n };
  });
});

describe('promo door 3 — the grant is AFTER the commit and OUTSIDE the transaction', () => {
  it('⚠️ runs in the order open -> write -> commit -> grant', async () => {
    const res = (await POST(req() as never)) as Response;
    expect(res.status).toBe(200);
    expect(events, 'the grant ran before the reactivation committed').toEqual([
      'tx:open',
      'write',
      'tx:commit',
      'grant',
    ]);
  });

  it('⚠️ the grant is NOT called while the transaction is open', async () => {
    await POST(req() as never);
    expect(grantSawTx, 'grantPromoCredit ran inside the lock transaction').toBe(false);
  });

  it('⚠️ the grant takes NO transaction client — the default client owns its own statement', async () => {
    await POST(req() as never);
    expect(grantPromoCredit).toHaveBeenCalledTimes(1);
    expect(
      grantPromoCredit.mock.calls[0],
      'a second argument is a transaction client, and a collision would poison it',
    ).toEqual(['prac-7']);
  });

  it('⚠️ a refused write (the trigger) means NO grant and NO audit', async () => {
    prisma.$transaction.mockRejectedValueOnce(new Error('users_last_owner_guard: refusing'));
    await expect(POST(req() as never)).rejects.toThrow(/users_last_owner_guard/);
    expect(grantPromoCredit, 'a practice was funded for a reactivation that did not happen').not.toHaveBeenCalled();
    expect(logAudit).not.toHaveBeenCalled();
  });
});

describe('promo door 3 — the audit rows', () => {
  it('⚠️ PROMO_GRANT_CREDITED is attributed to the TARGET practice, door "reactivation"', async () => {
    await POST(req() as never);
    const promo = logAudit.mock.calls.map((c) => c[0]).find((a) => a.action === 'PROMO_GRANT_CREDITED');
    expect(promo, 'a grant with no audit row').toBeDefined();
    expect(promo.targetType).toBe('Practice');
    expect(promo.targetId).toBe('prac-7');
    expect(promo.practiceId, 'attributed to the acting admin, not the funded practice').toBe('prac-7');
    expect(promo.metadata.door).toBe('reactivation');
    expect(promo.metadata.reactivatedUserId).toBe(TARGET);
    expect(promo.metadata.amountMicroUsd).toBe('10000000');
  });

  it('`already_granted` writes NO grant audit row, and says so on the reactivation row', async () => {
    grantPromoCredit.mockResolvedValueOnce({ granted: false, reason: 'already_granted' });
    const res = (await POST(req() as never)) as Response;
    expect((await res.json()).promo).toBe('already_granted');
    const actions = logAudit.mock.calls.map((c) => c[0].action);
    expect(actions).not.toContain('PROMO_GRANT_CREDITED');
    const row = logAudit.mock.calls.map((c) => c[0]).find((a) => a.action === 'USER_CREATED');
    expect(row.metadata).toMatchObject({ action: 'reactivated', promo: 'already_granted' });
    expect(row.practiceId).toBe('prac-7');
  });

  it('⚠️ a grant FAILURE does not un-reactivate anyone — 200, reported, recorded', async () => {
    grantPromoCredit.mockRejectedValueOnce(new Error('connection reset'));
    const spy = vi.spyOn(console, 'error').mockImplementation(() => {});
    const res = (await POST(req() as never)) as Response;
    spy.mockRestore();
    expect(res.status).toBe(200);
    const payload = await res.json();
    expect(payload).toMatchObject({ ok: true, promo: 'failed' });
    expect(events).toContain('tx:commit');
    const row = logAudit.mock.calls.map((c) => c[0]).find((a) => a.action === 'USER_CREATED');
    expect(row.metadata.promo, 'the failure left no trace on the audit trail').toBe('failed');
  });
});

describe('the reactivation itself', () => {
  it('clears the deactivation and bumps forceLogoutAt in ONE write', async () => {
    await POST(req() as never);
    const data = prisma.user.update.mock.calls[0][0].data;
    expect(data).toMatchObject({ isActive: true, deactivatedAt: null, deactivatedBy: null });
    expect(
      data.forceLogoutAt,
      'a session from before the deactivation would come back to life with the account',
    ).toBeInstanceOf(Date);
  });

  it('⚠️ NO-DOWNGRADE — a real CLINICIAN assignment is NOT overwritten with OWNER', async () => {
    await POST(req() as never);
    expect(prisma.user.update.mock.calls[0][0].data).not.toHaveProperty('practiceRole');
  });

  it('⚠️ …and a row with a practice and NO role gets OWNER back (the T6 CHECK)', async () => {
    prisma.user.findUnique.mockResolvedValue({ ...DEACTIVATED, practiceRole: null });
    await POST(req() as never);
    expect(prisma.user.update.mock.calls[0][0].data.practiceRole).toBe('OWNER');
  });

  it('⚠️ the orphan refusal is asked about THIS write, and a refusal writes nothing and funds nothing', async () => {
    wouldOrphanMember.mockResolvedValueOnce({ wouldOrphan: true, reason: 'no owner', restorableOwners: 1 });
    const res = (await POST(req() as never)) as Response;
    expect(res.status).toBe(409);
    expect((await res.json()).reason).toBe('NO_ACTIVE_OWNER');
    expect(prisma.$transaction).not.toHaveBeenCalled();
    expect(grantPromoCredit).not.toHaveBeenCalled();
    expect(logAudit).not.toHaveBeenCalled();
    const asked = wouldOrphanMember.mock.calls[0][0];
    expect(asked).toMatchObject({ kind: 'update', userId: TARGET });
    expect(asked.patch).toMatchObject({ isActive: true, deactivatedAt: null });
  });

  it('refuses an account that is not deactivated — no write, no grant', async () => {
    prisma.user.findUnique.mockResolvedValue({ ...DEACTIVATED, isActive: true, deactivatedAt: null });
    const res = (await POST(req() as never)) as Response;
    expect(res.status).toBe(409);
    expect((await res.json()).reason).toBe('NOT_DEACTIVATED');
    expect(prisma.$transaction).not.toHaveBeenCalled();
    expect(grantPromoCredit).not.toHaveBeenCalled();
  });

  it('⚠️ refuses a SOFT-DELETED account — it cannot be restored, so it must not fund the practice', async () => {
    prisma.user.findUnique.mockResolvedValue({ ...DEACTIVATED, softDeletedAt: new Date() });
    const res = (await POST(req() as never)) as Response;
    expect(res.status).toBe(409);
    expect((await res.json()).reason).toBe('SOFT_DELETED');
    expect(grantPromoCredit).not.toHaveBeenCalled();
  });

  it('refuses a body with unknown keys (strict)', async () => {
    const res = (await POST(req({ practiceRole: 'OWNER' }) as never)) as Response;
    expect(res.status).toBe(400);
    expect(prisma.$transaction).not.toHaveBeenCalled();
  });

  it('self-reactivation is refused with 403', async () => {
    const r = { url: 'https://x/api/admin/users/admin-1/reactivate', json: async () => ({}) } as unknown as Request;
    const res = (await POST(r as never)) as Response;
    expect(res.status).toBe(403);
    expect(prisma.user.findUnique).not.toHaveBeenCalled();
  });
});
