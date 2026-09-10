// ============================================================================
// GATE — ADMIN-1: WHO MAY ADMINISTER A PRACTICE, AND WHAT THAT PERMITS.
// ----------------------------------------------------------------------------
// ⚠️ WHAT WOULD MAKE THIS FILE FAIL, stated first:
//   · OWNER stops being assignable             -> the not-exclusive block
//   · the assignable enum stops constraining   -> the not-exclusive block
//   · the guard reads the SESSION's role       -> the staleness block
//   · a refusal stops being audited            -> the audit block
//   · the self-demotion guard is removed       -> the role-change block
//   · an OWNER becomes UN-demotable again      -> the ADMIN-5 role-change arms
//   · the actor is not re-read under the lock  -> the ADMIN-5 arms (all three doors)
//   · a trigger refusal escapes as a throw     -> the ADMIN-5 arms (all three doors)
//   · removal stops being a CAS / writes the wrong columns -> the removal block
//   · a transfer steps down BEFORE it promotes -> the transfer block
//   · a mint sets practiceId without the role  -> the mint block
//   · the raw code or its hash reaches an audit row -> the mint block
//   · a cross-practice target becomes reachable -> the scope block
//   · the CAS predicate leaves the WHERE clause -> the not-exclusive block
//   · a count-0 CAS writes an audit row anyway  -> the not-exclusive block
//   · a deactivated member becomes promotable   -> the not-exclusive block
//
// ⚠️ THE TWO SIDES ARE INDEPENDENT AND THIS FILE PROVES BOTH SEPARATELY. The
// OWNER-not-exclusive decision (branch `feat/ruling-195-owner-not-exclusive`)
// opened PROMOTION only. Demotion and removal stay refused, which is what keeps
// "every practice has at least one OWNER" STRUCTURAL — no owner COUNT is ever
// read. Deleting the demotion arms because "owners are assignable now" is the
// exact misreading this note exists to stop.
//
// ⚠️ AND THE ROLE WRITE *IS* A READ-THEN-WRITE, WHICH THIS FILE ONCE DENIED.
// An earlier version of this header claimed "no read-then-write race". That was
// false and an adversarial pass reproduced the counterexample: the widening made
// a previously-unreachable window reachable, because until then nothing could
// turn a target INTO an owner between the read and the write. The window is
// closed by a COMPARE-AND-SET in the WHERE clause, not by the guard above, and
// the two arms that pin it are the ones a refactor will be tempted to delete.
// ============================================================================

import { beforeEach, describe, expect, it, vi } from 'vitest';

// ⚠️ `vi.hoisted`, NOT plain consts. `vi.mock` is hoisted above every
// declaration in the file, so a factory closing over a top-level `const` throws
// `Cannot access 'prisma' before initialization` — and it throws at MODULE LOAD,
// which vitest reports as "no tests" rather than as a failure in any arm.
const { prisma, logAudit, getSession, queryRaw, executeRaw } = vi.hoisted(() => {
  // ⚠️ RULING #268 — THE ROLE CHANGE NOW RUNS INSIDE A TRANSACTION, because the
  // practice advisory lock must be taken BEFORE the row write or two concurrent
  // demotions deadlock (measured 10 of 10). So this mock grew a `$transaction`.
  //
  // ⚠️ IT HANDS THE CALLBACK **THE SAME `user` MOCKS**, deliberately. Every arm
  // below asserts on `prisma.user.updateMany`, and a `tx` carrying fresh spies
  // would make all of them pass vacuously — the write would happen on an object
  // nothing inspects. One set of spies, reachable both ways.
  //
  // ⚠️ AND `$queryRaw` ANSWERS `read committed`, WHICH IS A MODELLING CHOICE
  // AND NOT A CONVENIENCE. `withPracticeLock` refuses any other level (#269);
  // answering anything else here would make every arm in this file fail for a
  // reason that has nothing to do with what they test. The REFUSAL itself is
  // proved in `gate-admin5-last-owner-invariant.test.ts`, against a tx that
  // reports the elevated levels — not here.
  const queryRaw = vi.fn(async () => [{ level: 'read committed' }]);
  // ⚠️ THE LOCK IS AN **EXECUTE**. `pg_advisory_xact_lock` returns `void` and
  // `$queryRaw` cannot deserialize a void column, so taking it as a query is a
  // 500 against a real database. The double carries both, or it cannot witness
  // the wrong one being chosen — which is exactly how the first version shipped.
  const executeRaw = vi.fn(async () => 1);
  const user = {
    findUnique: vi.fn(),
    findFirst: vi.fn(),
    update: vi.fn(),
    updateMany: vi.fn(),
    findMany: vi.fn(),
  };
  const prisma = {
    user,
    inviteCode: { create: vi.fn(), updateMany: vi.fn(), findMany: vi.fn() },
    $queryRaw: queryRaw,
    $executeRaw: executeRaw,
    $transaction: vi.fn(async (fn: (tx: unknown) => unknown) =>
      fn({ user, $queryRaw: queryRaw, $executeRaw: executeRaw })
    ),
  };
  return { prisma, logAudit: vi.fn(), getSession: vi.fn(), queryRaw, executeRaw };
});

vi.mock('@meddoc/db', () => ({ default: prisma }));
vi.mock('@/lib/audit', () => ({ logAudit }));
vi.mock('@/lib/auth', () => ({ getSession }));
vi.mock('next/cache', () => ({ revalidatePath: vi.fn() }));

import {
  ADMIN_REFUSAL_MESSAGE,
  ASSIGNABLE_ROLES,
  PRACTICE_ADMIN_ROLE,
  generateInviteCode,
  isAssignableRole,
  requirePracticeAdmin,
} from '../practice-admin';
import {
  changeMemberRoleAction,
  mintSeatInviteAction,
  removeMemberAction,
  transferOwnershipAction,
} from '../../actions/practice-members';
import {
  ACTIVE_OWNER_WHERE,
  LAST_OWNER_REFUSAL,
  LIVE_MEMBER_WHERE,
} from '../last-owner-invariant';

