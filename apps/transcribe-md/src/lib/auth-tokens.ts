// ============================================================================
// One-time AuthToken helpers (T-M16.2)
// ----------------------------------------------------------------------------
// Every password-reset / email-verification / email-change flow goes
// through createAuthToken() to mint + consumeAuthToken() to redeem.
// The DB only ever sees SHA-256(token); the raw 32-byte base64url
// token is returned to the caller exactly once so they can embed it
// in an email URL.
//
// Security posture:
//   - SHA-256 is deliberate over bcrypt for one-shot tokens: the token
//     is already high-entropy (256 bits), so a KDF adds no effective
//     defense and would cost ~200ms per validation. SHA-256 matches
//     Auth.js v5 and the NextAuth adapter convention.
//   - Every mint invalidates prior unused tokens for the same
//     (user, purpose) pair by default. If the user clicks "forgot
//     password" twice, only the most-recent link works.
//   - consumeAuthToken() atomic via updateMany + WHERE usedAt IS NULL.
//     A second concurrent consume returns null and the caller shows
//     the generic "link invalid or expired" message.
// ============================================================================

import crypto from "node:crypto";

import prisma from "@meddoc/db";
import { Prisma, type AuthTokenPurpose } from "@prisma/client";

/** 32 bytes of CSPRNG randomness → ~43 chars base64url. */
const RAW_TOKEN_BYTES = 32;

export function generateRawToken(): string {
  return crypto.randomBytes(RAW_TOKEN_BYTES).toString("base64url");
}

export function hashToken(raw: string): string {
  return crypto.createHash("sha256").update(raw).digest("hex");
}

export interface CreateAuthTokenArgs {
  userId: string;
  purpose: AuthTokenPurpose;
  expiresInMs: number;
  /** Exact current normalized email expected by an email-address bearer
   * workflow. PASSWORD_RESET requires this and binds it into metadata. */
  expectedUserEmail?: string;
  /** Purpose-specific extras — EMAIL_CHANGE stores the pending
   *  new email address here. */
  metadata?: Record<string, unknown>;
}

export interface CreatedAuthToken {
  /** The raw token. Hand it to the caller to embed in an email URL
   *  — it is not stored plaintext anywhere. */
  token: string;
  /** Row id, useful for logging. */
  id: string;
  /** Exact recipient identity observed under the canonical user lock. */
  userEmail: string;
}

type AuthTokenTransaction = Prisma.TransactionClient;

async function lockAuthTokenUser(
  tx: AuthTokenTransaction,
  userId: string,
  expectedUserEmail?: string,
): Promise<{
  id: string;
  email: string;
  practiceId: string;
  isActive: boolean;
  deactivatedAt: Date | null;
  suspendedAt: Date | null;
  softDeletedAt: Date | null;
}> {
  const rows = await tx.$queryRaw<
    Array<{
      id: string;
      email: string;
      practiceId: string;
      isActive: boolean;
      deactivatedAt: Date | null;
      suspendedAt: Date | null;
      softDeletedAt: Date | null;
    }>
  >(
    Prisma.sql`
    SELECT "id", "email", "practiceId", "isActive", "deactivatedAt",
      "suspendedAt", "softDeletedAt"
    FROM "users" WHERE "id" = ${userId} FOR UPDATE
  `,
  );
  const user = rows[0];
  if (
    rows.length !== 1 ||
    user?.id !== userId ||
    (expectedUserEmail !== undefined && user.email !== expectedUserEmail)
  ) {
    throw new AuthTokenAuthorityError();
  }
  return user;
}

/** Caller and token mint share the canonical user-row serialization point. */
export async function createAuthTokenInTransaction(
  tx: AuthTokenTransaction,
  args: CreateAuthTokenArgs,
  token = generateRawToken(),
  now = new Date(),
): Promise<CreatedAuthToken> {
  if (
    args.purpose === "PASSWORD_RESET" &&
    (!args.expectedUserEmail ||
      args.expectedUserEmail !== args.expectedUserEmail.trim().toLowerCase())
  ) {
    throw new AuthTokenAuthorityError();
  }
  const lockedUser = await lockAuthTokenUser(
    tx,
    args.userId,
    args.expectedUserEmail,
  );
  if (
    !lockedUser.isActive ||
    lockedUser.deactivatedAt !== null ||
    lockedUser.suspendedAt !== null ||
    lockedUser.softDeletedAt !== null
  ) {
    throw new AuthTokenAuthorityError();
  }
  await tx.authToken.updateMany({
    where: {
      userId: args.userId,
      purpose: args.purpose,
      usedAt: null,
    },
    data: { usedAt: now },
  });
  const row = await tx.authToken.create({
    data: {
      userId: args.userId,
      purpose: args.purpose,
      tokenHash: hashToken(token),
      expiresAt: new Date(now.getTime() + args.expiresInMs),
      metadata:
        args.purpose === "PASSWORD_RESET"
          ? ({ email: args.expectedUserEmail } as Prisma.InputJsonValue)
          : args.metadata
            ? (args.metadata as Prisma.InputJsonValue)
            : undefined,
    },
    select: { id: true },
  });
  return { token, id: row.id, userEmail: lockedUser.email };
}

export async function createAuthToken(
  args: CreateAuthTokenArgs,
): Promise<CreatedAuthToken> {
  const token = generateRawToken();
  return prisma.$transaction((tx: AuthTokenTransaction) =>
    createAuthTokenInTransaction(tx, args, token),
  );
}

export interface ConsumeAuthTokenArgs {
  token: string;
  purpose: AuthTokenPurpose;
}

