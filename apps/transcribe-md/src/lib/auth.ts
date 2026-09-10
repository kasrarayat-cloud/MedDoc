// ============================================================================
// apps/transcribe-md — getSession() wrapper
// ----------------------------------------------------------------------------
// Calls auth() to read the shared JWT cookie (validated by the shared
// jwt() callback, which enforces single-session via UserSession lookups).
// Re-reads the DB to refresh isActive/role/practiceId so emergency
// revocation takes effect on the next request. Same shape and semantics
// as apps/scribe/src/lib/auth.ts.
// ============================================================================

import { auth } from '@/lib/nextauth';
import prisma from '@meddoc/db';
import {
  AuthError,
  SessionUnverifiableError,
  type Session,
  type UserRole,
} from '@meddoc/auth';

import { asPracticeId, asUserId, type PracticeId, type UserId } from '@/lib/practice-scope';
import {
  PracticeHostRefusedError,
  assertHostAdmitsPractice,
  practiceHostRoutingEnabled,
} from '@/lib/practice-host';

export { AuthError };
export type { UserRole };

/**
 * ⚠️ THE SESSION, WITH ITS IDS BRANDED — T5's closing hardening.
 *
 * `@meddoc/auth`'s `Session` types both ids as `string`, so `visitScope(userId)`
 * compiles and scopes a query by the wrong identity. That exact mistake reached
 * nine call sites of `loadVisitExportData` and `tsc` was silent through all of
 * them.
 *
 * The narrowing lives HERE, in the app, rather than in `@meddoc/auth`, because
 * this is the boundary the accessor cares about and widening the shared package
 * would drag every consumer into the change for no benefit of their own.
 *
 * `PracticeId`/`UserId` are `string` at runtime — this costs nothing and changes
 * no behaviour. It is assignment-compatible in the safe direction only.
 */
export type ScopedSession = Omit<Session, 'user'> & {
  user: Omit<Session['user'], 'id' | 'practiceId'> & {
    id: UserId;
    practiceId: PracticeId;
  };
};

export type { Session };