/**
 * The trigger's refusal in the MEASURED shape: Prisma 7 + adapter-pg against a
 * scratch pg16 surfaced it as a `DriverAdapterError` with no Prisma code, the
 * SQLSTATE on `cause.originalCode`. Thrown BY THE WRITE, so the arm measures
 * the door's catch, not a friendlier double handed to `$transaction`.
 */
const adapterError = (code: string, message: string) => ({
  name: 'DriverAdapterError',
  message,
  cause: { originalCode: code, originalMessage: message, kind: 'postgres', code, message },
});
const TRIGGER_REFUSAL = adapterError(
  '23514',
  'users_last_owner_guard: refusing to leave practice p-1 with zero active OWNERs while 2 other member(s) remain. Transfer ownership first.',
);
const CHECK_VIOLATION = adapterError(
  '23514',
  'new row for relation "users" violates check constraint "users_active_member_has_practice_role"',
);

const OWNER_SESSION = { user: { id: 'u-owner', practiceId: 'p-1' } };

function asOwner() {
  prisma.user.findUnique.mockResolvedValue({ practiceRole: 'OWNER', practiceId: 'p-1' });
  getSession.mockResolvedValue(OWNER_SESSION);
}

function form(entries: Record<string, string>): FormData {
  const fd = new FormData();
  for (const [k, v] of Object.entries(entries)) fd.set(k, v);
  return fd;
}

beforeEach(() => {
  vi.clearAllMocks();
  // ⚠️ THE CAS DEFAULT IS "IT MATCHED", so an arm that does not care about the
  // race is not silently exercising the count-0 refusal path. The two arms that
  // DO care set it explicitly.
  prisma.user.updateMany.mockResolvedValue({ count: 1 });
});

describe('⚠️ OWNER IS NOT EXCLUSIVE — the promotion side is now open', () => {
  it('OWNER is in the assignable set', () => {
    // The OWNER-not-exclusive decision (branch
    // `feat/ruling-195-owner-not-exclusive`) settles what ADMIN-1 shipped
    // fail-closed on: a practice may have more than one owner, and an owner may
    // create another. Administration can be handed on.
    expect([...ASSIGNABLE_ROLES]).toEqual(['OWNER', 'CLINICIAN', 'TECH']);
    expect(isAssignableRole('OWNER')).toBe(true);
  });

  it('and the administering role is still OWNER — the two are not the same list', () => {
    // ⚠️ NON-VACUITY, KEPT. The lists now overlap, so "OWNER is assignable"
    // could be satisfied by a build that collapsed the two concepts. It still
    // administers, and that is a separate fact from being handed out.
    expect(PRACTICE_ADMIN_ROLE).toBe('OWNER');
  });

  it('a mint may now issue an OWNER seat, and the row carries that role', async () => {
    asOwner();
    prisma.inviteCode.create.mockResolvedValue({ id: 'inv-1' });
    const res = await mintSeatInviteAction(null, form({ role: 'OWNER', label: 'A partner' }));
    expect(res?.ok).toBe(true);
    expect(prisma.inviteCode.create).toHaveBeenCalledOnce();
    // ⚠️ THE ROLE REACHES THE ROW. "ok:true" alone would also be returned by a
    // build that accepted OWNER and then silently minted a CLINICIAN seat —
    // which is the failure that looks like success.
    expect(prisma.inviteCode.create.mock.calls[0][0].data).toMatchObject({
      practiceRole: 'OWNER',
      practiceId: 'p-1',
    });
  });

  it('an existing member can be PROMOTED to OWNER, and it audits from -> to', async () => {
    asOwner();
    prisma.user.findFirst.mockResolvedValue({ id: 'u-2', practiceRole: 'CLINICIAN' });
    const res = await changeMemberRoleAction(null, form({ userId: 'u-2', role: 'OWNER' }));
    expect(res?.ok).toBe(true);
    expect(prisma.user.updateMany).toHaveBeenCalledOnce();
    expect(prisma.user.updateMany.mock.calls[0][0].data).toMatchObject({ practiceRole: 'OWNER' });
    expect(logAudit.mock.calls.at(-1)?.[0].metadata).toMatchObject({
      from: 'CLINICIAN',
      to: 'OWNER',
    });
  });

  it('⚠️ THE WRITE IS A COMPARE-AND-SET ON THE ROLE THAT WAS READ — the race the widening opened', async () => {
    // ⚠️ FOUND BY THE ADVERSARIAL PASS ON THIS BRANCH, NOT BY THE AUTHOR, AND
    // REPRODUCED: two concurrent requests, one promoting B to OWNER and one
    // demoting B, both read B as CLINICIAN, both clear the guard above, and the
    // demotion lands on an OWNER. Until this ruling the shape was INCIDENTALLY
    // safe — no in-app path could turn a target into an owner, so the row could
    // never become OWNER between the read and the write. Widening the
    // vocabulary is precisely what made the window reachable.
    //
    // The fix is one statement, not a transaction: `updateMany` re-asserts the
    // role that was read, so a row that moved matches zero rows.
    asOwner();
    prisma.user.findFirst.mockResolvedValue({ id: 'u-2', practiceRole: 'CLINICIAN' });
    prisma.user.updateMany.mockResolvedValue({ count: 1 });
    await changeMemberRoleAction(null, form({ userId: 'u-2', role: 'TECH' }));
    const where = prisma.user.updateMany.mock.calls[0][0].where;
    expect(where).toMatchObject({
      id: 'u-2',
      practiceId: 'p-1',
      practiceRole: 'CLINICIAN', // ← the CAS predicate. Without it the write is unconditional.
      deactivatedAt: null,
    });
  });

  it('⚠️ and a CAS that matches nothing REFUSES rather than writing a false audit row', async () => {
    // count 0 means the row moved under us. The old code would have written the
    // audit row from its stale snapshot — `from: CLINICIAN` for a row that was
    // OWNER when the UPDATE ran. A false entry in an append-only trail is worse
    // than a missing one, so we refuse and record nothing.
    asOwner();
    prisma.user.findFirst.mockResolvedValue({ id: 'u-2', practiceRole: 'CLINICIAN' });
    prisma.user.updateMany.mockResolvedValue({ count: 0 });
    const res = await changeMemberRoleAction(null, form({ userId: 'u-2', role: 'TECH' }));
    expect(res && !res.ok && res.reason).toBe('ROLE_CHANGED_UNDER_YOU');
    expect(logAudit).not.toHaveBeenCalled();
  });

  it('⚠️ a DEACTIVATED member is not a promotion target — an invisible owner could never be revoked', async () => {
    // Deactivation writes {isActive:false, deactivatedAt} and leaves practiceId
    // and practiceRole intact, so a deactivated member stays findable by
    // id+practice. Writing OWNER onto such a row produces an owner the members
    // page does not render. (Until ADMIN-5 `CANNOT_CHANGE_AN_OWNER` then made it
    // permanent; it is gone, and the invisible owner is still wrong.) The
    // listing already filters; the target lookup did not.
    asOwner();
    prisma.user.findFirst.mockResolvedValue(null); // the filter excludes them
    const res = await changeMemberRoleAction(null, form({ userId: 'u-gone', role: 'OWNER' }));
    expect(res && !res.ok && res.reason).toBe('TARGET_NOT_IN_PRACTICE');
    expect(prisma.user.findFirst.mock.calls[0][0].where).toMatchObject({ deactivatedAt: null });
    expect(prisma.user.updateMany).not.toHaveBeenCalled();
  });

  it('⚠️ a role OUTSIDE the set is still refused — widening is not opening', () => {
    // ⚠️ THE CONTROL FOR THE ARM ABOVE. `isAssignableRole('OWNER') === true`
    // would also hold in a build where the enum stopped constraining anything
    // at all, and that build would accept 'SUPER_ADMIN' from a form post.
    expect(isAssignableRole('SUPER_ADMIN')).toBe(false);
    expect(isAssignableRole('ADMIN')).toBe(false);
    expect(isAssignableRole('')).toBe(false);
  });
});

