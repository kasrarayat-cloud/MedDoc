// ============================================================================
// @meddoc/auth — UserSession helpers (T-M2 anti-account-sharing)
// ----------------------------------------------------------------------------
// A UserSession row represents one active login. The JWT the user carries
// in their cookie has a `sessionId` claim that points at this row. Rules:
//
//   1. A new login DELETES every prior UserSession for the user and inserts
//      a fresh row. Older JWTs — carrying stale sessionIds — no longer
//      resolve and are treated as signed out on their next request.
//
//   2. Every authenticated request (via the shared authConfig jwt callback)
//      validates the sessionId against the DB. Missing or expired → the
//      JWT is invalidated (jwt callback returns null) and the user is
//      redirected to /login.
//
//   3. JWTs minted before T-M2 rollout have NO sessionId claim. The jwt
//      callback treats those as legacy and lets them through so nobody
//      gets kicked off the moment the deploy lands. Their next login
//      takes them onto the new path.
//
// Runs in Node only. DO NOT import this from files that the edge
// middleware bundle pulls in.
// ============================================================================

import prisma from '@meddoc/db';
import type { TransactionClient } from '@meddoc/db';
import { PRACTICE_ADMITS_SELECT, practiceAdmits } from '@meddoc/db/practice-admits';
import { randomUUID, createHash } from 'node:crypto';

/** Default TTL for the UserSession row (not the JWT). The JWT's own
 *  maxAge — set per-app in each nextauth.ts — is the primary session
 *  lifetime; this just ensures rows don't accumulate forever. 7 days
 *  is the TranscribeMD TTL and is a safe upper bound for the shorter
 *  clinical apps too. */
const DEFAULT_USER_SESSION_TTL_MS = 7 * 24 * 60 * 60 * 1000;

export interface RecordSessionLoginInput {
  userId: string;
  /** Opaque token stored on the row and written into the JWT's
   *  `sessionId` claim. Generate with randomSessionToken() unless you
   *  need to align with an externally-issued ID. */
  sessionToken: string;
  ipAddress?: string | null;
  userAgent?: string | null;
  deviceFingerprint?: string | null;
  /** Override the default 7-day TTL for this row. */
  ttlMs?: number;
}

/**
 * Atomically revoke every prior UserSession for this user and create a
 * new one. Called from the shared jwt() callback when a successful
 * sign-in happens (i.e. `user` is present).
 *
 * The delete+insert runs inside a transaction so a concurrent second
 * sign-in can't see a partial "no sessions" state.
 */
export async function recordSessionLogin(input: RecordSessionLoginInput) {
  const ttl = input.ttlMs ?? DEFAULT_USER_SESSION_TTL_MS;
  const expiresAt = new Date(Date.now() + ttl);
  return prisma.$transaction(async (tx: TransactionClient) => {
    await tx.userSession.deleteMany({ where: { userId: input.userId } });
    return tx.userSession.create({
      data: {
        userId: input.userId,
        sessionToken: input.sessionToken,
        ipAddress: input.ipAddress ?? null,
        userAgent: input.userAgent ?? null,
        deviceFingerprint: input.deviceFingerprint ?? null,
        expiresAt,
      },
    });
  });
}

/**
 * Look up the UserSession by its opaque token. Returns the row when the
 * session is still valid (exists + not expired) and touches lastActiveAt
 * so the settings UI can show a live "last seen" timestamp. Returns null
 * when the row is absent (revoked by a newer login elsewhere) or has
 * passed its expiresAt — callers treat both as "signed out".
 *
 * The lastActiveAt update is fire-and-forget; a DB blip must NOT cause
 * the session to flap between valid/invalid.
 */
