// ============================================================================
// POST /api/mfa/disable — disable MFA for the current user
// ----------------------------------------------------------------------------
// Body: { password: string, token: string }
// Response: { ok: true }
//
// Disabling MFA requires both:
//   - The user's current password (re-authentication)
//   - A valid 6-digit TOTP token (proof they still control the factor)
//
// This dual-gate prevents an attacker who's stolen a session cookie
// from disabling MFA + locking the legit user out. Per HIPAA
// §164.312(a)(2)(ii) "Emergency access procedure" — the user can also
// use a recovery code in lieu of the TOTP token via this same endpoint.
//
// Platform-admin entitlement: this route refuses to disable MFA for any
// account carrying Product.SUPER_ADMIN, independent of its ordinary UserRole.
// Remove that entitlement through the separately audited admin flow first.
// ============================================================================

import { NextResponse } from "next/server";
import { z } from "zod";
import bcrypt from "bcryptjs";

import prisma from "@meddoc/db";
import { Product } from "@prisma/client";
import { apiError, withApiHandler } from "@/lib/api-error";
import { verifyTotpToken, findMatchingRecoveryHash } from "@/lib/mfa";
import { logAudit } from "@/lib/audit";
import { resolveMfaRequestActor } from "@/lib/mfa-request-actor";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const BodySchema = z.object({
  password: z.string().min(1).max(200),
  token: z.string().min(6).max(40).optional(),
  recoveryCode: z.string().min(8).max(40).optional(),
});

export const POST = withApiHandler("api:mfa:disable", async (req) => {
  const actor = await resolveMfaRequestActor(req.headers);
  if (!actor || actor.isAdminHost) return apiError("not found", 404);
  const userId = actor.userId;

  let body: unknown;
  try {
    body = await req.json();
  } catch {
    return apiError("invalid JSON body", 400);
  }
  const parsed = BodySchema.safeParse(body);
  if (!parsed.success) return apiError("invalid payload", 400);
  if (!parsed.data.token && !parsed.data.recoveryCode) {
    return apiError(
      "Either a 6-digit code or a recovery code is required.",
      400,
      { code: "TOKEN_REQUIRED" },
    );
  }

  const user = await prisma.user.findUnique({
    where: { id: userId },
    select: {
      id: true,
      email: true,
      role: true,
      products: true,
      practiceId: true,
      passwordHash: true,
      mfaEnabled: true,
      mfaSecret: true,
      mfaBackupCodes: true,
    },
  });
  if (!user) return apiError("not found", 404);

  if (!user.mfaEnabled || !user.mfaSecret) {
    return apiError("MFA is not enabled.", 400, {
      code: "MFA_NOT_ENABLED",
    });
  }

  // Platform administration is a Product entitlement, not merely a UserRole.
  // Preserve the legacy role guard as defense-in-depth for older accounts.
  if (
    user.role === "SUPER_ADMIN" ||
    user.products.includes(Product.SUPER_ADMIN)
  ) {
    void logAudit({
      action: "MFA_DISABLED",
      userId: user.id,
      userEmail: user.email,
      practiceId: user.practiceId,
      success: false,
      errorCode: "PLATFORM_ADMIN_MFA_REQUIRED",
    });
    return apiError(
      "Platform-admin accounts cannot disable MFA. Revoke the platform-admin entitlement first.",
      403,
      { code: "PLATFORM_ADMIN_MFA_REQUIRED" },
    );
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
      metadata: { stage: "disable" },
    });
    return apiError("Wrong password.", 400, { code: "WRONG_PASSWORD" });
  }

  let secondFactorOk = false;
  let usedRecovery = false;
  if (parsed.data.token) {
    secondFactorOk = verifyTotpToken(user.mfaSecret, parsed.data.token);
  } else if (parsed.data.recoveryCode) {
    const matched = findMatchingRecoveryHash(
      parsed.data.recoveryCode,
      user.mfaBackupCodes,
    );
    if (matched) {
      secondFactorOk = true;
      usedRecovery = true;
    }
  }

  if (!secondFactorOk) {
    void logAudit({
      action: "MFA_CHALLENGE_FAILED",
      userId: user.id,
      userEmail: user.email,
      practiceId: user.practiceId,
      success: false,
      errorCode: "INVALID_SECOND_FACTOR",
      metadata: { stage: "disable" },
    });
    return apiError("Invalid 6-digit code or recovery code.", 400, {
      code: "INVALID_SECOND_FACTOR",
    });
  }

  await prisma.user.update({
    where: { id: userId },
    data: {
      mfaEnabled: false,
      mfaSecret: null,
      mfaVerifiedAt: null,
      mfaBackupCodes: [],
    },
  });

  void logAudit({
    action: "MFA_DISABLED",
    userId: user.id,
    userEmail: user.email,
    practiceId: user.practiceId,
    success: true,
    metadata: { method: usedRecovery ? "recovery_code" : "totp" },
  });

  return NextResponse.json({ ok: true }, { status: 200 });
});