describe('⚠️ the guard reads the DATABASE, never the session', () => {
  it('a session claiming OWNER is refused when the row says TECH', async () => {
    // A JWT is minted at sign-in. A member demoted five minutes ago still
    // carries OWNER in their token, and this surface hands out SEATS — the one
    // place a stale elevation mints durable access for somebody else.
    prisma.user.findUnique.mockResolvedValue({ practiceRole: 'TECH', practiceId: 'p-1' });
    const res = await requirePracticeAdmin(OWNER_SESSION);
    expect(res.ok).toBe(false);
    expect(prisma.user.findUnique).toHaveBeenCalledOnce();
  });

  it('a NULL role refuses — fail-closed, not merely non-owner', async () => {
    prisma.user.findUnique.mockResolvedValue({ practiceRole: null, practiceId: 'p-1' });
    expect((await requirePracticeAdmin(OWNER_SESSION)).ok).toBe(false);
  });

  it('a missing row refuses', async () => {
    prisma.user.findUnique.mockResolvedValue(null);
    expect((await requirePracticeAdmin(OWNER_SESSION)).ok).toBe(false);
  });

  it("an OWNER of ANOTHER practice refuses — the session's practice must match the row", async () => {
    prisma.user.findUnique.mockResolvedValue({ practiceRole: 'OWNER', practiceId: 'p-2' });
    expect((await requirePracticeAdmin(OWNER_SESSION)).ok).toBe(false);
  });

  it('and a real owner passes — the arms above are not passing on a broken guard', async () => {
    asOwner();
    expect((await requirePracticeAdmin(OWNER_SESSION)).ok).toBe(true);
  });
});

describe('⚠️ every refusal is audited — a gate nothing records is one path from not existing', () => {
  it('the refusal writes PRACTICE_ADMIN_REFUSED with the role and no name', async () => {
    prisma.user.findUnique.mockResolvedValue({ practiceRole: 'TECH', practiceId: 'p-1' });
    await requirePracticeAdmin(OWNER_SESSION);
    expect(logAudit).toHaveBeenCalledOnce();
    const row = logAudit.mock.calls[0][0];
    expect(row.action).toBe('PRACTICE_ADMIN_REFUSED');
    expect(row.metadata.practiceRole).toBe('TECH');
    // Structured only. A name in an audit row is a person in a table that
    // outlives the reason it was written.
    expect(JSON.stringify(row)).not.toMatch(/name|email/i);
  });

  it('a practice MISMATCH is recorded distinctly from a wrong role', async () => {
    // One label for both would make a stale token and a demotion look the same
    // in an append-only trail.
    prisma.user.findUnique.mockResolvedValue({ practiceRole: 'OWNER', practiceId: 'p-2' });
    await requirePracticeAdmin(OWNER_SESSION);
    expect(logAudit.mock.calls[0][0].metadata.practiceMismatch).toBe(true);
  });

  it('and a PASSING guard writes nothing — the arm above is not counting noise', async () => {
    asOwner();
    await requirePracticeAdmin(OWNER_SESSION);
    expect(logAudit).not.toHaveBeenCalled();
  });
});

