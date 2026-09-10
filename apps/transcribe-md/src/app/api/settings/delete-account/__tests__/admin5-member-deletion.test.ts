// ============================================================================
// ADMIN-5 — SELF-SERVICE ACCOUNT DELETION IN A PRACTICE THAT IS NOT SOLO.
// ----------------------------------------------------------------------------
// Two claims the ADMIN-5 research made about `delete-account/route.ts`, DRIVEN
// rather than read:
//
//   (i)  the ACCOUNT_DELETED audit row was written BEFORE and OUTSIDE the
//        transaction, so a deletion the database refused (the last-owner
//        trigger, or the users->practices FK) left a row saying an account was
//        deleted when nothing was;
//   (ii) for a member of a multi-member practice it attempted a PRACTICE-WIDE
//        purge — every patient, task, medication, allergy and AI call of the
//        whole practice — and was saved only by `practice.delete` failing on
//        the users FK and rolling everything back. The migration header of
//        #210 names that FK "a coincidence that has been lucky".
//
// ⚠️ THESE ARMS WERE RUN AGAINST THE UNFIXED ROUTE FIRST, and every one of the
// four below that asserts the fix went RED there, with the observed facts in
// its message (the branch report carries the output). A test written only
// after the fix proves the fix passes; this is what proves the defect existed.
//
// The real-database half — the rolled-back transaction actually removing the
// audit row, and the FK actually refusing — is in `admin5-db-proofs.db.test.ts`.
// ============================================================================

import { beforeEach, describe, expect, it, vi } from 'vitest';

const { prisma, tx, logAudit, buildAuditRow, publishAuditRow, auth } = vi.hoisted(() => {
  const tx = {
    $queryRaw: vi.fn(async () => [{ level: 'read committed' }]),
    $executeRaw: vi.fn(async () => 1),
    auditLog: { create: vi.fn(async (_args: { data: Record<string, unknown> }) => ({})) },
    accountDeletion: { create: vi.fn(async () => ({})) },
    user: { delete: vi.fn(async () => ({})) },
    aiCall: { deleteMany: vi.fn(async () => ({ count: 0 })) },
    allergy: { deleteMany: vi.fn(async () => ({ count: 0 })) },
    medication: { deleteMany: vi.fn(async () => ({ count: 0 })) },
    task: { deleteMany: vi.fn(async () => ({ count: 0 })) },
    patient: { deleteMany: vi.fn(async () => ({ count: 0 })) },
    practice: { delete: vi.fn(async () => ({})) },
  };
  const prisma = {
    user: { findUnique: vi.fn(), count: vi.fn() },
    transcribeVisit: { count: vi.fn(async () => 3), findFirst: vi.fn(async () => ({ specialty: 'GI' })) },
    $transaction: vi.fn(async (fn: (t: typeof tx) => unknown) => fn(tx)),
  };
  return {
    prisma,
    tx,
    logAudit: vi.fn(async (_row: Record<string, unknown>) => undefined),
    buildAuditRow: vi.fn(async (input: Record<string, unknown>) => ({ ...input, practiceIdSnapshot: input.practiceId })),
    publishAuditRow: vi.fn(),
    auth: vi.fn(),
  };
});

vi.mock('@meddoc/db', () => ({ default: prisma }));
vi.mock('@/lib/audit', () => ({ logAudit, buildAuditRow, publishAuditRow }));
vi.mock('@/lib/nextauth', () => ({ auth }));
vi.mock('@/lib/rate-limit', () => ({ RATE_LIMITS: { SETTINGS: {} }, rateLimitOr429: () => null }));
vi.mock('@/lib/minio', () => ({ deleteAudioObjectsByPrefix: vi.fn(async () => ({ deleted: 0, failures: [] })) }));
vi.mock('@/lib/email', () => ({ sendAccountDeletedConfirmation: vi.fn() }));
vi.mock('@meddoc/ai', () => ({ redactPhi: (x: unknown) => String(x) }));
vi.mock('@meddoc/auth', () => ({ SessionUnverifiableError: class SessionUnverifiableError extends Error {} }));
vi.mock('bcryptjs', () => ({ default: { compare: vi.fn(async () => true) } }));

