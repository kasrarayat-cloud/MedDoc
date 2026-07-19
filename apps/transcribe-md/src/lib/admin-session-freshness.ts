// ============================================================================
// Admin-route session-freshness gate (Phase 19, h16-admin-session-7day)
// ----------------------------------------------------------------------------
// transcribe-md sets session.maxAge = 7 days because the consumer-doctor
// surface (app.quillmd.com) doesn't want users re-logging-in every 8
// hours. But admin.quillmd.com — which holds full PHI access + tenant-
// admin powers — inherited that 7-day TTL because the same NextAuth
// instance issues the cookie.
//
// This helper caps the admin surface specifically: a JWT older than
// ADMIN_SESSION_MAX_AGE_HOURS (12h by default) is rejected for /admin/*
// even though the cookie itself stays valid for the doctor flow.
//
// "Older than 12 h" means: the user_sessions row keyed by the JWT's
// sessionId was created more than 12 h ago. (We use the DB row, not
// the JWT iat, because the JWT is rolled forward by `updateAge`
// every 24 h and the iat would drift.)
//
// Usage:
//   const stale = await isAdminSessionStale(sessionId);
//   if (stale) return notFoundResponse();   // API
//   if (stale) notFound();                  // page
// ============================================================================

import prisma from '@meddoc/db';
import { Product, type UserRole } from '@prisma/client';

/** Maximum age of an admin session, in hours. JWT row in user_sessions
 *  older than this is rejected for /admin/* (the cookie itself stays
 *  valid for the doctor flow on app.quillmd.com). */
export const ADMIN_SESSION_MAX_AGE_HOURS = 12;

const ADMIN_SESSION_MAX_AGE_MS = ADMIN_SESSION_MAX_AGE_HOURS * 60 * 60 * 1000;

export interface VerifiedPlatformAdminSession {
  userId: string;
  email: string | null;
  role: UserRole;
  practiceId: string;
  sessionId: string;
  sessionCreatedAt: Date;
  sessionExpiresAt: Date;
  mfaEnabled: boolean;
  mfaVerifiedAt: Date | null;
}

interface VerifyPlatformAdminSessionInput {
  claimedUserId: string | null | undefined;
  sessionId: string | null | undefined;
  /** The page gate sets this false only to route an otherwise-valid operator
   * to MFA enrollment. Mutating APIs always use the default `true`. */
  requireMfa?: boolean;
  now?: Date;
}

/**
 * Secure, database-backed authorization for the platform-admin surface.
 * This deliberately duplicates the ordinary JWT callback's lifecycle checks:
 * that callback is availability-oriented and fails open on a transient DB
 * error, while platform administration must fail closed.
 */
export async function verifyFreshPlatformAdminSession(
  input: VerifyPlatformAdminSessionInput,
): Promise<VerifiedPlatformAdminSession | null> {
  if (!input.claimedUserId || !input.sessionId) return null;
  const now = input.now ?? new Date();

  try {
    const row = await prisma.userSession.findFirst({
      where: {
        sessionToken: input.sessionId,
        userId: input.claimedUserId,
      },
      select: {
        id: true,
        userId: true,
        createdAt: true,
        expiresAt: true,
        user: {
          select: {
            id: true,
            email: true,
            role: true,
            practiceId: true,
            products: true,
            isActive: true,
            deactivatedAt: true,
            suspendedAt: true,
            softDeletedAt: true,
            forceLogoutAt: true,
            mfaEnabled: true,
            mfaSecret: true,
            mfaVerifiedAt: true,
          },
        },
      },
    });
    if (!row || row.userId !== input.claimedUserId) return null;

    const user = row.user;
    if (
      user.id !== input.claimedUserId ||
      !user.isActive ||
      user.deactivatedAt ||
      user.suspendedAt ||
      user.softDeletedAt ||
      !user.products.includes(Product.SUPER_ADMIN)
    ) {
      return null;
    }

    const createdAtMs = row.createdAt.getTime();
    const nowMs = now.getTime();
    if (
      !Number.isFinite(createdAtMs) ||
      createdAtMs > nowMs ||
      nowMs - createdAtMs >= ADMIN_SESSION_MAX_AGE_MS ||
      row.expiresAt.getTime() <= nowMs ||
      (user.forceLogoutAt !== null &&
        user.forceLogoutAt.getTime() >= createdAtMs)
    ) {
      return null;
    }

    if (
      input.requireMfa !== false &&
      (!user.mfaEnabled || !user.mfaSecret || user.mfaVerifiedAt === null)
    ) {
      return null;
    }

    return {
      userId: user.id,
      email: user.email,
      role: user.role,
      practiceId: user.practiceId,
      sessionId: input.sessionId,
      sessionCreatedAt: row.createdAt,
      sessionExpiresAt: row.expiresAt,
      mfaEnabled: user.mfaEnabled,
      mfaVerifiedAt: user.mfaVerifiedAt,
    };
  } catch {
    // Do not log the Prisma error text here: connection errors can include a
    // credential-bearing URL. The caller receives only a closed decision.
    console.error(
      '[admin-session-freshness] database verification failed; access denied',
    );
    return null;
  }
}

/** Returns `true` when the session row is older than the admin ceiling
 *  OR can't be located (defensive — a missing row implies the session
 *  was rotated/revoked and shouldn't grant admin access).
 *
 *  Pass `null`/`undefined` for legacy sessions issued before the
 *  T-M2 sessionId tracking landed; those return `true` (force re-login)
 *  so admins on stale cookies pick up the new posture. */
export async function isAdminSessionStale(
  sessionId: string | null | undefined,
): Promise<boolean> {
  if (!sessionId) return true;
  try {
    const row = await prisma.userSession.findUnique({
      where: { sessionToken: sessionId },
      select: { createdAt: true },
    });
    if (!row) return true;
    const ageMs = Date.now() - row.createdAt.getTime();
    return ageMs > ADMIN_SESSION_MAX_AGE_MS;
  } catch {
    // Fail CLOSED on the admin surface — DB unreachable means we can't
    // verify freshness, and admin actions are too sensitive to let
    // through on a transient outage. Symmetrical with the page-layout
    // gate's notFound() posture.
    console.error(
      '[admin-session-freshness] database freshness read failed; treating as stale',
    );
    return true;
  }
}
