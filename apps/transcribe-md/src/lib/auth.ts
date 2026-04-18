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

export { AuthError };
export type { Session, UserRole };

export async function getSession(): Promise<Session | null> {
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

    return {
      user: {
        id: nextAuthSession.user.id,
        email: nextAuthSession.user.email ?? '',
        fullName: nextAuthSession.user.name ?? 'Unknown',
        role,
        practiceId,
      },
    };
  } catch {
    return null;
  }
}

export async function requireSession(): Promise<Session> {
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
