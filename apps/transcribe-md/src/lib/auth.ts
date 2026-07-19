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
import {
  evaluateTemplateTwinRollout,
  pinTemplateTwinRollout,
  TemplateTwinRolloutError,
  type TemplateTwinRolloutToken,
} from '@/lib/template-twin/rollout';

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

/** Fresh, fail-closed role evidence for physician-only clinical surfaces.
 * `getSession()` intentionally tolerates a transient DB failure for legacy
 * session continuity, so a JWT role must never be the final authorization
 * decision for Template Twin. */
export async function requireFreshDoctorIdentity(userId: string): Promise<{
  role: 'DOCTOR';
  practiceId: string;
  rolloutToken: TemplateTwinRolloutToken;
}> {
  try {
    const user = await prisma.user.findUnique({
      where: { id: userId },
      select: {
        role: true,
        isActive: true,
        practiceId: true,
        practice: { select: { templateTwinEnabled: true } },
      },
    });
    if (
      !user ||
      !user.isActive ||
      user.role !== 'DOCTOR' ||
      !user.practiceId
    ) {
      throw new AuthError(
        'FORBIDDEN',
        'An active physician account is required for Template Twin.',
      );
    }
    const rollout = evaluateTemplateTwinRollout({
      practiceEnabled: user.practice.templateTwinEnabled,
    });
    if (!rollout.allowed) {
      throw new AuthError('FORBIDDEN', rollout.reason);
    }
    let rolloutToken: TemplateTwinRolloutToken;
    try {
      rolloutToken = await pinTemplateTwinRollout({
        practiceId: user.practiceId,
      });
    } catch (error) {
      if (error instanceof TemplateTwinRolloutError) {
        throw new AuthError('FORBIDDEN', error.message);
      }
      throw error;
    }
    return {
      role: 'DOCTOR',
      practiceId: user.practiceId,
      rolloutToken,
    };
  } catch (error) {
    if (error instanceof AuthError) throw error;
    // Role evidence is mandatory on this boundary. Do not fall back to a
    // potentially stale JWT when the database cannot confirm the role.
    throw new AuthError(
      'FORBIDDEN',
      'An active physician account is required for Template Twin.',
    );
  }
}

export type TemplateTwinDoctorSession = Session & {
  /**
   * The persisted global + practice generations admitted by the fresh
   * physician authorization check. Configuration mutations must carry this
   * exact token to their final transaction; they must never re-pin after
   * provider, rendering, or browser work has started.
   */
  templateTwinRolloutToken: TemplateTwinRolloutToken;
};

export async function requireDoctorSession(): Promise<TemplateTwinDoctorSession> {
  const nextAuthSession = await auth();
  if (!nextAuthSession?.user?.id) {
    throw new AuthError('UNAUTHENTICATED', 'You must be logged in.');
  }
  const doctor = await requireFreshDoctorIdentity(nextAuthSession.user.id);
  return {
    templateTwinRolloutToken: doctor.rolloutToken,
    user: {
      id: nextAuthSession.user.id,
      email: nextAuthSession.user.email ?? '',
      fullName: nextAuthSession.user.name ?? 'Unknown',
      role: doctor.role,
      practiceId: doctor.practiceId,
    },
  };
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
