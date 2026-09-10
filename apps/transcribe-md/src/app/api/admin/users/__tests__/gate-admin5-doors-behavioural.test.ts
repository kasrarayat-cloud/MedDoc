/**
 * GATE — THE TWO ADMIN DOORS ARE **DRIVEN**, NOT READ.
 * ----------------------------------------------------------------------------
 * ⚠️ RULING #251 RETIRES TEXT SCANNERS AS PROOFS OF BEHAVIOUR, AND ROUND FIVE
 * SHOWED WHY WITH THIS EXACT PAIR OF DOORS.
 *
 * `gate-admin5-last-owner-invariant` asserts the refusal is called by comparing
 * `src.indexOf('await wouldStrandPractice(')` against `src.indexOf('.update({')`.
 * That is true of the shipped code and it is blind to both ways of breaking it:
 *
 *   FG-1 — pass the WRONG USER. `wouldStrandPractice(ctx.session.user.id)` asks
 *          whether the ADMIN would strand their own practice, always answers no
 *          for the target, and the text arm still passes because the call is
 *          still there and still before the write. It survived the whole suite.
 *   FG-2 — DELETE THE REFUSAL BRANCH. Make the call, throw the verdict away,
 *          write anyway. Call present, order right, arm green, guard inert.
 *
 * Both are invisible to any arm that reads source and visible to any arm that
 * runs the door. So this file runs the door.
 *
 * ⚠️ THE DB TRIGGER STILL REFUSES BOTH IN PRODUCTION — which is why round five
 * filed them as INSTRUMENT and not CODE. What is lost is the SENTENCE: the admin
 * gets a raw 500 from Postgres instead of the message naming the remedy, from a
 * guard whose entire purpose is to say why.
 */
import { beforeEach, describe, expect, it, vi } from 'vitest';

const { prisma, wouldStrandPractice, logAudit, withPracticeLock } = vi.hoisted(() => ({
  prisma: {
    user: { findUnique: vi.fn(), update: vi.fn() },
    $transaction: vi.fn(),
    $queryRaw: vi.fn(async () => [{ level: 'read committed' }]),
  },
  wouldStrandPractice: vi.fn(),
  logAudit: vi.fn(),
  withPracticeLock: vi.fn(),
}));

// ⚠️ THE GATE IS BYPASSED, THE DOOR IS NOT. `adminApi` becomes a pass-through
// supplying a session, so these arms measure the handler's OWN logic. Its authz
// is proved by the admin-api gates; duplicating it here would be a second reader
// of that rule.
vi.mock('@/lib/admin-api-gate', () => ({
  adminApi:
    (_key: string, handler: (req: unknown, ctx: unknown) => unknown) =>
    (req: unknown) =>
      handler(req, { session: { user: { id: 'admin-1', email: 'a@x' } } }),
}));
vi.mock('@meddoc/db', () => ({ default: prisma }));
vi.mock('@/lib/audit', () => ({ logAudit }));
// ⚠️ ADMIN-5 — THE REAL MODULE, WITH TWO SPIES ON TOP. `classifyGuardError`
// must be the SHIPPED one: an arm that mocks the classifier measures the mock's
// opinion of the trigger's sentence, which is exactly the thing that drifts.
vi.mock('@/lib/last-owner-invariant', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/lib/last-owner-invariant')>()),
  wouldStrandPractice,
  withPracticeLock,
}));

import { LAST_OWNER_REFUSAL } from '@/lib/last-owner-invariant';

import { POST as SUSPEND } from '../[id]/suspend/route';
import { POST as SOFT_DELETE } from '../[id]/soft-delete/route';
import { POST as UNSUSPEND } from '../[id]/unsuspend/route';
import { POST as FORCE_LOGOUT } from '../[id]/force-logout/route';
import { POST as GRANT_ADMIN } from '../[id]/grant-admin/route';
import { POST as REVOKE_ADMIN } from '../[id]/revoke-admin/route';

const TARGET = 'target-9';
const TARGET_EMAIL = 't@x.com';

