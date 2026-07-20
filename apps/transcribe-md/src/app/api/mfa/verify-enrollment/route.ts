// ============================================================================
// POST /api/mfa/verify-enrollment — complete MFA enrollment
// ----------------------------------------------------------------------------
// Body: { token: string }   // 6-digit TOTP code
// Response (success):
//   { ok: true, recoveryCodes: string[] }   // 10 plaintext codes — shown ONCE
// Response (failure): apiError 400 with code IN_VALID_TOKEN
//
// Validates the user-supplied 6-digit code against the staged
// `mfaSecret`. On success:
//   - Flips `mfaEnabled = true`
//   - Sets `mfaVerifiedAt = NOW()`
//   - Generates 10 fresh recovery codes; stores their SHA-256 hashes
//     in `mfaBackupCodes`
//   - Returns the plaintext codes to the user ONCE (the only time the
//     server will ever expose them — they cannot be re-shown later)
//   - Emits MFA_ENABLED audit row
// ============================================================================

import { NextResponse } from "next/server";
import { z } from "zod";

import prisma from "@meddoc/db";
import type { Prisma } from "@prisma/client";
import { apiError, withApiHandler } from "@/lib/api-error";
import {
  verifyStoredMfaTotpToken,
  generateRecoveryCodes,
  hashRecoveryCodes,
} from "@/lib/mfa";
import {
  appendAuthMutationAuditInTransaction,
  logAudit,
} from "@/lib/audit";
import { resolveMfaRequestActor } from "@/lib/mfa-request-actor";
import { RATE_LIMITS, sharedRateLimitOr429 } from "@/lib/rate-limit";
import {
  AccountMutationAuthorityError,
  lockCurrentAccountMutationAuthority,
} from "@/lib/account-mutation-authority";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const BodySchema = z.object({
  token: z.string().min(6).max(8), // strip-whitespace happens in verifyTotpToken
});

class MfaEnrollmentStateChangedError extends Error {}

export const POST = withApiHandler("api:mfa:verify-enrollment", async (req) => {
  const actor = await resolveMfaRequestActor(req.headers);
  if (!actor) return apiError("not found", 404);
  const userId = actor.userId;
  const currentSessionId = actor.sessionId;
  if (!currentSessionId) {
    return apiError("unauthorized", 401);
  }
  const blocked = await sharedRateLimitOr429(RATE_LIMITS.MFA, userId);
  if (blocked) return blocked;

  let body: unknown;
  try {
    body = await req.json();
  } catch {
    return apiError("invalid JSON body", 400);
  }
  const parsed = BodySchema.safeParse(body);
  if (!parsed.success) return apiError("invalid token payload", 400);

  const user = await prisma.user.findUnique({
    where: { id: userId },
    select: {
      id: true,
      email: true,
      practiceId: true,
      mfaSecret: true,
      mfaEnabled: true,
      mfaVerifiedAt: true,
      mfaBackupCodes: true,
    },
  });
  if (!user) return apiError("not found", 404);
  if (user.practiceId !== actor.practiceId) return apiError("not found", 404);
  if (user.mfaEnabled) {
    return apiError("MFA is already enrolled.", 409, {
      code: "MFA_ALREADY_ENABLED",
    });
  }

  if (!user.mfaSecret) {
    // No staged secret — caller must hit /api/mfa/enroll first.
    return apiError("No staged MFA secret. Start enrollment first.", 400, {
      code: "NO_STAGED_SECRET",
    });
  }

  if (!verifyStoredMfaTotpToken(user.id, user.mfaSecret, parsed.data.token)) {
    void logAudit({
      action: "MFA_CHALLENGE_FAILED",
      userId: user.id,
      userEmail: user.email,
      practiceId: user.practiceId,
      success: false,
      errorCode: "INVALID_TOKEN",
      metadata: { stage: "enrollment_verification" },
    });
    return apiError("Invalid 6-digit code. Try again.", 400, {
      code: "INVALID_TOKEN",
    });
  }

  // Generate + hash recovery codes BEFORE writing to DB so we have
  // the plaintext to return.
  const plaintextCodes = generateRecoveryCodes(10);
  const hashedCodes = hashRecoveryCodes(plaintextCodes);

  // Security audit P1-J — flipping mfaEnabled=true while sibling
  // sessions stay live means "MFA-enabled" no longer implies "this
  // session went through an MFA challenge". Revoke every OTHER
  // UserSession on enrollment so any pre-MFA tab/device must
  // re-authenticate AND complete the new MFA challenge. Keep the
  // exact current database-backed session (the user just finished a
  // TOTP challenge in this tab). Legacy/sessionless claims are rejected
  // before any account read or mutation because they cannot establish the
  // transaction-scoped authority required for credential changes.

  const verifiedAt = new Date();
  try {
    await prisma.$transaction(async (tx: Prisma.TransactionClient) => {
      const current = await lockCurrentAccountMutationAuthority(tx, {
        userId,
        sessionId: currentSessionId,
        expectedPracticeId: actor.practiceId,
        expectedEmail: user.email,
        surface: actor.isAdminHost ? "platform-admin" : "physician",
        requireMfa: false,
      });
      const sameBackupCodes =
        current.user.mfaBackupCodes.length === user.mfaBackupCodes.length &&
        current.user.mfaBackupCodes.every(
          (code, index) => code === user.mfaBackupCodes[index],
        );
      if (
        current.user.mfaEnabled ||
        current.user.mfaEnabled !== user.mfaEnabled ||
        current.user.mfaSecret !== user.mfaSecret ||
        current.user.mfaVerifiedAt !== null ||
        user.mfaVerifiedAt !== null ||
        !sameBackupCodes
      ) {
        throw new MfaEnrollmentStateChangedError();
      }
      await tx.user.update({
        where: { id: userId },
        data: {
          mfaEnabled: true,
          mfaVerifiedAt: verifiedAt,
          mfaBackupCodes: hashedCodes,
        },
      });
      await tx.userSession.deleteMany({
        where: {
          userId,
          NOT: { sessionToken: currentSessionId },
        },
      });
      await appendAuthMutationAuditInTransaction(tx, {
        action: "MFA_ENABLED",
        userId: current.user.id,
        userEmail: current.user.email,
        practiceId: current.user.practiceId,
        metadata: {
          stage: "enrollment_completed",
          recoveryCodesIssued: 10,
          keptCurrentSession: true,
        },
      });
    });
  } catch (error) {
    if (
      error instanceof AccountMutationAuthorityError ||
      error instanceof MfaEnrollmentStateChangedError
    ) {
      return apiError("MFA enrollment changed. Start again.", 409, {
        code: "MFA_ENROLLMENT_STATE_CHANGED",
      });
    }
    throw error;
  }

  return NextResponse.json(
    { ok: true, recoveryCodes: plaintextCodes },
    { status: 200 },
  );
});