describe('⚠️ role changes — the guards that keep a practice administrable', () => {
  it('you cannot change your OWN role', async () => {
    asOwner();
    const res = await changeMemberRoleAction(null, form({ userId: 'u-owner', role: 'TECH' }));
    expect(res?.ok).toBe(false);
    expect(res && !res.ok && res.reason).toBe('CANNOT_CHANGE_OWN_ROLE');
    // ⚠️ REFUSED BEFORE THE READ. The self-demotion guard must not depend on a
    // query succeeding.
    expect(prisma.user.findFirst).not.toHaveBeenCalled();
    expect(prisma.user.update).not.toHaveBeenCalled();
  });

  // ══════════════════════════════════════════════════════════════════════════
  // ADMIN-5 — OWNER DEMOTION IS OPEN, AND THE INVARIANT IS THE DATABASE'S.
  //
  // These three arms REPLACE the ADMIN-1 arms that pinned `CANNOT_CHANGE_AN_OWNER`
  // (an owner's role could never change here). That refusal is deleted, not
  // weakened: `users_last_owner_guard` is the only enforcer (#210, #310(a)), and
  // what this door owes is (1) to re-read its ACTOR under the lock and (2) to
  // SPEAK the trigger's refusal instead of throwing it.
  // ══════════════════════════════════════════════════════════════════════════
  it('⚠️ ADMIN-5 — an OWNER can be demoted by another owner, as a CAS on OWNER, audited OWNER -> TECH', async () => {
    asOwner();
    prisma.user.findFirst.mockResolvedValue({ id: 'u-2', practiceRole: 'OWNER' });
    const res = await changeMemberRoleAction(null, form({ userId: 'u-2', role: 'TECH' }));
    expect(res?.ok).toBe(true);
    expect(prisma.user.updateMany).toHaveBeenCalledOnce();
    expect(prisma.user.updateMany.mock.calls[0][0].where).toMatchObject({ id: 'u-2', practiceRole: 'OWNER' });
    expect(logAudit.mock.calls.at(-1)?.[0]).toMatchObject({
      action: 'PRACTICE_ROLE_CHANGED',
      metadata: { from: 'OWNER', to: 'TECH' },
    });
  });

  it('⚠️ ADMIN-5 — the ACTOR is re-read UNDER the lock with ACTIVE_OWNER_WHERE; a stale actor writes nothing', async () => {
    // `requirePracticeAdmin` ran before the lock and reads the role column only.
    // Two owners demoting each other both pass it; without a re-read under the
    // lock the second acts on authority the first has just removed.
    asOwner();
    prisma.user.findFirst
      .mockResolvedValueOnce({ id: 'u-2', practiceRole: 'OWNER' }) // target, before the lock
      .mockResolvedValueOnce(null); // the actor, re-read under it — demoted a moment ago
    const res = await changeMemberRoleAction(null, form({ userId: 'u-2', role: 'TECH' }));
    expect(res && !res.ok && res.reason).toBe('ROLE_MAY_NOT_ADMINISTER');
    expect(prisma.user.updateMany, 'a demoted actor still wrote').not.toHaveBeenCalled();

    const recheck = prisma.user.findFirst.mock.calls[1][0].where;
    expect(recheck, 'the re-read is not the ONE active-owner predicate').toMatchObject({
      id: 'u-owner',
      practiceId: 'p-1',
      ...ACTIVE_OWNER_WHERE,
    });
    const lockAt = Math.min(...executeRaw.mock.invocationCallOrder);
    expect(prisma.user.findFirst.mock.invocationCallOrder[1], 'the actor was re-read OUTSIDE the lock').toBeGreaterThan(lockAt);
    expect(logAudit.mock.calls.at(-1)?.[0]).toMatchObject({
      action: 'PRACTICE_ADMIN_REFUSED',
      metadata: { refusal: 'ROLE_MAY_NOT_ADMINISTER', attempted: 'ROLE_CHANGE', recheckedUnderLock: true },
    });
  });

  it('⚠️ ADMIN-5 — the TRIGGER refusing is spoken as LAST_OWNER and audited, never thrown', async () => {
    asOwner();
    prisma.user.findFirst.mockResolvedValue({ id: 'u-2', practiceRole: 'OWNER' });
    prisma.user.updateMany.mockRejectedValueOnce(TRIGGER_REFUSAL);
    const res = await changeMemberRoleAction(null, form({ userId: 'u-2', role: 'TECH' }));
    expect(res).toMatchObject({ ok: false, reason: 'LAST_OWNER', message: LAST_OWNER_REFUSAL });
    const actions = logAudit.mock.calls.map((c) => c[0].action);
    expect(actions).toEqual(['PRACTICE_ADMIN_REFUSED']);
    expect(logAudit.mock.calls[0][0].metadata).toMatchObject({
      refusal: 'LAST_OWNER',
      attempted: 'ROLE_CHANGE',
      source: 'trigger',
      to: 'TECH',
    });
  });

  it('⚠️ ADMIN-5 — an error that is NOT a last-owner refusal is rethrown, not dressed up', async () => {
    asOwner();
    prisma.user.findFirst.mockResolvedValue({ id: 'u-2', practiceRole: 'CLINICIAN' });
    prisma.user.updateMany.mockRejectedValueOnce(CHECK_VIOLATION);
    await expect(changeMemberRoleAction(null, form({ userId: 'u-2', role: 'TECH' }))).rejects.toBe(CHECK_VIOLATION);
    expect(logAudit).not.toHaveBeenCalled();
  });

  it('⚠️ the retired refusal is GONE, and LAST_OWNER speaks the friendly-refusal file\'s own sentence', () => {
    // A refusal string that outlives its refusal is how a page starts lying —
    // "ask support if a partner is leaving" would send a doctor away from a page
    // that now does it.
    expect('CANNOT_CHANGE_AN_OWNER' in ADMIN_REFUSAL_MESSAGE).toBe(false);
    expect(ADMIN_REFUSAL_MESSAGE.LAST_OWNER).toBe(LAST_OWNER_REFUSAL);
  });

  it('a target in ANOTHER practice is not found — scoped in the WHERE, not after it', async () => {
    asOwner();
    prisma.user.findFirst.mockResolvedValue(null);
    const res = await changeMemberRoleAction(null, form({ userId: 'u-elsewhere', role: 'TECH' }));
    expect(res && !res.ok && res.reason).toBe('TARGET_NOT_IN_PRACTICE');
    // The practice is a conjunct of the query itself.
    expect(prisma.user.findFirst.mock.calls[0][0].where).toMatchObject({ practiceId: 'p-1' });
  });

  it('a real change writes the row AND audits from -> to', async () => {
    asOwner();
    prisma.user.findFirst.mockResolvedValue({ id: 'u-2', practiceRole: 'CLINICIAN' });
    const res = await changeMemberRoleAction(null, form({ userId: 'u-2', role: 'TECH' }));
    expect(res?.ok).toBe(true);
    expect(prisma.user.updateMany).toHaveBeenCalledOnce();
    const audit = logAudit.mock.calls.at(-1)?.[0];
    expect(audit.action).toBe('PRACTICE_ROLE_CHANGED');
    expect(audit.metadata).toMatchObject({ from: 'CLINICIAN', to: 'TECH' });
  });

  it('⚠️ #268 BEHAVIOURAL — the practice lock is taken, and taken BEFORE the write', async () => {
    // ⚠️ THIS IS THE BEHAVIOURAL HALF, AND RULING #251 IS WHY IT EXISTS.
    // `gate-admin5` asserts the lock's position by READING THE SOURCE, which
    // #251 retires as a proof of behaviour: a text scan cannot tell a call from
    // a comment, and it survives any refactor that moves the call into a helper
    // it does not know to read. This arm asserts what actually RAN, by
    // invocation order, on the same spies every other arm here inspects.
    // A NON-OWNER target. (This arm was written when `CANNOT_CHANGE_AN_OWNER`
    // made an owner target unreachable; ADMIN-5 deleted that refusal, and the
    // owner-demotion arms above run the same lock for an OWNER target.) The
    // lock wraps EVERY role change, which is the conservative choice: the next
    // door added to this file inherits it.
    asOwner();
    prisma.user.findFirst.mockResolvedValue({ id: 'u-2', practiceRole: 'CLINICIAN' });
    const res = await changeMemberRoleAction(null, form({ userId: 'u-2', role: 'TECH' }));
    expect(res?.ok).toBe(true);

    // The lock query ran, and it is the advisory lock rather than the level probe.
    const lockCalls = (executeRaw.mock.calls as unknown as unknown[][]).filter((c) =>
      String(c[0]).includes('pg_advisory_xact_lock')
    );
    expect(lockCalls.length, 'the demotion never took the practice lock').toBe(1);

    // ⚠️ ORDER, BY INVOCATION INDEX — the property the deadlock turns on.
    // `invocationCallOrder` is vitest's global monotonic counter, so it orders
    // calls ACROSS two different spies, which is exactly what is needed here:
    // the lock is on `$queryRaw` and the write is on `user.updateMany`.
    const lockAt = Math.min(...executeRaw.mock.invocationCallOrder);
    const writeAt = Math.min(...prisma.user.updateMany.mock.invocationCallOrder);
    expect(prisma.user.updateMany).toHaveBeenCalledOnce();
    expect(
      lockAt,
      'the row was written before the practice lock was taken — the shape that deadlocked 10 of 10',
    ).toBeLessThan(writeAt);
  });

  it('a no-op writes NOTHING — an append-only trail must not record changes that did not happen', async () => {
    asOwner();
    prisma.user.findFirst.mockResolvedValue({ id: 'u-2', practiceRole: 'TECH' });
    const res = await changeMemberRoleAction(null, form({ userId: 'u-2', role: 'TECH' }));
    expect(res?.ok).toBe(true);
    expect(prisma.user.update).not.toHaveBeenCalled();
    expect(logAudit).not.toHaveBeenCalled();
  });

  it('a NON-OWNER caller changes nothing', async () => {
    prisma.user.findUnique.mockResolvedValue({ practiceRole: 'CLINICIAN', practiceId: 'p-1' });
    getSession.mockResolvedValue({ user: { id: 'u-c', practiceId: 'p-1' } });
    const res = await changeMemberRoleAction(null, form({ userId: 'u-2', role: 'TECH' }));
    expect(res?.ok).toBe(false);
    expect(prisma.user.update).not.toHaveBeenCalled();
  });
});

