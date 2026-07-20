// ============================================================================
// POST /api/mfa/enroll — start MFA enrollment
// ----------------------------------------------------------------------------
// Body: { password: string }
// Response: { ok: true, otpauthUri, qrPngDataUrl }
//
// Generates a fresh TOTP secret, returns the otpauth URI + QR image so
// the user can scan it with their authenticator app. The secret is
// staged in `users.mfaSecret` but `users.mfaEnabled` stays false —
// enrollment is only "complete" once the user submits a valid 6-digit
// code via /api/mfa/verify-enrollment, which flips mfaEnabled to true
// and generates the recovery codes.
//
// Already-enrolled users must disable MFA with password + current-factor proof
// before enrolling again. A live session alone can never replace a factor.
// ============================================================================

import { NextResponse } from "next/server";
import { z } from "zod";
import bcrypt from "bcryptjs";

import prisma from "@meddoc/db";
import type { Prisma } from "@prisma/client";
import { apiError, withApiHandler } from "@/lib/api-error";
import { generateMfaEnrollment } from "@/lib/mfa";
import { encryptMfaSecretForUser } from "@/lib/mfa-secret-envelope";
import { appendAuthMutationAuditInTransaction } from "@/lib/audit";
import { resolveMfaRequestActor } from "@/lib/mfa-request-actor";
import { RATE_LIMITS, sharedRateLimitOr429 } from "@/lib/rate-limit";
import {
  AccountMutationAuthorityError,
  lockCurrentAccountMutationAuthority,
} from "@/lib/account-mutation-authority";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const BodySchema = z.object({
  password: z.string().min(1).max(200),
});

class MfaEnrollmentStateChangedError extends Error {}

export const POST = withApiHandler("api:mfa:enroll", async (req) => {
  const actor = await resolveMfaRequestActor(req.headers);
  if (!actor) return apiError("not found", 404);
  const userId = actor.userId;
  const currentSessionId = actor.sessionId;
  if (!currentSessionId) return apiError("unauthorized", 401);
  const blocked = await sharedRateLimitOr429(RATE_LIMITS.MFA, userId);
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
    where: { id: userId },
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
  if (!user) return apiError("not found", 404);
  if (user.practiceId !== actor.practiceId) return apiError("not found", 404);
  if (user.mfaEnabled) {
    return apiError("MFA is already enrolled.", 409, {
      code: "MFA_ALREADY_ENABLED",
    });
  }

  const passwordOk = await bcrypt.compare(
    parsed.data.password,
    user.passwordHash,
  );
  if (!passwordOk) {
    return apiError("Wrong password.", 400, { code: "WRONG_PASSWORD" });
  }

  const enrollment = await generateMfaEnrollment(user.email);
  const encryptedSecret = encryptMfaSecretForUser({
    userId: user.id,
    plaintextSecret: enrollment.secret,
  });

  // Stage the secret. mfaEnabled stays false — only verify-enrollment
  // flips it. If the user abandons enrollment (closes the tab), the
  // staged secret stays in mfaSecret but mfaEnabled remains false; a
  // future re-enrollment overwrites the stale secret cleanly.
  try {
    await prisma.$transaction(async (tx: Prisma.TransactionClient) => {
      const current = await lockCurrentAccountMutationAuthority(tx, {
        userId,
        sessionId: currentSessionId,
        expectedPracticeId: actor.practiceId,
        expectedPasswordHash: user.passwordHash,
        expectedEmail: user.email,
        surface: actor.isAdminHost ? "platform-admin" : "physician",
        requireMfa: false,
      });
      const sameVerifiedAt =
        current.user.mfaVerifiedAt?.getTime() === user.mfaVerifiedAt?.getTime();
      const sameBackupCodes =
        current.user.mfaBackupCodes.length === user.mfaBackupCodes.length &&
        current.user.mfaBackupCodes.every(
          (code, index) => code === user.mfaBackupCodes[index],
        );
      if (
        current.user.mfaEnabled ||
        current.user.mfaEnabled !== user.mfaEnabled ||
        current.user.mfaSecret !== user.mfaSecret ||
        !sameVerifiedAt ||
        !sameBackupCodes
      ) {
        throw new MfaEnrollmentStateChangedError();
      }
      await tx.user.update({
        where: { id: userId },
        data: {
          mfaEnabled: false,
          mfaSecret: encryptedSecret,
          mfaVerifiedAt: null,
          mfaBackupCodes: [],
        },
      });
      await tx.userSession.deleteMany({
        where: {
          userId,
          NOT: { sessionToken: currentSessionId },
        },
      });
      await appendAuthMutationAuditInTransaction(tx, {
        action: "MFA_ENROLLMENT_STARTED",
        userId: current.user.id,
        userEmail: current.user.email,
        practiceId: current.user.practiceId,
        metadata: { stage: "enrollment_started" },
      });
    });
  } catch (error) {
    if (
      error instanceof AccountMutationAuthorityError ||
      error instanceof MfaEnrollmentStateChangedError
    ) {
      return apiError("MFA enrollment state changed. Try again.", 409, {
        code: "MFA_ENROLLMENT_STATE_CHANGED",
      });
    }
    throw error;
  }

  return NextResponse.json(
    {
      ok: true,
      otpauthUri: enrollment.otpauthUri,
      qrPngDataUrl: enrollment.qrPngDataUrl,
    },
    { status: 200 },
  );
});
