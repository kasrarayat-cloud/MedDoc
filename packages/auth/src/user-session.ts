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
//   3. A JWT without a sessionId is invalid. The T-M2 migration grace
//      period is over; every authenticated request must bind to an exact
//      current UserSession row and current database identity.
//
// Runs in Node only. DO NOT import this from files that the edge
// middleware bundle pulls in.
// ============================================================================

import prisma from "@meddoc/db";
import { randomUUID, createHash } from "node:crypto";

/** Default TTL for the UserSession row (not the JWT). The JWT's own
 *  maxAge — set per-app in each nextauth.ts — is the primary session
 *  lifetime; this just ensures rows don't accumulate forever. 7 days
 *  is the TranscribeMD TTL and is a safe upper bound for the shorter
 *  clinical apps too. */
const DEFAULT_USER_SESSION_TTL_MS = 7 * 24 * 60 * 60 * 1000;

export type CurrentSessionUserRole =
  | "DOCTOR"
  | "STAFF"
  | "ADMIN"
  | "SUPER_ADMIN";

export type CurrentSessionProduct =
  | "MEDDOC_PRO"
  | "TRANSCRIBE_MD"
  | "SUPER_ADMIN";

export interface SessionValidationGrant {
  allowedRoles?: readonly CurrentSessionUserRole[];
  requiredProducts?: readonly CurrentSessionProduct[];
}

export interface SessionValidationPolicy extends SessionValidationGrant {
  /** Optional disjunction for surfaces with two independently sufficient
   * current-database grants. An empty array denies every session. */
  anyOf?: readonly SessionValidationGrant[];
}

export interface ValidateSessionInput extends SessionValidationPolicy {
  sessionToken: string;
  expectedUserId: string;
  expectedPracticeId: string;
  now?: Date;
}

export interface RevokeAllUserSessionsFromCurrentSessionInput {
  /** Exact opaque token carried by the signed JWT. */
  sessionToken: string;
  /** Exact user bound into the same signed JWT. */
  userId: string;
  now?: Date;
}

function satisfiesSessionGrant(
  user: {
    role: CurrentSessionUserRole;
    products: readonly CurrentSessionProduct[];
  },
  grant: SessionValidationGrant,
): boolean {
  return (
    (grant.allowedRoles === undefined ||
      grant.allowedRoles.includes(user.role)) &&
    (grant.requiredProducts === undefined ||
      grant.requiredProducts.every((product) =>
        user.products.includes(product),
      ))
  );
}

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
 * The delete+insert runs inside a transaction while locking the canonical
 * user row. PostgreSQL therefore serializes concurrent sign-ins for the same
 * user; the later transaction revokes the earlier token before creating its
 * own, so at most one UserSession remains after both commits.
 */
