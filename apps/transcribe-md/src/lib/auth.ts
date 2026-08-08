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
import { AuthError, type Session, type UserRole } from '@meddoc/auth';

import { asPracticeId, asUserId, type PracticeId, type UserId } from '@/lib/practice-scope';

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

    try {
      const dbUser = await prisma.user.findUnique({
        where: { id: nextAuthSession.user.id },
        select: { role: true, isActive: true, practiceId: true },
      });
      if (!dbUser || !dbUser.isActive) return null;
      if (!role && dbUser.role) role = dbUser.role as UserRole;
      if (dbUser.practiceId) practiceId = dbUser.practiceId;
    } catch (err) {
      // ⚠️ THIS IS A FAIL-OPEN, AND IT USED TO BE COMPLETELY SILENT.
      //
      // The line above — `if (!dbUser || !dbUser.isActive) return null` — is the
      // ONLY `isActive` check on this path. When the lookup throws, it never
      // executes, and the session is rebuilt from JWT-claimed `role` and
      // `practiceId`. So a DEACTIVATED, suspended, soft-deleted or
      // force-logged-out account continues to be served, bounded only by the
      // JWT's 8-hour maxAge.
      //
      // It does NOT require the database to be down. `PRISMA_POOL_MAX=10` with a
      // 20s pool timeout makes failures PER-QUERY under load — this lookup can
      // time out while the clinical queries that follow it succeed, which is
      // exactly the shape that admits a request rather than breaking it.
      //
      // ⚠️ THE BEHAVIOUR IS DELIBERATELY UNCHANGED HERE. Failing closed would
      // sign a clinician out mid-dictation on a transient blip, and that
      // trade-off is a war-room ruling, not a code decision — it is pending.
      // What ships now is the ability to KNOW. Previously this was `catch {}`
      // with a comment: if it had ever fired, in production, for any account, no
      // artefact anywhere would show it.
      //
      // ⚠️ AND IT IS A LOG, NOT AN AUDIT ROW, ON PURPOSE. An audit row writes to
      // the same database that just failed, so the one condition it exists to
      // record is the condition in which it is least likely to land. A row that
      // reliably fails to write during the event it describes is worse than a
      // log — it reads as coverage. `SESSION_FAILOPEN` is greppable; alert on it.
      console.error(
        '[auth] SESSION_FAILOPEN: user lookup failed — isActive/role/practiceId ' +
          'NOT verified against the database; serving JWT-claimed values. ' +
          'A revoked or deactivated account is admitted while this persists.',
        {
          userId: nextAuthSession.user.id,
          hadRoleClaim: Boolean(role),
          hadPracticeClaim: Boolean(practiceId),
          error: err instanceof Error ? err.message : String(err),
        }
      );
    }

    if (!role || !practiceId) return null;

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
  } catch {
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
