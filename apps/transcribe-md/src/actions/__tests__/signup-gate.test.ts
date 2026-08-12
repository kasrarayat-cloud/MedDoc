// ============================================================================
// AN UNINVITED SIGNUP CREATES NOTHING.
// ----------------------------------------------------------------------------
// This is the assertion that matters, and it is not "an error was returned".
// It is that `prisma.$transaction` was NEVER CALLED — no User, no Practice, no
// product grant, no auth token, no verification email. A gate that shows an
// error message while still writing the row is the pretend-success class this
// codebase has been bitten by before (`intents:[]` was legal, so a no-tool
// request looked like a question).
//
// The three facts the pilot decision rests on:
//   1. uninvited  → refused, and nothing is written
//   2. invited    → succeeds, and the account is created exactly as before
//   3. waitlist   → a row is written and NO account comes with it
// ============================================================================

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  userFindUnique: vi.fn(),
  transaction: vi.fn(),
  inviteFindUnique: vi.fn(),
  inviteUpdateMany: vi.fn(),
  waitlistUpsert: vi.fn(),
  logAudit: vi.fn(),
  checkRateLimit: vi.fn(),
  createAuthToken: vi.fn(),
  sendEmailVerification: vi.fn(),
  sendAccountExists: vi.fn(),
  signIn: vi.fn(),
  grantPromoCredit: vi.fn(),
}));

vi.mock('@meddoc/db', () => ({
  default: {
    user: { findUnique: mocks.userFindUnique },
    $transaction: mocks.transaction,
    inviteCode: {
      findUnique: mocks.inviteFindUnique,
      updateMany: mocks.inviteUpdateMany,
      fields: { maxUses: { modelName: 'InviteCode', name: 'maxUses' } },
    },
    waitlistEntry: { upsert: mocks.waitlistUpsert },
  },
}));
// B7 step 3c, door 1 of 3 — the signup transaction now grants the $10 promo.
vi.mock('@meddoc/ai', () => ({ grantPromoCredit: mocks.grantPromoCredit }));
vi.mock('next/headers', () => ({ headers: vi.fn(async () => new Map()) }));
vi.mock('@/lib/audit', () => ({ logAudit: mocks.logAudit }));
vi.mock('@/lib/rate-limit', () => ({
  RATE_LIMITS: { SIGNUP: { bucket: 'signup', windows: [] }, LOGIN: { bucket: 'login', windows: [] } },
  checkRateLimit: mocks.checkRateLimit,
  clientIpFromHeaders: () => '203.0.113.9',
}));
vi.mock('@/lib/nextauth', () => ({ signIn: mocks.signIn }));
vi.mock('@/lib/auth-tokens', () => ({ createAuthToken: mocks.createAuthToken }));
vi.mock('@/lib/email-enabled', () => ({ isEmailDeliveryEnabled: () => false }));
vi.mock('@/lib/email-auto-confirm', () => ({ isAutoConfirmDomain: () => false }));
vi.mock('@/lib/email', () => ({
  sendEmailVerification: mocks.sendEmailVerification,
  sendAccountExistsEmail: mocks.sendAccountExists,
}));

import { signupAction } from '../auth';
import { joinWaitlistAction } from '../waitlist';

const ORIGINAL_ENV = process.env.SIGNUP_INVITE_CODES;

/** A signup form that is valid in every respect EXCEPT the invite code, so a
 *  refusal can only be the gate — never a stray validation miss. */
function signupForm(inviteCode: string | null): FormData {
  const fd = new FormData();
  fd.set('email', 'new.doctor@example.com');
  fd.set('name', 'New Doctor');
  fd.set('password', 'CorrectHorse9');
  fd.set('confirmPassword', 'CorrectHorse9');
  fd.set('acceptTerms', 'on');
  if (inviteCode !== null) fd.set('inviteCode', inviteCode);
  return fd;
}

beforeEach(() => {
  vi.clearAllMocks();
  mocks.checkRateLimit.mockReturnValue({ allowed: true, retryAfterSec: 0 });
  mocks.userFindUnique.mockResolvedValue(null);
  mocks.inviteFindUnique.mockResolvedValue(null);
  mocks.transaction.mockImplementation(async (fn: (tx: unknown) => Promise<void>) => {
    await fn({ practice: { create: async () => ({ id: 'p1' }) }, user: { create: async () => ({ id: 'u1' }) }, inviteCode: { updateMany: mocks.inviteUpdateMany } });
  });
  mocks.inviteUpdateMany.mockResolvedValue({ count: 1 });
  mocks.grantPromoCredit.mockResolvedValue({
    granted: true,
    ledgerEntryId: 'le1',
    amountMicroUsd: 10_000_000n,
    balanceAfter: 10_000_000n,
    seq: 1n,
  });
  mocks.createAuthToken.mockResolvedValue({ raw: 'tok' });
  process.env.SIGNUP_INVITE_CODES = 'PILOT-ALPHA';
});