// ============================================================================
// ADMIN-5 — REMOVING A MEMBER.
// ============================================================================
describe('⚠️ ADMIN-5 — removeMemberAction', () => {
  // ⚠️ `clearAllMocks` DOES NOT DRAIN A `mockResolvedValueOnce` QUEUE. A refusal
  // arm that returns before its second read leaves the queued target behind,
  // and the NEXT arm then reads it — measured: four arms here passed or failed
  // on their neighbour's fixture on the first run. Reset the two spies whose
  // queues these arms fill.
  beforeEach(() => {
    prisma.user.findFirst.mockReset();
    prisma.user.updateMany.mockReset();
    prisma.user.updateMany.mockResolvedValue({ count: 1 });
  });

  /** actor re-check (under the lock) then the target read (under the lock). */
  const underLock = (target: { id: string; practiceRole: string | null } | null, actor: object | null = { id: 'u-owner' }) =>
    prisma.user.findFirst.mockResolvedValueOnce(actor).mockResolvedValueOnce(target);

  it('you cannot remove YOURSELF — refused by its own name, before any read or lock', async () => {
    asOwner();
    const res = await removeMemberAction(null, form({ userId: 'u-owner' }));
    expect(res && !res.ok && res.reason).toBe('CANNOT_REMOVE_YOURSELF');
    expect(prisma.user.findFirst).not.toHaveBeenCalled();
    expect(prisma.$transaction).not.toHaveBeenCalled();
  });

  it('⚠️ removal is a COMPARE-AND-SET writing exactly the deactivation columns, and the role goes NULL', async () => {
    asOwner();
    underLock({ id: 'u-2', practiceRole: 'CLINICIAN' });
    const res = await removeMemberAction(null, form({ userId: 'u-2' }));
    expect(res?.ok).toBe(true);
    expect(prisma.user.updateMany).toHaveBeenCalledOnce();
    const { where, data } = prisma.user.updateMany.mock.calls[0][0];
    // the CAS: the role read UNDER the lock, and the practice, in the WHERE
    expect(where).toEqual({ id: 'u-2', practiceId: 'p-1', deactivatedAt: null, practiceRole: 'CLINICIAN' });
    // ⚠️ NULL, because the column's own doc requires it of a deactivated row —
    // and because a removed ex-OWNER that kept `OWNER` would count as a
    // "rescuer" in the trigger's exemption 2 while no door can restore them.
    expect(data.practiceRole).toBeNull();
    expect(data.isActive).toBe(false);
    expect(data.deactivatedBy).toBe('u-owner');
    expect(data.deactivatedAt).toBeInstanceOf(Date);
    // a live session dies on its next request
    expect(data.forceLogoutAt).toBeInstanceOf(Date);
    expect(Object.keys(data).sort()).toEqual(
      ['deactivatedAt', 'deactivatedBy', 'forceLogoutAt', 'isActive', 'practiceRole'],
    );
  });

  it('audits PRACTICE_MEMBER_REMOVED with the role they HELD — the row no longer carries it', async () => {
    asOwner();
    underLock({ id: 'u-2', practiceRole: 'OWNER' });
    await removeMemberAction(null, form({ userId: 'u-2' }));
    expect(logAudit.mock.calls.at(-1)?.[0]).toMatchObject({
      action: 'PRACTICE_MEMBER_REMOVED',
      targetId: 'u-2',
      metadata: { removedRole: 'OWNER', practiceId: 'p-1' },
    });
    expect(JSON.stringify(logAudit.mock.calls.at(-1)?.[0])).not.toMatch(/email|name/i);
  });

  it('⚠️ the lock is taken on THIS practice, BEFORE the actor re-read, the target read and the write', async () => {
    asOwner();
    underLock({ id: 'u-2', practiceRole: 'TECH' });
    await removeMemberAction(null, form({ userId: 'u-2' }));
    const lockCalls = (executeRaw.mock.calls as unknown as unknown[][]).filter((c) =>
      String(c[0]).includes('pg_advisory_xact_lock'),
    );
    expect(lockCalls.length).toBe(1);
    expect(lockCalls[0]).toContain('p-1');
    const lockAt = Math.min(...executeRaw.mock.invocationCallOrder);
    for (const at of prisma.user.findFirst.mock.invocationCallOrder) expect(at).toBeGreaterThan(lockAt);
    expect(prisma.user.updateMany.mock.invocationCallOrder[0]).toBeGreaterThan(lockAt);
    // and the actor re-read is the ONE predicate
    expect(prisma.user.findFirst.mock.calls[0][0].where).toMatchObject({ id: 'u-owner', ...ACTIVE_OWNER_WHERE });
  });

  it('⚠️ a STALE actor (removed a moment ago by the other owner) removes nobody — the #306 class', async () => {
    // Two owners of a practice with no other live member remove each other. The
    // second removal is ALLOWED by the trigger (exemption 2: the first victim's
    // row is inactive with a NULL role, neither member nor rescuer) and leaves a
    // practice with no live user. The re-read under the lock is what refuses it.
    asOwner();
    underLock({ id: 'u-2', practiceRole: 'OWNER' }, null);
    const res = await removeMemberAction(null, form({ userId: 'u-2' }));
    expect(res && !res.ok && res.reason).toBe('ROLE_MAY_NOT_ADMINISTER');
    expect(prisma.user.updateMany).not.toHaveBeenCalled();
    expect(logAudit.mock.calls.at(-1)?.[0]).toMatchObject({
      action: 'PRACTICE_ADMIN_REFUSED',
      metadata: { refusal: 'ROLE_MAY_NOT_ADMINISTER', attempted: 'REMOVE', recheckedUnderLock: true },
    });
  });

  it('a target not in this practice (or already removed) is not found, and nothing is written', async () => {
    asOwner();
    underLock(null);
    const res = await removeMemberAction(null, form({ userId: 'u-elsewhere' }));
    expect(res && !res.ok && res.reason).toBe('TARGET_NOT_IN_PRACTICE');
    expect(prisma.user.findFirst.mock.calls[1][0].where).toMatchObject({ practiceId: 'p-1', deactivatedAt: null });
    expect(prisma.user.updateMany).not.toHaveBeenCalled();
  });

  it('⚠️ a CAS that matches nothing refuses, and writes NO removal row', async () => {
    asOwner();
    underLock({ id: 'u-2', practiceRole: 'CLINICIAN' });
    prisma.user.updateMany.mockResolvedValueOnce({ count: 0 });
    const res = await removeMemberAction(null, form({ userId: 'u-2' }));
    expect(res && !res.ok && res.reason).toBe('ROLE_CHANGED_UNDER_YOU');
    expect(logAudit.mock.calls.map((c) => c[0].action)).not.toContain('PRACTICE_MEMBER_REMOVED');
  });

  it('⚠️ the TRIGGER refusing is spoken as LAST_OWNER and audited', async () => {
    asOwner();
    underLock({ id: 'u-2', practiceRole: 'OWNER' });
    prisma.user.updateMany.mockRejectedValueOnce(TRIGGER_REFUSAL);
    const res = await removeMemberAction(null, form({ userId: 'u-2' }));
    expect(res).toMatchObject({ ok: false, reason: 'LAST_OWNER', message: LAST_OWNER_REFUSAL });
    expect(logAudit.mock.calls.map((c) => c[0].action)).toEqual(['PRACTICE_ADMIN_REFUSED']);
    expect(logAudit.mock.calls[0][0].metadata).toMatchObject({ refusal: 'LAST_OWNER', attempted: 'REMOVE', source: 'trigger' });
  });

  it('a NON-OWNER caller removes nobody', async () => {
    prisma.user.findUnique.mockResolvedValue({ practiceRole: 'CLINICIAN', practiceId: 'p-1' });
    getSession.mockResolvedValue({ user: { id: 'u-c', practiceId: 'p-1' } });
    const res = await removeMemberAction(null, form({ userId: 'u-2' }));
    expect(res && !res.ok && res.reason).toBe('ROLE_MAY_NOT_ADMINISTER');
    expect(prisma.$transaction).not.toHaveBeenCalled();
  });
});