export interface ConsumedAuthToken {
  id: string;
  userId: string;
  /** Whatever was stored at mint time. Caller casts to the expected
   *  shape for their purpose. */
  metadata: unknown;
}

export interface AuthTokenCandidate {
  id: string;
  userId: string;
}

/** Read-only routing lookup; all authority is re-established under lock. */
export async function findAuthTokenCandidate(
  args: ConsumeAuthTokenArgs,
): Promise<AuthTokenCandidate | null> {
  if (!args.token || args.token.length < 20) return null;
  return prisma.authToken.findUnique({
    where: { tokenHash: hashToken(args.token) },
    select: { id: true, userId: true },
  });
}

export class AuthTokenAuthorityError extends Error {
  constructor() {
    super("Auth token authority changed.");
    this.name = "AuthTokenAuthorityError";
  }
}

function emailFromTokenMetadata(metadata: unknown): string | null {
  if (
    typeof metadata !== "object" ||
    metadata === null ||
    Array.isArray(metadata) ||
    !("email" in metadata) ||
    typeof metadata.email !== "string"
  ) {
    return null;
  }
  return metadata.email;
}

/**
 * Lock the token's canonical user first, then require this exact token to be
 * the sole current, unused, unexpired token for its purpose. Credential and
 * identity mutations must happen in this same transaction.
 */
export async function lockCurrentAuthTokenForMutation(
  tx: AuthTokenTransaction,
  args: ConsumeAuthTokenArgs & { candidate: AuthTokenCandidate; now?: Date },
) {
  const tokenHash = hashToken(args.token);
  await lockAuthTokenUser(tx, args.candidate.userId);
  const locked = await tx.$queryRaw<Array<{ id: string }>>(Prisma.sql`
    SELECT "id"
    FROM "auth_tokens"
    WHERE "id" = ${args.candidate.id}
      AND "userId" = ${args.candidate.userId}
      AND "tokenHash" = ${tokenHash}
    FOR UPDATE
  `);
  if (locked.length !== 1 || locked[0]?.id !== args.candidate.id) {
    throw new AuthTokenAuthorityError();
  }

  const [token, currentTokens, user] = await Promise.all([
    tx.authToken.findUnique({
      where: { id: args.candidate.id },
      select: {
        id: true,
        userId: true,
        tokenHash: true,
        purpose: true,
        expiresAt: true,
        usedAt: true,
        metadata: true,
      },
    }),
    tx.authToken.findMany({
      where: {
        userId: args.candidate.userId,
        purpose: args.purpose,
        usedAt: null,
      },
      orderBy: [{ createdAt: "desc" }, { id: "desc" }],
      select: { id: true },
      take: 2,
    }),
    tx.user.findUnique({
      where: { id: args.candidate.userId },
      select: {
        id: true,
        email: true,
        practiceId: true,
        name: true,
        isActive: true,
        deactivatedAt: true,
        suspendedAt: true,
        softDeletedAt: true,
      },
    }),
  ]);
  const now = args.now ?? new Date();
  const passwordResetEmail = token
    ? emailFromTokenMetadata(token.metadata)
    : null;
  if (
    !token ||
    !user ||
    token.id !== args.candidate.id ||
    token.userId !== args.candidate.userId ||
    token.tokenHash !== tokenHash ||
    token.purpose !== args.purpose ||
    token.usedAt !== null ||
    token.expiresAt.getTime() <= now.getTime() ||
    (token.purpose === "PASSWORD_RESET" &&
      (passwordResetEmail === null || passwordResetEmail !== user.email)) ||
    currentTokens.length !== 1 ||
    currentTokens[0]?.id !== token.id ||
    !user.isActive ||
    user.deactivatedAt !== null ||
    user.suspendedAt !== null ||
    user.softDeletedAt !== null
  ) {
    throw new AuthTokenAuthorityError();
  }
  return { token, user, now };
}

export async function consumeLockedAuthToken(
  tx: AuthTokenTransaction,
  tokenId: string,
  now = new Date(),
): Promise<void> {
  const consumed = await tx.authToken.updateMany({
    where: { id: tokenId, usedAt: null },
    data: { usedAt: now },
  });
  if (consumed.count !== 1) throw new AuthTokenAuthorityError();
}

/** Atomically validate + mark a token used. Returns null for any
 *  failure reason (wrong purpose, already used, expired, not found)
 *  so callers show one generic error message and don't leak which
 *  condition was violated. */
export async function consumeAuthToken(
  args: ConsumeAuthTokenArgs,
): Promise<ConsumedAuthToken | null> {
  const candidate = await findAuthTokenCandidate(args);
  if (!candidate) return null;
  try {
    return await prisma.$transaction(async (tx: AuthTokenTransaction) => {
      const locked = await lockCurrentAuthTokenForMutation(tx, {
        ...args,
        candidate,
      });
      await consumeLockedAuthToken(tx, locked.token.id, locked.now);
      return {
        id: locked.token.id,
        userId: locked.token.userId,
        metadata: locked.token.metadata,
      };
    });
  } catch (error) {
    if (error instanceof AuthTokenAuthorityError) return null;
    throw error;
  }
}

/** Revoke every unused token of a given purpose for a user. Used by
 *  password-reset to also invalidate any verification-email links in
 *  flight when a password changes. */
export async function invalidateAuthTokens(
  userId: string,
  purpose: AuthTokenPurpose,
): Promise<void> {
  await prisma.$transaction(async (tx: AuthTokenTransaction) => {
    await lockAuthTokenUser(tx, userId);
    await tx.authToken.updateMany({
      where: { userId, purpose, usedAt: null },
      data: { usedAt: new Date() },
    });
  });
}