afterEach(() => {
  if (ORIGINAL_ENV === undefined) delete process.env.SIGNUP_INVITE_CODES;
  else process.env.SIGNUP_INVITE_CODES = ORIGINAL_ENV;
});

describe('1. uninvited signup is refused, and NOTHING is written', () => {
  it('no code at all', async () => {
    const res = await signupAction({ ok: false, errors: {} } as never, signupForm(null));
    expect(res?.ok).toBe(false);
    expect(mocks.transaction, 'NO ACCOUNT MAY BE CREATED').not.toHaveBeenCalled();
  });

  it('a wrong code', async () => {
    const res = await signupAction({ ok: false, errors: {} } as never, signupForm('NOPE'));
    expect(res?.ok).toBe(false);
    expect(mocks.transaction, 'NO ACCOUNT MAY BE CREATED').not.toHaveBeenCalled();
  });

  it('the refusal is recorded, WITHOUT the email address', async () => {
    await signupAction({ ok: false, errors: {} } as never, signupForm('NOPE'));
    const call = mocks.logAudit.mock.calls.find(
      (c) => c[0]?.action === 'SIGNUP_REJECTED_NO_INVITE',
    );
    expect(call, 'the operator needs to see refusals').toBeTruthy();
    // A rejected signup is not an account. Logging the address would build the
    // very list the gate exists to prevent.
    expect(JSON.stringify(call?.[0])).not.toContain('new.doctor@example.com');
  });

  it('the gate runs BEFORE the email lookup, so it opens no enumeration oracle', async () => {
    // Signup deliberately returns an identical response for an existing and a
    // new email (PR-F). If the invite check ran after that lookup, a prober
    // without a code could still probe. It must not even get that far.
    await signupAction({ ok: false, errors: {} } as never, signupForm('NOPE'));
    expect(mocks.userFindUnique).not.toHaveBeenCalled();
  });
});

// ============================================================================
// B7 STEP 3c — DOOR 1: A SIGNUP FUNDS ITS PRACTICE, OR IT DOES NOT HAPPEN.
// ----------------------------------------------------------------------------
// ⚠️ THESE ARMS EXIST BECAUSE THE WIRING BROKE THIS FILE, AND THE BREAKAGE WAS
// THE USEFUL PART. `mocks.transaction`'s fake client had no `ledgerEntry`, so
// the grant threw, the signup's own catch swallowed it into `ok: false`, and
// "creates the account" went red — a test written about invite codes correctly
// detecting a change to the money path. Repairing it by teaching the mock to
// grant would have restored green and asserted nothing; these arms are what
// make the repair carry its weight.
// ============================================================================
describe('2b. the signup grants the $10 promo — B7 step 3c, door 1', () => {
  it('grants exactly once, for the practice the signup just minted', async () => {
    await signupAction({ ok: false, errors: {} } as never, signupForm('PILOT-ALPHA'));
    expect(mocks.grantPromoCredit).toHaveBeenCalledOnce();
    expect(mocks.grantPromoCredit.mock.calls[0][0]).toBe('p1');
  });

  it('passes the TRANSACTION CLIENT, not the global prisma', async () => {
    // ⚠️ THE WHOLE SAFETY PROPERTY IS IN THE SECOND ARGUMENT. With `tx`, a
    // failed grant rolls the practice and user back with it. With the global
    // client, the grant is a separate transaction — and a failure leaves a
    // practice that exists, works, and is funded by nobody. Both spellings
    // typecheck and both look correct in review.
    await signupAction({ ok: false, errors: {} } as never, signupForm('PILOT-ALPHA'));
    const [, client] = mocks.grantPromoCredit.mock.calls[0];
    expect(client, 'the grant was not given the transaction client').toBeDefined();
    // It is the object the $transaction mock handed the callback — identified
    // by a member only that fake carries.
    expect((client as { practice?: unknown }).practice).toBeDefined();
  });

  it('A FAILED GRANT CREATES NO ACCOUNT', async () => {
    // The inverse of the arm above, and the reason it matters. If the grant
    // throws, the signup must fail — not succeed with an unfunded practice.
    mocks.grantPromoCredit.mockRejectedValueOnce(new Error('ledger refused'));
    const res = await signupAction({ ok: false, errors: {} } as never, signupForm('PILOT-ALPHA'));
    expect(res?.ok, 'an unfundable signup reported success').toBe(false);
  });

  it('audits the grant — and NOT when the practice already had one', async () => {
    // `already_granted` is the absence of an event (a T8 invite into an
    // existing, already-funded clinic). No row, deliberately — see the schema
    // comment on PROMO_GRANT_CREDITED.
    await signupAction({ ok: false, errors: {} } as never, signupForm('PILOT-ALPHA'));
    expect(
      mocks.logAudit.mock.calls.find((c) => c[0]?.action === 'PROMO_GRANT_CREDITED'),
      'a grant was written with no audit row',
    ).toBeTruthy();

    vi.clearAllMocks();
    mocks.checkRateLimit.mockReturnValue({ allowed: true, retryAfterSec: 0 });
    mocks.userFindUnique.mockResolvedValue(null);
    mocks.inviteFindUnique.mockResolvedValue(null);
    mocks.transaction.mockImplementation(async (fn: (tx: unknown) => Promise<void>) => {
      await fn({
        practice: { create: async () => ({ id: 'p1' }) },
        user: { create: async () => ({ id: 'u1' }) },
        inviteCode: { updateMany: mocks.inviteUpdateMany },
      });
    });
    mocks.grantPromoCredit.mockResolvedValue({ granted: false, reason: 'already_granted' });

    await signupAction({ ok: false, errors: {} } as never, signupForm('PILOT-ALPHA'));
    expect(
      mocks.logAudit.mock.calls.find((c) => c[0]?.action === 'PROMO_GRANT_CREDITED'),
      'audited a grant that never happened',
    ).toBeUndefined();
  });

  it('the audit row carries no PHI and no raw BigInt', async () => {
    await signupAction({ ok: false, errors: {} } as never, signupForm('PILOT-ALPHA'));
    const call = mocks.logAudit.mock.calls.find((c) => c[0]?.action === 'PROMO_GRANT_CREDITED');
    const json = JSON.stringify(call?.[0]);
    // A grant is a fact about a wallet. The doctor's address is not part of it.
    expect(json).not.toContain('new.doctor@example.com');
    expect(json).not.toContain('New Doctor');
    // JSON.stringify throws on a bigint — that it serialised at all is the
    // assertion. The metadata column is JSON.
    expect(json).toContain('10000000');
  });
});