// ============================================================================
// ADMIN-5a — HANDING THE PRACTICE ON.
// ============================================================================
describe('⚠️ ADMIN-5a — transferOwnershipAction', () => {
  // Same reason as the removal block: undrained `…Once` queues leak between arms.
  beforeEach(() => {
    prisma.user.findFirst.mockReset();
    prisma.user.updateMany.mockReset();
    prisma.user.updateMany.mockResolvedValue({ count: 1 });
  });

  /** actor re-check, then the incoming owner — both under the lock. */
  const underLock = (target: { id: string; practiceRole: string | null } | null, actor: object | null = { id: 'u-owner' }) =>
    prisma.user.findFirst.mockResolvedValueOnce(actor).mockResolvedValueOnce(target);

  it('the step-down role must be a NON-owner role or LEAVE — OWNER is not a way to step down', async () => {
    asOwner();
    for (const then of ['OWNER', 'SUPER_ADMIN', '']) {
      const res = await transferOwnershipAction(null, form({ userId: 'u-2', then }));
      expect(res && !res.ok && res.reason).toBe('ROLE_NOT_ASSIGNABLE');
    }
    expect(prisma.$transaction).not.toHaveBeenCalled();
  });

  it('you cannot transfer to YOURSELF — refused before any read', async () => {
    asOwner();
    const res = await transferOwnershipAction(null, form({ userId: 'u-owner', then: 'CLINICIAN' }));
    expect(res && !res.ok && res.reason).toBe('TRANSFER_TARGET_INVALID');
    expect(prisma.$transaction).not.toHaveBeenCalled();
  });

  it('⚠️ the incoming owner must be a LIVE member — a suspended one is refused, nothing written', async () => {
    asOwner();
    underLock(null);
    const res = await transferOwnershipAction(null, form({ userId: 'u-susp', then: 'CLINICIAN' }));
    expect(res && !res.ok && res.reason).toBe('TRANSFER_TARGET_INVALID');
    expect(prisma.user.findFirst.mock.calls[1][0].where).toMatchObject({
      id: 'u-susp',
      practiceId: 'p-1',
      ...LIVE_MEMBER_WHERE,
    });
    expect(prisma.user.updateMany).not.toHaveBeenCalled();
  });

  it('⚠️ THE ORDER IS LOAD-BEARING — promote the target FIRST, then step the actor down', async () => {
    // Step-down-first by a sole owner is refused by the trigger (it judges each
    // statement on the state that statement produced). Promote-first means the
    // step-down already sees the new owner.
    asOwner();
    underLock({ id: 'u-2', practiceRole: 'CLINICIAN' });
    const res = await transferOwnershipAction(null, form({ userId: 'u-2', then: 'CLINICIAN' }));
    expect(res?.ok).toBe(true);
    expect(prisma.user.updateMany).toHaveBeenCalledTimes(2);
    const [first, second] = prisma.user.updateMany.mock.calls.map((c) => c[0]);
    expect(first.where, 'the FIRST write is not the promotion').toMatchObject({ id: 'u-2', practiceRole: 'CLINICIAN' });
    expect(first.data).toEqual({ practiceRole: 'OWNER' });
    expect(second.where, 'the SECOND write is not the actor stepping down').toMatchObject({
      id: 'u-owner',
      practiceId: 'p-1',
      ...ACTIVE_OWNER_WHERE,
    });
    expect(second.data).toEqual({ practiceRole: 'CLINICIAN' });
    const lockAt = Math.min(...executeRaw.mock.invocationCallOrder);
    expect(Math.min(...prisma.user.updateMany.mock.invocationCallOrder)).toBeGreaterThan(lockAt);
  });

  it('two PRACTICE_ROLE_CHANGED rows, one per person, sharing ONE transferId', async () => {
    asOwner();
    underLock({ id: 'u-2', practiceRole: 'TECH' });
    await transferOwnershipAction(null, form({ userId: 'u-2', then: 'TECH' }));
    const rows = logAudit.mock.calls.map((c) => c[0]);
    expect(rows.map((r) => [r.action, r.targetId])).toEqual([
      ['PRACTICE_ROLE_CHANGED', 'u-2'],
      ['PRACTICE_ROLE_CHANGED', 'u-owner'],
    ]);
    expect(rows[0].metadata).toMatchObject({ from: 'TECH', to: 'OWNER', practiceId: 'p-1' });
    expect(rows[1].metadata).toMatchObject({ from: 'OWNER', to: 'TECH', practiceId: 'p-1' });
    expect(rows[0].metadata.transferId).toMatch(/^[0-9a-f-]{36}$/);
    expect(rows[1].metadata.transferId).toBe(rows[0].metadata.transferId);
  });

  it('⚠️ LEAVE deactivates the actor (role NULL, session killed) and records PRACTICE_MEMBER_REMOVED', async () => {
    asOwner();
    underLock({ id: 'u-2', practiceRole: 'CLINICIAN' });
    const res = await transferOwnershipAction(null, form({ userId: 'u-2', then: 'LEAVE' }));
    expect(res?.ok).toBe(true);
    const leave = prisma.user.updateMany.mock.calls[1][0].data;
    expect(leave).toMatchObject({ isActive: false, deactivatedBy: 'u-owner', practiceRole: null });
    expect(leave.deactivatedAt).toBeInstanceOf(Date);
    expect(leave.forceLogoutAt).toBeInstanceOf(Date);
    const rows = logAudit.mock.calls.map((c) => c[0]);
    expect(rows.map((r) => r.action)).toEqual(['PRACTICE_ROLE_CHANGED', 'PRACTICE_MEMBER_REMOVED']);
    expect(rows[1]).toMatchObject({ targetId: 'u-owner', metadata: { removedRole: 'OWNER', practiceId: 'p-1' } });
    expect(rows[1].metadata.transferId).toBe(rows[0].metadata.transferId);
  });

  it('handing over to an EXISTING co-owner writes no promotion and no promotion row', async () => {
    asOwner();
    underLock({ id: 'u-2', practiceRole: 'OWNER' });
    const res = await transferOwnershipAction(null, form({ userId: 'u-2', then: 'CLINICIAN' }));
    expect(res?.ok).toBe(true);
    expect(prisma.user.updateMany).toHaveBeenCalledOnce();
    expect(prisma.user.updateMany.mock.calls[0][0].where).toMatchObject({ id: 'u-owner' });
    expect(logAudit.mock.calls.map((c) => [c[0].action, c[0].targetId])).toEqual([['PRACTICE_ROLE_CHANGED', 'u-owner']]);
  });

  it('⚠️ a step-down that matches nothing ROLLS BACK the promotion — it throws inside the transaction, never returns', async () => {
    // Returning from the callback would COMMIT the promotion without its paired
    // step-down. The throw is what makes $transaction roll both back.
    asOwner();
    underLock({ id: 'u-2', practiceRole: 'CLINICIAN' });
    prisma.user.updateMany.mockResolvedValueOnce({ count: 1 }).mockResolvedValueOnce({ count: 0 });
    const txResult = vi.fn();
    prisma.$transaction.mockImplementationOnce(async (fn: (tx: unknown) => unknown) => {
      try {
        const v = await fn({ user: prisma.user, $queryRaw: queryRaw, $executeRaw: executeRaw });
        txResult('committed', v);
        return v;
      } catch (e) {
        txResult('rolled-back');
        throw e;
      }
    });
    const res = await transferOwnershipAction(null, form({ userId: 'u-2', then: 'CLINICIAN' }));
    expect(txResult).toHaveBeenCalledWith('rolled-back');
    expect(res && !res.ok && res.reason).toBe('ROLE_CHANGED_UNDER_YOU');
    expect(logAudit).not.toHaveBeenCalled();
  });

  it('a promotion CAS that matches nothing refuses before the actor steps down', async () => {
    asOwner();
    underLock({ id: 'u-2', practiceRole: 'CLINICIAN' });
    prisma.user.updateMany.mockResolvedValueOnce({ count: 0 });
    const res = await transferOwnershipAction(null, form({ userId: 'u-2', then: 'LEAVE' }));
    expect(res && !res.ok && res.reason).toBe('ROLE_CHANGED_UNDER_YOU');
    expect(prisma.user.updateMany).toHaveBeenCalledOnce();
  });

  it('⚠️ a STALE actor hands nothing on', async () => {
    asOwner();
    underLock({ id: 'u-2', practiceRole: 'CLINICIAN' }, null);
    const res = await transferOwnershipAction(null, form({ userId: 'u-2', then: 'LEAVE' }));
    expect(res && !res.ok && res.reason).toBe('ROLE_MAY_NOT_ADMINISTER');
    expect(prisma.user.updateMany).not.toHaveBeenCalled();
  });

  it('⚠️ the TRIGGER refusing is spoken as LAST_OWNER, audited with the transferId', async () => {
    asOwner();
    underLock({ id: 'u-2', practiceRole: 'CLINICIAN' });
    prisma.user.updateMany.mockResolvedValueOnce({ count: 1 }).mockRejectedValueOnce(TRIGGER_REFUSAL);
    const res = await transferOwnershipAction(null, form({ userId: 'u-2', then: 'LEAVE' }));
    expect(res).toMatchObject({ ok: false, reason: 'LAST_OWNER', message: LAST_OWNER_REFUSAL });
    expect(logAudit.mock.calls.map((c) => c[0].action)).toEqual(['PRACTICE_ADMIN_REFUSED']);
    expect(logAudit.mock.calls[0][0].metadata).toMatchObject({ refusal: 'LAST_OWNER', attempted: 'TRANSFER', then: 'LEAVE' });
    expect(logAudit.mock.calls[0][0].metadata.transferId).toMatch(/^[0-9a-f-]{36}$/);
  });
});

