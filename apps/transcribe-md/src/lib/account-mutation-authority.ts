import "server-only";

import { Prisma, Product } from "@prisma/client";

import { hasCompleteMfaEnrollment } from "@/lib/mfa-enrollment-state";

const PLATFORM_ADMIN_SESSION_MAX_AGE_MS = 12 * 60 * 60 * 1000;

export type AccountMutationSurface = "physician" | "platform-admin";

export interface AccountMutationAuthorityInput {
  userId: string;
  sessionId: string | null | undefined;
  expectedPracticeId: string;
  surface: AccountMutationSurface;
  expectedPasswordHash?: string;
  expectedEmail?: string;
  /** Platform-admin mutations require complete current MFA by default.
   * First-time enrollment/verification may opt out explicitly. */
  requireMfa?: boolean;
  now?: Date;
}

export class AccountMutationAuthorityError extends Error {
  readonly code = "ACCOUNT_AUTHORITY_CHANGED" as const;

  constructor() {
    super("Current account-mutation authority could not be established.");
    this.name = "AccountMutationAuthorityError";
  }
}

function deny(): never {
  throw new AccountMutationAuthorityError();
}

/**
 * Final, transaction-scoped authority for credential, MFA, email, and account
 * mutations. The documented lock order is the Template Twin lifecycle
 * advisory lock, practice, user, then exact UserSession. User updates fire a
 * lifecycle trigger that takes the same advisory lock, so acquiring it first
 * avoids an inversion with release-control transactions. Callers must mutate
 * in this same transaction after this returns.
 */
export async function lockCurrentAccountMutationAuthority(
  tx: Prisma.TransactionClient,
  input: AccountMutationAuthorityInput,
) {
  if (!input.sessionId || !input.expectedPracticeId) deny();

  await tx.$queryRaw(Prisma.sql`
    SELECT pg_advisory_xact_lock(73119, 20260719)
  `);

  const lockedPractices = await tx.$queryRaw<Array<{ id: string }>>(Prisma.sql`
    SELECT "id"
    FROM "practices"
    WHERE "id" = ${input.expectedPracticeId}
    FOR UPDATE
  `);
  if (
    lockedPractices.length !== 1 ||
    lockedPractices[0]?.id !== input.expectedPracticeId
  ) {
    deny();
  }

  const lockedUsers = await tx.$queryRaw<Array<{ id: string }>>(Prisma.sql`
    SELECT "id"
    FROM "users"
    WHERE "id" = ${input.userId}
    FOR UPDATE
  `);
  if (lockedUsers.length !== 1 || lockedUsers[0]?.id !== input.userId) deny();

  const lockedSessions = await tx.$queryRaw<Array<{ id: string }>>(Prisma.sql`
    SELECT "id"
    FROM "user_sessions"
    WHERE "userId" = ${input.userId}
      AND "sessionToken" = ${input.sessionId}
    FOR UPDATE
  `);
  if (lockedSessions.length !== 1) deny();

  const [user, practice, session] = await Promise.all([
    tx.user.findUnique({
      where: { id: input.userId },
      select: {
        id: true,
        email: true,
        name: true,
        passwordHash: true,
        role: true,
        products: true,
        practiceId: true,
        isActive: true,
        deactivatedAt: true,
        suspendedAt: true,
        softDeletedAt: true,
        forceLogoutAt: true,
        mfaEnabled: true,
        mfaSecret: true,
        mfaVerifiedAt: true,
        mfaBackupCodes: true,
      },
    }),
    tx.practice.findUnique({
      where: { id: input.expectedPracticeId },
      select: { id: true, isActive: true },
    }),
    tx.userSession.findUnique({
      where: { sessionToken: input.sessionId },
      select: {
        userId: true,
        createdAt: true,
        expiresAt: true,
      },
    }),
  ]);

  const now = input.now ?? new Date();
  const nowMs = now.getTime();
  const createdAtMs = session?.createdAt.getTime() ?? Number.NaN;
  const expiresAtMs = session?.expiresAt.getTime() ?? Number.NaN;
  if (
    !user ||
    !practice ||
    !session ||
    user.id !== input.userId ||
    session.userId !== input.userId ||
    user.practiceId !== input.expectedPracticeId ||
    practice.id !== input.expectedPracticeId ||
    !practice.isActive ||
    !user.isActive ||
    user.deactivatedAt !== null ||
    user.suspendedAt !== null ||
    user.softDeletedAt !== null ||
    !Number.isFinite(nowMs) ||
    !Number.isFinite(createdAtMs) ||
    !Number.isFinite(expiresAtMs) ||
    createdAtMs > nowMs ||
    expiresAtMs <= nowMs ||
    (user.forceLogoutAt !== null &&
      user.forceLogoutAt.getTime() >= createdAtMs) ||
    (input.expectedPasswordHash !== undefined &&
      user.passwordHash !== input.expectedPasswordHash) ||
    (input.expectedEmail !== undefined && user.email !== input.expectedEmail)
  ) {
    deny();
  }

  if (input.surface === "physician") {
    if (
      user.role !== "DOCTOR" ||
      !user.products.includes(Product.TRANSCRIBE_MD)
    ) {
      deny();
    }
  } else {
    if (
      !user.products.includes(Product.SUPER_ADMIN) ||
      nowMs - createdAtMs >= PLATFORM_ADMIN_SESSION_MAX_AGE_MS ||
      (input.requireMfa !== false && !hasCompleteMfaEnrollment(user, now))
    ) {
      deny();
    }
  }

  return { user, session };
}
