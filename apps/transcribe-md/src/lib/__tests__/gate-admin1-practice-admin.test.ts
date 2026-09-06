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
//
// ⚠️ THE TWO SIDES ARE INDEPENDENT AND THIS FILE PROVES BOTH SEPARATELY. The
// OWNER-not-exclusive decision (branch `feat/ruling-195-owner-not-exclusive`)
// opened PROMOTION only. Demotion and removal stay refused, which is what keeps
// "every practice has at least one OWNER" STRUCTURAL — no count, no
// read-then-write race. Deleting the demotion arms because "owners are
// assignable now" is the exact misreading this note exists to stop.
// ============================================================================

import { beforeEach, describe, expect, it, vi } from 'vitest';

// ⚠️ `vi.hoisted`, NOT plain consts. `vi.mock` is hoisted above every
// declaration in the file, so a factory closing over a top-level `const` throws
// `Cannot access 'prisma' before initialization` — and it throws at MODULE LOAD,
// which vitest reports as "no tests" rather than as a failure in any arm.
const { prisma, logAudit, getSession } = vi.hoisted(() => ({
  prisma: {
    user: { findUnique: vi.fn(), findFirst: vi.fn(), update: vi.fn(), findMany: vi.fn() },
    inviteCode: { create: vi.fn(), updateMany: vi.fn(), findMany: vi.fn() },
  },
  logAudit: vi.fn(),
  getSession: vi.fn(),
}));

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
    expect(prisma.user.update).toHaveBeenCalledOnce();
    expect(prisma.user.update.mock.calls[0][0].data).toMatchObject({ practiceRole: 'OWNER' });
    expect(logAudit.mock.calls.at(-1)?.[0].metadata).toMatchObject({
      from: 'CLINICIAN',
      to: 'OWNER',
    });
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
    expect(prisma.user.update).toHaveBeenCalledOnce();
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