describe('2. an invited signup succeeds', () => {
  it('creates the account', async () => {
    const res = await signupAction(
      { ok: false, errors: {} } as never,
      signupForm('PILOT-ALPHA'),
    );
    expect(mocks.transaction, 'the account MUST be created').toHaveBeenCalledOnce();
    expect(res?.ok).toBe(true);
  });

  it('and a DB-backed code is SPENT in the same transaction', async () => {
    delete process.env.SIGNUP_INVITE_CODES;
    mocks.inviteFindUnique.mockResolvedValue({
      id: 'inv1',
      maxUses: 1,
      usedCount: 0,
      expiresAt: null,
      revokedAt: null,
    });
    await signupAction({ ok: false, errors: {} } as never, signupForm('REAL-CODE'));
    expect(mocks.transaction).toHaveBeenCalledOnce();
    // Spent INSIDE the transaction — if the account rolls back, so does the use.
    expect(mocks.inviteUpdateMany).toHaveBeenCalledOnce();
  });

  it('losing the race for the last use rolls the whole signup back', async () => {
    delete process.env.SIGNUP_INVITE_CODES;
    mocks.inviteFindUnique.mockResolvedValue({
      id: 'inv1',
      maxUses: 1,
      usedCount: 0,
      expiresAt: null,
      revokedAt: null,
    });
    // Somebody else took the last use between the check and the write.
    mocks.inviteUpdateMany.mockResolvedValue({ count: 0 });
    const res = await signupAction(
      { ok: false, errors: {} } as never,
      signupForm('REAL-CODE'),
    );
    expect(res?.ok, 'a code with no uses left must not mint an account').toBe(false);
  });
});

describe('3. the waitlist creates NO account', () => {
  it('writes a waitlist row and nothing else', async () => {
    mocks.waitlistUpsert.mockResolvedValue({ id: 'w1' });
    const fd = new FormData();
    fd.set('email', 'curious@example.com');
    fd.set('name', 'Curious Clinician');
    fd.set('source', 'marketing-home');

    const res = await joinWaitlistAction({ ok: false }, fd);

    expect(res?.ok).toBe(true);
    expect(mocks.waitlistUpsert, 'the row must be written').toHaveBeenCalledOnce();
    // THE POINT OF THE WHOLE CHANGE: a prospect is not a user.
    expect(mocks.transaction, 'NO account').not.toHaveBeenCalled();
    expect(mocks.createAuthToken, 'NO auth token').not.toHaveBeenCalled();
    expect(mocks.signIn, 'NO session').not.toHaveBeenCalled();
  });

  it('a broken write still thanks the person', async () => {
    // Fail soft. A waitlist row is a nicety; telling a prospective customer
    // their details broke something is worse than quietly retrying later.
    mocks.waitlistUpsert.mockRejectedValue(new Error('db down'));
    const fd = new FormData();
    fd.set('email', 'curious@example.com');
    const res = await joinWaitlistAction({ ok: false }, fd);
    expect(res?.ok).toBe(true);
    expect(mocks.transaction).not.toHaveBeenCalled();
  });
});