// ⚠️ THE TWO DOORS DO NOT TAKE THE SAME BODY, AND PRETENDING THEY DO IS HOW
// THIS FILE FIRST "PASSED". `soft-delete` requires a `confirmEmail` matching
// the target's address; driving it with `{}` returns 400 before it ever reaches
// the guard, so all four arms would have measured a rejected request rather
// than the door — three of them by asserting things that are trivially true of
// a 400. The body is per-door for that reason.
const DOORS = [
  ['suspend', SUSPEND, {}] as const,
  ['soft-delete', SOFT_DELETE, { confirmEmail: TARGET_EMAIL }] as const,
];

// ⚠️ RULING #289 — THE OTHER FOUR DOORS, DRIVEN FOR THE LOCK AND NOTHING ELSE.
// They are a SEPARATE list because they do not answer the strand question and
// must not be given its arms: none of them removes an owner seat, so
// `wouldStrandPractice` is not theirs to call and an arm demanding it would be
// asserting a requirement nobody made. What they DO share with the two above is
// the write, and therefore the lock.
//
// ⚠️ AND ONLY ONE OF THE FOUR CAN REACH THE TRIGGER'S LOCK TODAY — SAID HERE SO
// THE ARM IS NOT READ AS PROVING MORE THAN IT DOES. `unsuspend` clears
// `suspendedAt`, which makes a live member of a row that was not one, so
// `users_no_orphan_member` fails both exemptions and takes
// `pg_advisory_xact_lock`. `products` and `forceLogoutAt` are in NEITHER
// predicate, so the other three exit at an exemption and take no lock at all.
// They are locked because that safety is a property of a COLUMN LIST — #241a
// moved the member predicate once already — and the migration's own header says
// the door set is OPEN.
const LOCK_ONLY_DOORS = [
  ['unsuspend', UNSUSPEND, {}] as const,
  ['force-logout', FORCE_LOGOUT, {}] as const,
  ['grant-admin', GRANT_ADMIN, { confirmEmail: TARGET_EMAIL }] as const,
  ['revoke-admin', REVOKE_ADMIN, { confirmEmail: TARGET_EMAIL }] as const,
];

const req = (body: unknown) =>
  ({
    url: `https://x/api/admin/users/${TARGET}/act`,
    json: async () => body,
  }) as unknown as Request;

beforeEach(() => {
  vi.clearAllMocks();
  prisma.user.findUnique.mockResolvedValue({
    id: TARGET,
    email: TARGET_EMAIL,
    practiceId: 'prac-7',
  });
  prisma.user.update.mockResolvedValue({});
  withPracticeLock.mockImplementation(
    async (_tx: unknown, _p: string, write: () => Promise<unknown>) => write()
  );
  prisma.$transaction.mockImplementation(async (fn: (tx: unknown) => unknown) =>
    fn({ user: prisma.user, $queryRaw: prisma.$queryRaw })
  );
});

