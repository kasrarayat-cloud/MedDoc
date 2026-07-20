// ============================================================================
// POST /api/auth/reset-password (T-M16.2)
// ----------------------------------------------------------------------------
// Body: { token: string, password: string, confirmPassword: string }
//
// Validates the token, updates the password, revokes every UserSession
// for the account so any logged-in device logs out immediately.
// Returns 200 on success, 400 on invalid token / weak password /
// mismatch. Rate limited (AUTH_EMAIL bucket) to slow brute-force
// attempts against enumerated tokens — see `rateLimitOr429` below.
// ============================================================================

import { z } from "zod";
import { NextResponse } from "next/server";
import bcrypt from "bcryptjs";

import prisma from "@meddoc/db";
import { AuthTokenPurpose, type Prisma } from "@prisma/client";

import { apiError, withApiHandler } from "@/lib/api-error";
import { appendAuthMutationAuditInTransaction } from "@/lib/audit";
import {
  AuthTokenAuthorityError,
  consumeLockedAuthToken,
  findAuthTokenCandidate,
  lockCurrentAuthTokenForMutation,
} from "@/lib/auth-tokens";
import {
  RATE_LIMITS,
  clientIpFromRequest,
  sharedRateLimitOr429,
} from "@/lib/rate-limit";
import { log } from "@/lib/log";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

// Mirror signupAction's policy — same regex, same minimum length, so
// a user coming via password-reset gets the same strength guarantee
// as a fresh signup.
const PasswordSchema = z
  .string()
  .min(10, "Password must be at least 10 characters")
  .regex(/[a-z]/, "Password must contain a lowercase letter")
  .regex(/[A-Z]/, "Password must contain an uppercase letter")
  .regex(/\d/, "Password must contain a digit");

const BodySchema = z
  .object({
    token: z.string().min(20).max(200),
    password: PasswordSchema,
    confirmPassword: z.string(),
  })
  .refine((d) => d.password === d.confirmPassword, {
    message: "Passwords do not match",
    path: ["confirmPassword"],
  });

export const POST = withApiHandler(
  "api:auth:reset-password",
  async (req) => {
    const blocked = await sharedRateLimitOr429(
      RATE_LIMITS.AUTH_EMAIL,
      clientIpFromRequest(req),
    );
    if (blocked) return blocked;

    let body: unknown;
    try {
      body = await req.json();
    } catch {
      return apiError("invalid JSON body", 400);
    }
    const parsed = BodySchema.safeParse(body);
    if (!parsed.success) {
      // Collapse Zod's detailed message to a single field-shaped error.
      const first = parsed.error.issues[0];
      const field = first?.path.join(".") || "_form";
      return NextResponse.json(
        { error: first?.message || "invalid payload", field },
        { status: 400 },
      );
    }

    const candidate = await findAuthTokenCandidate({
      token: parsed.data.token,
      purpose: AuthTokenPurpose.PASSWORD_RESET,
    });
    if (!candidate) {
      // Generic message — don't distinguish expired vs already-used vs
      // not-found so an attacker fishing for reset tokens gets the same
      // answer regardless.
      return apiError(
        "This reset link is invalid or has expired. Request a new one.",
        400,
      );
    }

    const passwordHash = await bcrypt.hash(parsed.data.password, 12);

    let result: { userId: string };
    try {
      result = await prisma.$transaction(
        async (tx: Prisma.TransactionClient) => {
          // The token's user row is the serialization point. Re-establish the
          // exact, current token authority under lock, then keep the credential
          // mutation, token consumption/invalidation, and session revocation in
          // this same transaction. A stale or superseded link changes nothing.
          const locked = await lockCurrentAuthTokenForMutation(tx, {
            token: parsed.data.token,
            purpose: AuthTokenPurpose.PASSWORD_RESET,
            candidate,
          });

          // Consume the exact locked bearer before the password mutation. The
          // database security trigger retires every remaining reset/change
          // bearer when credentials change, so doing this afterward would
          // make the legitimate current redemption fail closed too.
          await consumeLockedAuthToken(tx, locked.token.id, locked.now);
          await tx.user.update({
            where: { id: locked.user.id },
            data: {
              passwordHash,
              failedLoginCount: 0,
              lockedUntil: null,
            },
          });
          await tx.userSession.deleteMany({
            where: { userId: locked.user.id },
          });
          await tx.authToken.updateMany({
            where: {
              userId: locked.user.id,
              purpose: {
                in: [
                  AuthTokenPurpose.PASSWORD_RESET,
                  AuthTokenPurpose.EMAIL_CHANGE,
                ],
              },
              usedAt: null,
            },
            data: { usedAt: locked.now },
          });
          await appendAuthMutationAuditInTransaction(tx, {
            action: "PASSWORD_CHANGED",
            userId: locked.user.id,
            userEmail: locked.user.email,
            practiceId: locked.user.practiceId,
            metadata: { via: "reset_token" },
          });
          return { userId: locked.user.id };
        },
      );
    } catch (error) {
      if (error instanceof AuthTokenAuthorityError) {
        return apiError(
          "This reset link is invalid or has expired. Request a new one.",
          400,
        );
      }
      console.error("[auth:reset-password] credential mutation failed");
      return apiError("Could not reset the password. Try again.", 500);
    }

    log.info("auth:reset-password", "password reset + sessions revoked", {
      userId: result.userId,
    });

    return NextResponse.json({ ok: true }, { status: 200 });
  },
  { exposeTimingHeaders: false },
);
