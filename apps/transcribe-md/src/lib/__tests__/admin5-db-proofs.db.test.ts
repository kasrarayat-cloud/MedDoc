// @vitest-environment node
// ============================================================================
// ADMIN-5 — PROOFS AGAINST A REAL POSTGRES, THROUGH THE REAL DOORS.
// ----------------------------------------------------------------------------
// ⚠️ SKIPPED UNLESS `ADMIN5_PROOF_DATABASE_URL` IS SET, AND FAIL-CLOSED WHEN IT
// IS: the URL must name a qa/test/e2e/ci database (`@meddoc/db/guard`) or the
// suite throws before connecting. The unit job has no Postgres and leaves this
// unset, so in CI this file reports as skipped — it is an EVIDENCE HARNESS, run
// by hand against a scratch database carrying every migration:
//
//   ADMIN5_PROOF_DATABASE_URL=postgresql://…/meddoc_qa_test \
//     npx vitest run src/lib/__tests__/admin5-db-proofs.db.test.ts
//
// It never runs against production and it reaps every practice it creates.
//
// ── WHAT IT PROVES ─────────────────────────────────────────────────────────
// RULING #212: "the guard and the trigger must EACH refuse alone". On this
// branch the "guard" is the friendly pre-check (`wouldStrandPractice`) and the
// trigger is the ONLY enforcer (#210, #310(a)). The four worlds, driven
// through the real SUPER_ADMIN suspend route:
//
//                          sequential               concurrent (gated)
//   shipped                refused (pre-check)      one refused (TRIGGER)
//   pre-check deleted      refused (TRIGGER)        one refused (TRIGGER)
//   trigger disabled       refused (pre-check)      BOTH WRITE -> 0 owners
//   both gone              WRITES -> 0 owners       —
//
// The concurrent column's negative control is the point: under a race the
// pre-check does NOT refuse (both racers pass it — the overlap witness below
// shows both parked at the practice lock, which is AFTER the pre-check), so
// the trigger is what holds the invariant.
//
// ⚠️ THE OVERLAP WITNESS IS A STATE ASSERTION AT A BARRIER, NOT A SAMPLER
// (#252). A third connection holds the practice's advisory lock; the racers
// are launched; `pg_locks` must show TWO ungranted waiters on exactly that key
// pair, with the gate's grant as positive control, before the gate is
// released. If they never meet, the arm FAILS rather than certifying.
// ============================================================================

import pg from 'pg';
import bcrypt from 'bcryptjs';
import { afterAll, beforeAll, describe, expect, it, vi } from 'vitest';

import { checkNonProdDb, describeDbTarget } from '@meddoc/db/guard';

const PROOF_URL = process.env.ADMIN5_PROOF_DATABASE_URL;

// ⚠️ BEFORE ANY IMPORT OF `@meddoc/db`: the client reads DATABASE_URL when it
// is built. The routes are imported dynamically in `beforeAll` for the same
// reason, so a CI run with no URL never constructs a client at all.
const toggles = vi.hoisted(() => {
  if (process.env.ADMIN5_PROOF_DATABASE_URL) {
    process.env.DATABASE_URL = process.env.ADMIN5_PROOF_DATABASE_URL;
  }
  return {
    precheckDeleted: false,
    authSession: null as null | { user: { id: string; practiceId: string; email?: string } },
  };
});