describe('#251 — the doors are driven, so the refusal cannot be faked', () => {
  it.each(DOORS)(
    '⚠️ %s asks about the TARGET, not the acting admin — kills FG-1',
    async (_name, POST, body) => {
      wouldStrandPractice.mockResolvedValue({ wouldStrand: false });
      await POST(req(body) as never);

      expect(wouldStrandPractice).toHaveBeenCalledTimes(1);
      // ⚠️ THE ARGUMENT IS THE WHOLE FINDING. Passing `ctx.session.user.id`
      // asks whether the ADMIN would strand their practice — a question whose
      // answer is almost always "no" — and every text arm stays green.
      expect(
        wouldStrandPractice.mock.calls[0][0],
        'the door asked about the wrong user, so the refusal can never fire for the target',
      ).toBe(TARGET);
      expect(wouldStrandPractice.mock.calls[0][0]).not.toBe('admin-1');
    }
  );

  it.each(DOORS)(
    '⚠️ %s ACTS on the verdict — a 409 and NO write — kills FG-2',
    async (_name, POST, body) => {
      wouldStrandPractice.mockResolvedValue({
        wouldStrand: true,
        reason: 'refusal-text',
        membersLeft: 3,
      });
      const res = (await POST(req(body) as never)) as Response;

      expect(res.status, 'the door wrote through a refusal').toBe(409);
      const payload = (await res.json()) as { reason?: string; membersLeft?: number };
      expect(payload.reason).toBe('LAST_OWNER');
      // ⚠️ AND THE COUNT REACHES THE CALLER. A refusal that cannot say how many
      // people are affected is not the sentence this guard exists to produce.
      expect(payload.membersLeft).toBe(3);

      expect(prisma.user.update, 'the row was written despite the refusal').not.toHaveBeenCalled();
      expect(prisma.$transaction, 'the door opened its write transaction anyway').not.toHaveBeenCalled();
      // ⚠️ ADMIN-5 — THIS ARM USED TO ASSERT *NO* AUDIT ROW, AND THAT WAS HALF
      // RIGHT. The half that stays: no `USER_SUSPENDED` / `USER_SOFT_DELETED`
      // for a write that did not happen — a false entry in an append-only
      // trail. The half that changed: the REFUSAL itself is now recorded,
      // because the one act this invariant exists to stop used to leave no
      // trace when it was stopped.
      expect(logAudit, 'the refusal was not recorded exactly once').toHaveBeenCalledTimes(1);
      expect(logAudit.mock.calls[0][0]).toMatchObject({
        action: 'PRACTICE_ADMIN_REFUSED',
        targetId: TARGET,
        practiceId: 'prac-7',
        metadata: { refusal: 'LAST_OWNER', source: 'precheck', membersLeft: 3 },
      });
      const actions = logAudit.mock.calls.map((c) => (c[0] as { action: string }).action);
      expect(actions, 'a success row for a refused write').not.toContain('USER_SUSPENDED');
      expect(actions, 'a success row for a refused write').not.toContain('USER_SOFT_DELETED');
    }
  );

  // ══════════════════════════════════════════════════════════════════════════
  // ADMIN-5 — THE TRIGGER'S REFUSAL, WHICH THE PRE-CHECK CANNOT SEE.
  //
  // The pre-check runs OUTSIDE the lock, so two admins suspending the last two
  // owners at once both pass it and `users_last_owner_guard` refuses the
  // second. Until ADMIN-5 that reached the admin as "Internal server error".
  //
  // ⚠️ THE ERROR BELOW IS THE MEASURED SHAPE, thrown BY THE WRITE ITSELF — not
  // a friendlier double handed to `$transaction`. Prisma 7 + adapter-pg against
  // a scratch pg16 surfaced the trigger's RAISE as a `DriverAdapterError` with
  // the SQLSTATE on `cause.originalCode` and no Prisma code at all.
  // ══════════════════════════════════════════════════════════════════════════
  const adapterError = (code: string, message: string) => ({
    name: 'DriverAdapterError',
    message,
    cause: { originalCode: code, originalMessage: message, kind: 'postgres', code, message },
  });
  const TRIGGER_REFUSAL = adapterError(
    '23514',
    'users_last_owner_guard: refusing to leave practice prac-7 with zero active OWNERs while 2 other member(s) remain. Transfer ownership first.',
  );

  it.each(DOORS)(
    '⚠️ ADMIN-5 — %s maps the TRIGGER\'s refusal to 409 LAST_OWNER, audited as the trigger\'s',
    async (_name, POST, body) => {
      wouldStrandPractice.mockResolvedValue({ wouldStrand: false });
      prisma.user.update.mockRejectedValueOnce(TRIGGER_REFUSAL);

      const res = (await POST(req(body) as never)) as Response;
      expect(res.status, 'a trigger refusal reached the admin as something other than a 409').toBe(409);
      const payload = (await res.json()) as { reason?: string; membersLeft?: number; error?: string };
      expect(payload.reason).toBe('LAST_OWNER');
      // the count the TRIGGER reported, and the pre-check's own sentence — not a new one
      expect(payload.membersLeft).toBe(2);
      expect(payload.error).toBe(LAST_OWNER_REFUSAL);

      expect(logAudit).toHaveBeenCalledTimes(1);
      expect(logAudit.mock.calls[0][0]).toMatchObject({
        action: 'PRACTICE_ADMIN_REFUSED',
        targetId: TARGET,
        practiceId: 'prac-7',
        metadata: { refusal: 'LAST_OWNER', source: 'trigger', membersLeft: 2 },
      });
    },
  );

  it.each(DOORS)(
    '⚠️ ADMIN-5 — %s does NOT dress up an error that is not a last-owner refusal',
    async (_name, POST, body) => {
      // A CHECK violation shares the trigger's SQLSTATE (measured). Mapping it to
      // "transfer ownership first" would name a remedy that fixes nothing, so it
      // must stay a thrown error — which `adminApi` turns into its generic 500.
      wouldStrandPractice.mockResolvedValue({ wouldStrand: false });
      const check = adapterError(
        '23514',
        'new row for relation "users" violates check constraint "users_active_member_has_practice_role"',
      );
      prisma.user.update.mockRejectedValueOnce(check);

      await expect(POST(req(body) as never)).rejects.toBe(check);
      expect(logAudit, 'an unrelated database error was recorded as a last-owner refusal').not.toHaveBeenCalled();
    },
  );

  it.each(DOORS)(
    'POSITIVE CONTROL — %s DOES write when nobody is stranded',
    async (_name, POST, body) => {
      // ⚠️ WITHOUT THIS, BOTH ARMS ABOVE PASS ON A DOOR THAT REFUSES
      // EVERYTHING. A guard that never writes satisfies "did not write on a
      // refusal" perfectly.
      wouldStrandPractice.mockResolvedValue({ wouldStrand: false });
      const res = (await POST(req(body) as never)) as Response;
      expect(res.status).toBe(200);
      expect(prisma.user.update, 'the door refuses even when it should write').toHaveBeenCalledTimes(1);
    }
  );

  it.each(DOORS)(
    '⚠️ %s takes the practice lock, on the TARGET practice — #268',
    async (_name, POST, body) => {
      wouldStrandPractice.mockResolvedValue({ wouldStrand: false });
      await POST(req(body) as never);
      expect(withPracticeLock).toHaveBeenCalledTimes(1);
      expect(
        withPracticeLock.mock.calls[0][1],
        'the lock was taken on the wrong practice, so it serializes nothing',
      ).toBe('prac-7');
    }
  );
});

