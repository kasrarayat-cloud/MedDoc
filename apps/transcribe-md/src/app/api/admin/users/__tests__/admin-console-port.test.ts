/**
 * THE CONSOLE PORT (#310 step 3) — the ported doors, DRIVEN.
 * ----------------------------------------------------------------------------
 * `gate-admin5-doors-behavioural` proves the lock and the strand refusal for
 * every door. This file proves what each ported door does that the retired
 * meddoc-pro original did DIFFERENTLY — the corrections are the point of the
 * port, and a correction nobody pins is one edit from being undone:
 *
 *   deactivate  writes the three deactivation columns together + forceLogoutAt
 *   profile     refuses `email` (strict body) — no unverified address change
 *   sessions    reads `user_sessions`, never returns the bearer `sessionToken`
 *   revoke      finds the session by id AND user — never another person's
 *   create      existing practice only, explicit role, TRANSCRIBE_MD, no
 *               admin-typed password, credential by the reset-token email
 *   unsuspend   gains the orphan refusal it never had (raw 500 before)
 */
import { beforeEach, describe, expect, it, vi } from 'vitest';

const {
  prisma,
  wouldStrandPractice,
  wouldOrphanMember,
  logAudit,
  withPracticeLock,
  revokeSession,
  createAuthToken,
  sendPasswordResetEmail,
} = vi.hoisted(() => ({
  prisma: {
    user: { findUnique: vi.fn(), update: vi.fn(), create: vi.fn() },
    practice: { findUnique: vi.fn(), create: vi.fn() },
    userSession: { findMany: vi.fn(), findFirst: vi.fn() },
    $transaction: vi.fn(),
  },
  wouldStrandPractice: vi.fn(),
  wouldOrphanMember: vi.fn(),
  logAudit: vi.fn(),
  withPracticeLock: vi.fn(),
  revokeSession: vi.fn(),
  createAuthToken: vi.fn(),
  sendPasswordResetEmail: vi.fn(),
}));

vi.mock('@/lib/admin-api-gate', () => ({
  adminApi:
    (_key: string, handler: (req: unknown, ctx: unknown) => unknown) =>
    (req: unknown) =>
      handler(req, { session: { user: { id: 'admin-1', email: 'a@x', practiceId: 'admin-practice' } } }),
}));
vi.mock('@meddoc/db', () => ({ default: prisma }));
vi.mock('@meddoc/auth', () => ({ revokeSession }));
vi.mock('@/lib/audit', () => ({ logAudit }));
vi.mock('@/lib/last-owner-invariant', () => ({ wouldStrandPractice, wouldOrphanMember, withPracticeLock }));
vi.mock('@/lib/auth-tokens', () => ({ createAuthToken }));
vi.mock('@/lib/email', () => ({ sendPasswordResetEmail }));
vi.mock('@/lib/email-enabled', () => ({ isEmailDeliveryEnabled: () => true }));
vi.mock('@/lib/email-auto-confirm', () => ({ isAutoConfirmDomain: () => false }));
vi.mock('bcryptjs', () => ({ default: { hash: vi.fn(async (secret: string) => `hash(${secret.length})`) } }));

import { POST as DEACTIVATE } from '../[id]/deactivate/route';
import { POST as PROFILE } from '../[id]/profile/route';
import { GET as SESSIONS } from '../[id]/sessions/route';
import { POST as REVOKE } from '../[id]/sessions/[sid]/revoke/route';
import { POST as UNSUSPEND } from '../[id]/unsuspend/route';
import { POST as CREATE } from '../route';

const TARGET = 'target-9';
const TARGET_EMAIL = 't@x.com';
const ROW = {
  id: TARGET,
  email: TARGET_EMAIL,
  name: 'Old Name',
  role: 'DOCTOR',
  practiceId: 'prac-7',
  practiceRole: 'OWNER',
  isActive: true,
  deactivatedAt: null,
  suspendedAt: null,
  softDeletedAt: null,
  forceLogoutAt: null,
};

const at = (path: string, body: unknown = {}) =>
  ({ url: `https://x/api/admin/users/${path}`, json: async () => body }) as unknown as Request;