import { POST } from '../route';

const req = () =>
  ({ json: async () => ({ password: 'pw', confirmation: 'DELETE' }), url: 'https://x/api/settings/delete-account' }) as never;

const ME = { id: 'u-me', email: 'me@x.test', name: 'Dr Me', passwordHash: 'h', practiceId: 'p-1' };
/** What Postgres does to `practice.delete` while another user row references it. */
const FK_REFUSAL = Object.assign(new Error('Foreign key constraint violated on the constraint: `users_practiceId_fkey`'), {
  name: 'DriverAdapterError',
  cause: { originalCode: '23001', kind: 'postgres', code: '23001' },
});

const accountDeletedRows = () =>
  [...logAudit.mock.calls, ...buildAuditRow.mock.calls]
    .map((c) => c[0] as { action?: string })
    .filter((row) => row.action === 'ACCOUNT_DELETED');

beforeEach(() => {
  vi.clearAllMocks();
  auth.mockResolvedValue({ user: { id: 'u-me', practiceId: 'p-1' } });
  prisma.user.findUnique.mockResolvedValue(ME);
  prisma.$transaction.mockImplementation(async (fn: (t: typeof tx) => unknown) => fn(tx));
  tx.practice.delete.mockResolvedValue({});
  tx.user.delete.mockResolvedValue({});
});

describe('ADMIN-5 — delete-account in a practice with other members', () => {
  it('⚠️ CLAIM (ii) — a member of a multi-member practice is refused BY NAME, before ANY write', async () => {
    // Other members exist (live ones). What the database would do to the
    // unfixed route: the user row goes, the practice-wide purge runs, and
    // `practice.delete` is refused by the FK — so the whole thing rolls back.
    prisma.user.count.mockResolvedValue(2);
    tx.practice.delete.mockRejectedValue(FK_REFUSAL);

    const res = (await POST(req(), {} as never)) as Response;
    const body = (await res.json()) as { error?: string; code?: string };

    expect(
      tx.patient.deleteMany,
      `CLAIM (ii): a PRACTICE-WIDE purge was attempted — patient.deleteMany(${JSON.stringify(tx.patient.deleteMany.mock.calls)})`,
    ).not.toHaveBeenCalled();
    expect(prisma.$transaction, 'the destructive transaction was opened at all').not.toHaveBeenCalled();
    expect(res.status, `status ${res.status}: ${JSON.stringify(body)}`).toBe(409);
    expect(body.code).toBe('PRACTICE_HAS_MEMBERS');
    // the sentence names what to do instead, and does not promise a deletion
    expect(body.error).toMatch(/other members/i);
    expect(body.error).toMatch(/remove you|transfer ownership/i);
    expect(accountDeletedRows(), 'an ACCOUNT_DELETED row for a refused deletion').toEqual([]);
  });

  it('⚠️ the refusal counts OTHER rows of THIS practice — scoped, and excluding the user', async () => {
    prisma.user.count.mockResolvedValue(1);
    await POST(req(), {} as never);
    const where = prisma.user.count.mock.calls[0]?.[0]?.where;
    expect(where, 'the membership count is not scoped to the practice').toMatchObject({
      practiceId: 'p-1',
      id: { not: 'u-me' },
    });
    // ⚠️ AND IT COUNTS EVERY OTHER ROW, NOT ONLY LIVE ONES — EXACT KEYS, because
    // `toMatchObject` is partial and would pass a count narrowed to live
    // members. A removed ex-member's row still holds the users->practices FK,
    // so a live-only count lets the deletion through to a guaranteed rollback.
    expect(Object.keys(where ?? {}).sort(), 'the first count is narrowed — it must see every other row').toEqual([
      'id',
      'practiceId',
    ]);
  });

  it('⚠️ only FORMER members remain (removed/deactivated) — still refused by name, not a 500', async () => {
    // Their rows still reference the practice, so `practice.delete` cannot
    // succeed; the honest answer is a sentence, not "please try again".
    prisma.user.count.mockResolvedValueOnce(1).mockResolvedValueOnce(0);
    tx.practice.delete.mockRejectedValue(FK_REFUSAL);
    const res = (await POST(req(), {} as never)) as Response;
    const body = (await res.json()) as { code?: string; error?: string };
    expect(res.status, `status ${res.status}: ${JSON.stringify(body)}`).toBe(409);
    expect(body.code).toBe('PRACTICE_HAS_FORMER_MEMBERS');
    expect(prisma.$transaction).not.toHaveBeenCalled();
  });
});