describe('⚠️ minting a seat', () => {
  it('sets BOTH practiceId and practiceRole — the database refuses them apart', async () => {
    asOwner();
    prisma.inviteCode.create.mockResolvedValue({ id: 'inv-1' });
    const res = await mintSeatInviteAction(null, form({ role: 'TECH', label: 'New tech' }));
    expect(res?.ok).toBe(true);
    const data = prisma.inviteCode.create.mock.calls[0][0].data;
    expect(data.practiceId).toBe('p-1');
    expect(data.practiceRole).toBe('TECH');
    // ⚠️ ONE USE. A seat is a person; a reusable code handed to one hire admits
    // everyone they forward it to.
    expect(data.maxUses).toBe(1);
  });

  it('⚠️ NEITHER THE RAW CODE NOR ITS HASH REACHES AN AUDIT ROW', async () => {
    asOwner();
    prisma.inviteCode.create.mockResolvedValue({ id: 'inv-1' });
    const res = await mintSeatInviteAction(null, form({ role: 'CLINICIAN', label: 'Dr A' }));
    expect(res?.ok).toBe(true);
    const code = res && res.ok ? res.code : '';
    const hash = prisma.inviteCode.create.mock.calls[0][0].data.codeHash;
    const audit = JSON.stringify(logAudit.mock.calls.at(-1)?.[0]);
    // An audit row carrying the hash lets a database read mint signups — the
    // exact property `codeHash` exists to deny.
    expect(audit).not.toContain(code);
    expect(audit).not.toContain(hash);
    expect(logAudit.mock.calls.at(-1)?.[0].action).toBe('PRACTICE_SEAT_INVITED');
  });

  it('the code is returned ONCE and the row stores only a hash of it', async () => {
    asOwner();
    prisma.inviteCode.create.mockResolvedValue({ id: 'inv-1' });
    const res = await mintSeatInviteAction(null, form({ role: 'TECH', label: 'x' }));
    const stored = prisma.inviteCode.create.mock.calls[0][0].data.codeHash;
    expect(res?.ok).toBe(true);
    expect(stored).toMatch(/^[0-9a-f]{64}$/);
    expect(stored).not.toBe(res && res.ok ? res.code : '');
  });

  it('an SSN-shaped label is refused — the invite table is outside clinical retention', async () => {
    asOwner();
    const res = await mintSeatInviteAction(null, form({ role: 'TECH', label: 'ssn 123-45-6789' }));
    expect(res?.ok).toBe(false);
    expect(prisma.inviteCode.create).not.toHaveBeenCalled();
  });

  it('an empty label is refused, and a normal one is not — the arm above is not refusing everything', async () => {
    asOwner();
    prisma.inviteCode.create.mockResolvedValue({ id: 'inv-1' });
    expect((await mintSeatInviteAction(null, form({ role: 'TECH', label: '   ' })))?.ok).toBe(false);
    expect((await mintSeatInviteAction(null, form({ role: 'TECH', label: 'Locum cover' })))?.ok).toBe(true);
  });
});

describe('the seat code itself', () => {
  it('carries no letter a human confuses when reading it aloud', () => {
    // Crockford-style: no I, L, O or U — so a code read over the phone cannot be
    // transcribed into a different one, and cannot spell anything.
    const code = generateInviteCode();
    expect(code).toMatch(/^[0-9A-HJKMNP-TV-Z]{4}(-[0-9A-HJKMNP-TV-Z]{4}){3}$/);
    expect(code).not.toMatch(/[ILOU]/);
  });

  it('does not repeat across calls', () => {
    const seen = new Set(Array.from({ length: 50 }, () => generateInviteCode()));
    expect(seen.size).toBe(50);
  });
});
