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
