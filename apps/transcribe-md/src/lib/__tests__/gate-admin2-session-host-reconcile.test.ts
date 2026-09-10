// ============================================================================
// ADMIN-2 (#196) — getSession() RECONCILES THE HOST AGAINST THE PRACTICE.
// ----------------------------------------------------------------------------
// Claims this file makes, each one an arm that was made to red:
//
//   1. FLAG OFF → BYTE-IDENTICAL. With PRACTICE_HOST_ROUTING unset (production
//      today) getSession returns exactly what it returned before ADMIN-2, reads
//      no header for it and queries no practice — even on a host whose
//      practice is not the user's.
//   2. FLAG ON, practice host of ANOTHER practice → REFUSED BY NAME
//      (`PracticeHostRefusedError`), and the refusal ESCAPES getSession's outer
//      `catch { return null }` — the trap #182(1) already fell into once.
//   3. FLAG ON, the user's OWN practice host, or a neutral host → the same
//      session as flag-off. The reconcile admits without altering anything.
//   4. A practice lookup that cannot answer → SessionUnverifiableError (503),
//      not "mismatch" and not "neutral".
//   5. Through withApiHandler the refusal is a 403 with its code, not a 500.
// ============================================================================
import type { NextRequest } from 'next/server';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const userFindUnique = vi.fn();
const practiceFindFirst = vi.fn();
const authFn = vi.fn();
const headerBag = new Map<string, string>();
const headersFn = vi.fn(async () => headerBag);

vi.mock('@meddoc/db', () => ({
  __esModule: true,
  default: {
    user: { findUnique: (...a: unknown[]) => userFindUnique(...a) },
    practice: { findFirst: (...a: unknown[]) => practiceFindFirst(...a) },
  },
}));
vi.mock('@/lib/nextauth', () => ({ auth: () => authFn() }));
vi.mock('next/headers', () => ({ headers: () => headersFn() }));
vi.mock('@/lib/audit', () => ({ logAudit: vi.fn() }));
// api-error.ts imports redactPhi from @meddoc/ai, whose cold import alone
// outlasts vitest's 5s default; the redactor is not under test here.
vi.mock('@meddoc/ai', () => ({ redactPhi: (x: unknown) => String(x) }));

const SESSION = {
  user: { id: 'usr_1', email: 'doc@example.invalid', name: 'Doc', role: 'DOCTOR', practiceId: 'prac_A' },
};
const EXPECTED = {
  user: { id: 'usr_1', email: 'doc@example.invalid', fullName: 'Doc', role: 'DOCTOR', practiceId: 'prac_A' },
};

async function getSession() {
  const mod = await import('../auth');
  return mod.getSession();
}

const PREV_FLAG = process.env.PRACTICE_HOST_ROUTING;
function setFlag(v: string | undefined) {
  if (v === undefined) delete process.env.PRACTICE_HOST_ROUTING;
  else process.env.PRACTICE_HOST_ROUTING = v;
}

beforeEach(() => {
  vi.clearAllMocks();
  headerBag.clear();
  authFn.mockResolvedValue(SESSION);
  userFindUnique.mockResolvedValue({ role: 'DOCTOR', isActive: true, practiceId: 'prac_A' });
  // `northside` belongs to prac_B — NOT the user's practice.
  practiceFindFirst.mockImplementation(async (args: { where: { slug: string } }) =>
    args.where.slug === 'northside' ? { id: 'prac_B' } : args.where.slug === 'eastgate' ? { id: 'prac_A' } : null,
  );
});
afterEach(() => setFlag(PREV_FLAG));

describe('ADMIN-2 — flag OFF is byte-identical', () => {
  it.each([[undefined], ['false'], ['1']])(
    '⚠️ PRACTICE_HOST_ROUTING=%j: another practice\'s host changes NOTHING — same session, no header read, no practice query',
    async (flag) => {
      setFlag(flag);
      // Baseline: no host at all.
      const baseline = await getSession();
      headerBag.set('host', 'northside.quillmd.com');
      const onForeignPracticeHost = await getSession();

      expect(baseline).toEqual(EXPECTED);
      expect(onForeignPracticeHost, 'flag off must not reconcile').toEqual(baseline);
      expect(headersFn, 'flag off read a header for the reconcile').not.toHaveBeenCalled();
      expect(practiceFindFirst, 'flag off queried a practice').not.toHaveBeenCalled();
    },
  );
});

