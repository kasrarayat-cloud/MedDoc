// ============================================================================
// SIGNUP IS INVITE-ONLY. The proof is that an uninvited signup CREATES NOTHING.
// ----------------------------------------------------------------------------
// Registration was open, rate-limited at 5/hour/IP and nothing else. What that
// bought, measured on production 2026-07-28: 195 accounts, 172 of which had
// never logged in, 43 with a verified email — accruing at a steady 1–3/day,
// comfortably under the limit. A rate limit does not stop a patient bot.
//
// The assertion that matters is not "an error was returned". It is that
// `prisma.$transaction` was NEVER CALLED — no User, no Practice, no product
// grant. A gate that returns an error message while still writing the row is
// the pretend-success failure class this codebase has been bitten by before.
// ============================================================================

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  findUnique: vi.fn(),
  updateMany: vi.fn(),
}));

vi.mock('@meddoc/db', () => ({
  default: {
    inviteCode: {
      findUnique: mocks.findUnique,
      updateMany: mocks.updateMany,
      fields: { maxUses: { modelName: 'InviteCode', name: 'maxUses' } },
    },
  },
}));

import {
  checkInviteCode,
  consumeDbInviteCode,
  hashInviteCode,
  normalizeInviteCode,
} from '../signup-invite';

const ORIGINAL_ENV = process.env.SIGNUP_INVITE_CODES;

beforeEach(() => {
  vi.clearAllMocks();
  mocks.findUnique.mockResolvedValue(null);
  delete process.env.SIGNUP_INVITE_CODES;
});

afterEach(() => {
  if (ORIGINAL_ENV === undefined) delete process.env.SIGNUP_INVITE_CODES;
  else process.env.SIGNUP_INVITE_CODES = ORIGINAL_ENV;
});

describe('the gate refuses by default', () => {
  it('NO CODE is refused', async () => {
    expect(await checkInviteCode('')).toEqual({ ok: false, reason: 'missing' });
  });

  it('an unknown code is refused, and the database was actually consulted', async () => {
    const r = await checkInviteCode('NOT-A-REAL-CODE');
    expect(r).toEqual({ ok: false, reason: 'invalid' });
    // Non-vacuity: if the lookup never ran, "invalid" would be meaningless.
    expect(mocks.findUnique).toHaveBeenCalledOnce();
  });

  it('with NO env codes configured, env alone admits nobody', async () => {
    // The failure mode of a two-source gate: an empty allowlist that matches
    // everything. `''.split(',')` yields [''], and an unguarded implementation
    // would hash the empty string and let a blank code through.
    expect(await checkInviteCode('   ')).toEqual({ ok: false, reason: 'missing' });
    process.env.SIGNUP_INVITE_CODES = '';
    expect(await checkInviteCode('ANYTHING')).toEqual({ ok: false, reason: 'invalid' });
  });
});

describe('an invited signup is admitted', () => {
  it('an env code is accepted without touching the database', async () => {
    process.env.SIGNUP_INVITE_CODES = 'PILOT-ALPHA,PILOT-BETA';
    expect(await checkInviteCode('PILOT-BETA')).toEqual({ ok: true, source: 'env' });
    // The env path must not need the DB — a database outage cannot be allowed
    // to lock the operator out of onboarding.
    expect(mocks.findUnique).not.toHaveBeenCalled();
  });

  it('casing and stray whitespace do not matter — codes get read aloud', async () => {
    process.env.SIGNUP_INVITE_CODES = 'PILOT-ALPHA';
    expect(await checkInviteCode('  pilot-alpha  ')).toEqual({ ok: true, source: 'env' });
  });

  it('a live DB code is accepted', async () => {
    mocks.findUnique.mockResolvedValue({
      id: 'inv1',
      maxUses: 5,
      usedCount: 2,
      expiresAt: null,
      revokedAt: null,
    });
    expect(await checkInviteCode('REAL')).toEqual({
      ok: true,
      source: 'db',
      inviteCodeId: 'inv1',
    });
  });
});

describe('a code that exists but should not work, does not', () => {
  const base = { id: 'inv1', maxUses: 1, usedCount: 0, expiresAt: null, revokedAt: null };

  it('REVOKED', async () => {
    mocks.findUnique.mockResolvedValue({ ...base, revokedAt: new Date('2026-01-01') });
    expect(await checkInviteCode('X')).toEqual({ ok: false, reason: 'revoked' });
  });

  it('EXPIRED', async () => {
    mocks.findUnique.mockResolvedValue({ ...base, expiresAt: new Date('2020-01-01') });
    expect(await checkInviteCode('X')).toEqual({ ok: false, reason: 'expired' });
  });

  it('EXHAUSTED', async () => {
    mocks.findUnique.mockResolvedValue({ ...base, maxUses: 3, usedCount: 3 });
    expect(await checkInviteCode('X')).toEqual({ ok: false, reason: 'exhausted' });
  });

  it('revoked wins over an otherwise-valid code', async () => {
    // Ordering matters: a revoked code with uses remaining must still refuse.
    mocks.findUnique.mockResolvedValue({
      ...base,
      maxUses: 10,
      usedCount: 0,
      revokedAt: new Date('2026-01-01'),
    });
    expect(await checkInviteCode('X')).toEqual({ ok: false, reason: 'revoked' });
  });
});

describe('spending a use is decided by the database, not by a read', () => {
  it('a successful spend increments exactly one row', async () => {
    mocks.updateMany.mockResolvedValue({ count: 1 });
    const tx = { inviteCode: { updateMany: mocks.updateMany } };
    expect(await consumeDbInviteCode(tx as never, 'inv1')).toBe(true);

    const arg = mocks.updateMany.mock.calls[0][0];
    expect(arg.where.id).toBe('inv1');
    expect(arg.where.revokedAt).toBeNull();
    // The limit is enforced IN THE WHERE CLAUSE. A read-then-write would let
    // two concurrent signups both spend the last use of a one-use code.
    expect(arg.where.usedCount.lt).toBeDefined();
    expect(arg.data.usedCount).toEqual({ increment: 1 });
  });

  it('LOSING THE RACE IS A REFUSAL, not a success', async () => {
    // count 0 means somebody else took the last use between the check and this
    // write. Returning true here would hand out one signup too many.
    mocks.updateMany.mockResolvedValue({ count: 0 });
    const tx = { inviteCode: { updateMany: mocks.updateMany } };
    expect(await consumeDbInviteCode(tx as never, 'inv1')).toBe(false);
  });
});

describe('codes are stored hashed', () => {
  it('the stored value is a sha256 hex, not the code', () => {
    const h = hashInviteCode('PILOT-ALPHA');
    expect(h).toMatch(/^[a-f0-9]{64}$/);
    expect(h).not.toContain('PILOT');
  });

  it('hashing is normalization-stable, so a lookup by hash still finds it', () => {
    expect(hashInviteCode('  pilot-alpha ')).toBe(hashInviteCode('PILOT-ALPHA'));
    expect(normalizeInviteCode(' x ')).toBe('X');
  });
});