beforeEach(() => {
  vi.clearAllMocks();
  prisma.user.findUnique.mockResolvedValue({ ...ROW });
  prisma.user.update.mockResolvedValue({});
  prisma.user.create.mockResolvedValue({ id: 'new-1' });
  withPracticeLock.mockImplementation(async (_tx: unknown, _p: string, write: () => Promise<unknown>) => write());
  prisma.$transaction.mockImplementation(async (fn: (tx: unknown) => unknown) => fn({ user: prisma.user }));
  wouldStrandPractice.mockResolvedValue({ wouldStrand: false });
  wouldOrphanMember.mockResolvedValue({ wouldOrphan: false });
  createAuthToken.mockResolvedValue({ token: 'raw-token', id: 'tok-1' });
  sendPasswordResetEmail.mockResolvedValue({ id: 'mail-1' });
});

// ════════════════════════════════════════════════════════════════════════════
describe('deactivate', () => {
  const body = { confirmEmail: TARGET_EMAIL };

  it('⚠️ writes isActive, deactivatedAt, deactivatedBy AND forceLogoutAt in one write', async () => {
    const res = (await DEACTIVATE(at(`${TARGET}/deactivate`, body) as never)) as Response;
    expect(res.status).toBe(200);
    const data = prisma.user.update.mock.calls[0][0].data;
    expect(data.isActive).toBe(false);
    expect(data.deactivatedAt, 'isActive=false without deactivatedAt is the #226 shape').toBeInstanceOf(Date);
    expect(data.deactivatedBy).toBe('admin-1');
    expect(data.forceLogoutAt, 'an old session would revive on a later reactivation').toBeInstanceOf(Date);
  });

  it('⚠️ KEEPS practiceRole — a later reactivation has something to restore', async () => {
    await DEACTIVATE(at(`${TARGET}/deactivate`, body) as never);
    expect(prisma.user.update.mock.calls[0][0].data).not.toHaveProperty('practiceRole');
  });

  it('refuses an already-deactivated account — no transaction, no audit', async () => {
    prisma.user.findUnique.mockResolvedValue({ ...ROW, isActive: false, deactivatedAt: new Date() });
    const res = (await DEACTIVATE(at(`${TARGET}/deactivate`, body) as never)) as Response;
    expect(res.status).toBe(409);
    expect((await res.json()).reason).toBe('ALREADY_DEACTIVATED');
    expect(prisma.$transaction).not.toHaveBeenCalled();
    expect(logAudit).not.toHaveBeenCalled();
  });

  it('⚠️ …but REPAIRS the inconsistent row (isActive=false, deactivatedAt NULL)', async () => {
    prisma.user.findUnique.mockResolvedValue({ ...ROW, isActive: false, deactivatedAt: null });
    const res = (await DEACTIVATE(at(`${TARGET}/deactivate`, body) as never)) as Response;
    expect(res.status).toBe(200);
    expect(prisma.user.update.mock.calls[0][0].data.deactivatedAt).toBeInstanceOf(Date);
  });

  it('refuses a confirmEmail that does not match — no transaction', async () => {
    const res = (await DEACTIVATE(at(`${TARGET}/deactivate`, { confirmEmail: 'x@y.com' }) as never)) as Response;
    expect(res.status).toBe(400);
    expect(prisma.$transaction).not.toHaveBeenCalled();
  });

  it('audits USER_DEACTIVATED on the TARGET practice, after the write', async () => {
    await DEACTIVATE(at(`${TARGET}/deactivate`, body) as never);
    expect(logAudit).toHaveBeenCalledTimes(1);
    expect(logAudit.mock.calls[0][0]).toMatchObject({
      action: 'USER_DEACTIVATED',
      targetId: TARGET,
      practiceId: 'prac-7',
    });
  });
});

