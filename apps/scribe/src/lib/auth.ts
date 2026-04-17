// ============================================================================
// apps/scribe — getSession() wrapper
// ----------------------------------------------------------------------------
// Parallel to apps/meddoc-pro/src/lib/auth.ts but backed by apps/scribe's
// own (provider-less) NextAuth instance. Calls auth() to read the shared
// JWT cookie, then re-reads the DB to refresh isActive/role/practiceId —
// same "emergency revocation takes effect on next request" semantics.
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