export async function validateSession(sessionToken: string) {
  // Phase 6: include the user's lifecycle fields so we can invalidate
  // sessions for suspended / soft-deleted / inactive accounts AND for
  // sessions issued before the latest forceLogoutAt (suspend / soft-
  // delete / revoke-admin all bump that timestamp). One JOIN keeps
  // the per-request cost the same as the original single-row lookup.
  const row = await prisma.userSession.findUnique({
    where: { sessionToken },
    include: {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      user: {
        select: {
          isActive: true,
          suspendedAt: true,
          softDeletedAt: true,
          forceLogoutAt: true,
          // ADMIN-6a D2 — the member's PRACTICE, through the one predicate's
          // own select. Same JOIN depth as the user lookup it rides on.
          practice: { select: PRACTICE_ADMITS_SELECT },
        } as any,
      },
    },
  });
  if (!row) return null;
  if (row.expiresAt <= new Date()) {
    // Clean up on the way out. deleteMany rather than delete so a race
    // with another validator doesn't throw P2025.
    await prisma.userSession
      .deleteMany({ where: { id: row.id } })
      .catch(() => {});
    return null;
  }

  // Phase 6 lifecycle gates. The Prisma client's typing for `user` here
  // is the strict User shape and may not yet include the new admin
  // fields (depending on regen state in CI), so we read them via an
  // `any`-cast and treat missing values as "not set". The actual columns
  // are NULL by default for accounts that have never been touched by an
  // admin action, so the fast path is unchanged.
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const user = (row as any).user as
    | {
        isActive?: boolean;
        suspendedAt?: Date | null;
        softDeletedAt?: Date | null;
        forceLogoutAt?: Date | null;
        practice?: { isActive?: unknown } | null;
      }
    | undefined;
  // ⚠️ ADMIN-6a D2 — AN ARCHIVED PRACTICE ENDS EVERY ONE OF ITS SESSIONS HERE.
  // A `null` from this function is the DEFINITIVE answer (#182(1)): the jwt
  // callback returns null and the cookie goes. That one line covers every
  // `auth()`, `getSession()`/`requireSession()` and `adminApi()` caller in both
  // apps, which is why the practice flag needs no per-route check.
  //
  // ⚠️ FAIL-CLOSED ON ABSENCE, DELIBERATELY OUTSIDE `if (user)`. The user and
  // its practice are NOT NULL foreign keys, so in production both always load;
  // the only way to reach an absent practice is a select that forgot it, and
  // that must refuse rather than admit. `practiceAdmits` treats absence as no.
  if (!practiceAdmits(user?.practice)) return null;
  if (user) {
    if (user.isActive === false) return null;
    if (user.suspendedAt) return null;
    if (user.softDeletedAt) return null;
    if (user.forceLogoutAt && user.forceLogoutAt > row.createdAt) {
      // Session predates the latest force-logout marker — treat as
      // revoked. Don't delete the row (keep the audit trail of when
      // the session existed); the next login will overwrite it via
      // recordSessionLogin's delete-then-create transaction.
      return null;
    }
  }

  prisma.userSession
    .update({
      where: { id: row.id },
      data: { lastActiveAt: new Date() },
    })
    .catch((err: unknown) => {
      console.error('[auth] UserSession.lastActiveAt touch failed:', err);
    });
  return row;
}

/** Revoke one specific session — used by the /settings "Sign out" button. */
export async function revokeSession(sessionToken: string) {
  await prisma.userSession.deleteMany({ where: { sessionToken } });
}

/** Revoke every session for this user — used by "Sign out all devices". */
export async function revokeAllUserSessions(userId: string) {
  await prisma.userSession.deleteMany({ where: { userId } });
}

/** List currently-active sessions for a user. Used by /settings to show
 *  which device is logged in. With single-session enforcement the list
 *  is always length 0 or 1, but the shape anticipates a future relaxation. */
export async function getUserSessions(userId: string) {
  return prisma.userSession.findMany({
    where: { userId, expiresAt: { gt: new Date() } },
    orderBy: { lastActiveAt: 'desc' },
  });
}

/** Generate an opaque, URL-safe session token. 36 chars, 122 bits of
 *  entropy — indistinguishable from random for an attacker guessing. */
export function randomSessionToken(): string {
  return randomUUID();
}

/**
 * Cheap, deterministic device fingerprint. Today it hashes UA +
 * Accept-Language; we can fold in client-side signals (canvas, font
 * metrics, timezone) later without changing the column shape since we
 * always store the hash digest.
 */
export function computeDeviceFingerprint(
  userAgent: string | null | undefined,
  acceptLanguage: string | null | undefined
): string | null {
  if (!userAgent && !acceptLanguage) return null;
  return createHash('sha256')
    .update(`${userAgent ?? ''}|${acceptLanguage ?? ''}`)
    .digest('hex')
    .slice(0, 32);
}