describe('ADMIN-5 — the ACCOUNT_DELETED row rides the transaction', () => {
  it('⚠️ CLAIM (i) — a deletion the database REFUSES leaves no ACCOUNT_DELETED row behind', async () => {
    // A solo practice (nobody else), but the transaction fails anyway — the
    // last-owner trigger, an FK, a dead connection. The unfixed route had
    // already written ACCOUNT_DELETED outside the transaction by then.
    prisma.user.count.mockResolvedValue(0);
    tx.user.delete.mockRejectedValue(FK_REFUSAL);

    const res = (await POST(req(), {} as never)) as Response;
    expect(res.status).toBe(500);
    const outside = logAudit.mock.calls.map((c) => (c[0] as { action?: string }).action);
    expect(
      outside,
      'CLAIM (i): ACCOUNT_DELETED was written OUTSIDE the transaction, so it survives the rollback',
    ).not.toContain('ACCOUNT_DELETED');
    // ⚠️ AND IT WAS STILL WRITTEN — inside, where the rollback removes it. A
    // route that simply stopped auditing would pass the arm above.
    expect(tx.auditLog.create, 'the deletion is no longer audited at all').toHaveBeenCalledOnce();
    expect(tx.auditLog.create.mock.calls[0]?.[0]).toMatchObject({ data: { action: 'ACCOUNT_DELETED', targetId: 'u-me' } });
    expect(publishAuditRow, 'a rolled-back row was published to the live stream').not.toHaveBeenCalled();
  });

  it('⚠️ inside the transaction it is the FIRST write, while the user and practice rows still exist', async () => {
    // Written first so it carries valid references; the FKs then DETACH it
    // (SET NULL) as the user and practice go, and `practiceIdSnapshot` keeps
    // the tenant. That was S4c's reason for "audit first", and it still holds.
    prisma.user.count.mockResolvedValue(0);
    await POST(req(), {} as never);
    const auditAt = tx.auditLog.create.mock.invocationCallOrder[0]!;
    const lockAt = tx.$executeRaw.mock.invocationCallOrder[0]!;
    expect(auditAt, 'the audit row was written before the practice lock').toBeGreaterThan(lockAt);
    for (const later of [tx.accountDeletion.create, tx.user.delete, tx.patient.deleteMany, tx.practice.delete]) {
      expect(later.mock.invocationCallOrder[0], 'a destructive write preceded the audit row').toBeGreaterThan(auditAt);
    }
  });

  it('⚠️ FAIL-CLOSED, as S4c required — if the row cannot be BUILT, nothing is deleted', async () => {
    prisma.user.count.mockResolvedValue(0);
    buildAuditRow.mockRejectedValueOnce(new Error('audit unavailable'));
    const res = (await POST(req(), {} as never)) as Response;
    expect(res.status).toBe(500);
    expect(prisma.$transaction).not.toHaveBeenCalled();
  });

  it('a SOLO practice deletes exactly as before — every write, the practice last, published after commit', async () => {
    prisma.user.count.mockResolvedValue(0);
    const res = (await POST(req(), {} as never)) as Response;
    expect(res.status).toBe(200);
    expect(tx.user.delete).toHaveBeenCalledWith({ where: { id: 'u-me' } });
    for (const t of [tx.aiCall, tx.allergy, tx.medication, tx.task, tx.patient]) {
      expect(t.deleteMany).toHaveBeenCalledWith({ where: { practiceId: 'p-1' } });
    }
    expect(tx.practice.delete).toHaveBeenCalledWith({ where: { id: 'p-1' } });
    expect(publishAuditRow).toHaveBeenCalledOnce();
    expect(accountDeletedRows().length, 'the row was built exactly once').toBe(1);
  });
});
