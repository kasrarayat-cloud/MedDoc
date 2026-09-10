// ============================================================================
// ADMIN-6a D1 — LOGIN REFUSES A MEMBER OF AN ARCHIVED PRACTICE
// ----------------------------------------------------------------------------
// Drives the REAL `authorize()` from `nextauth.ts`. `next-auth` and its
// Credentials provider are replaced by capture shims so the config object the
// module builds is observable; everything authorize() itself does runs as
// shipped. Mocking authorize would test the mock.
//
// The POSITIVE CONTROL is the load-bearing arm: the same user, same password,
// with an ACTIVE practice, must come back admitted. Without it, "archived →
// null" is satisfied by an authorize() that refuses everyone.
// ============================================================================
import bcrypt from 'bcryptjs';
import { beforeEach, describe, expect, it, vi } from 'vitest';

type Authorize = (c: Record<string, string>) => Promise<unknown>;

const h = vi.hoisted(() => ({
  config: null as null | { providers: { authorize: (c: Record<string, string>) => Promise<unknown> }[] },
  userFindUnique: vi.fn(async (_a: unknown): Promise<unknown> => null),
  userUpdate: vi.fn(async (_a: unknown) => ({})),
  logAudit: vi.fn(async (_a: { action: string; errorCode?: string; userId?: string }) => undefined),
}));

vi.mock('next-auth', () => ({
  default: (cfg: unknown) => {
    h.config = cfg as never;
    return { handlers: {}, auth: vi.fn(), signIn: vi.fn(), signOut: vi.fn() };
  },
}));
vi.mock('next-auth/providers/credentials', () => ({ default: (opts: unknown) => opts }));
vi.mock('@sentry/nextjs', () => ({}));
vi.mock('@/lib/auth.config', () => ({ default: {} }));
vi.mock('@meddoc/auth', () => ({ revokeSession: vi.fn(), revokeAllUserSessions: vi.fn() }));
vi.mock('@meddoc/ai', () => ({ redactPhi: (x: unknown) => x }));
vi.mock('@/lib/email-enabled', () => ({ isEmailDeliveryEnabled: () => false }));
vi.mock('@/lib/audit', () => ({ logAudit: h.logAudit }));
vi.mock('@meddoc/db', () => ({
  default: { user: { findUnique: h.userFindUnique, update: h.userUpdate } },
}));

await import('../nextauth');
const authorize = (h.config!.providers[0]!.authorize as Authorize).bind(null);

const PASSWORD = 'CorrectHorse9';
const HASH = bcrypt.hashSync(PASSWORD, 4);
const member = (practice: unknown) => ({
  id: 'u_member',
  email: 'member@example.invalid',
  name: 'Member',
  role: 'DOCTOR',
  practiceId: 'prac_T',
  isActive: true,
  suspendedAt: null,
  softDeletedAt: null,
  lockedUntil: null,
  emailVerified: new Date('2026-01-01T00:00:00Z'),
  passwordHash: HASH,
  failedLoginCount: 0,
  products: ['TRANSCRIBE_MD'],
  mfaEnabled: false,
  mfaSecret: null,
  mfaBackupCodes: [],
  practice,
});

beforeEach(() => {
  vi.clearAllMocks();
});

describe('ADMIN-6a D1 — authorize() and the practice flag', () => {
  it('POSITIVE CONTROL — the same member with an ACTIVE practice is admitted', async () => {
    h.userFindUnique.mockResolvedValue(member({ isActive: true }));
    const out = (await authorize({ email: 'member@example.invalid', password: PASSWORD })) as { id?: string } | null;
    expect(out, 'a valid member of an active practice was refused — every arm below is vacuous').not.toBeNull();
    expect(out!.id).toBe('u_member');
  });

  it('⚠️ a member of an ARCHIVED practice is refused, and the refusal is RECORDED by name', async () => {
    h.userFindUnique.mockResolvedValue(member({ isActive: false }));
    const out = await authorize({ email: 'member@example.invalid', password: PASSWORD });
    expect(out, 'an archived practice still mints sessions').toBeNull();
    const row = h.logAudit.mock.calls.find((c) => c[0].action === 'LOGIN_FAILED')?.[0];
    expect(row?.errorCode).toBe('ACCOUNT_PRACTICE_ARCHIVED');
    expect(row?.userId).toBe('u_member');
  });

  it('⚠️ …and the SAME member is admitted again after a restore — their own row was never touched', async () => {
    h.userFindUnique.mockResolvedValueOnce(member({ isActive: false }));
    expect(await authorize({ email: 'member@example.invalid', password: PASSWORD })).toBeNull();
    h.userFindUnique.mockResolvedValueOnce(member({ isActive: true }));
    expect(await authorize({ email: 'member@example.invalid', password: PASSWORD })).not.toBeNull();
  });

  it('⚠️ FAIL-CLOSED — a lookup that did not load the practice refuses', async () => {
    h.userFindUnique.mockResolvedValue(member(undefined));
    expect(await authorize({ email: 'member@example.invalid', password: PASSWORD })).toBeNull();
  });

  it('⚠️ the door LOADS the practice through the predicate\'s own select', async () => {
    h.userFindUnique.mockResolvedValue(member({ isActive: true }));
    await authorize({ email: 'member@example.invalid', password: PASSWORD });
    expect(h.userFindUnique.mock.calls[0]![0]).toEqual({
      where: { email: 'member@example.invalid' },
      include: { practice: { select: { isActive: true } } },
    });
  });
});
