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
import { hasSuperAdminProduct } from '../super-admin';

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

// ============================================================================
// ONE PREDICATE FOR "PLATFORM SUPER_ADMIN" — the disable lock and the gates
// ----------------------------------------------------------------------------
// lockout[1]: both admin gates admit on `Product.SUPER_ADMIN in products`, read
// from the DB row. The disable lock compared `role === 'SUPER_ADMIN'`, a
// different fact. In production both platform SUPER_ADMINs are role DOCTOR, so
// the one enrolled admin could self-disable MFA and was then refused by the
// gates. Every credential below is VALID (password + current code), so the only
// thing that can refuse is the lock.
// ============================================================================

describe('/api/mfa/disable — a platform SUPER_ADMIN cannot remove its factor', () => {
  const tryDisable = async (row: Record<string, unknown>) => {
    seat({ mfaEnabled: true, mfaSecret: S1, mfaVerifiedAt: VERIFIED_AT, ...row });
    const res = await DISABLE(post({ password: PASSWORD, token: totp(S1) }), ctx);
    return { res, body: await res.json() };
  };

  it('products SUPER_ADMIN, role DOCTOR (the production shape) -> 403 SUPER_ADMIN_LOCKED, factor kept', async () => {
    const { res, body } = await tryDisable({
      role: 'DOCTOR',
      products: ['TRANSCRIBE_MD', 'SUPER_ADMIN'],
    });
    expect(res.status, 'a platform SUPER_ADMIN disabled its own MFA').toBe(403);
    expect(body.code).toBe('SUPER_ADMIN_LOCKED');
    expect(h.row.mfaEnabled).toBe(true);
    expect(h.row.mfaSecret).toBe(S1);
    expect(h.update).not.toHaveBeenCalled();
  });

  it('role SUPER_ADMIN without the product is STILL locked (the repair never widens)', async () => {
    const { res, body } = await tryDisable({ role: 'SUPER_ADMIN', products: ['TRANSCRIBE_MD'] });
    expect(res.status).toBe(403);
    expect(body.code).toBe('SUPER_ADMIN_LOCKED');
    expect(h.row.mfaEnabled).toBe(true);
  });

  it('POSITIVE CONTROL — a non-admin with valid credentials can still disable', async () => {
    const { res } = await tryDisable({ role: 'DOCTOR', products: ['TRANSCRIBE_MD'] });
    expect(res.status).toBe(200);
    expect(h.row.mfaEnabled).toBe(false);
  });

  // ⚠️ SAME PREDICATE, NOT MERELY A SIMILAR ONE. The last two rows are shapes
  // Prisma never returns for an enum[] column; they exist to tell the shared
  // array-only predicate apart from a restated `.includes` that is
  // substring-true on the string 'SUPER_ADMIN'. The table is the declared
  // semantics, and the SHARED predicate is held to it too.
  it.each([
    [[], false],
    [['TRANSCRIBE_MD'], false],
    [['SUPER_ADMIN'], true],
    [['TRANSCRIBE_MD', 'SUPER_ADMIN'], true],
    ['SUPER_ADMIN', false],
    [null, false],
  ])('role DOCTOR, products=%j -> locked=%s, exactly as hasSuperAdminProduct says', async (products, locked) => {
    expect(hasSuperAdminProduct(products)).toBe(locked);
    const { res } = await tryDisable({ role: 'DOCTOR', products });
    expect(res.status === 403, `disable lock disagrees with the gates' predicate for ${JSON.stringify(products)}`).toBe(
      locked
    );
  });
});

describe('/settings/security/mfa — the Disable button follows the SAME lock', () => {
  function findEl(n: unknown, type: unknown): { props: Record<string, unknown> } | null {
    if (Array.isArray(n)) {
      for (const c of n) {
        const f = findEl(c, type);
        if (f) return f;
      }
      return null;
    }
    if (n && typeof n === 'object' && 'type' in n) {
      const el = n as { type: unknown; props?: { children?: unknown } };
      if (el.type === type) return el as { props: Record<string, unknown> };
      return findEl(el.props?.children, type);
    }
    return null;
  }

  it.each([
    ['products SUPER_ADMIN, role DOCTOR', { role: 'DOCTOR', products: ['SUPER_ADMIN'] }, true],
    ['role SUPER_ADMIN, no product', { role: 'SUPER_ADMIN', products: [] }, true],
    ['non-admin', { role: 'DOCTOR', products: ['TRANSCRIBE_MD'] }, false],
  ])(
    '%s (row %o) -> disableLocked=%s',
    async (_label, row, locked) => {
      seat({ mfaEnabled: true, mfaSecret: S1, mfaVerifiedAt: VERIFIED_AT, ...row });
      const { default: Page } = await import('../../app/settings/security/mfa/page');
      const { MfaManagementPanel } = await import(
        '../../app/settings/security/mfa/mfa-management-panel'
      );
      const tree = await Page({ searchParams: Promise.resolve({}) });
      const panel = findEl(tree, MfaManagementPanel);
      expect(panel, 'the management panel did not render for an enrolled user').not.toBeNull();
      expect(panel!.props.disableLocked).toBe(locked);
    },
    30_000
  );
});
