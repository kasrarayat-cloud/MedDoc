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

import crypto from 'node:crypto';

import prisma from '@meddoc/db';
import type { AuthTokenPurpose, Prisma } from '@prisma/client';

/** 32 bytes of CSPRNG randomness → ~43 chars base64url. */
const RAW_TOKEN_BYTES = 32;

export function generateRawToken(): string {
  return crypto.randomBytes(RAW_TOKEN_BYTES).toString('base64url');
}

export function hashToken(raw: string): string {
  return crypto.createHash('sha256').update(raw).digest('hex');
}

export interface CreateAuthTokenArgs {
  userId: string;
  purpose: AuthTokenPurpose;
  expiresInMs: number;
  /** Purpose-specific extras — EMAIL_CHANGE stores the pending
   *  new email address here. */
  metadata?: Record<string, unknown>;
  /** Default true. Marks any prior unused tokens of the same
   *  (userId, purpose) as used so only the newest link works. */
  invalidatePrior?: boolean;
}

export interface CreatedAuthToken {
  /** The raw token. Hand it to the caller to embed in an email URL
   *  — it is not stored plaintext anywhere. */
  token: string;
  /** Row id, useful for logging. */
  id: string;
}

export async function createAuthToken(
  args: CreateAuthTokenArgs
): Promise<CreatedAuthToken> {
  if (args.invalidatePrior ?? true) {
    await prisma.authToken.updateMany({
      where: {
        userId: args.userId,
        purpose: args.purpose,
        usedAt: null,
      },
      data: { usedAt: new Date() },
    });
  }
  const token = generateRawToken();
  const row = await prisma.authToken.create({
    data: {
      userId: args.userId,
      purpose: args.purpose,
      tokenHash: hashToken(token),
      expiresAt: new Date(Date.now() + args.expiresInMs),
      metadata: args.metadata
        ? (args.metadata as Prisma.InputJsonValue)
        : undefined,
    },
    select: { id: true },
  });
  return { token, id: row.id };
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

/** Atomically validate + mark a token used. Returns null for any
 *  failure reason (wrong purpose, already used, expired, not found)
 *  so callers show one generic error message and don't leak which
 *  condition was violated. */
export async function consumeAuthToken(
  args: ConsumeAuthTokenArgs
): Promise<ConsumedAuthToken | null> {
  if (!args.token || args.token.length < 20) return null;
  const tokenHash = hashToken(args.token);

  const row = await prisma.authToken.findUnique({
    where: { tokenHash },
    select: {
      id: true,
      userId: true,
      purpose: true,
      expiresAt: true,
      usedAt: true,
      metadata: true,
    },
  });
  if (!row) return null;
  if (row.purpose !== args.purpose) return null;
  if (row.usedAt !== null) return null;
  if (row.expiresAt < new Date()) return null;

  // Atomic consume — second concurrent call gets count=0.
  const updated = await prisma.authToken.updateMany({
    where: { id: row.id, usedAt: null },
    data: { usedAt: new Date() },
  });
  if (updated.count === 0) return null;

  return { id: row.id, userId: row.userId, metadata: row.metadata };
}

/** Revoke every unused token of a given purpose for a user. Used by
 *  password-reset to also invalidate any verification-email links in
 *  flight when a password changes. */
export async function invalidateAuthTokens(
  userId: string,
  purpose: AuthTokenPurpose
): Promise<void> {
  await prisma.authToken.updateMany({
    where: { userId, purpose, usedAt: null },
    data: { usedAt: new Date() },
  });
}