// The pre-check, deletable at runtime — the "#212 delete the guard" world.
vi.mock('@/lib/last-owner-invariant', async (importOriginal) => {
  const real = await importOriginal<typeof import('@/lib/last-owner-invariant')>();
  return {
    ...real,
    wouldStrandPractice: async (id: string) =>
      toggles.precheckDeleted ? { wouldStrand: false as const } : real.wouldStrandPractice(id),
  };
});
// ⚠️ The ADMIN gate is bypassed, the DOOR is not — its authz is proved elsewhere.
vi.mock('@/lib/admin-api-gate', () => ({
  adminApi:
    (_key: string, handler: (req: unknown, ctx: unknown) => unknown) =>
    (req: unknown) =>
      handler(req, { session: { user: { id: 'a5db-superadmin', email: 'sa@x.test' } } }),
}));
const { getSession } = vi.hoisted(() => ({ getSession: vi.fn() }));
vi.mock('@/lib/auth', () => ({ getSession }));
vi.mock('@/lib/nextauth', () => ({ auth: vi.fn(async () => toggles.authSession) }));
vi.mock('next/cache', () => ({ revalidatePath: vi.fn() }));
vi.mock('@/lib/redis', () => ({
  getRedis: () => ({ publish: async () => 0 }),
  isRedisReady: () => false,
  ADMIN_AUDIT_STREAM_CHANNEL: 'a5db',
}));
vi.mock('@/lib/signup-invite', () => ({ hashInviteCode: (x: string) => x, normalizeInviteCode: (x: string) => x }));
vi.mock('@/lib/rate-limit', () => ({ RATE_LIMITS: { SETTINGS: {} }, rateLimitOr429: () => null }));
vi.mock('@/lib/minio', () => ({ deleteAudioObjectsByPrefix: vi.fn(async () => ({ deleted: 0, failures: [] })) }));
vi.mock('@/lib/email', () => ({ sendAccountDeletedConfirmation: vi.fn() }));
vi.mock('@meddoc/ai', () => ({ redactPhi: (x: unknown) => String(x) }));
vi.mock('@meddoc/auth', () => ({ SessionUnverifiableError: class SessionUnverifiableError extends Error {} }));

vi.setConfig({ testTimeout: 60_000, hookTimeout: 60_000 });

type Door = (req: unknown) => Promise<Response>;
type Action = (prev: null, fd: FormData) => Promise<{ ok: boolean; reason?: string; message?: string } | null>;

