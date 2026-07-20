import "server-only";

import { Prisma, Product, type UserRole } from "@prisma/client";

const LOGIN_FAILURE_THRESHOLD = 5;
const LOGIN_LOCKOUT_MS = 15 * 60 * 1000;
const DEFAULT_SESSION_TTL_MS = 7 * 24 * 60 * 60 * 1000;

export type CredentialSessionSurface = "physician" | "admin";

export interface CredentialUserSnapshot {
  id: string;
  email: string;
  name: string | null;
  practiceId: string;
  passwordHash: string;
  role: UserRole;
  products: readonly Product[];
  emailVerified: Date | null;
  mfaEnabled: boolean;
  mfaSecret: string | null;
  mfaVerifiedAt: Date | null;
  mfaBackupCodes: readonly string[];
}

export type CredentialSecondFactorProof =
  | { kind: "none" }
  | { kind: "totp" }
  | { kind: "recovery"; matchedHash: string };

export class CredentialSessionAuthorityError extends Error {
  constructor() {
    super("Final credential session authority changed.");
    this.name = "CredentialSessionAuthorityError";
  }
}

function sameInstant(left: Date | null, right: Date | null): boolean {
  return left?.getTime() === right?.getTime();
}

function sameStrings(
  left: readonly string[],
  right: readonly string[],
): boolean {
  return (
    left.length === right.length &&
    left.every((value, index) => value === right[index])
  );
}

function surfaceAllows(
  surface: CredentialSessionSurface,
  user: { role: UserRole; products: readonly Product[] },
): boolean {
  if (surface === "physician") {
    return (
      user.role === "DOCTOR" && user.products.includes(Product.TRANSCRIBE_MD)
    );
  }
  return (
    user.products.includes(Product.SUPER_ADMIN) ||
    ((user.role === "ADMIN" || user.role === "SUPER_ADMIN") &&
      user.products.includes(Product.TRANSCRIBE_MD))
  );
}

async function lockCredentialUser(
  tx: Prisma.TransactionClient,
  snapshot: CredentialUserSnapshot,
) {
  const practices = await tx.$queryRaw<Array<{ id: string }>>(Prisma.sql`
    SELECT "id" FROM "practices"
    WHERE "id" = ${snapshot.practiceId}
    FOR UPDATE
  `);
  if (practices.length !== 1 || practices[0]?.id !== snapshot.practiceId) {
    throw new CredentialSessionAuthorityError();
  }
  const users = await tx.$queryRaw<Array<{ id: string }>>(Prisma.sql`
    SELECT "id" FROM "users"
    WHERE "id" = ${snapshot.id}
    FOR UPDATE
  `);
  if (users.length !== 1 || users[0]?.id !== snapshot.id) {
    throw new CredentialSessionAuthorityError();
  }

  const [practice, user] = await Promise.all([
    tx.practice.findUnique({
      where: { id: snapshot.practiceId },
      select: { id: true, isActive: true },
    }),
    tx.user.findUnique({
      where: { id: snapshot.id },
      select: {
        id: true,
        email: true,
        name: true,
        practiceId: true,
        passwordHash: true,
        role: true,
        products: true,
        emailVerified: true,
        isActive: true,
        deactivatedAt: true,
        suspendedAt: true,
        softDeletedAt: true,
        lockedUntil: true,
        failedLoginCount: true,
        mfaEnabled: true,
        mfaSecret: true,
        mfaVerifiedAt: true,
        mfaBackupCodes: true,
      },
    }),
  ]);
  if (
    !practice ||
    !user ||
    practice.id !== snapshot.practiceId ||
    !practice.isActive ||
    user.id !== snapshot.id ||
    user.email !== snapshot.email ||
    user.practiceId !== snapshot.practiceId ||
    user.passwordHash !== snapshot.passwordHash ||
    user.role !== snapshot.role ||
    !sameStrings(user.products, snapshot.products) ||
    !sameInstant(user.emailVerified, snapshot.emailVerified) ||
    user.mfaEnabled !== snapshot.mfaEnabled ||
    user.mfaSecret !== snapshot.mfaSecret ||
    !sameInstant(user.mfaVerifiedAt, snapshot.mfaVerifiedAt) ||
    !sameStrings(user.mfaBackupCodes, snapshot.mfaBackupCodes) ||
    !user.isActive ||
    user.deactivatedAt !== null ||
    user.suspendedAt !== null ||
    user.softDeletedAt !== null
  ) {
    throw new CredentialSessionAuthorityError();
  }
  return user;
}

export interface FinalizeCredentialSessionInput {
  snapshot: CredentialUserSnapshot;
  surface: CredentialSessionSurface;
  secondFactor: CredentialSecondFactorProof;
  requireVerifiedEmail: boolean;
  sessionToken: string;
  ipAddress?: string | null;
  userAgent?: string | null;
  deviceFingerprint?: string | null;
  ttlMs?: number;
  now?: Date;
}