// ════════════════════════════════════════════════════════════════════════════
describe('profile', () => {
  it('⚠️ REFUSES `email` — the strict body keeps address changes on confirm-email', async () => {
    const res = (await PROFILE(at(`${TARGET}/profile`, { email: 'new@x.com' }) as never)) as Response;
    expect(res.status).toBe(400);
    expect(prisma.$transaction).not.toHaveBeenCalled();
  });

  it('⚠️ refuses `email` even beside a legitimate field', async () => {
    const res = (await PROFILE(at(`${TARGET}/profile`, { name: 'N', email: 'new@x.com' }) as never)) as Response;
    expect(res.status).toBe(400);
    expect(prisma.user.update).not.toHaveBeenCalled();
  });

  it('refuses SUPER_ADMIN as a role — platform admin has its own confirm-email doors', async () => {
    const res = (await PROFILE(at(`${TARGET}/profile`, { role: 'SUPER_ADMIN' }) as never)) as Response;
    expect(res.status).toBe(400);
  });

  it('does not re-role a row whose legacy role is SUPER_ADMIN', async () => {
    prisma.user.findUnique.mockResolvedValue({ ...ROW, role: 'SUPER_ADMIN' });
    const res = (await PROFILE(at(`${TARGET}/profile`, { role: 'STAFF' }) as never)) as Response;
    expect(res.status).toBe(409);
    expect(prisma.$transaction).not.toHaveBeenCalled();
  });

  it('a role-only change is USER_ROLE_CHANGED with from -> to', async () => {
    await PROFILE(at(`${TARGET}/profile`, { role: 'STAFF' }) as never);
    expect(prisma.user.update.mock.calls[0][0].data).toEqual({ role: 'STAFF' });
    expect(logAudit.mock.calls[0][0]).toMatchObject({
      action: 'USER_ROLE_CHANGED',
      practiceId: 'prac-7',
      metadata: { changed: { role: { from: 'DOCTOR', to: 'STAFF' } } },
    });
  });

  it('a name change is USER_UPDATED, and the NAME ITSELF never reaches the audit row', async () => {
    await PROFILE(at(`${TARGET}/profile`, { name: 'Dr New Person' }) as never);
    expect(prisma.user.update.mock.calls[0][0].data).toEqual({ name: 'Dr New Person' });
    expect(logAudit.mock.calls[0][0].action).toBe('USER_UPDATED');
    expect(JSON.stringify(logAudit.mock.calls[0][0])).not.toContain('Dr New Person');
  });

  it('an unchanged body is a no-op refusal — no transaction, no audit', async () => {
    const res = (await PROFILE(at(`${TARGET}/profile`, { name: 'Old Name', role: 'DOCTOR' }) as never)) as Response;
    expect(res.status).toBe(400);
    expect((await res.json()).reason).toBe('NO_CHANGE');
    expect(prisma.$transaction).not.toHaveBeenCalled();
    expect(logAudit).not.toHaveBeenCalled();
  });
});

// ════════════════════════════════════════════════════════════════════════════
describe('sessions', () => {
  const now = Date.now();
  const FULL = [
    // active
    { id: 's1', sessionToken: 'SECRET-TOKEN-1', ipAddress: '1.1.1.1', userAgent: 'UA', createdAt: new Date(now - 60_000), lastActiveAt: new Date(now), expiresAt: new Date(now + 3_600_000) },
    // expired
    { id: 's2', sessionToken: 'SECRET-TOKEN-2', ipAddress: null, userAgent: null, createdAt: new Date(now - 9e8), lastActiveAt: new Date(now - 9e8), expiresAt: new Date(now - 1000) },
  ];
  beforeEach(() => {
    // Returns ONLY what the route selects — so a select that asked for the
    // token would get it, exactly as Prisma would hand it over.
    prisma.userSession.findMany.mockImplementation(async (q: { select: Record<string, boolean> }) =>
      FULL.map((r) =>
        Object.fromEntries(Object.entries(r).filter(([k]) => q.select?.[k])),
      ),
    );
  });

  it('⚠️ never SELECTS the bearer sessionToken, and never returns it', async () => {
    const res = (await SESSIONS(at(`${TARGET}/sessions`) as never)) as Response;
    expect(res.status).toBe(200);
    const q = prisma.userSession.findMany.mock.calls[0][0];
    expect(q.select.sessionToken, 'the credential behind the JWT was read into the admin API').toBeUndefined();
    const text = JSON.stringify(await res.json());
    expect(text).not.toContain('SECRET-TOKEN');
    expect(text).not.toContain('sessionToken');
  });

  it('reads user_sessions for THIS user, and states each row\'s status', async () => {
    const res = (await SESSIONS(at(`${TARGET}/sessions`) as never)) as Response;
    expect(prisma.userSession.findMany.mock.calls[0][0].where).toEqual({ userId: TARGET });
    const { sessions } = await res.json();
    expect(sessions.map((s: { id: string; status: string }) => [s.id, s.status])).toEqual([
      ['s1', 'active'],
      ['s2', 'expired'],
    ]);
  });

  it('a session older than forceLogoutAt reads "invalidated", as validateSession would treat it', async () => {
    prisma.user.findUnique.mockResolvedValue({ ...ROW, forceLogoutAt: new Date(now) });
    const { sessions } = await ((await SESSIONS(at(`${TARGET}/sessions`) as never)) as Response).json();
    expect(sessions[0].status).toBe('invalidated');
  });

  it('⚠️ revoke finds the session by id AND user — another person\'s session id is a 404', async () => {
    prisma.userSession.findFirst.mockResolvedValue(null);
    const res = (await REVOKE(at(`${TARGET}/sessions/s-other/revoke`) as never)) as Response;
    expect(res.status).toBe(404);
    expect(prisma.userSession.findFirst.mock.calls[0][0].where).toEqual({ id: 's-other', userId: TARGET });
    expect(revokeSession).not.toHaveBeenCalled();
  });

  it('revoke ends the row through revokeSession and audits it on the TARGET practice', async () => {
    prisma.userSession.findFirst.mockResolvedValue({ id: 's1', sessionToken: 'SECRET-TOKEN-1' });
    const res = (await REVOKE(at(`${TARGET}/sessions/s1/revoke`) as never)) as Response;
    expect(res.status).toBe(200);
    expect(revokeSession).toHaveBeenCalledWith('SECRET-TOKEN-1');
    expect(logAudit.mock.calls[0][0]).toMatchObject({
      action: 'SESSION_EXPIRED',
      practiceId: 'prac-7',
      metadata: { reason: 'admin_revoke', sessionId: 's1' },
    });
    expect(JSON.stringify(await res.json())).not.toContain('SECRET-TOKEN');
    expect(JSON.stringify(logAudit.mock.calls[0][0])).not.toContain('SECRET-TOKEN');
  });

  it('revoking your own session from here is refused', async () => {
    const res = (await REVOKE(at('admin-1/sessions/s1/revoke') as never)) as Response;
    expect(res.status).toBe(403);
    expect(revokeSession).not.toHaveBeenCalled();
  });
});