describe('ADMIN-2 — flag ON', () => {
  beforeEach(() => setFlag('true'));

  it("⚠️ another practice's host → PracticeHostRefusedError, by name — NOT null", async () => {
    const spy = vi.spyOn(console, 'warn').mockImplementation(() => {});
    headerBag.set('host', 'northside.quillmd.com');
    const { PracticeHostRefusedError } = await import('../practice-host');
    const err = await getSession().then(
      (v) => ({ resolved: v }),
      (e: unknown) => e,
    );
    expect(err, 'the refusal was swallowed into a value (null reads as "signed out")').toBeInstanceOf(
      PracticeHostRefusedError,
    );
    expect((err as InstanceType<typeof PracticeHostRefusedError>).reason).toBe('practice_mismatch');
    expect((err as { digest?: string }).digest).toBe('PRACTICE_HOST_REFUSED');
    spy.mockRestore();
  });

  it('⚠️ compares against the practice from the DATABASE, not the token', async () => {
    // Token says prac_B (northside's), the DB says the user moved to prac_A.
    const spy = vi.spyOn(console, 'warn').mockImplementation(() => {});
    authFn.mockResolvedValue({ user: { ...SESSION.user, practiceId: 'prac_B' } });
    headerBag.set('host', 'northside.quillmd.com');
    await expect(getSession()).rejects.toMatchObject({ reason: 'practice_mismatch' });
    spy.mockRestore();
  });

  it("the user's OWN practice host → the same session as flag-off", async () => {
    headerBag.set('host', 'eastgate.quillmd.com');
    expect(await getSession()).toEqual(EXPECTED);
    expect(practiceFindFirst).toHaveBeenCalledTimes(1);
  });

  it.each(['app.quillmd.com', 'admin.quillmd.com', 'localhost:3011'])(
    'neutral host %s → the same session, no practice query',
    async (h) => {
      headerBag.set('host', h);
      expect(await getSession()).toEqual(EXPECTED);
      expect(practiceFindFirst).not.toHaveBeenCalled();
    },
  );

  it.each([
    ['solo-k3j9x2-lx9q.quillmd.com', 'machine_slug'],
    ['nosuch.quillmd.com', 'unknown_practice'],
    ['api.quillmd.com', 'reserved_label'],
    ['evil.example', 'foreign_host'],
  ])('%s → refused (%s)', async (h, reason) => {
    const spy = vi.spyOn(console, 'warn').mockImplementation(() => {});
    headerBag.set('host', h);
    await expect(getSession()).rejects.toMatchObject({ name: 'PracticeHostRefusedError', reason });
    spy.mockRestore();
  });

  it('⚠️ a practice lookup that cannot answer → SessionUnverifiableError (503), not a mismatch', async () => {
    const spy = vi.spyOn(console, 'error').mockImplementation(() => {});
    practiceFindFirst.mockRejectedValue(new Error('pool timeout'));
    headerBag.set('host', 'northside.quillmd.com');
    const { SessionUnverifiableError } = await import('@meddoc/auth');
    await expect(getSession()).rejects.toBeInstanceOf(SessionUnverifiableError);
    spy.mockRestore();
  });

  it('a deactivated user is still refused as before (null) — the reconcile does not mask it', async () => {
    userFindUnique.mockResolvedValue({ role: 'DOCTOR', isActive: false, practiceId: 'prac_A' });
    headerBag.set('host', 'northside.quillmd.com');
    expect(await getSession()).toBeNull();
    expect(practiceFindFirst).not.toHaveBeenCalled();
  });
});

describe('ADMIN-2 — the refusal through withApiHandler', () => {
  it('the api-error digest literal IS PracticeHostRefusedError.DIGEST', async () => {
    const { PRACTICE_HOST_REFUSED_DIGEST } = await import('../api-error');
    const { PracticeHostRefusedError } = await import('../practice-host');
    expect(PRACTICE_HOST_REFUSED_DIGEST).toBe(PracticeHostRefusedError.DIGEST);
  });

  it('⚠️ a route whose getSession() is refused answers 403 PRACTICE_HOST_REFUSED, not 500', async () => {
    const spy = vi.spyOn(console, 'warn').mockImplementation(() => {});
    const errSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
    setFlag('true');
    headerBag.set('host', 'northside.quillmd.com');
    const { withApiHandler } = await import('../api-error');
    const { NextResponse } = await import('next/server');
    const route = withApiHandler('api:test:admin2', async () => {
      await getSession();
      return NextResponse.json({ ok: true });
    });
    const res = await route({} as NextRequest, { params: Promise.resolve({}) });
    expect(res.status).toBe(403);
    expect(((await res.json()) as { code?: string }).code).toBe('PRACTICE_HOST_REFUSED');
    spy.mockRestore();
    errSpy.mockRestore();
  });
});