export async function getSession(): Promise<ScopedSession | null> {
  try {
    const nextAuthSession = await auth();
    if (!nextAuthSession?.user?.id) return null;

    let role = nextAuthSession.user.role as UserRole | undefined;
    let practiceId = nextAuthSession.user.practiceId as string | undefined;

    // ⚠️ RULING #182(1) — THE TOKEN MAY SAY "I COULD NOT BE VERIFIED".
    // `packages/auth`'s jwt callback marks a token whose `validateSession`
    // lookup THREW, rather than returning null (which would clear the cookie
    // and eject a working doctor over a blip). Reading such a token as a
    // session is exactly the fail-open this ruling ends.
    if ((nextAuthSession.user as { sessionVerifyFailed?: boolean }).sessionVerifyFailed) {
      throw new SessionUnverifiableError('validateSession could not reach the database');
    }

    try {
      const dbUser = await prisma.user.findUnique({
        where: { id: nextAuthSession.user.id },
        select: { role: true, isActive: true, practiceId: true },
      });
      // ⚠️ A DEFINITIVE ANSWER. The database replied and the account is gone or
      // deactivated: the session is invalid, full stop.
      if (!dbUser || !dbUser.isActive) return null;
      if (!role && dbUser.role) role = dbUser.role as UserRole;
      if (dbUser.practiceId) practiceId = dbUser.practiceId;
    } catch (err) {
      // ⚠️ THE RESERVED FAIL-OPEN IS SETTLED — RULING #182(1) RULES IT THE SAME
      // WAY AS ITS SIBLING. The comment that stood here said the trade-off was
      // "a war-room ruling, not a code decision — it is pending". The ruling
      // came, and it is: a lookup that CANNOT ANSWER refuses the request.
      //
      // What that comment got exactly right, and what this fix keeps: this does
      // NOT require the database to be down. `PRISMA_POOL_MAX=10` with a 20s
      // pool timeout makes failures PER-QUERY under load, so this lookup can
      // time out while the clinical queries after it succeed. That is the shape
      // that ADMITS a request rather than breaking it — which is why serving
      // from JWT claims was never safe, and equally why ejecting the doctor
      // would be wrong. The answer is neither: refuse THIS request, keep the
      // session, let the next one re-validate.
      //
      // The log is kept verbatim in spirit — it is what made the ruling
      // possible — with the consequence line corrected, because it now
      // describes a refusal rather than an admission.
      console.error(
        '[auth] SESSION_UNVERIFIABLE: user lookup failed — isActive/role/' +
          'practiceId could NOT be verified against the database. The request ' +
          'is REFUSED (503) and no JWT-claimed values are served. The session ' +
          'is NOT ended and the cookie is NOT cleared.',
        {
          userId: nextAuthSession.user.id,
          hadRoleClaim: Boolean(role),
          hadPracticeClaim: Boolean(practiceId),
          error: err instanceof Error ? err.message : String(err),
        }
      );
      throw new SessionUnverifiableError('the user lookup could not reach the database');
    }

    if (!role || !practiceId) return null;

    // ⚠️ ADMIN-2 (#196) — ON A PRACTICE HOST, THE HOST'S PRACTICE MUST BE THE
    // USER'S. Checked AFTER the database re-read above, so it compares against
    // the practice the user is in NOW, not the one the token was minted with.
    // A mismatch throws `PracticeHostRefusedError` — by name, never `null`,
    // which every caller would read as "signed out". The flag is checked FIRST:
    // with it off, no header is read and no practice is queried.
    if (practiceHostRoutingEnabled()) {
      await assertHostAdmitsPractice(practiceId, nextAuthSession.user.id);
    }

    // ⚠️ THE ONE PLACE THE BRANDS ARE MINTED. `asPracticeId` refuses an empty
    // value, so a `PracticeId` anywhere downstream is a real, non-empty practice
    // — the accessor's runtime guard becomes a boundary check rather than a
    // last line of defence.
    return {
      user: {
        id: asUserId(nextAuthSession.user.id),
        email: nextAuthSession.user.email ?? '',
        fullName: nextAuthSession.user.name ?? 'Unknown',
        role,
        practiceId: asPracticeId(practiceId),
      },
    };
  } catch (err) {
    // ⚠️ #182(1) — THE UNVERIFIABLE REFUSAL MUST ESCAPE, AND THIS CATCH ATE IT.
    //
    // The inner handler throws `SessionUnverifiableError` when the database
    // could not answer. This outer `catch { return null }` swallowed it and
    // returned "no session" — which every caller reads as SIGNED OUT and
    // bounces to /login. That is EJECTION ON A BLIP: precisely the defect
    // #181(d) introduced and #182(1) exists to end, silently reintroduced by a
    // catch three lines below the fix.
    //
    // A fix whose throw cannot escape its own function is not a fix. Caught by
    // the arm in `auth-failopen-observability`, which asserted a rejection and
    // got `null`.
    if (err instanceof SessionUnverifiableError) throw err;
    // ADMIN-2 — the same trap, the same cure: a host refusal eaten here would
    // read as "signed out" and bounce to a /login the same host refuses again.
    if (err instanceof PracticeHostRefusedError) throw err;
    return null;
  }
}

export async function requireSession(): Promise<ScopedSession> {
  const s = await getSession();
  if (!s) throw new AuthError('UNAUTHENTICATED', 'You must be logged in.');
  return s;
}

/** Read the current NextAuth session cookie and return the JWT's
 *  sessionId claim (if present). Used by the /settings page to show
 *  the active UserSession row. Returns null when the user isn't
 *  signed in or their token pre-dates T-M2 (no sessionId yet). */
export async function getCurrentSessionId(): Promise<string | null> {
  const session = await auth();
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  return (session?.user as any)?.sessionId ?? null;
}