// ════════════════════════════════════════════════════════════════════════════
describe('unsuspend — the orphan refusal it never had', () => {
  it('⚠️ asks about THIS write and refuses with a sentence, not a 500', async () => {
    wouldOrphanMember.mockResolvedValueOnce({ wouldOrphan: true, reason: 'sentence', restorableOwners: 0 });
    const res = (await UNSUSPEND(at(`${TARGET}/unsuspend`) as never)) as Response;
    expect(res.status).toBe(409);
    expect(await res.json()).toMatchObject({ reason: 'NO_ACTIVE_OWNER', error: 'sentence' });
    expect(prisma.$transaction).not.toHaveBeenCalled();
    expect(wouldOrphanMember.mock.calls[0][0]).toEqual({
      kind: 'update',
      userId: TARGET,
      patch: { suspendedAt: null, suspendedBy: null, suspendedReason: null },
    });
  });
});

// ════════════════════════════════════════════════════════════════════════════
describe('create — into an EXISTING practice only', () => {
  const body = { email: 'New@X.com', name: 'New Person', practiceId: 'prac-7', practiceRole: 'CLINICIAN' };
  beforeEach(() => {
    prisma.user.findUnique.mockResolvedValue(null);
    prisma.practice.findUnique.mockResolvedValue({ id: 'prac-7', name: 'Practice Seven' });
  });
  const post = (b: unknown) => CREATE(at('', b) as never) as Promise<Response>;

  it('⚠️ writes TRANSCRIBE_MD, the body\'s role and practice — and mints no practice', async () => {
    const res = await post(body);
    expect(res.status).toBe(200);
    const data = prisma.user.create.mock.calls[0][0].data;
    expect(data.products, 'the schema default MEDDOC_PRO cannot sign in here').toEqual(['TRANSCRIBE_MD']);
    expect(data.practiceRole, 'the original made every account an OWNER').toBe('CLINICIAN');
    expect(data.practiceId).toBe('prac-7');
    expect(data.email).toBe('new@x.com');
    expect(data.isActive).toBe(true);
    expect(prisma.practice.create, 'a FOURTH promo door — a practice minted by the console').not.toHaveBeenCalled();
    expect(withPracticeLock.mock.calls[0][1]).toBe('prac-7');
  });

  it('⚠️ an unknown practice is refused — nothing is created to receive the account', async () => {
    prisma.practice.findUnique.mockResolvedValue(null);
    const res = await post(body);
    expect(res.status).toBe(404);
    expect((await res.json()).reason).toBe('PRACTICE_NOT_FOUND');
    expect(prisma.$transaction).not.toHaveBeenCalled();
    expect(prisma.practice.create).not.toHaveBeenCalled();
  });

  it('⚠️ an admin-typed PASSWORD is refused outright (strict body)', async () => {
    const res = await post({ ...body, password: 'Hunter2Hunter2' });
    expect(res.status).toBe(400);
    expect(prisma.$transaction).not.toHaveBeenCalled();
  });

  it('practiceRole is REQUIRED — no silent OWNER default', async () => {
    const { practiceRole: _drop, ...noRole } = body;
    const res = await post(noRole);
    expect(res.status).toBe(400);
  });

  it('an existing email is a 409 before any write', async () => {
    prisma.user.findUnique.mockResolvedValue({ id: 'someone' });
    const res = await post(body);
    expect(res.status).toBe(409);
    expect((await res.json()).reason).toBe('EMAIL_TAKEN');
    expect(prisma.$transaction).not.toHaveBeenCalled();
  });

  it('a unique violation inside the transaction (lost race) is also a 409', async () => {
    prisma.$transaction.mockRejectedValueOnce(Object.assign(new Error('Unique'), { code: 'P2002' }));
    const res = await post(body);
    expect(res.status).toBe(409);
  });

  it('⚠️ the orphan refusal is asked about the row AS INSERTED', async () => {
    wouldOrphanMember.mockResolvedValueOnce({ wouldOrphan: true, reason: 'sentence', restorableOwners: 0 });
    const res = await post(body);
    expect(res.status).toBe(409);
    expect(prisma.$transaction).not.toHaveBeenCalled();
    const asked = wouldOrphanMember.mock.calls[0][0];
    expect(asked).toMatchObject({ kind: 'insert', practiceId: 'prac-7' });
    expect(asked.row).toEqual({
      practiceRole: 'CLINICIAN',
      isActive: true,
      deactivatedAt: null,
      suspendedAt: null,
      softDeletedAt: null,
    });
  });

  it('⚠️ the credential is the RESET-TOKEN email, 1 hour, and no password is returned or stored from input', async () => {
    const res = await post(body);
    const payload = await res.json();
    expect(createAuthToken).toHaveBeenCalledWith(
      expect.objectContaining({ userId: 'new-1', purpose: 'PASSWORD_RESET', expiresInMs: 3_600_000 }),
    );
    expect(sendPasswordResetEmail.mock.calls[0][0]).toMatchObject({ toEmail: 'new@x.com' });
    expect(sendPasswordResetEmail.mock.calls[0][0].resetUrl).toContain('token=raw-token');
    expect(payload.credentialEmail).toEqual({ sent: true, errorCode: null });
    expect(JSON.stringify(payload)).not.toContain('raw-token');
    expect(JSON.stringify(payload).toLowerCase()).not.toContain('password');
    // a 32-byte random secret, base64url — 43 characters — never a body field
    expect(prisma.user.create.mock.calls[0][0].data.passwordHash).toBe('hash(43)');
  });

  it('with email delivery ON, the account is created UNVERIFIED — as a self-signup is', async () => {
    await post(body);
    expect(prisma.user.create.mock.calls[0][0].data.emailVerified).toBeNull();
  });

  it('a failed credential email does NOT undo the account — 200, reported', async () => {
    sendPasswordResetEmail.mockRejectedValueOnce(Object.assign(new Error('down'), { name: 'ResendError' }));
    const spy = vi.spyOn(console, 'error').mockImplementation(() => {});
    const res = await post(body);
    spy.mockRestore();
    expect(res.status).toBe(200);
    expect((await res.json()).credentialEmail).toEqual({ sent: false, errorCode: 'ResendError' });
    expect(prisma.user.create).toHaveBeenCalledTimes(1);
  });

  it('audits USER_CREATED on the NEW account\'s practice', async () => {
    await post(body);
    const created = logAudit.mock.calls.map((c) => c[0]).find((a) => a.action === 'USER_CREATED');
    expect(created).toMatchObject({ targetId: 'new-1', practiceId: 'prac-7' });
    expect(created.metadata).toMatchObject({ createdVia: 'admin_console', practiceRole: 'CLINICIAN' });
  });
});