export async function recordSessionLogin(input: RecordSessionLoginInput) {
  const ttl = input.ttlMs ?? DEFAULT_USER_SESSION_TTL_MS;
  const expiresAt = new Date(Date.now() + ttl);
  return prisma.$transaction(async (tx: typeof prisma) => {
    const lockedUsers = (await tx.$queryRaw`
      SELECT "id"
      FROM "users"
      WHERE "id" = ${input.userId}
      FOR UPDATE
    `) as Array<{ id: string }>;
    if (lockedUsers.length !== 1 || lockedUsers[0]?.id !== input.userId) {
      throw new Error("Unable to establish current session authority.");
    }
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
 * Resolve the opaque token to an exact current database identity. Session,
 * user, tenant, lifecycle, role-policy, product, and practice-state checks
 * are one fail-closed decision. A practice transfer invalidates the old JWT
 * rather than silently moving an in-flight browser session to another tenant.
 *
 * The lastActiveAt update is fire-and-forget; a DB blip must NOT cause
 * the session to flap between valid/invalid.
 */
export async function validateSession(input: ValidateSessionInput) {
  if (
    !input.sessionToken ||
    !input.expectedUserId ||
    !input.expectedPracticeId
  ) {
    return null;
  }
  const now = input.now ?? new Date();
  const row = await prisma.userSession.findUnique({
    where: { sessionToken: input.sessionToken },
    select: {
      id: true,
      userId: true,
      createdAt: true,
      expiresAt: true,
      user: {
        select: {
          id: true,
          email: true,
          name: true,
          role: true,
          practiceId: true,
          products: true,
          isActive: true,
          deactivatedAt: true,
          suspendedAt: true,
          softDeletedAt: true,
          forceLogoutAt: true,
          practice: {
            select: {
              id: true,
              isActive: true,
            },
          },
        },
      },
    },
  });
  if (!row) return null;
  if (row.expiresAt <= now) {
    // Clean up on the way out. deleteMany rather than delete so a race
    // with another validator doesn't throw P2025.
    await prisma.userSession
      .deleteMany({ where: { id: row.id } })
      .catch(() => {});
    return null;
  }

  const user = row.user;
  if (
    row.userId !== input.expectedUserId ||
    user.id !== input.expectedUserId ||
    user.practiceId !== input.expectedPracticeId ||
    user.practice.id !== user.practiceId ||
    user.practice.isActive !== true ||
    user.isActive !== true ||
    user.deactivatedAt !== null ||
    user.suspendedAt !== null ||
    user.softDeletedAt !== null ||
    row.createdAt > now ||
    (user.forceLogoutAt !== null && user.forceLogoutAt >= row.createdAt) ||
    !satisfiesSessionGrant(user, input) ||
    (input.anyOf !== undefined &&
      !input.anyOf.some((grant) => satisfiesSessionGrant(user, grant)))
  ) {
    return null;
  }

  void prisma.userSession
    .updateMany({
      where: {
        id: row.id,
        userId: input.expectedUserId,
        sessionToken: input.sessionToken,
      },
      data: { lastActiveAt: now },
    })
    .catch(() => {
      // Database-driver errors can embed connection URLs and credentials.
      // Session touch is best-effort, so log only a fixed operational code.
      console.error("[auth] UserSession.lastActiveAt touch failed");
    });
  return row;
}

/** Revoke one specific session — used by the /settings "Sign out" button. */
export async function revokeSession(sessionToken: string) {
  await prisma.userSession.deleteMany({ where: { sessionToken } });
}

/**
 * Revoke every session only while the calling JWT still identifies an exact,
 * current UserSession for an active user in an active practice.
 *
 * Practice, user, and exact session locks remain held through deletion. This
 * serializes against a concurrent login's canonical user lock: if the newer
 * login commits first, the stale token row is gone and this operation denies
 * without deleting the replacement session.
 */
export async function revokeAllUserSessionsFromCurrentSession(
  input: RevokeAllUserSessionsFromCurrentSessionInput,
): Promise<boolean> {
  const now = input.now ?? new Date();
  const nowMs = now.getTime();
  if (!input.sessionToken || !input.userId || !Number.isFinite(nowMs)) {
    return false;
  }

  return prisma.$transaction(async (tx: typeof prisma) => {
    // The join supplies only a routing hint. The exact association is checked
    // again after the canonical user row is locked below.
    const lockedPractices = (await tx.$queryRaw`
      SELECT practice."id", practice."isActive"
      FROM "practices" practice
      JOIN "users" account
        ON account."practiceId" = practice."id"
      WHERE account."id" = ${input.userId}
      FOR UPDATE OF practice
    `) as Array<{ id: string; isActive: boolean }>;
    if (lockedPractices.length !== 1 || lockedPractices[0]?.isActive !== true) {
      return false;
    }

    const lockedUsers = (await tx.$queryRaw`
      SELECT
        "id",
        "practiceId",
        "isActive",
        "deactivatedAt",
        "suspendedAt",
        "softDeletedAt",
        "forceLogoutAt"
      FROM "users"
      WHERE "id" = ${input.userId}
      FOR UPDATE
    `) as Array<{
      id: string;
      practiceId: string;
      isActive: boolean;
      deactivatedAt: Date | null;
      suspendedAt: Date | null;
      softDeletedAt: Date | null;
      forceLogoutAt: Date | null;
    }>;
    const user = lockedUsers[0];
    if (
      lockedUsers.length !== 1 ||
      !user ||
      user.id !== input.userId ||
      user.practiceId !== lockedPractices[0]?.id ||
      user.isActive !== true ||
      user.deactivatedAt !== null ||
      user.suspendedAt !== null ||
      user.softDeletedAt !== null
    ) {
      return false;
    }

    const lockedSessions = (await tx.$queryRaw`
      SELECT "id", "userId", "createdAt", "expiresAt"
      FROM "user_sessions"
      WHERE "userId" = ${input.userId}
        AND "sessionToken" = ${input.sessionToken}
      FOR UPDATE
    `) as Array<{
      id: string;
      userId: string;
      createdAt: Date;
      expiresAt: Date;
    }>;
    const session = lockedSessions[0];
    const createdAtMs = session?.createdAt.getTime() ?? Number.NaN;
    const expiresAtMs = session?.expiresAt.getTime() ?? Number.NaN;
    if (
      lockedSessions.length !== 1 ||
      !session ||
      session.userId !== input.userId ||
      !Number.isFinite(createdAtMs) ||
      !Number.isFinite(expiresAtMs) ||
      createdAtMs > nowMs ||
      expiresAtMs <= nowMs ||
      (user.forceLogoutAt !== null &&
        user.forceLogoutAt.getTime() >= createdAtMs)
    ) {
      return false;
    }

    await tx.userSession.deleteMany({ where: { userId: input.userId } });
    return true;
  });
}

/** Low-level revocation for trusted server-side lifecycle cleanup. JWT-driven
 * actions must use revokeAllUserSessionsFromCurrentSession instead. */
export async function revokeAllUserSessions(userId: string) {
  await prisma.userSession.deleteMany({ where: { userId } });
}

/** List currently-active sessions for a user. Used by /settings to show
 *  which device is logged in. With single-session enforcement the list
 *  is always length 0 or 1, but the shape anticipates a future relaxation. */
export async function getUserSessions(userId: string) {
  return prisma.userSession.findMany({
    where: { userId, expiresAt: { gt: new Date() } },
    orderBy: { lastActiveAt: "desc" },
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
  acceptLanguage: string | null | undefined,
): string | null {
  if (!userAgent && !acceptLanguage) return null;
  return createHash("sha256")
    .update(`${userAgent ?? ""}|${acceptLanguage ?? ""}`)
    .digest("hex")
    .slice(0, 32);
}