describe.skipIf(!PROOF_URL)('ADMIN-5 — real-database proofs (scratch Postgres only)', () => {
  let db: pg.Client;
  let SUSPEND: Door;
  let DELETE_ACCOUNT: (req: unknown, ctx: unknown) => Promise<Response>;
  let changeRole: Action;
  let removeMember: Action;
  let transfer: Action;
  let PW_HASH = '';
  const created: string[] = [];
  const startedAt = new Date();
  let seq = 0;

  const q = async <R = Record<string, unknown>>(sql: string, params: unknown[] = []) =>
    (await db.query(sql, params)).rows as R[];

  const form = (entries: Record<string, string>) => {
    const fd = new FormData();
    for (const [k, v] of Object.entries(entries)) fd.set(k, v);
    return fd;
  };
  const suspendReq = (id: string) =>
    ({ url: `https://x/api/admin/users/${id}/suspend`, json: async () => ({}) }) as unknown;

  /** A practice and its members, OWNERS FIRST (the orphan arm refuses a live
   *  non-owner into an ownerless practice). Ids are unique per call. */
  async function practice(members: [tag: string, role: 'OWNER' | 'CLINICIAN' | 'TECH'][]) {
    const id = `a5db_p${++seq}_${Date.now().toString(36)}`;
    await q(`INSERT INTO practices(id,name,slug,"updatedAt") VALUES ($1,$1,$1,now())`, [id]);
    created.push(id);
    const ids: Record<string, string> = {};
    for (const [tag, role] of members) {
      const uid = `${id}_${tag}`;
      await q(
        `INSERT INTO users(id,email,"passwordHash","updatedAt","practiceId","practiceRole","isActive")
         VALUES ($1,$2,$3,now(),$4,$5,true)`,
        [uid, `${uid}@x.test`, PW_HASH, id, role],
      );
      ids[tag] = uid;
    }
    return { id, ...ids } as { id: string } & Record<string, string>;
  }

  const activeOwners = async (p: string) =>
    Number((await q<{ n: string }>(`SELECT count(*) n FROM users u WHERE "practiceId"=$1 AND users_is_active_owner(u)`, [p]))[0]!.n);
  const liveUsers = async (p: string) =>
    Number((await q<{ n: string }>(`SELECT count(*) n FROM users u WHERE "practiceId"=$1 AND users_is_live_member(u)`, [p]))[0]!.n);
  const auditRows = async (targets: string[]) =>
    q<{ action: string; metadata: Record<string, unknown>; targetId: string; practiceId: string | null; practiceIdSnapshot: string | null }>(
      `SELECT action, metadata, "targetId", "practiceId", "practiceIdSnapshot" FROM audit_logs
        WHERE "targetId" = ANY($1) AND "timestamp" >= $2 ORDER BY "timestamp", id`,
      [targets, startedAt],
    );

  async function setTrigger(enabled: boolean) {
    await q(`ALTER TABLE users ${enabled ? 'ENABLE' : 'DISABLE'} TRIGGER users_last_owner_guard_after_write`);
    const [row] = await q<{ tgenabled: string }>(
      `SELECT tgenabled FROM pg_trigger WHERE tgname='users_last_owner_guard_after_write'`,
    );
    // POSITIVE CONTROL on the toggle itself: a DISABLE that did not take would
    // make every "trigger absent" cell below measure the shipped world.
    expect(row?.tgenabled, 'the trigger toggle did not take').toBe(enabled ? 'O' : 'D');
  }

  /** A third connection holding the practice's advisory lock — the barrier. */
  async function gate(practiceId: string) {
    const g = new pg.Client({ connectionString: PROOF_URL });
    await g.connect();
    await g.query('BEGIN');
    await g.query(`SELECT pg_advisory_xact_lock(hashtext('users_last_owner_guard'), hashtext($1))`, [practiceId]);
    return {
      release: async () => {
        await g.query('COMMIT');
        await g.end();
      },
    };
  }
  /** Two UNGRANTED waiters on exactly the guard's key pair, with the gate's grant held. */
  async function witness(practiceId: string, n = 2, timeoutMs = 15_000) {
    const deadline = Date.now() + timeoutMs;
    for (;;) {
      const [r] = await q<{ waiting: number; held: number }>(
        `SELECT count(*) FILTER (WHERE NOT granted)::int AS waiting, count(*) FILTER (WHERE granted)::int AS held
           FROM pg_locks
          WHERE locktype='advisory' AND objsubid=2
            AND classid::bigint = (hashtext('users_last_owner_guard')::bigint & 4294967295)
            AND objid::bigint   = (hashtext($1)::bigint & 4294967295)`,
        [practiceId],
      );
      if (r!.waiting >= n) {
        expect(r!.held, 'positive control: the gate itself does not hold the key the racers wait on').toBe(1);
        return r!;
      }
      if (Date.now() > deadline) {
        throw new Error(
          `OVERLAP WITNESS: ${r!.waiting} waiter(s) on the practice lock after ${timeoutMs}ms — the racers never met at the barrier; refusing to certify this arm`,
        );
      }
      await new Promise((res) => setTimeout(res, 25));
    }
  }

  beforeAll(async () => {
    const guard = checkNonProdDb(describeDbTarget(PROOF_URL!).database, describeDbTarget(PROOF_URL!).host);
    if (!guard.ok) throw new Error(`[admin5-db-proofs] FAIL-CLOSED: ${guard.reason}`);
    db = new pg.Client({ connectionString: PROOF_URL });
    await db.connect();
    // POSITIVE CONTROL: the thing under test is installed and armed.
    const trig = await q<{ tgenabled: string }>(
      `SELECT tgenabled FROM pg_trigger WHERE tgname='users_last_owner_guard_after_write'`,
    );
    expect(trig.map((t) => t.tgenabled), 'the last-owner trigger is not installed and enabled').toEqual(['O']);
    PW_HASH = await bcrypt.hash('a5db-pw', 4);
    SUSPEND = (await import('@/app/api/admin/users/[id]/suspend/route')).POST as unknown as Door;
    DELETE_ACCOUNT = (await import('@/app/api/settings/delete-account/route')).POST as unknown as typeof DELETE_ACCOUNT;
    const actions = await import('@/actions/practice-members');
    changeRole = actions.changeMemberRoleAction as unknown as Action;
    removeMember = actions.removeMemberAction as unknown as Action;
    transfer = actions.transferOwnershipAction as unknown as Action;
  });

  afterAll(async () => {
    if (!db) return;
    await q(`ALTER TABLE users ENABLE TRIGGER users_last_owner_guard_after_write`);
    await q(`DROP TRIGGER IF EXISTS a5db_fail_practice_delete ON practices`);
    await q(`DROP FUNCTION IF EXISTS a5db_fail_practice_delete()`);
    for (const p of created) {
      await q(`DELETE FROM users u WHERE u."practiceId"=$1 AND NOT users_is_active_owner(u)`, [p]);
      await q(`DELETE FROM users WHERE "practiceId"=$1`, [p]);
      await q(`DELETE FROM practices WHERE id=$1`, [p]);
    }
    const [left] = await q<{ n: string }>(
      `SELECT (SELECT count(*) FROM users WHERE "practiceId" = ANY($1)) + (SELECT count(*) FROM practices WHERE id = ANY($1)) AS n`,
      [created],
    );
    const [armed] = await q<{ tgenabled: string }>(
      `SELECT tgenabled FROM pg_trigger WHERE tgname='users_last_owner_guard_after_write'`,
    );
    await db.end();
    // ⚠️ A REAP THAT REPORTS NOTHING IS A CLAIM; the count is the evidence.
    expect(Number(left!.n), 'fixture rows survived the reap').toBe(0);
    expect(armed!.tgenabled, 'the trigger was left DISABLED').toBe('O');
  });

  // ══════════════════════════════════════════════════════════════════════════
  // #212 — SEQUENTIAL. The last active owner of a practice with a live member.
  // ══════════════════════════════════════════════════════════════════════════
  describe('#212 sequential — each refuses alone, and with both gone nothing does', () => {
    async function suspendLastOwner(opts: { trigger: boolean; precheck: boolean }) {
      const p = await practice([['a', 'OWNER'], ['c', 'CLINICIAN']]);
      toggles.precheckDeleted = !opts.precheck;
      await setTrigger(opts.trigger);
      try {
        const res = await SUSPEND(suspendReq(p.a!));
        const body = (await res.json()) as { reason?: string; membersLeft?: number };
        return { p, status: res.status, body, owners: await activeOwners(p.id), audit: await auditRows([p.a!]) };
      } finally {
        toggles.precheckDeleted = false;
        await setTrigger(true);
      }
    }

    it('shipped — the PRE-CHECK refuses (409), nothing is written', async () => {
      const r = await suspendLastOwner({ trigger: true, precheck: true });
      expect(r.status).toBe(409);
      expect(r.body.reason).toBe('LAST_OWNER');
      expect(r.owners).toBe(1);
      expect(r.audit.map((a) => [a.action, a.metadata.source])).toEqual([['PRACTICE_ADMIN_REFUSED', 'precheck']]);
    });

    it('⚠️ #212(a) — pre-check DELETED: the TRIGGER refuses alone, and the real error maps to 409', async () => {
      const r = await suspendLastOwner({ trigger: true, precheck: false });
      expect(r.status, 'the trigger refusal escaped as something other than a 409').toBe(409);
      expect(r.body).toMatchObject({ reason: 'LAST_OWNER', membersLeft: 1 });
      expect(r.owners, 'the last owner was suspended').toBe(1);
      expect(r.audit.map((a) => [a.action, a.metadata.source])).toEqual([['PRACTICE_ADMIN_REFUSED', 'trigger']]);
    });

    it('⚠️ #212(b) — trigger ABSENT: the PRE-CHECK refuses alone (sequential)', async () => {
      const r = await suspendLastOwner({ trigger: false, precheck: true });
      expect(r.status).toBe(409);
      expect(r.owners).toBe(1);
      expect(r.audit.map((a) => a.metadata.source)).toEqual(['precheck']);
    });

    it('CONTROL — both gone: NOTHING refuses, and the practice is left with no owner', async () => {
      // Without this cell the three above are consistent with a third enforcer
      // nobody knows about. With it, each refusal above is attributable.
      const r = await suspendLastOwner({ trigger: false, precheck: false });
      expect(r.status).toBe(200);
      expect(r.owners, 'something else refused — the attribution above is unproven').toBe(0);
    });
  });

  // ══════════════════════════════════════════════════════════════════════════
  // #212 — CONCURRENT. Two admins suspend the last two owners at once.
  // ══════════════════════════════════════════════════════════════════════════
  describe('#212 concurrent — gated at the practice lock, witnessed by pg_locks', () => {
    async function race(opts: { trigger: boolean; precheck: boolean }) {
      const p = await practice([['a', 'OWNER'], ['b', 'OWNER'], ['c', 'CLINICIAN']]);
      toggles.precheckDeleted = !opts.precheck;
      await setTrigger(opts.trigger);
      const g = await gate(p.id);
      try {
        const ra = SUSPEND(suspendReq(p.a!));
        const rb = SUSPEND(suspendReq(p.b!));
        // ⚠️ BOTH ARE PARKED AT THE LOCK — which is AFTER the pre-check. So both
        // pre-checks have already run and said "another owner remains".
        const seen = await witness(p.id, 2);
        await g.release();
        const statuses = (await Promise.all([ra, rb])).map((r) => r.status).sort();
        return { p, seen, statuses, owners: await activeOwners(p.id), audit: await auditRows([p.a!, p.b!]) };
      } finally {
        toggles.precheckDeleted = false;
        await setTrigger(true);
      }
    }

    it('⚠️ #212(a) — pre-check DELETED: exactly one refused, BY THE TRIGGER, one owner left', async () => {
      const r = await race({ trigger: true, precheck: false });
      expect(r.seen.waiting).toBe(2);
      expect(r.statuses).toEqual([200, 409]);
      expect(r.owners).toBe(1);
      expect(r.audit.filter((a) => a.action === 'PRACTICE_ADMIN_REFUSED').map((a) => a.metadata.source)).toEqual(['trigger']);
    });

    it('shipped — the pre-check CANNOT see the race; the trigger refuses the second', async () => {
      const r = await race({ trigger: true, precheck: true });
      expect(r.seen.waiting).toBe(2);
      expect(r.statuses).toEqual([200, 409]);
      expect(r.owners).toBe(1);
      expect(r.audit.filter((a) => a.action === 'PRACTICE_ADMIN_REFUSED').map((a) => a.metadata.source)).toEqual(['trigger']);
    });

    it('⚠️ #212(c) NEGATIVE CONTROL — trigger ABSENT, pre-check present: BOTH write, ZERO owners', async () => {
      // The pre-check refuses the sequential case alone (above) and CANNOT
      // refuse this one: both racers passed it before either wrote. This cell is
      // what makes "the trigger holds the concurrent case" a measurement.
      const r = await race({ trigger: false, precheck: true });
      expect(r.seen.waiting).toBe(2);
      expect(r.statuses, 'the pre-check refused a racer — then this is not the race').toEqual([200, 200]);
      expect(r.owners).toBe(0);
    });
  });

  // ══════════════════════════════════════════════════════════════════════════
  // ADMIN-5 / 5a — THE PRACTICE-OWNER DOORS ON REAL ROWS.
  // ══════════════════════════════════════════════════════════════════════════
  describe('ADMIN-5 panel doors', () => {
    const as = (userId: string, practiceId: string) => ({ user: { id: userId, practiceId } });

    it('⚠️ remove ∥ remove, TWO owners and nobody else — the actor re-read keeps one owner', async () => {
      // The #306-class case: the trigger ALLOWS the second removal (exemption 2 —
      // the first victim is inactive with a NULL role, neither member nor
      // rescuer), so only the actor re-read under the lock stands between this
      // practice and zero live users.
      const p = await practice([['a', 'OWNER'], ['b', 'OWNER']]);
      toggles.authSession = { user: { id: p.a!, practiceId: p.id } };
      getSession.mockReset();
      getSession.mockResolvedValueOnce(as(p.a!, p.id)).mockResolvedValueOnce(as(p.b!, p.id));
      const g = await gate(p.id);
      const ra = removeMember(null, form({ userId: p.b! }));
      const rb = removeMember(null, form({ userId: p.a! }));
      await witness(p.id, 2);
      await g.release();
      const results = await Promise.all([ra, rb]);
      const reasons = results.map((r) => (r?.ok ? 'ok' : r?.reason)).sort();
      expect(reasons).toEqual(['ROLE_MAY_NOT_ADMINISTER', 'ok']);
      expect(await liveUsers(p.id), 'the practice was emptied').toBe(1);
      expect(await activeOwners(p.id)).toBe(1);
    });

    it('demote ∥ demote, two owners and a clinician — one wins, the other is refused, one owner left', async () => {
      const p = await practice([['a', 'OWNER'], ['b', 'OWNER'], ['c', 'CLINICIAN']]);
      toggles.authSession = { user: { id: p.a!, practiceId: p.id } };
      getSession.mockReset();
      getSession.mockResolvedValueOnce(as(p.a!, p.id)).mockResolvedValueOnce(as(p.b!, p.id));
      const g = await gate(p.id);
      const ra = changeRole(null, form({ userId: p.b!, role: 'CLINICIAN' }));
      const rb = changeRole(null, form({ userId: p.a!, role: 'CLINICIAN' }));
      await witness(p.id, 2);
      await g.release();
      const reasons = (await Promise.all([ra, rb])).map((r) => (r?.ok ? 'ok' : r?.reason)).sort();
      expect(reasons).toEqual(['ROLE_MAY_NOT_ADMINISTER', 'ok']);
      expect(await activeOwners(p.id)).toBe(1);
    });

    it('removal writes the deactivation columns on the real row, keeps the row, and records the role held', async () => {
      const p = await practice([['a', 'OWNER'], ['c', 'CLINICIAN']]);
      toggles.authSession = { user: { id: p.a!, practiceId: p.id } };
      getSession.mockReset();
      getSession.mockResolvedValue(as(p.a!, p.id));
      const res = await removeMember(null, form({ userId: p.c! }));
      expect(res?.ok).toBe(true);
      const [row] = await q<{
        isActive: boolean; deactivatedAt: Date | null; deactivatedBy: string | null;
        practiceRole: string | null; forceLogoutAt: Date | null; practiceId: string;
      }>(`SELECT "isActive","deactivatedAt","deactivatedBy","practiceRole","forceLogoutAt","practiceId" FROM users WHERE id=$1`, [p.c!]);
      expect(row, 'the removed member\'s row was DELETED').toBeTruthy();
      expect(row).toMatchObject({ isActive: false, deactivatedBy: p.a!, practiceRole: null, practiceId: p.id });
      expect(row!.deactivatedAt).toBeInstanceOf(Date);
      expect(row!.forceLogoutAt).toBeInstanceOf(Date);
      const audit = await auditRows([p.c!]);
      expect(audit.map((a) => [a.action, a.metadata.removedRole])).toEqual([['PRACTICE_MEMBER_REMOVED', 'CLINICIAN']]);
    });

    it('⚠️ ADMIN-5a — a SOLE owner hands the practice to a clinician and LEAVES, in one step', async () => {
      const p = await practice([['a', 'OWNER'], ['c', 'CLINICIAN']]);
      toggles.authSession = { user: { id: p.a!, practiceId: p.id } };
      getSession.mockReset();
      getSession.mockResolvedValue(as(p.a!, p.id));
      const res = await transfer(null, form({ userId: p.c!, then: 'LEAVE' }));
      expect(res, JSON.stringify(res)).toMatchObject({ ok: true });
      const rows = await q<{ id: string; practiceRole: string | null; isActive: boolean; owner: boolean }>(
        `SELECT id, "practiceRole", "isActive", users_is_active_owner(u) AS owner FROM users u WHERE "practiceId"=$1 ORDER BY id`,
        [p.id],
      );
      expect(rows).toEqual([
        { id: p.a!, practiceRole: null, isActive: false, owner: false },
        { id: p.c!, practiceRole: 'OWNER', isActive: true, owner: true },
      ]);
      const audit = await auditRows([p.a!, p.c!]);
      expect(audit.map((a) => [a.action, a.targetId])).toEqual([
        ['PRACTICE_ROLE_CHANGED', p.c!],
        ['PRACTICE_MEMBER_REMOVED', p.a!],
      ]);
      expect(audit[0]!.metadata.transferId).toBe(audit[1]!.metadata.transferId);
    });

    it('ADMIN-5a — a SUSPENDED member cannot be handed the practice; nothing changes', async () => {
      const p = await practice([['a', 'OWNER'], ['c', 'CLINICIAN']]);
      await q(`UPDATE users SET "suspendedAt"=now() WHERE id=$1`, [p.c!]);
      getSession.mockReset();
      getSession.mockResolvedValue(as(p.a!, p.id));
      const res = await transfer(null, form({ userId: p.c!, then: 'LEAVE' }));
      expect(res?.reason).toBe('TRANSFER_TARGET_INVALID');
      expect(await activeOwners(p.id)).toBe(1);
      const [a] = await q<{ owner: boolean }>(`SELECT users_is_active_owner(u) owner FROM users u WHERE id=$1`, [p.a!]);
      expect(a!.owner).toBe(true);
    });
  });

  // ══════════════════════════════════════════════════════════════════════════
  // DELETE-ACCOUNT — the report's two claims, on a real database.
  // ══════════════════════════════════════════════════════════════════════════
  describe('delete-account', () => {
    const del = async (userId: string, practiceId: string) => {
      toggles.authSession = { user: { id: userId, practiceId } };
      const req = { url: 'https://x/api/settings/delete-account', json: async () => ({ password: 'a5db-pw', confirmation: 'DELETE' }) };
      const res = await DELETE_ACCOUNT(req, {});
      return { status: res.status, body: (await res.json()) as { code?: string; error?: string } };
    };
    const accountDeleted = async (userId: string) =>
      (await auditRows([userId])).filter((a) => a.action === 'ACCOUNT_DELETED');

    it('⚠️ a CLINICIAN in a two-member practice is refused by name; no ACCOUNT_DELETED row; nothing moves', async () => {
      const p = await practice([['a', 'OWNER'], ['c', 'CLINICIAN']]);
      const r = await del(p.c!, p.id);
      const rows = await accountDeleted(p.c!);
      expect(
        { status: r.status, code: r.body.code, accountDeletedRows: rows.length },
        'observed on the real database',
      ).toEqual({ status: 409, code: 'PRACTICE_HAS_MEMBERS', accountDeletedRows: 0 });
      expect(await liveUsers(p.id)).toBe(2);
    });

    it('⚠️ a deletion the database REFUSES mid-transaction leaves NO ACCOUNT_DELETED row (the rollback takes it)', async () => {
      // Fault injected in the scratch database: a trigger that refuses THIS
      // practice's delete, standing in for any failure after the audit write.
      const p = await practice([['o', 'OWNER']]);
      await q(`CREATE OR REPLACE FUNCTION a5db_fail_practice_delete() RETURNS trigger AS $f$
               BEGIN RAISE EXCEPTION 'a5db injected failure'; END $f$ LANGUAGE plpgsql`);
      await q(`CREATE TRIGGER a5db_fail_practice_delete BEFORE DELETE ON practices
               FOR EACH ROW WHEN (OLD.id = '${p.id}') EXECUTE FUNCTION a5db_fail_practice_delete()`);
      try {
        const r = await del(p.o!, p.id);
        const rows = await accountDeleted(p.o!);
        expect(
          { status: r.status, accountDeletedRows: rows.length },
          'observed on the real database',
        ).toEqual({ status: 500, accountDeletedRows: 0 });
        const [still] = await q<{ n: string }>(`SELECT count(*) n FROM users WHERE id=$1`, [p.o!]);
        expect(Number(still!.n), 'the user was deleted though the transaction failed').toBe(1);
      } finally {
        await q(`DROP TRIGGER IF EXISTS a5db_fail_practice_delete ON practices`);
      }
    });

    it('⚠️ only a REMOVED ex-member remains — refused by name (not a 500), and nothing is deleted', async () => {
      // ADMIN-5 makes this reachable in-app: an owner removes their only
      // clinician (deactivated, row kept), then deletes their own account. The
      // removed row still holds the users->practices FK, so the purge cannot
      // succeed; the honest answer is a sentence.
      const p = await practice([['o', 'OWNER'], ['c', 'CLINICIAN']]);
      toggles.authSession = { user: { id: p.o!, practiceId: p.id } };
      getSession.mockReset();
      getSession.mockResolvedValue({ user: { id: p.o!, practiceId: p.id } });
      expect((await removeMember(null, form({ userId: p.c! })))?.ok, 'fixture: the removal did not happen').toBe(true);
      const r = await del(p.o!, p.id);
      expect({ status: r.status, code: r.body.code }).toEqual({ status: 409, code: 'PRACTICE_HAS_FORMER_MEMBERS' });
      const [still] = await q<{ n: string }>(`SELECT count(*) n FROM users WHERE "practiceId"=$1`, [p.id]);
      expect(Number(still!.n)).toBe(2);
      expect(await accountDeleted(p.o!)).toHaveLength(0);
    });

    it('a SOLO practice deletes as before — user and practice gone, ONE row, tenant kept on the snapshot', async () => {
      const p = await practice([['o', 'OWNER']]);
      const r = await del(p.o!, p.id);
      expect(r.status).toBe(200);
      const [gone] = await q<{ u: string; pr: string }>(
        `SELECT (SELECT count(*) FROM users WHERE id=$1) u, (SELECT count(*) FROM practices WHERE id=$2) pr`,
        [p.o!, p.id],
      );
      expect([Number(gone!.u), Number(gone!.pr)]).toEqual([0, 0]);
      const rows = await accountDeleted(p.o!);
      expect(rows).toHaveLength(1);
      // detached by the FK as the practice went, kept by the snapshot
      expect(rows[0]).toMatchObject({ practiceId: null, practiceIdSnapshot: p.id });
    });
  });
});
