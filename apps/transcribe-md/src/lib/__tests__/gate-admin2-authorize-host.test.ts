// ============================================================================
// ADMIN-2 (#196) — authorize() REFUSES MEMBERS OF OTHER PRACTICES ON A
// PRACTICE HOST. The REAL authorize from lib/nextauth.ts, captured by mocking
// NextAuth() and the Credentials() factory to hand back their options.
// ----------------------------------------------------------------------------
//   · flag OFF → the same user object as before, no header read, no practice
//     query, even on another practice's host.
//   · flag ON, another practice's host → null, one LOGIN_FAILED row naming
//     PRACTICE_HOST_REFUSED, and no login recorded (no counter reset).
//   · flag ON, own practice host / neutral host → admitted.
//   · flag ON, the lookup throws → refused (fail closed), host_unverifiable.
// ============================================================================
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const captured: { cfg?: { providers: Array<{ authorize: (c: unknown) => Promise<unknown> }> } } = {};
const userFindUnique = vi.fn();
const userUpdate = vi.fn(async () => ({}));
const practiceFindFirst = vi.fn();
const logAudit = vi.fn();
const headerBag = new Map<string, string>();
const headersFn = vi.fn(async () => headerBag);

vi.mock('next-auth', () => ({
  default: (cfg: typeof captured.cfg) => {
    captured.cfg = cfg;
    return { handlers: {}, auth: vi.fn(), signIn: vi.fn(), signOut: vi.fn() };
  },
}));
vi.mock('next-auth/providers/credentials', () => ({ default: (opts: unknown) => opts }));
vi.mock('bcryptjs', () => ({ default: { hashSync: () => 'dummy', compare: vi.fn(async () => true) } }));
vi.mock('@sentry/nextjs', () => ({ setUser: vi.fn(), setTag: vi.fn() }));
vi.mock('@/lib/auth.config', () => ({ default: {} }));
vi.mock('@meddoc/ai', () => ({ redactPhi: (x: unknown) => String(x) }));
vi.mock('@/lib/email-enabled', () => ({ isEmailDeliveryEnabled: () => false }));
vi.mock('@/lib/audit', () => ({ logAudit: (...a: unknown[]) => logAudit(...a) }));
vi.mock('next/headers', () => ({ headers: () => headersFn() }));
vi.mock('@meddoc/db', () => ({
  __esModule: true,
  default: {
    user: {
      findUnique: (...a: unknown[]) => userFindUnique(...a),
      update: (...a: unknown[]) => userUpdate(...(a as [])),
    },
    practice: { findFirst: (...a: unknown[]) => practiceFindFirst(...a) },
  },
}));

const USER = {
  id: 'usr_1',
  email: 'doc@example.invalid',
  name: 'Doc',
  role: 'DOCTOR',
  practiceId: 'prac_A',
  isActive: true,
  suspendedAt: null,
  softDeletedAt: null,
  lockedUntil: null,
  emailVerified: new Date('2026-01-01T00:00:00Z'),
  passwordHash: 'hash',
  failedLoginCount: 0,
  products: ['TRANSCRIBE_MD'],
  mfaEnabled: false,
  mfaSecret: null,
  mfaBackupCodes: [],
};
const CREDS = { email: 'doc@example.invalid', password: 'correct horse' };
const ADMITTED = {
  id: 'usr_1',
  email: 'doc@example.invalid',
  name: 'Doc',
  role: 'DOCTOR',
  practiceId: 'prac_A',
  pendingRecoveryHash: null,
  mfaBackupCodes: undefined,
};

async function authorize(): Promise<unknown> {
  await import('../nextauth');
  const provider = captured.cfg!.providers[0]!;
  return provider.authorize(CREDS);
}

const PREV_FLAG = process.env.PRACTICE_HOST_ROUTING;
function setFlag(v: string | undefined) {
  if (v === undefined) delete process.env.PRACTICE_HOST_ROUTING;
  else process.env.PRACTICE_HOST_ROUTING = v;
}
const loginRecorded = () =>
  userUpdate.mock.calls.some((c) => 'lastLogin' in ((c as unknown as [{ data: object }])[0]?.data ?? {}));

