// ============================================================================
// POST /api/mfa/recovery-codes/rotate — replace every recovery code
// ----------------------------------------------------------------------------
// Body: { password: string, token: string }
// Success: { ok: true, recoveryCodes: string[] } (shown exactly once)
//
// Rotation requires the current password and a current TOTP from the enrolled
// authenticator. A recovery code cannot authorize replacement of the recovery
// set. The transaction re-establishes exact account/session/MFA authority,
// writes only v2 verifiers, revokes every other session, and appends a distinct
// immutable audit receipt before any plaintext code is returned.
// ============================================================================

import bcrypt from "bcryptjs";
import { NextResponse } from "next/server";
import type { Prisma } from "@prisma/client";
import { z } from "zod";

import prisma from "@meddoc/db";
import {
  AccountMutationAuthorityError,
  lockCurrentAccountMutationAuthority,
} from "@/lib/account-mutation-authority";
import { apiError, withApiHandler } from "@/lib/api-error";
import { appendAuthMutationAuditInTransaction, logAudit } from "@/lib/audit";
import { hasCompleteMfaEnrollment } from "@/lib/mfa-enrollment-state";
import {
  generateRecoveryCodes,
  hashRecoveryCodes,
  verifyStoredMfaTotpToken,
} from "@/lib/mfa";
import { resolveMfaRequestActor } from "@/lib/mfa-request-actor";
import { RATE_LIMITS, sharedRateLimitOr429 } from "@/lib/rate-limit";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const BodySchema = z.object({
  password: z.string().min(1).max(200),
  token: z.string().min(6).max(8),
});

class MfaRecoveryRotationStateChangedError extends Error {}

function sameStrings(left: readonly string[], right: readonly string[]) {
  return (
    left.length === right.length &&
    left.every((value, index) => value === right[index])
  );
}

export const POST = withApiHandler(
  "api:mfa:recovery-codes:rotate",
  async (req) => {
    const actor = await resolveMfaRequestActor(req.headers);
    if (!actor) return apiError("not found", 404);
    const currentSessionId = actor.sessionId;
    if (!currentSessionId) return apiError("unauthorized", 401);

    const blocked = await sharedRateLimitOr429(RATE_LIMITS.MFA, actor.userId);
    if (blocked) return blocked;

    let body: unknown;
    try {
      body = await req.json();
    } catch {
      return apiError("invalid JSON body", 400);
    }
    const parsed = BodySchema.safeParse(body);
    if (!parsed.success) return apiError("invalid payload", 400);

    const user = await prisma.user.findUnique({
      where: { id: actor.userId },
      select: {
        id: true,
        email: true,
        practiceId: true,
        passwordHash: true,
        mfaEnabled: true,
        mfaSecret: true,
        mfaVerifiedAt: true,
        mfaBackupCodes: true,
      },
    });
    if (!user || user.practiceId !== actor.practiceId) {
      return apiError("not found", 404);
    }
    if (!hasCompleteMfaEnrollment(user)) {
      return apiError("MFA is not enabled.", 400, {
        code: "MFA_NOT_ENABLED",
      });
    }

    const passwordOk = await bcrypt.compare(
      parsed.data.password,
      user.passwordHash,
    );
    if (!passwordOk) {
      void logAudit({
        action: "MFA_CHALLENGE_FAILED",
        userId: user.id,
        userEmail: user.email,
        practiceId: user.practiceId,
        success: false,
        errorCode: "WRONG_PASSWORD",
        metadata: { stage: "recovery_code_rotation" },
      });
      return apiError("Wrong password.", 400, { code: "WRONG_PASSWORD" });
    }

    if (
      !verifyStoredMfaTotpToken(
        user.id,
        user.mfaSecret as string,
        parsed.data.token,
      )
    ) {
      void logAudit({
        action: "MFA_CHALLENGE_FAILED",
        userId: user.id,
        userEmail: user.email,
        practiceId: user.practiceId,
        success: false,
        errorCode: "INVALID_TOKEN",
        metadata: { stage: "recovery_code_rotation" },
      });
      return apiError("Invalid 6-digit code. Try again.", 400, {
        code: "INVALID_TOKEN",
      });
    }

    const plaintextCodes = generateRecoveryCodes(10);
    const hashedCodes = hashRecoveryCodes(plaintextCodes);

    try {
      await prisma.$transaction(async (tx: Prisma.TransactionClient) => {
        const current = await lockCurrentAccountMutationAuthority(tx, {
          userId: user.id,
          sessionId: currentSessionId,
          expectedPracticeId: actor.practiceId,
          expectedPasswordHash: user.passwordHash,
          expectedEmail: user.email,
          surface: actor.isAdminHost ? "platform-admin" : "physician",
        });
        const sameVerifiedAt =
          current.user.mfaVerifiedAt?.getTime() ===
          user.mfaVerifiedAt?.getTime();
        if (
          !hasCompleteMfaEnrollment(current.user) ||
          current.user.mfaEnabled !== user.mfaEnabled ||
          current.user.mfaSecret !== user.mfaSecret ||
          !sameVerifiedAt ||
          !sameStrings(current.user.mfaBackupCodes, user.mfaBackupCodes)
        ) {
          throw new MfaRecoveryRotationStateChangedError();
        }

        await tx.user.update({
          where: { id: user.id },
          data: { mfaBackupCodes: hashedCodes },
        });
        await tx.userSession.deleteMany({
          where: {
            userId: user.id,
            NOT: { sessionToken: currentSessionId },
          },
        });
        await appendAuthMutationAuditInTransaction(tx, {
          action: "MFA_RECOVERY_CODES_ROTATED",
          userId: current.user.id,
          userEmail: current.user.email,
          practiceId: current.user.practiceId,
          metadata: {
            recoveryCodesIssued: 10,
            keptCurrentSession: true,
            authorizationMethod: "password_and_totp",
          },
        });
      });
    } catch (error) {
      if (
        error instanceof AccountMutationAuthorityError ||
        error instanceof MfaRecoveryRotationStateChangedError
      ) {
        return apiError("MFA state changed. Try again.", 409, {
          code: "MFA_STATE_CHANGED",
        });
      }
      throw error;
    }

    return NextResponse.json(
      { ok: true, recoveryCodes: plaintextCodes },
      { status: 200 },
    );
  },
);
