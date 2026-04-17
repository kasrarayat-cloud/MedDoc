// ============================================================================
// Authentication & RBAC Helpers (apps/meddoc-pro)
// ----------------------------------------------------------------------------
// Types moved to @meddoc/auth in M1 so apps/scribe can share them; the
// getSession() logic stays here because it depends on THIS app's NextAuth
// instance (which adds the Credentials provider + signIn audit events).
// apps/scribe has its own parallel getSession().
// ============================================================================

import { headers } from 'next/headers';
import { auth } from '@/lib/nextauth';
import prisma from '@meddoc/db';
import { AuthError, type Session, type UserRole } from '@meddoc/auth';

export { AuthError };
export type { Session, UserRole };

const USE_MOCK_SESSION = process.env.AUTH_USE_MOCK === 'true';

function getMockSession(): Session {
  return {
    user: {
      id: 'mock_user_doctor_01',
      email: 'doctor@meddoc.local',
      fullName: 'Dr. Bakhtiar Moussazadeh',
      role: 'DOCTOR',
      practiceId: 'clinic_main',
    },
  };
}

/**
 * Get the current authenticated user session.
 * Returns null if not logged in.
 */
export async function getSession(): Promise<Session | null> {
  try {
    const nextAuthSession = await auth();
    if (nextAuthSession?.user?.id) {
      let role = nextAuthSession.user.role as UserRole | undefined;
      let practiceId = nextAuthSession.user.practiceId as string | undefined;

      try {
        const dbUser = await prisma.user.findUnique({
          where: { id: nextAuthSession.user.id },
          select: { role: true, isActive: true, practiceId: true },
        });
        if (!dbUser || !dbUser.isActive) {
          return null;
        }
        if (!role && dbUser.role) role = dbUser.role as UserRole;
        if (dbUser.practiceId) practiceId = dbUser.practiceId;
      } catch {
        // DB unreachable — fail open using the JWT's cached claims.
      }

      if (role && practiceId) {
        return {
          user: {
            id: nextAuthSession.user.id,
            email: nextAuthSession.user.email ?? '',
            fullName: nextAuthSession.user.name ?? 'Unknown',
            role,
            practiceId,
          },
        };
      }
    }
  } catch {
    // auth() threw — fall through to dev fallback / unauth below.
  }

  if (USE_MOCK_SESSION) {
    return getMockSession();
  }

  return null;
}

/**
 * Authorization guard. Throws `AuthError` if the user is not logged in
 * or doesn't have one of the allowed roles.
 */
export async function requireRole(allowed: UserRole[]): Promise<Session> {
  const session = await getSession();
  if (!session) {
    throw new AuthError('UNAUTHENTICATED', 'You must be logged in.');
  }
  if (!allowed.includes(session.user.role)) {
    throw new AuthError(
      'FORBIDDEN',
      `Role ${session.user.role} cannot perform this action.`
    );
  }
  return session;
}

/**
 * Get the request IP and user-agent from Next.js headers (server-side only).
 */
export async function getRequestContext(): Promise<{
  ipAddress: string | null;
  userAgent: string | null;
}> {
  try {
    const h = await headers();
    const ipAddress =
      h.get('x-forwarded-for')?.split(',')[0]?.trim() ||
      h.get('x-real-ip') ||
      null;
    const userAgent = h.get('user-agent') || null;
    return { ipAddress, userAgent };
  } catch {
    return { ipAddress: null, userAgent: null };
  }
}