beforeEach(() => {
  vi.clearAllMocks();
  headerBag.clear();
  userFindUnique.mockResolvedValue(USER);
  practiceFindFirst.mockImplementation(async (args: { where: { slug: string } }) =>
    args.where.slug === 'northside' ? { id: 'prac_B' } : args.where.slug === 'eastgate' ? { id: 'prac_A' } : null,
  );
});
afterEach(() => setFlag(PREV_FLAG));

describe('authorize — flag OFF is byte-identical', () => {
  it("⚠️ another practice's host admits exactly as before — no header read, no practice query", async () => {
    setFlag(undefined);
    const baseline = await authorize();
    headerBag.set('host', 'northside.quillmd.com');
    const onForeignHost = await authorize();
    expect(baseline).toEqual(ADMITTED);
    expect(onForeignHost).toEqual(baseline);
    expect(headersFn).not.toHaveBeenCalled();
    expect(practiceFindFirst).not.toHaveBeenCalled();
    expect(logAudit.mock.calls.filter((c) => (c[0] as { errorCode?: string }).errorCode === 'PRACTICE_HOST_REFUSED')).toHaveLength(0);
  });
});

describe('authorize — flag ON', () => {
  beforeEach(() => setFlag('true'));

  it("⚠️ a member of ANOTHER practice on a practice host → refused, audited by name, no login recorded", async () => {
    headerBag.set('host', 'northside.quillmd.com');
    expect(await authorize()).toBeNull();
    const rows = logAudit.mock.calls.map((c) => c[0] as { action: string; errorCode?: string; metadata?: { reason?: string } });
    const row = rows.find((r) => r.errorCode === 'PRACTICE_HOST_REFUSED');
    expect(row, 'no audit row names the refusal').toBeDefined();
    expect(row!.action).toBe('LOGIN_FAILED');
    expect(row!.metadata?.reason).toBe('practice_mismatch');
    expect(loginRecorded(), 'a refused sign-in recorded a login').toBe(false);
  });

  it('a member of the host practice → admitted', async () => {
    headerBag.set('host', 'eastgate.quillmd.com');
    expect(await authorize()).toEqual(ADMITTED);
  });

  it('the neutral app host → admitted, no practice query', async () => {
    headerBag.set('host', 'app.quillmd.com');
    expect(await authorize()).toEqual(ADMITTED);
    expect(practiceFindFirst).not.toHaveBeenCalled();
  });

  it('⚠️ the practice lookup throws → refused (fail closed) as host_unverifiable', async () => {
    const spy = vi.spyOn(console, 'error').mockImplementation(() => {});
    practiceFindFirst.mockRejectedValue(new Error('pool timeout'));
    headerBag.set('host', 'eastgate.quillmd.com');
    expect(await authorize()).toBeNull();
    const row = logAudit.mock.calls
      .map((c) => c[0] as { errorCode?: string; metadata?: { reason?: string } })
      .find((r) => r.errorCode === 'PRACTICE_HOST_REFUSED');
    expect(row?.metadata?.reason).toBe('host_unverifiable');
    spy.mockRestore();
  });

  it('a wrong password on a practice host still counts as a failed credential (lockout unchanged)', async () => {
    const bcrypt = (await import('bcryptjs')).default as unknown as { compare: ReturnType<typeof vi.fn> };
    bcrypt.compare.mockResolvedValueOnce(false);
    headerBag.set('host', 'northside.quillmd.com');
    expect(await authorize()).toBeNull();
    const codes = logAudit.mock.calls.map((c) => (c[0] as { errorCode?: string }).errorCode);
    expect(codes).toContain('CREDENTIALS_MISMATCH');
    expect(codes).not.toContain('PRACTICE_HOST_REFUSED');
  });
});