/**
 * Linearization point for password/MFA proof and session issuance. The
 * expensive password/TOTP checks happen before this transaction; their exact
 * credential snapshot is then rechecked under the canonical user lock before
 * a recovery code is consumed or any UserSession is created.
 */
export async function finalizeCredentialSession(
  tx: Prisma.TransactionClient,
  input: FinalizeCredentialSessionInput,
) {
  const user = await lockCredentialUser(tx, input.snapshot);
  const now = input.now ?? new Date();
  if (
    (user.lockedUntil !== null && user.lockedUntil.getTime() > now.getTime()) ||
    !surfaceAllows(input.surface, user) ||
    (input.requireVerifiedEmail && user.emailVerified === null)
  ) {
    throw new CredentialSessionAuthorityError();
  }

  const nextBackupCodes = [...user.mfaBackupCodes];
  if (input.secondFactor.kind === "none") {
    if (user.mfaEnabled) throw new CredentialSessionAuthorityError();
  } else {
    if (
      !user.mfaEnabled ||
      !user.mfaSecret?.trim() ||
      user.mfaVerifiedAt === null ||
      user.mfaVerifiedAt.getTime() > now.getTime()
    ) {
      throw new CredentialSessionAuthorityError();
    }
    if (input.secondFactor.kind === "recovery") {
      const index = nextBackupCodes.indexOf(input.secondFactor.matchedHash);
      if (index < 0) throw new CredentialSessionAuthorityError();
      nextBackupCodes.splice(index, 1);
    }
  }

  await tx.user.update({
    where: { id: user.id },
    data: {
      lastLogin: now,
      failedLoginCount: 0,
      lockedUntil: null,
      ...(input.secondFactor.kind === "recovery"
        ? { mfaBackupCodes: nextBackupCodes }
        : {}),
    },
  });
  await tx.userSession.deleteMany({ where: { userId: user.id } });
  if (input.secondFactor.kind !== "none") {
    await tx.auditLog.create({
      data: {
        userId: user.id,
        userEmailSnapshot: user.email,
        action: "MFA_CHALLENGE_PASSED",
        targetId: user.id,
        targetType: "User",
        ipAddress: input.ipAddress ?? null,
        userAgent: input.userAgent ?? null,
        metadata: {
          stage: "login",
          method:
            input.secondFactor.kind === "recovery" ? "recovery_code" : "totp",
        },
        success: true,
        practiceId: user.practiceId,
        timestamp: now,
      },
    });
  }
  await tx.auditLog.create({
    data: {
      userId: user.id,
      userEmailSnapshot: user.email,
      action: "LOGIN_SUCCESS",
      targetId: user.id,
      targetType: "UserSession",
      ipAddress: input.ipAddress ?? null,
      userAgent: input.userAgent ?? null,
      metadata: {
        surface: input.surface,
        secondFactor: input.secondFactor.kind,
      },
      success: true,
      practiceId: user.practiceId,
      timestamp: now,
    },
  });
  const session = await tx.userSession.create({
    data: {
      userId: user.id,
      sessionToken: input.sessionToken,
      ipAddress: input.ipAddress ?? null,
      userAgent: input.userAgent ?? null,
      deviceFingerprint: input.deviceFingerprint ?? null,
      expiresAt: new Date(
        now.getTime() + (input.ttlMs ?? DEFAULT_SESSION_TTL_MS),
      ),
    },
  });
  return { user, session };
}

export interface RecordCredentialFailureInput {
  snapshot: CredentialUserSnapshot;
  surface: CredentialSessionSurface;
  now?: Date;
}

/** Atomic thresholding for password and second-factor failures. */
export async function recordCredentialFailure(
  tx: Prisma.TransactionClient,
  input: RecordCredentialFailureInput,
): Promise<{ recorded: boolean; locked: boolean; failedLoginCount: number }> {
  const user = await lockCredentialUser(tx, input.snapshot);
  const now = input.now ?? new Date();
  if (!surfaceAllows(input.surface, user)) {
    throw new CredentialSessionAuthorityError();
  }
  if (user.lockedUntil !== null && user.lockedUntil.getTime() > now.getTime()) {
    return {
      recorded: false,
      locked: true,
      failedLoginCount: user.failedLoginCount,
    };
  }
  const priorCount =
    user.lockedUntil !== null && user.lockedUntil.getTime() <= now.getTime()
      ? 0
      : user.failedLoginCount;
  const failedLoginCount = priorCount + 1;
  const locked = failedLoginCount >= LOGIN_FAILURE_THRESHOLD;
  await tx.user.update({
    where: { id: user.id },
    data: {
      failedLoginCount,
      lockedUntil: locked ? new Date(now.getTime() + LOGIN_LOCKOUT_MS) : null,
    },
  });
  return { recorded: true, locked, failedLoginCount };
}
