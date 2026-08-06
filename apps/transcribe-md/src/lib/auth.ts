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
    } catch {
      // DB unreachable — fall through with JWT-claimed values.
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
