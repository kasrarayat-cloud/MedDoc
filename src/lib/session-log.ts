// ============================================================================
// Session Login Logger
// ----------------------------------------------------------------------------
// Captures the real client IP/UA from request headers (via getRequestContext)
// and persists them on successful sign-in:
//   1. User.lastLoginIp — denormalized source of truth for the admin table
//   2. SessionLog row   — per-login audit trail
//
// Fire-and-forget: call sites (events.signIn in NextAuth) must not fail
// login when logging fails. `x-forwarded-for` / `x-real-ip` are honored
// inside getRequestContext; with no reverse proxy, ipAddress comes back
// null and we store null honestly rather than a fake fallback.
// ============================================================================

import prisma, { isDatabaseHealthy } from './db';
import { getRequestContext } from './auth';

export async function recordLoginIp(
  userId: string,
  practiceId: string
): Promise<void> {
  try {
    if (!(await isDatabaseHealthy())) return;

    const { ipAddress, userAgent } = await getRequestContext();

    // Write BOTH rows even if ipAddress is null — we still want the
    // session log (the row proves the login happened). The admin UI
    // renders '--' when ipAddress is null, which is the honest display.
    await Promise.all([
      prisma.user.update({
        where: { id: userId },
        data: { lastLoginIp: ipAddress },
      }),
      prisma.sessionLog.create({
        data: {
          userId,
          practiceId,
          ipAddress,
          userAgent: userAgent ?? null,
          action: 'LOGIN',
        },
      }),
    ]);
  } catch (err) {
    console.warn('[session-log] recordLoginIp failed:', err);
  }
}
