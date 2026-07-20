// ============================================================================
// POST /api/settings/change-password (T-M16.2)
// ----------------------------------------------------------------------------
// Body: { currentPassword, newPassword, confirmPassword }
//
// Validates the current password, applies the same policy as signup on
// the new one, and revokes every OTHER UserSession (keeping the
// current session live so the user isn't booted out of the tab they
// just used to change their own password).
// ============================================================================

import { z } from "zod";
import { NextResponse } from "next/server";
import bcrypt from "bcryptjs";

import prisma from "@meddoc/db";
import { AuthTokenPurpose, type Prisma } from "@prisma/client";
import { apiError, withApiHandler } from "@/lib/api-error";
import { auth } from "@/lib/nextauth";
import { RATE_LIMITS, sharedRateLimitOr429 } from "@/lib/rate-limit";
import { log } from "@/lib/log";
import { appendAuthMutationAuditInTransaction } from "@/lib/audit";
import {
  AccountMutationAuthorityError,
  lockCurrentAccountMutationAuthority,
} from "@/lib/account-mutation-authority";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const PasswordSchema = z
  .string()
  .min(10, "Password must be at least 10 characters")
  .regex(/[a-z]/, "Password must contain a lowercase letter")
  .regex(/[A-Z]/, "Password must contain an uppercase letter")
  .regex(/\d/, "Password must contain a digit");

const BodySchema = z
  .object({
    currentPassword: z.string().min(1, "Enter your current password"),
    newPassword: PasswordSchema,
    confirmPassword: z.string(),
  })
  .refine((d) => d.newPassword === d.confirmPassword, {
    message: "Passwords do not match",
    path: ["confirmPassword"],
  })
  .refine((d) => d.newPassword !== d.currentPassword, {
    message: "New password must be different from current",
    path: ["newPassword"],
  });

export const POST = withApiHandler(
  "api:settings:change-password",
  async (req) => {
    const session = await auth();
    const userId = session?.user?.id;
    const currentSessionToken = session?.user?.sessionId;
    const practiceId = session?.user?.practiceId;
    if (!userId || !currentSessionToken || !practiceId) {
      return apiError("unauthorized", 401);
    }

    const blocked = await sharedRateLimitOr429(RATE_LIMITS.SETTINGS, userId);
    if (blocked) return blocked;

    let body: unknown;
    try {
      body = await req.json();
    } catch {
      return apiError("invalid JSON body", 400);
    }
    const parsed = BodySchema.safeParse(body);
    if (!parsed.success) {
      const first = parsed.error.issues[0];
      const field = first?.path.join(".") || "_form";
      return NextResponse.json(
        { error: first?.message || "invalid payload", field },
        { status: 400 },
      );
    }

    const user = await prisma.user.findUnique({
      where: { id: userId },
      select: {
        id: true,
        email: true,
        practiceId: true,
        passwordHash: true,
      },
    });
    if (!user || user.practiceId !== practiceId) {
      return apiError("unauthorized", 401);
    }

    const ok = await bcrypt.compare(
      parsed.data.currentPassword,
      user.passwordHash,
    );
    if (!ok) {
      return NextResponse.json(
        { error: "Current password is incorrect.", field: "currentPassword" },
        { status: 400 },
      );
    }

    const newHash = await bcrypt.hash(parsed.data.newPassword, 12);

    try {
      await prisma.$transaction(async (tx: Prisma.TransactionClient) => {
        const current = await lockCurrentAccountMutationAuthority(tx, {
          userId,
          sessionId: currentSessionToken,
          expectedPracticeId: practiceId,
          expectedPasswordHash: user.passwordHash,
          expectedEmail: user.email,
          surface: "physician",
        });
        await tx.user.update({
          where: { id: userId },
          data: {
            passwordHash: newHash,
            failedLoginCount: 0,
            lockedUntil: null,
          },
        });
        await tx.authToken.updateMany({
          where: {
            userId,
            purpose: {
              in: [
                AuthTokenPurpose.PASSWORD_RESET,
                AuthTokenPurpose.EMAIL_CHANGE,
              ],
            },
            usedAt: null,
          },
          data: { usedAt: new Date() },
        });
        await tx.userSession.deleteMany({
          where: {
            userId,
            NOT: { sessionToken: currentSessionToken },
          },
        });
        await appendAuthMutationAuditInTransaction(tx, {
          action: "PASSWORD_CHANGED",
          userId,
          userEmail: current.user.email,
          practiceId: current.user.practiceId,
          metadata: { keptCurrentSession: true },
        });
      });
    } catch (error) {
      if (error instanceof AccountMutationAuthorityError) {
        return apiError("Account state changed. Sign in again.", 409, {
          code: "ACCOUNT_AUTHORITY_CHANGED",
        });
      }
      console.error(
        "[api:settings:change-password] credential mutation failed",
      );
      return apiError("Could not update your password. Try again.", 500);
    }

    log.info("api:settings:change-password", "password updated", {
      userId,
      keptCurrentSession: true,
    });
    return NextResponse.json({ ok: true }, { status: 200 });
  },
);
