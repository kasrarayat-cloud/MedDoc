// ============================================================================
// ADMIN-6a D3 — AN INVITE INTO AN ARCHIVED PRACTICE IS REFUSED
// ----------------------------------------------------------------------------
// Two reads, one door, and each read has its own arm:
//
//   · the PRE-CHECK, at the invite gate, BEFORE the email lookup — so a holder
//     of a code for an archived practice learns nothing about which emails
//     exist (PR-F makes an existing email look like success; a new one would
//     otherwise come back "invite rejected");
//   · the AUTHORITATIVE read, inside the signup transaction — so a practice
//     archived between the gate and the insert still admits nobody, and the
//     user row and the invite spend roll back together.
//
// Both answer with the SAME uniform `INVITE_REJECTED_MESSAGE` as every other
// invite refusal. The reason goes to the operator's audit row only.
// ============================================================================
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  userFindUnique: vi.fn(),
  practiceFindUnique: vi.fn(),
  txPracticeFindUnique: vi.fn(),
  txPracticeCreate: vi.fn(),
  txUserCreate: vi.fn(),
  transaction: vi.fn(),
  inviteFindUnique: vi.fn(),
  inviteUpdateMany: vi.fn(),
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
    practice: { findUnique: mocks.practiceFindUnique },
    $transaction: mocks.transaction,
    inviteCode: {
      findUnique: mocks.inviteFindUnique,
      updateMany: mocks.inviteUpdateMany,
      fields: { maxUses: { modelName: 'InviteCode', name: 'maxUses' } },
    },
    waitlistEntry: { upsert: vi.fn() },
  },
}));
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
import { INVITE_REJECTED_MESSAGE } from '@/lib/signup-invite';

const ORIGINAL_ENV = process.env.SIGNUP_INVITE_CODES;
const EMAIL = 'invited.clinician@example.com';

function form(): FormData {
  const fd = new FormData();
  fd.set('email', EMAIL);
  fd.set('name', 'Invited Clinician');
  fd.set('password', 'CorrectHorse9');
  fd.set('confirmPassword', 'CorrectHorse9');
  fd.set('acceptTerms', 'on');
  fd.set('inviteCode', 'SEAT-INTO-PRACTICE');
  return fd;
}

/** A DB code that admits into an EXISTING practice (T8 membership). */
const MEMBERSHIP_CODE = {
  id: 'inv_T',
  maxUses: 5,
  usedCount: 0,
  expiresAt: null,
  revokedAt: null,
  practiceId: 'prac_T',
  practiceRole: 'CLINICIAN',
};

beforeEach(() => {
  vi.clearAllMocks();
  delete process.env.SIGNUP_INVITE_CODES;
  mocks.checkRateLimit.mockReturnValue({ allowed: true, retryAfterSec: 0 });
  mocks.userFindUnique.mockResolvedValue(null);
  mocks.inviteFindUnique.mockResolvedValue(MEMBERSHIP_CODE);
  mocks.inviteUpdateMany.mockResolvedValue({ count: 1 });
  mocks.practiceFindUnique.mockResolvedValue({ isActive: true });
  mocks.txPracticeFindUnique.mockResolvedValue({ id: 'prac_T', isActive: true });
  mocks.txPracticeCreate.mockResolvedValue({ id: 'p_new' });
  mocks.txUserCreate.mockResolvedValue({ id: 'u_new' });
  mocks.transaction.mockImplementation(async (fn: (tx: unknown) => Promise<void>) => {
    await fn({
      practice: { findUnique: mocks.txPracticeFindUnique, create: mocks.txPracticeCreate },
      user: { create: mocks.txUserCreate },
      inviteCode: { updateMany: mocks.inviteUpdateMany },
    });
  });
  mocks.grantPromoCredit.mockResolvedValue({ granted: false, reason: 'already_granted' });
});

afterEach(() => {
  if (ORIGINAL_ENV === undefined) delete process.env.SIGNUP_INVITE_CODES;
  else process.env.SIGNUP_INVITE_CODES = ORIGINAL_ENV;
});

