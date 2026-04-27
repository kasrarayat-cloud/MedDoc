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

/** Maximum age of an admin session, in hours. JWT row in user_sessions
 *  older than this is rejected for /admin/* (the cookie itself stays
 *  valid for the doctor flow on app.quillmd.com). */
export const ADMIN_SESSION_MAX_AGE_HOURS = 12;

const ADMIN_SESSION_MAX_AGE_MS = ADMIN_SESSION_MAX_AGE_HOURS * 60 * 60 * 1000;

/** Returns `true` when the session row is older than the admin ceiling
 *  OR can't be located (defensive — a missing row implies the session
 *  was rotated/revoked and shouldn't grant admin access).
 *
 *  Pass `null`/`undefined` for legacy sessions issued before the
 *  T-M2 sessionId tracking landed; those return `true` (force re-login)
 *  so admins on stale cookies pick up the new posture. */
export async function isAdminSessionStale(
  sessionId: string | null | undefined
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
  } catch (err) {
    // Fail CLOSED on the admin surface — DB unreachable means we can't
    // verify freshness, and admin actions are too sensitive to let
    // through on a transient outage. Symmetrical with the page-layout
    // gate's notFound() posture.
    console.error(
      '[admin-session-freshness] DB read failed; treating as stale:',
      err instanceof Error ? err.message : err
    );
    return true;
  }
}
