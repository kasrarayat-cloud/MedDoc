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

const {
  prisma,
  wouldStrandPractice,
  wouldOrphanMember,
  logAudit,
  withPracticeLock,
  grantPromoCredit,
  createAuthToken,
  sendPasswordResetEmail,
} = vi.hoisted(() => ({
  prisma: {
    user: { findUnique: vi.fn(), update: vi.fn(), create: vi.fn() },
    practice: { findUnique: vi.fn() },
    $transaction: vi.fn(),
    $queryRaw: vi.fn(async () => [{ level: 'read committed' }]),
  },
  wouldStrandPractice: vi.fn(),
  wouldOrphanMember: vi.fn(),
  logAudit: vi.fn(),
  withPracticeLock: vi.fn(),
  grantPromoCredit: vi.fn(),
  createAuthToken: vi.fn(),
  sendPasswordResetEmail: vi.fn(),
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
vi.mock('@/lib/last-owner-invariant', () => ({
  wouldStrandPractice,
  wouldOrphanMember,
  withPracticeLock,
  LAST_OWNER_REFUSAL: 'refusal-text',
}));
// The console port's doors reach these; stubbed so the arms measure the door.
vi.mock('@meddoc/ai/billing-grant', () => ({ grantPromoCredit }));
vi.mock('@/lib/auth-tokens', () => ({ createAuthToken }));
vi.mock('@/lib/email', () => ({ sendPasswordResetEmail }));
vi.mock('@/lib/email-enabled', () => ({ isEmailDeliveryEnabled: () => false }));
vi.mock('@/lib/email-auto-confirm', () => ({ isAutoConfirmDomain: () => false }));
vi.mock('bcryptjs', () => ({ default: { hash: vi.fn(async () => 'hash') } }));

import { POST as SUSPEND } from '../[id]/suspend/route';
import { POST as SOFT_DELETE } from '../[id]/soft-delete/route';
import { POST as UNSUSPEND } from '../[id]/unsuspend/route';
import { POST as FORCE_LOGOUT } from '../[id]/force-logout/route';
import { POST as GRANT_ADMIN } from '../[id]/grant-admin/route';
import { POST as REVOKE_ADMIN } from '../[id]/revoke-admin/route';
// The console port (#310 step 3). ⚠️ `DOORS` AND `LOCK_ONLY_DOORS` ARE LISTED
// BY IMPORT, so a door added to the tree is NOT exercised here until it is
// added below — which is why every ported door is added in the same change.
import { POST as DEACTIVATE } from '../[id]/deactivate/route';
import { POST as REACTIVATE } from '../[id]/reactivate/route';
import { POST as PROFILE } from '../[id]/profile/route';
import { POST as CREATE } from '../route';

const TARGET = 'target-9';
const TARGET_EMAIL = 't@x.com';

// ⚠️ THE TWO DOORS DO NOT TAKE THE SAME BODY, AND PRETENDING THEY DO IS HOW
// THIS FILE FIRST "PASSED". `soft-delete` requires a `confirmEmail` matching
// the target's address; driving it with `{}` returns 400 before it ever reaches
// the guard, so all four arms would have measured a rejected request rather
// than the door — three of them by asserting things that are trivially true of
// a 400. The body is per-door for that reason.
// The row every door reads unless its own setup says otherwise: an ACTIVE
// OWNER of `prac-7`. Carries the columns the ported doors read, so their no-op
// refusals see a realistic row rather than `undefined`.
const BASE_ROW = {
  id: TARGET,
  email: TARGET_EMAIL,
  practiceId: 'prac-7',
  practiceRole: 'OWNER',
  role: 'DOCTOR',
  name: 'Old Name',
  isActive: true,
  deactivatedAt: null,
  suspendedAt: null,
  softDeletedAt: null,
};

/** Per-door fixture tweak, run after `beforeEach`. */
type Setup = () => void;
const noSetup: Setup = () => {};

const DOORS = [
  ['suspend', SUSPEND, {}, noSetup] as const,
  ['soft-delete', SOFT_DELETE, { confirmEmail: TARGET_EMAIL }, noSetup] as const,
  // Deactivation removes an owner seat exactly as suspension does, so it gets
  // the strand arms as well as the lock arms.
  ['deactivate', DEACTIVATE, { confirmEmail: TARGET_EMAIL }, noSetup] as const,
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
  ['unsuspend', UNSUSPEND, {}, noSetup] as const,
  ['force-logout', FORCE_LOGOUT, {}, noSetup] as const,
  ['grant-admin', GRANT_ADMIN, { confirmEmail: TARGET_EMAIL }, noSetup] as const,
  ['revoke-admin', REVOKE_ADMIN, { confirmEmail: TARGET_EMAIL }, noSetup] as const,
  // ⚠️ THE CONSOLE PORT'S ADDING DOORS. None removes an owner seat, so none
  // answers the strand question; each makes or edits a `users` row, so each
  // must lock. Reactivate and create ADD a live member — the orphan arm's
  // locking path — which is the half of the #268 deadlock they could complete.
  [
    'reactivate',
    REACTIVATE,
    {},
    () => prisma.user.findUnique.mockResolvedValue({ ...BASE_ROW, isActive: false, deactivatedAt: new Date() }),
  ] as const,
  ['profile', PROFILE, { name: 'New Name' }, noSetup] as const,
  [
    'create',
    CREATE,
    { email: 'new@x.com', name: 'New Person', practiceId: 'prac-7', practiceRole: 'CLINICIAN' },
    () => {
      // no account has this email; the practice exists
      prisma.user.findUnique.mockResolvedValue(null);
      prisma.practice.findUnique.mockResolvedValue({ id: 'prac-7', name: 'Practice Seven' });
    },
  ] as const,
];

const req = (body: unknown) =>
  ({
    url: `https://x/api/admin/users/${TARGET}/act`,
    json: async () => body,
  }) as unknown as Request;

beforeEach(() => {
  vi.clearAllMocks();
  prisma.user.findUnique.mockResolvedValue({ ...BASE_ROW });
  prisma.user.update.mockResolvedValue({});
  prisma.user.create.mockResolvedValue({ id: 'new-1' });
  wouldOrphanMember.mockResolvedValue({ wouldOrphan: false });
  grantPromoCredit.mockResolvedValue({ granted: false, reason: 'already_granted' });
  createAuthToken.mockResolvedValue({ token: 'tok', id: 'tok-row' });
  sendPasswordResetEmail.mockResolvedValue({ id: 'mail-1' });
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
    async (_name, POST, body, setup) => {
      setup();
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
    async (_name, POST, body, setup) => {
      setup();
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
      expect(logAudit, 'an audit row for a write that was refused').not.toHaveBeenCalled();
    }
  );

  it.each(DOORS)(
    'POSITIVE CONTROL — %s DOES write when nobody is stranded',
    async (_name, POST, body, setup) => {
      setup();
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
    async (_name, POST, body, setup) => {
      setup();
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
    async (_name, POST, body, setup) => {
      setup();
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
    async (_name, POST, body, setup) => {
      setup();
      // ⚠️ THE ARM ABOVE PASSES ON A DOOR THAT TAKES THE LOCK AND THEN WRITES
      // OUTSIDE IT — call present, practice right, ordering wrong. So this one
      // makes the lock a no-op and asserts the write does not happen: if the
      // write is inside, an unrun callback means an unwritten row.
      withPracticeLock.mockImplementation(async () => undefined);
      prisma.user.update.mockClear();
      prisma.user.create.mockClear();

      await POST(req(body) as never).catch(() => undefined);

      // ⚠️ BOTH VERBS. The create door writes with `create`, so an arm that
      // watched `update` alone would pass on a create written beside the lock.
      expect(
        prisma.user.update,
        'the row was written even though the lock never ran its callback — ' +
          'the write is beside the lock, not inside it',
      ).not.toHaveBeenCalled();
      expect(
        prisma.user.create,
        'the row was CREATED even though the lock never ran its callback',
      ).not.toHaveBeenCalled();
    },
  );
});
