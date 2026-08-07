// ============================================================================
// getSession's DB-error path FAILS OPEN — and now says so out loud.
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

  it('FIRES: the lookup throws → SESSION_FAILOPEN is logged AND the session is still served', async () => {
    const spy = vi.spyOn(console, 'error').mockImplementation(() => {});
    findUnique.mockRejectedValue(new Error('pool timeout'));

    const s = await callGetSession();

    // Behaviour UNCHANGED — this ships observability only. If this assertion
    // ever flips, the pending ruling was applied without updating this file.
    expect(s, 'the fail-open behaviour changed; that is a war-room ruling').not.toBeNull();
    expect(s?.user.practiceId).toBe('prac_1');

    const logged = spy.mock.calls.map((c) => String(c[0])).join('\n');
    expect(logged, 'the fail-open fired and said nothing').toContain('SESSION_FAILOPEN');
    // The message must name the CONSEQUENCE, not just the operation — "user
    // lookup failed" reads as a hiccup; the point is that isActive was skipped.
    expect(logged).toMatch(/isActive/);
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