function refusalAudit() {
  return mocks.logAudit.mock.calls.find(
    (c) => c[0]?.action === 'SIGNUP_REJECTED_NO_INVITE' && c[0]?.metadata?.reason === 'practice_archived',
  )?.[0];
}

describe('ADMIN-6a D3 — invite redemption and the practice flag', () => {
  it('POSITIVE CONTROL — an invite into an ACTIVE practice creates the member there', async () => {
    const res = await signupAction({ ok: false, errors: {} } as never, form());
    expect(res?.ok, `an invite into an active practice was refused — every arm below is vacuous: ${JSON.stringify(res)}`).toBe(true);
    expect(mocks.txUserCreate).toHaveBeenCalledOnce();
    expect(mocks.txUserCreate.mock.calls[0]![0].data).toMatchObject({ practiceId: 'prac_T', practiceRole: 'CLINICIAN' });
  });

  it('⚠️ PRE-CHECK — an archived practice is refused with the UNIFORM message and nothing is written', async () => {
    mocks.practiceFindUnique.mockResolvedValue({ isActive: false });
    const res = (await signupAction({ ok: false, errors: {} } as never, form())) as {
      ok: boolean;
      errors: Record<string, string>;
    };
    expect(res.ok).toBe(false);
    expect(res.errors.inviteCode).toBe(INVITE_REJECTED_MESSAGE);
    expect(mocks.transaction, 'an account was started in an archived practice').not.toHaveBeenCalled();
  });

  it('⚠️ PRE-CHECK runs BEFORE the email lookup — no enumeration oracle for a code holder', async () => {
    mocks.practiceFindUnique.mockResolvedValue({ isActive: false });
    await signupAction({ ok: false, errors: {} } as never, form());
    expect(
      mocks.userFindUnique,
      'the email was looked up first — an existing address would now answer differently from a new one',
    ).not.toHaveBeenCalled();
  });

  it('⚠️ the refusal is RECORDED for the operator, attributed to the practice, WITHOUT the email', async () => {
    mocks.practiceFindUnique.mockResolvedValue({ isActive: false });
    await signupAction({ ok: false, errors: {} } as never, form());
    const row = refusalAudit();
    expect(row, 'the refusal left no audit row').toBeTruthy();
    expect(row.practiceId).toBe('prac_T');
    expect(JSON.stringify(row)).not.toContain(EMAIL);
  });

  it('⚠️ AUTHORITATIVE — archived BETWEEN the gate and the insert: refused, no user, no spend', async () => {
    // The gate saw an active practice; the transaction sees it archived.
    mocks.txPracticeFindUnique.mockResolvedValue({ id: 'prac_T', isActive: false });
    const res = (await signupAction({ ok: false, errors: {} } as never, form())) as {
      ok: boolean;
      errors: Record<string, string>;
    };
    expect(res.ok).toBe(false);
    expect(res.errors.inviteCode, 'the race answered with a different message — a prober can tell the cases apart').toBe(
      INVITE_REJECTED_MESSAGE,
    );
    expect(mocks.txUserCreate, 'a member was created in an archived practice').not.toHaveBeenCalled();
    expect(mocks.inviteUpdateMany, 'the invite was spent on a refused signup').not.toHaveBeenCalled();
    expect(refusalAudit()).toBeTruthy();
  });

  it('a LEGACY code (no membership) never reads the practice flag — a solo signup mints its own', async () => {
    mocks.inviteFindUnique.mockResolvedValue({ ...MEMBERSHIP_CODE, practiceId: null, practiceRole: null });
    const res = await signupAction({ ok: false, errors: {} } as never, form());
    expect(res?.ok).toBe(true);
    expect(mocks.practiceFindUnique).not.toHaveBeenCalled();
    expect(mocks.txPracticeFindUnique).not.toHaveBeenCalled();
    expect(mocks.txPracticeCreate).toHaveBeenCalledOnce();
  });
});