describe('#289 — every writer is DRIVEN, not read', () => {
  it.each(LOCK_ONLY_DOORS)(
    '⚠️ %s takes the practice lock, on the TARGET practice',
    async (_name, POST, body) => {
      const res = (await POST(req(body) as never)) as Response;

      // POSITIVE CONTROL FIRST. Every assertion below is satisfied by a door
      // that returned 400 without doing anything, and three of these four parse
      // a body — driving them with the wrong one measures a rejected request.
      expect(res.status, 'the door refused the request, so nothing below is about the write').toBe(200);

      expect(withPracticeLock, 'the door writes outside the lock').toHaveBeenCalledTimes(1);
      expect(
        withPracticeLock.mock.calls[0][1],
        'the lock was taken on the wrong practice, so it serializes nothing',
      ).toBe('prac-7');
    },
  );

  // ⚠️ ROUND FINDING 4 — POINTED AT **EVERY** DOOR, NOT JUST THE LOCK-ONLY FOUR.
  //
  // This arm was `it.each(LOCK_ONLY_DOORS)`, so `suspend` and `soft-delete` —
  // the ONLY two doors that remove an owner seat, and therefore the only two
  // that can reach the trigger's `pg_advisory_xact_lock` — had a "takes the
  // lock" arm and NOTHING about ordering.
  //
  // MEASURED: splitting either door into two transactions, lock-first in
  // TEXTUAL order, left both gates green at 16/16 and 7/7. `pg_advisory_xact_lock`
  // is transaction-scoped, so it is released at the first commit and the row
  // write runs unserialized — the #268 deadlock fully restored, by an edit that
  // still reads correctly top to bottom.
  //
  // The arm itself was never broken: the identical mutation applied to
  // `unsuspend`, a LOCK_ONLY door, reddened it. It was simply not aimed at the
  // two doors the deadlock was measured on.
  it.each([...DOORS, ...LOCK_ONLY_DOORS])(
    '⚠️ %s writes INSIDE the lock, never beside it',
    async (_name, POST, body) => {
      // ⚠️ THE ARM ABOVE PASSES ON A DOOR THAT TAKES THE LOCK AND THEN WRITES
      // OUTSIDE IT — call present, practice right, ordering wrong. So this one
      // makes the lock a no-op and asserts the write does not happen: if the
      // write is inside, an unrun callback means an unwritten row.
      withPracticeLock.mockImplementation(async () => undefined);
      prisma.user.update.mockClear();

      await POST(req(body) as never);

      expect(
        prisma.user.update,
        'the row was written even though the lock never ran its callback — ' +
          'the write is beside the lock, not inside it',
      ).not.toHaveBeenCalled();
    },
  );
});
