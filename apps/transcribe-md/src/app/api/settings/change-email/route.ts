// ============================================================================
// POST /api/settings/change-email (T-M16.2)
// ----------------------------------------------------------------------------
// Body: { newEmail, password }
//
// Starts the email-change flow. Does NOT mutate User.email — that
// happens in /api/auth/confirm-email after the user clicks the link
// we send to the NEW address.
//
//   1. Verify password (proof of account ownership).
//   2. Re-establish exact current practice/user/session/password authority.
//   3. Atomically enqueue the destination-bound request and immutable audit.
//   4. Return a generic response; the isolated dispatcher performs target
//      conflict checks, token minting, and provider delivery later.
//
// If verified email delivery is unavailable, the route returns 503 before
// admitting a request. This route never sees a raw bearer or provider result.
// ============================================================================

import { z } from "zod";
import { NextResponse } from "next/server";
import bcrypt from "bcryptjs";

import prisma from "@meddoc/db";
import { type Prisma } from "@prisma/client";

import { apiError, withApiHandler } from "@/lib/api-error";
import { auth } from "@/lib/nextauth";
import { RATE_LIMITS, sharedRateLimitOr429 } from "@/lib/rate-limit";
import { isEmailDeliveryEnabled } from "@/lib/email-enabled";
import { log } from "@/lib/log";
import { appendAuthMutationAuditInTransaction } from "@/lib/audit";
import { enqueueAuthEmailChangeRequestInTransaction } from "@/lib/auth-email-outbox";
import {
  AccountMutationAuthorityError,
  lockCurrentAccountMutationAuthority,
} from "@/lib/account-mutation-authority";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const BodySchema = z.object({
  newEmail: z.string().email().max(254),
  password: z.string().min(1),
});

const GENERIC_OK_BODY = {
  ok: true,
  message:
    "Check your new email for a confirmation link. Your email won't change until you click it.",
} as const;

export const POST = withApiHandler("api:settings:change-email", async (req) => {
  const session = await auth();
  const userId = session?.user?.id;
  const currentSessionToken = session?.user?.sessionId;
  const practiceId = session?.user?.practiceId;
  if (!userId || !currentSessionToken || !practiceId) {
    return apiError("unauthorized", 401);
  }

  const blocked = await sharedRateLimitOr429(RATE_LIMITS.SETTINGS, userId);
  if (blocked) return blocked;

  // Never create a bearer token that this deployment cannot deliver.
  if (!isEmailDeliveryEnabled()) {
    return apiError("Email change is temporarily unavailable.", 503, {
      code: "EMAIL_DELIVERY_UNAVAILABLE",
    });
  }

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

  const newEmail = parsed.data.newEmail.trim().toLowerCase();

  const user = await prisma.user.findUnique({
    where: { id: userId },
    select: {
      id: true,
      email: true,
      name: true,
      practiceId: true,
      passwordHash: true,
    },
  });
  if (!user || user.practiceId !== practiceId) {
    return apiError("unauthorized", 401);
  }

  if (user.email === newEmail) {
    return NextResponse.json(
      {
        error: "That's already your current email.",
        field: "newEmail",
      },
      { status: 400 },
    );
  }

  const ok = await bcrypt.compare(parsed.data.password, user.passwordHash);
  if (!ok) {
    return NextResponse.json(
      { error: "Password is incorrect.", field: "password" },
      { status: 400 },
    );
  }

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

      await enqueueAuthEmailChangeRequestInTransaction(tx, {
        userId,
        expectedCurrentEmail: current.user.email,
        requestedNewEmail: newEmail,
        expectedPracticeId: current.user.practiceId,
        expectedSessionToken: currentSessionToken,
        expectedPasswordHash: current.user.passwordHash,
      });
      await appendAuthMutationAuditInTransaction(tx, {
        action: "EMAIL_CHANGE_REQUESTED",
        userId,
        userEmail: current.user.email,
        practiceId: current.user.practiceId,
        metadata: { newEmailDomain: newEmail.split("@")[1] ?? "unknown" },
      });
    });
  } catch (error) {
    if (error instanceof AccountMutationAuthorityError) {
      return apiError("Account state changed. Sign in again.", 409, {
        code: "ACCOUNT_AUTHORITY_CHANGED",
      });
    }
    console.error("[api:settings:change-email] durable request failed");
    return apiError("Could not start the email change. Try again.", 500);
  }

  log.info("api:settings:change-email", "durable request accepted", {
    userId: user.id,
  });
  return NextResponse.json(GENERIC_OK_BODY, { status: 200 });
});
