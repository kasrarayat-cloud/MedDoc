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
const { prisma, logAudit, getSession, changeRoleGuarded, removeMemberGuarded } = vi.hoisted(() => ({
  changeRoleGuarded: vi.fn(),
  removeMemberGuarded: vi.fn(),
  prisma: {
    user: {
      findUnique: vi.fn(),
      findFirst: vi.fn(),
      update: vi.fn(),
      updateMany: vi.fn(),
      findMany: vi.fn(),
    },
    inviteCode: { create: vi.fn(), updateMany: vi.fn(), findMany: vi.fn() },
  },
  logAudit: vi.fn(),
  getSession: vi.fn(),
}));

vi.mock('@meddoc/db', () => ({ default: prisma }));
vi.mock('@/lib/audit', () => ({ logAudit }));
vi.mock('@/lib/auth', () => ({ getSession }));
vi.mock('next/cache', () => ({ revalidatePath: vi.fn() }));
// ⚠️ THE GUARD IS MOCKED HERE, AND THIS FILE SAYS SO RATHER THAN IMPLYING
// COVERAGE IT DOES NOT HAVE. These arms prove the ACTION routes to the guard and
// speaks its outcomes; they prove NOTHING about whether the guard is correct
// under concurrency, because this harness mocks Prisma entirely and cannot
// produce an interleaving. That proof is `tests/e2e/scenarios/40-admin5-last-owner.spec.ts`,
// which races the SHIPPED SQL against a real Postgres.
vi.mock('@/lib/practice-owner-guard', () => ({ changeRoleGuarded, removeMemberGuarded }));

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
    changeRoleGuarded.mockResolvedValue({ outcome: 'APPLIED', from: 'CLINICIAN' });
    const res = await changeMemberRoleAction(null, form({ userId: 'u-2', role: 'OWNER' }));
    expect(res?.ok).toBe(true);
    expect(changeRoleGuarded).toHaveBeenCalledWith({
      practiceId: 'p-1',
      userId: 'u-2',
      toRole: 'OWNER',
    });
    // ⚠️ `from` COMES FROM THE GUARD, NOT FROM THE PRE-LOCK SNAPSHOT. `target`
    // was read before the practice was locked, so it can name a role the row no
    // longer held when the UPDATE ran — a false entry in an append-only trail.
    // The guard reports what it saw inside the transaction it wrote in.
    expect(logAudit.mock.calls.at(-1)?.[0].metadata).toMatchObject({
      from: 'CLINICIAN',
      to: 'OWNER',
    });
  });

  it('⚠️ THE WRITE HAPPENS UNDER THE PRACTICE LOCK — the race the widening opened, closed harder', async () => {
    // ⚠️ THE MECHANISM MOVED; THE LESSON DID NOT, AND DELETING THIS ARM WOULD
    // HAVE LOST IT. It was written when the fix was a COMPARE-AND-SET: an
    // adversarial pass on the #195 branch reproduced two concurrent requests,
    // one promoting B to OWNER and one demoting B, both reading B as CLINICIAN,
    // both clearing the guard, and the demotion landing on an OWNER. Until that
    // ruling the shape was INCIDENTALLY safe, because no in-app path could turn
    // a target into an owner between the read and the write.
    //
    // ADMIN-5 replaces the CAS with a practice-scoped row lock plus a single
    // conditional statement, which closes that race STRICTLY MORE than the CAS
    // did — the CAS could only refuse a row that had already moved, whereas the
    // lock prevents the other actor from moving it at all. So the arm asserts
    // what it can still see from here: that this action performs NO role write
    // of its own, and hands the whole decision to the guard.
    //
    // ⚠️ AND IT SAYS WHAT IT CANNOT SEE. This harness mocks Prisma, so it cannot
    // produce an interleaving and cannot prove the lock works. That proof races
    // the SHIPPED SQL against a real Postgres in
    // `tests/e2e/scenarios/40-admin5-last-owner.spec.ts`; here, a second write
    // path appearing beside the guard is the thing being prevented.
    asOwner();
    prisma.user.findFirst.mockResolvedValue({ id: 'u-2', practiceRole: 'CLINICIAN' });
    changeRoleGuarded.mockResolvedValue({ outcome: 'APPLIED', from: 'CLINICIAN' });
    await changeMemberRoleAction(null, form({ userId: 'u-2', role: 'TECH' }));
    expect(changeRoleGuarded).toHaveBeenCalledOnce();
    expect(prisma.user.updateMany).not.toHaveBeenCalled();
    expect(prisma.user.update).not.toHaveBeenCalled();
  });

  it('⚠️ and a guard that wrote NOTHING refuses rather than writing a false audit row', async () => {
    // The row moved under us. The pre-guard code would have written the audit
    // row from its stale snapshot — `from: CLINICIAN` for a row that was OWNER
    // when the UPDATE ran. A false entry in an append-only trail is worse than
    // a missing one, so the refusal writes nothing at all.
    asOwner();
    prisma.user.findFirst.mockResolvedValue({ id: 'u-2', practiceRole: 'CLINICIAN' });
    changeRoleGuarded.mockResolvedValue({ outcome: 'TARGET_MOVED' });
    const res = await changeMemberRoleAction(null, form({ userId: 'u-2', role: 'TECH' }));
    expect(res && !res.ok && res.reason).toBe('ROLE_CHANGED_UNDER_YOU');
    expect(logAudit).not.toHaveBeenCalled();
  });

  it('⚠️ a DEACTIVATED member is not a promotion target — an invisible owner could never be revoked', async () => {
    // A removed member keeps their practiceId, so the row stays findable by
    // id+practice. Writing OWNER onto such a row produces an owner the members
    // page does not render. The listing already filters; the target lookup did
    // not.
    //
    // ⚠️ THE OLD JUSTIFICATION HERE WAS FALSE IN TWO WAYS AND IS REPLACED, NOT
    // TRIMMED: removal now NULLs practiceRole (it does not "leave it intact"),
    // and `changeMemberRoleAction` was never "the only practiceRole write in
    // the app" — the legacy system-admin app's `activateUserAction` writes
    // OWNER onto a NULL-role user. The arm itself is unchanged and still
    // valuable; only its reasoning was wrong.
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

  it("⚠️ ADMIN-5 — an OWNER's role CAN be changed now, and the invariant moved to the database", async () => {
    // ⚠️ THIS ARM USED TO ASSERT THE OPPOSITE, AND THE INVERSION IS THE POINT.
    // It read "an OWNER's role cannot be changed — which is what keeps 'every
    // practice has an owner' structural". That refusal was the invariant. It is
    // now enforced by `changeRoleGuarded`, so the arm asserts the ROUTING: the
    // action must hand the decision to the guard rather than make it here.
    asOwner();
    prisma.user.findFirst.mockResolvedValue({ id: 'u-2', practiceRole: 'OWNER' });
    changeRoleGuarded.mockResolvedValue({ outcome: 'APPLIED', from: 'OWNER' });
    const res = await changeMemberRoleAction(null, form({ userId: 'u-2', role: 'TECH' }));
    expect(res?.ok).toBe(true);
    expect(changeRoleGuarded).toHaveBeenCalledWith({
      practiceId: 'p-1',
      userId: 'u-2',
      toRole: 'TECH',
    });
    // ⚠️ AND THE ACTION MUST NOT WRITE THE ROW ITSELF. A second write path
    // beside the guard is a second door to the invariant, which is the exact
    // defect removal nearly shipped with.
    expect(prisma.user.update).not.toHaveBeenCalled();
    expect(prisma.user.updateMany).not.toHaveBeenCalled();
  });

  it('⚠️ the LAST OWNER is refused, the refusal is AUDITED, and the doctor is told what to do', async () => {
    asOwner();
    prisma.user.findFirst.mockResolvedValue({ id: 'u-2', practiceRole: 'OWNER' });
    changeRoleGuarded.mockResolvedValue({ outcome: 'LAST_OWNER' });
    const res = await changeMemberRoleAction(null, form({ userId: 'u-2', role: 'TECH' }));
    expect(res && !res.ok && res.reason).toBe('LAST_OWNER');
    // ⚠️ THE MESSAGE MUST SAY WHAT TO DO NEXT. "Refused" alone leaves a doctor
    // with a partner leaving and no route; the recovery is one sentence and it
    // is the difference between a guard and a wall.
    expect(res && !res.ok && res.message).toMatch(/make someone else an owner/i);
    expect(logAudit).toHaveBeenCalledWith(
      expect.objectContaining({
        action: 'PRACTICE_ADMIN_REFUSED',
        metadata: expect.objectContaining({ refusal: 'LAST_OWNER', attempted: 'ROLE_CHANGE' }),
      }),
    );
  });

  it('⚠️ a row that moved under the guard fails CLOSED, and writes NO audit row', async () => {
    asOwner();
    prisma.user.findFirst.mockResolvedValue({ id: 'u-2', practiceRole: 'CLINICIAN' });
    changeRoleGuarded.mockResolvedValue({ outcome: 'TARGET_MOVED' });
    const res = await changeMemberRoleAction(null, form({ userId: 'u-2', role: 'TECH' }));
    expect(res && !res.ok && res.reason).toBe('ROLE_CHANGED_UNDER_YOU');
    // An append-only trail that records changes which did not happen is worse
    // than one that misses none.
    expect(logAudit).not.toHaveBeenCalled();
  });

  it('⚠️ OWNER -> OWNER is a NO-OP and never reaches the guard — the arm #195 said not to delete', async () => {
    // ⚠️ KEPT, RE-AIMED, NOT DELETED. Ruling #195 recorded this arm with the
    // instruction "do not delete it as redundant — it stopped being redundant
    // the moment the list widened", and ADMIN-5 is exactly the refactor that
    // would have deleted it. What it isolates has changed, and the new target
    // is sharper than the old one:
    //
    // the last-owner clause cannot tell a lateral OWNER -> OWNER from a
    // demotion — both have a current role of OWNER — so if this reached the
    // guard, a SOLO owner re-asserting their own role would be REFUSED for want
    // of a second owner. The no-op arm above the guard is what prevents that,
    // and this is the only test that can see it.
    asOwner();
    prisma.user.findFirst.mockResolvedValue({ id: 'u-2', practiceRole: 'OWNER' });
    const res = await changeMemberRoleAction(null, form({ userId: 'u-2', role: 'OWNER' }));
    expect(res?.ok).toBe(true);
    expect(changeRoleGuarded).not.toHaveBeenCalled();
    expect(prisma.user.update).not.toHaveBeenCalled();
    // A no-op writes no row: the trail records changes that happened.
    expect(logAudit).not.toHaveBeenCalled();
  });

  it('⚠️ no refusal message promises a capability that now exists', () => {
    // ⚠️ THIS ARM TRACKED A MESSAGE THAT NO LONGER EXISTS, AND ITS SUBJECT MOVED
    // RATHER THAN VANISHING. It used to pin `CANNOT_CHANGE_AN_OWNER` — first
    // against "not settled", then against naming demotion. ADMIN-5 retires that
    // refusal, so the arm now pins the CLASS: a message that tells the doctor to
    // ask support for something the page in front of them does is the defect,
    // whichever string carries it.
    for (const [reason, message] of Object.entries(ADMIN_REFUSAL_MESSAGE)) {
      expect(message, `${reason} still sends the doctor to support`).not.toMatch(
        /ask support/i,
      );
      expect(message, `${reason} still claims a capability is unbuilt`).not.toMatch(
        /isn't available yet|not available yet|yet\b.*demot/i,
      );
    }
    // And the refusal that IS still real says the recoverable thing.
    expect(ADMIN_REFUSAL_MESSAGE.LAST_OWNER).toMatch(/make someone else an owner/i);
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
    changeRoleGuarded.mockResolvedValue({ outcome: 'APPLIED', from: 'CLINICIAN' });
    const res = await changeMemberRoleAction(null, form({ userId: 'u-2', role: 'TECH' }));
    expect(res?.ok).toBe(true);
    expect(changeRoleGuarded).toHaveBeenCalledOnce();
    const audit = logAudit.mock.calls.at(-1)?.[0];
    expect(audit.action).toBe('PRACTICE_ROLE_CHANGED');
    expect(audit.metadata).toMatchObject({ from: 'CLINICIAN', to: 'TECH' });
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
