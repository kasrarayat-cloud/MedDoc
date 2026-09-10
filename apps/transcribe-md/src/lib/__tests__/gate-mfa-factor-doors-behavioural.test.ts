// @vitest-environment node
// ============================================================================
// THE DOORS THAT CHANGE AN ACCOUNT'S SECOND FACTOR — DRIVEN
// ----------------------------------------------------------------------------
// Both admin gates admit on `users.mfaEnabled`. That flag means "the owner
// controls this account's factor" only while nobody can REPLACE the factor
// without proving they hold it. The PR #952 refutation round (bypass[1],
// re-verified) showed /api/mfa/enroll did exactly that: for an already-enrolled
// user it overwrote `mfaSecret` with a fresh secret, returned it to the caller,
// left `mfaEnabled=true`, and asked for nothing but a session cookie. Login
// then checked TOTP against the caller's secret, not the owner's.
//
// Re-enrolment therefore goes through /api/mfa/disable, which requires the
// password AND the current factor (TOTP or a recovery code), and only then
// back through enroll. These arms run both real route handlers against an
// in-memory user row, with real otplib and real bcrypt.
// ============================================================================

import bcrypt from 'bcryptjs';
import { generateSync } from 'otplib';
import type { NextRequest } from 'next/server';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const h = vi.hoisted(() => ({
  row: {} as Record<string, unknown>,
  update: vi.fn(),
  updateMany: vi.fn(),
  auth: vi.fn(),
  logAudit: vi.fn(),
}));

vi.mock('@meddoc/db', () => ({
  default: {
    user: {
      findUnique: vi.fn(async () => ({ ...h.row })),
      update: h.update,
      updateMany: h.updateMany,
    },
  },
}));
vi.mock('@/lib/nextauth', () => ({ auth: h.auth }));
vi.mock('@/lib/audit', () => ({ logAudit: h.logAudit }));

import { POST as ENROLL } from '../../app/api/mfa/enroll/route';
import { POST as DISABLE } from '../../app/api/mfa/disable/route';

/** The OWNER's authenticator secret. */
const S1 = 'JBSWY3DPEHPK3PXPJBSWY3DPEHPK3PXP';
const PASSWORD = 'correct horse battery staple';
const HASH = bcrypt.hashSync(PASSWORD, 4);
const VERIFIED_AT = new Date('2026-09-01T00:00:00.000Z');

const totp = (secret: string) => generateSync({ secret });
const ctx = { params: Promise.resolve({}) };
const post = (body?: unknown) =>
  new Request('https://app.example.test/api/mfa/x', {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: body === undefined ? '{}' : JSON.stringify(body),
  }) as unknown as NextRequest;

function seat(row: Record<string, unknown>) {
  for (const k of Object.keys(h.row)) delete h.row[k];
  Object.assign(h.row, {
    id: 'u-1',
    email: 'u1@example.test',
    practiceId: 'p-1',
    role: 'DOCTOR',
    products: ['TRANSCRIBE_MD'],
    passwordHash: HASH,
    mfaBackupCodes: ['hash-1'],
    ...row,
  });
}

beforeEach(() => {
  vi.clearAllMocks();
  h.update.mockImplementation(async ({ data }: { data: Record<string, unknown> }) => {
    Object.assign(h.row, data);
    return { ...h.row };
  });
  // Honours the WHERE the way Postgres would: a conditional write whose
  // predicate no longer matches changes nothing and reports count 0.
  h.updateMany.mockImplementation(
    async ({ where, data }: { where: Record<string, unknown>; data: Record<string, unknown> }) => {
      const matches = Object.entries(where).every(([k, v]) => h.row[k] === v);
      if (!matches) return { count: 0 };
      Object.assign(h.row, data);
      return { count: 1 };
    }
  );
  h.auth.mockResolvedValue({ user: { id: 'u-1', email: 'u1@example.test', sessionId: 's-1' } });
});

describe('/api/mfa/enroll — cannot replace a factor that is already enrolled', () => {
  it('an ENROLLED user is refused, and the owner\'s secret is untouched', async () => {
    seat({ mfaEnabled: true, mfaSecret: S1, mfaVerifiedAt: VERIFIED_AT });
    const res = await ENROLL(post(), ctx);
    const body = await res.json();

    expect(res.status, 'enroll replaced the factor of an enrolled account').toBe(409);
    expect(body.code).toBe('MFA_ALREADY_ENABLED');
    expect(body.otpauthUri, 'a secret was handed to the caller').toBeUndefined();
    // ⚠️ The ROW is the claim, not the status: a refusal returned AFTER the
    // write would give the same 409 with the owner's factor already gone.
    expect(h.row.mfaSecret).toBe(S1);
    expect(h.row.mfaVerifiedAt).toBe(VERIFIED_AT);
    expect(h.row.mfaEnabled).toBe(true);
    expect(h.update).not.toHaveBeenCalled();
  });

  it('POSITIVE CONTROL — an UN-enrolled user can still enrol (the recovery path)', async () => {
    seat({ mfaEnabled: false, mfaSecret: null, mfaVerifiedAt: null });
    const res = await ENROLL(post(), ctx);
    const body = await res.json();

    expect(res.status).toBe(200);
    expect(typeof h.row.mfaSecret).toBe('string');
    expect(String(body.otpauthUri)).toContain(String(h.row.mfaSecret));
    // Staged only: enrolment completes at verify-enrollment.
    expect(h.row.mfaEnabled).toBe(false);
  });
});

describe('/api/mfa/disable — requires the password AND the current factor', () => {
  beforeEach(() => seat({ mfaEnabled: true, mfaSecret: S1, mfaVerifiedAt: VERIFIED_AT }));

  const unchanged = () => {
    expect(h.row.mfaEnabled, 'MFA was disabled without the current factor').toBe(true);
    expect(h.row.mfaSecret).toBe(S1);
    expect(h.update).not.toHaveBeenCalled();
  };

  it('password but NO factor -> 400 TOKEN_REQUIRED, nothing changes', async () => {
    const res = await DISABLE(post({ password: PASSWORD }), ctx);
    expect(res.status).toBe(400);
    expect((await res.json()).code).toBe('TOKEN_REQUIRED');
    unchanged();
  });

  it('password and a WRONG code -> 400 INVALID_SECOND_FACTOR, nothing changes', async () => {
    const good = totp(S1);
    const wrong = good === '000000' ? '111111' : '000000';
    const res = await DISABLE(post({ password: PASSWORD, token: wrong }), ctx);
    expect(res.status).toBe(400);
    expect((await res.json()).code).toBe('INVALID_SECOND_FACTOR');
    unchanged();
  });

  it('the right code but a WRONG password -> 400 WRONG_PASSWORD, nothing changes', async () => {
    const res = await DISABLE(post({ password: 'not it', token: totp(S1) }), ctx);
    expect(res.status).toBe(400);
    expect((await res.json()).code).toBe('WRONG_PASSWORD');
    unchanged();
  });

  it('POSITIVE CONTROL — password + the current code disables it', async () => {
    const res = await DISABLE(post({ password: PASSWORD, token: totp(S1) }), ctx);
    expect(res.status).toBe(200);
    expect(h.row.mfaEnabled).toBe(false);
    expect(h.row.mfaSecret).toBeNull();
  });
});
