// ============================================================================
// GATE — ADMIN-1: WHO MAY ADMINISTER A PRACTICE, AND WHAT THAT PERMITS.
// ----------------------------------------------------------------------------
// ⚠️ WHAT WOULD MAKE THIS FILE FAIL, stated first:
//   · OWNER stops being assignable             -> the not-exclusive block
//   · the assignable enum stops constraining   -> the not-exclusive block
//   · the guard reads the SESSION's role       -> the staleness block
//   · a refusal stops being audited            -> the audit block
//   · the self-demotion guard is removed       -> the role-change block
//   · an OWNER becomes demotable               -> the role-change block
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
const { prisma, logAudit, getSession, queryRaw } = vi.hoisted(() => {
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
    $transaction: vi.fn(async (fn: (tx: unknown) => unknown) =>
      fn({ user, $queryRaw: queryRaw })
    ),
  };
  return { prisma, logAudit: vi.fn(), getSession: vi.fn(), queryRaw };
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
} from '../../actions/practice-members';

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
    // page does not render — and CANNOT_CHANGE_AN_OWNER then refuses to ever
    // move it, because this action is the only practiceRole write in the app.
    // The listing already filters; the target lookup did not.
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

  it("an OWNER's role cannot be changed — which is what keeps 'every practice has an owner' structural", async () => {
    asOwner();
    prisma.user.findFirst.mockResolvedValue({ id: 'u-2', practiceRole: 'OWNER' });
    const res = await changeMemberRoleAction(null, form({ userId: 'u-2', role: 'TECH' }));
    expect(res && !res.ok && res.reason).toBe('CANNOT_CHANGE_AN_OWNER');
    expect(prisma.user.update).not.toHaveBeenCalled();
  });

  it('⚠️ the OWNER refusal is UNCONDITIONAL — it does not depend on the target role being outside the set', async () => {
    // ⚠️ THIS IS THE ARM THE WIDENING MADE NECESSARY, AND IT IS THE ONE A
    // CARELESS REFACTOR DELETES. Before the ruling, "you cannot demote an
    // owner" was ALSO enforced incidentally by `RoleSchema`, because every
    // reachable target role was CLINICIAN or TECH. Now OWNER is a legal target,
    // so the only thing standing between an owner and a role write is the
    // explicit `CANNOT_CHANGE_AN_OWNER` branch. Asking for OWNER -> OWNER is
    // the case that isolates it: the schema accepts it, and the guard must
    // still refuse BEFORE any update.
    asOwner();
    prisma.user.findFirst.mockResolvedValue({ id: 'u-2', practiceRole: 'OWNER' });
    const res = await changeMemberRoleAction(null, form({ userId: 'u-2', role: 'OWNER' }));
    expect(res && !res.ok && res.reason).toBe('CANNOT_CHANGE_AN_OWNER');
    expect(prisma.user.update).not.toHaveBeenCalled();
  });

  it('⚠️ the refusal message no longer says the question is unsettled — promotion IS settled', () => {
    // A message that still read "who may promote and demote an owner is not
    // settled" would be false in the doctor's face the day promotion shipped.
    expect(ADMIN_REFUSAL_MESSAGE.CANNOT_CHANGE_AN_OWNER).not.toMatch(/not settled/i);
    expect(ADMIN_REFUSAL_MESSAGE.CANNOT_CHANGE_AN_OWNER).toMatch(/demot|remov/i);
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
    // ⚠️ A NON-OWNER TARGET, AND THE REASON IS A REAL PROPERTY OF THIS DOOR.
    // `CANNOT_CHANGE_AN_OWNER` (practice-members.ts) refuses to move an OWNER
    // row AT ALL, so an owner DEMOTION is unreachable from here — it lives on
    // ADMIN-5's door (PR #1026). Writing this arm against an OWNER target
    // measures the refusal, not the lock, and it did on its first run.
    // The lock wraps EVERY role change regardless, which is the conservative
    // choice: the next door added to this file inherits it.
    asOwner();
    prisma.user.findFirst.mockResolvedValue({ id: 'u-2', practiceRole: 'CLINICIAN' });
    const res = await changeMemberRoleAction(null, form({ userId: 'u-2', role: 'TECH' }));
    expect(res?.ok).toBe(true);

    // The lock query ran, and it is the advisory lock rather than the level probe.
    const lockCalls = queryRaw.mock.calls.filter((c) =>
      String(c[0]).includes('pg_advisory_xact_lock')
    );
    expect(lockCalls.length, 'the demotion never took the practice lock').toBe(1);

    // ⚠️ ORDER, BY INVOCATION INDEX — the property the deadlock turns on.
    // `invocationCallOrder` is vitest's global monotonic counter, so it orders
    // calls ACROSS two different spies, which is exactly what is needed here:
    // the lock is on `$queryRaw` and the write is on `user.updateMany`.
    const lockAt = Math.min(...queryRaw.mock.invocationCallOrder);
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
