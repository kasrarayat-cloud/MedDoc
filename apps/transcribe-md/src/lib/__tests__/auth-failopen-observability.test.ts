// ============================================================================
// getSession's DB-error path FAILS CLOSED — #182(1). It used to fail OPEN.
// ----------------------------------------------------------------------------
// `lib/auth.ts` guards clinical access with exactly one `isActive` check:
//
//     const dbUser = await prisma.user.findUnique(...)
//     if (!dbUser || !dbUser.isActive) return null;
//
// It sits inside a try/catch. When the lookup THROWS, that line never executes
// and the session is rebuilt from JWT-claimed `role` and `practiceId` — so a
// deactivated, suspended, soft-deleted or force-logged-out account keeps being
// served, bounded only by the JWT's 8-hour maxAge.
//
// ⚠️ THE CATCH USED TO BE `catch {}` — NO LOG, NO ROW, NOTHING. If it had ever
// fired in production, for any account, no artefact anywhere would show it. That
// is what these tests protect: not the behaviour (which is a pending war-room
// ruling on availability vs revocation) but the ability to KNOW.
//
// ⚠️ AND IT DOES NOT NEED THE DATABASE TO BE DOWN. `PRISMA_POOL_MAX=10` with a
// 20s pool timeout makes failures PER-QUERY under load: this lookup can time out
// while the clinical queries after it succeed. That is the shape that admits a
// request rather than breaking it, and it is why "the DB was down so nothing
// worked anyway" is not a reassurance.
//
// BOTH DIRECTIONS ARE ASSERTED, because a log that always fires is as useless as
// one that never does:
//
//   FIRES   the lookup throws            → SESSION_FAILOPEN logged, session served
//   SILENT  the lookup succeeds          → nothing logged
//   SILENT  the user is legitimately off → nothing logged, session REFUSED
//
// The third is the one that separates "auth fell open" from "auth worked": a
// deactivated user on a HEALTHY database must be refused with no alarm at all.
// ============================================================================

import { beforeEach, describe, expect, it, vi } from 'vitest';

const findUnique = vi.fn();
const authFn = vi.fn();

vi.mock('@meddoc/db', () => ({
  __esModule: true,
  default: { user: { findUnique: (...a: unknown[]) => findUnique(...a) } },
  prisma: { user: { findUnique: (...a: unknown[]) => findUnique(...a) } },
}));

vi.mock('@/lib/nextauth', () => ({ auth: () => authFn() }));

const SESSION = {
  user: { id: 'usr_1', email: 'doc@example.invalid', name: 'Doc', role: 'DOCTOR', practiceId: 'prac_1' },
};

async function callGetSession() {
  const mod = await import('../auth');
  return mod.getSession();
}

describe('getSession — the DB-error fail-open is observable', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.resetModules();
    authFn.mockResolvedValue(SESSION);
  });

  it('⚠️ #182(1): the lookup throws → the request is REFUSED, loudly, and nothing is served', async () => {
    // ⚠️ THIS ARM ASSERTED THE OPPOSITE UNTIL 2026-09-04, AND ITS OWN COMMENT
    // SAID SO: "Behaviour UNCHANGED — this ships observability only. If this
    // assertion ever flips, the pending ruling was applied without updating
    // this file."
    //
    // The ruling came. #182(1) separates two answers this branch used to merge:
    //   · a DEFINITIVE "revoked / inactive"  → the session is invalid
    //   · "the database could not answer"    → the REQUEST is refused, 503,
    //     the session is NOT ended and the cookie is NOT cleared
    //
    // Serving from JWT-claimed `role` and `practiceId` admitted a deactivated,
    // suspended or soft-deleted account for the life of the token. The
    // observability this file shipped is exactly what made the ruling possible,
    // and it is KEPT — only the RETURN moved, which is why the log assertions
    // below are unchanged in spirit.
    const spy = vi.spyOn(console, 'error').mockImplementation(() => {});
    findUnique.mockRejectedValue(new Error('pool timeout'));

    await expect(
      callGetSession(),
      'the session was still served from JWT claims — the fail-open is back',
    ).rejects.toThrow(/SESSION_UNVERIFIABLE|could not be verified/i);

    const logged = spy.mock.calls.map((c) => String(c[0])).join('\n');
    expect(logged, 'the refusal fired and said nothing').toContain('SESSION_UNVERIFIABLE');
    // The message must still name the CONSEQUENCE rather than the operation.
    expect(logged).toMatch(/isActive/);
    // ⚠️ AND IT MUST SAY THE SESSION SURVIVES. A refusal that reads like a
    // sign-out sends whoever is on call looking for the wrong thing.
    expect(logged).toMatch(/NOT ended|NOT cleared/);
    spy.mockRestore();
  });

  it('SILENT: the lookup succeeds → nothing is logged', async () => {
    const spy = vi.spyOn(console, 'error').mockImplementation(() => {});
    findUnique.mockResolvedValue({ role: 'DOCTOR', isActive: true, practiceId: 'prac_1' });

    const s = await callGetSession();

    expect(s).not.toBeNull();
    const logged = spy.mock.calls.map((c) => String(c[0])).join('\n');
    expect(logged, 'a healthy lookup must not raise the alarm').not.toContain('SESSION_FAILOPEN');
    spy.mockRestore();
  });

  it('SILENT: a deactivated user on a HEALTHY database is REFUSED, with no alarm', async () => {
    const spy = vi.spyOn(console, 'error').mockImplementation(() => {});
    findUnique.mockResolvedValue({ role: 'DOCTOR', isActive: false, practiceId: 'prac_1' });

    const s = await callGetSession();

    // This is the control that makes the first test mean something: the alarm
    // must distinguish "we could not check" from "we checked and said no".
    expect(s, 'a deactivated user was served on a healthy database').toBeNull();
    const logged = spy.mock.calls.map((c) => String(c[0])).join('\n');
    expect(logged, 'a working refusal must not look like a fail-open').not.toContain('SESSION_FAILOPEN');
    spy.mockRestore();
  });
});
