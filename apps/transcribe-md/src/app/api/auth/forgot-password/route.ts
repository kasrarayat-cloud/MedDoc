// ============================================================================
// POST /api/auth/forgot-password (T-M16.2)
// ----------------------------------------------------------------------------
// Body:  { email: string }
// Status: 200 always (anti-enumeration — no way to tell whether the
//         address exists on the account side).
//
// The request path only admits a durable, address-hashed outbox intent.
// Account resolution, supersession, token minting, and delivery happen later
// inside the isolated dispatcher/database boundary.
//
// If verified email delivery is unavailable, no bearer token is minted and
// the same generic anti-enumeration response is returned.
//
// Rate limit: 5 requests / hour / IP via the inline limiter. This is the
// same bucket as /api/auth/resend-verification because they're both
// "email me a token" — an attacker mixing the two against one user's
// address shouldn't bypass the cap.
// ============================================================================

import { z } from "zod";
import { NextResponse } from "next/server";

import { AuthEmailPurpose } from "@prisma/client";

import { apiError, withApiHandler } from "@/lib/api-error";
import { enqueueAuthEmailRequest } from "@/lib/auth-email-outbox";
import {
  RATE_LIMITS,
  clientIpFromRequest,
  sharedRateLimitOr429,
} from "@/lib/rate-limit";
import { isEmailDeliveryEnabled } from "@/lib/email-enabled";
import { log } from "@/lib/log";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const BodySchema = z.object({
  email: z.string().email().max(254),
});

const GENERIC_OK_BODY = {
  ok: true,
  message:
    "If an account exists for that email, we've sent a reset link. Check your inbox.",
} as const;

export const POST = withApiHandler(
  "api:auth:forgot-password",
  async (req) => {
    const ip = clientIpFromRequest(req);
    // AUTH_EMAIL bucket is shared with resend-verification / reset-password
    // / verify-email / confirm-email so an attacker mixing them can't
    // bypass by round-robin.
    const blocked = await sharedRateLimitOr429(RATE_LIMITS.AUTH_EMAIL, ip);
    if (blocked) return blocked;

    let body: unknown;
    try {
      body = await req.json();
    } catch {
      return apiError("invalid JSON body", 400);
    }
    const parsed = BodySchema.safeParse(body);
    // Bad JSON → 400. Unknown email → 200 (see below).
    if (!parsed.success) return apiError("invalid email", 400);

    const email = parsed.data.email.trim().toLowerCase();

    if (!isEmailDeliveryEnabled()) {
      log.info(
        "auth:forgot-password",
        "request suppressed — delivery unavailable",
      );
      return NextResponse.json(GENERIC_OK_BODY, { status: 200 });
    }

    // Known and unknown addresses take the same durable enqueue path. Account
    // resolution, token minting, and provider delivery happen later in the
    // isolated dispatcher; neither raw address nor raw token is stored here.
    try {
      await enqueueAuthEmailRequest({
        email,
        purpose: AuthEmailPurpose.PASSWORD_RESET,
      });
    } catch {
      console.error("[auth:forgot-password] durable enqueue failed");
    }

    return NextResponse.json(GENERIC_OK_BODY, { status: 200 });
  },
  { exposeTimingHeaders: false },
);
