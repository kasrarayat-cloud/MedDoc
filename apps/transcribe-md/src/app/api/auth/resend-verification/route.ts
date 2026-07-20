// ============================================================================
// POST /api/auth/resend-verification (T-M16.2)
// ----------------------------------------------------------------------------
// Body: { email: string }
//
// Enqueues a durable EMAIL_VERIFICATION delivery intent, same shape
// as /api/auth/forgot-password: anti-enumeration always-200 response,
// shared 5/hour/IP rate-limit bucket ("auth-email:<ip>"). When verified
// delivery is unavailable, no bearer token is minted.
//
// Behavior matrix:
//   - User exists + unverified: issue token + send email.
//   - User exists + already verified: silently succeed (no email —
//     there's nothing to resend, and we don't want to reveal that
//     this address is verified).
//   - User doesn't exist: silently succeed.
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

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const BodySchema = z.object({
  email: z.string().email().max(254),
});

const GENERIC_OK_BODY = {
  ok: true,
  message:
    "If an unverified account exists for that email, we've sent a new verification link.",
} as const;

export const POST = withApiHandler(
  "api:auth:resend-verification",
  async (req) => {
    const ip = clientIpFromRequest(req);
    // AUTH_EMAIL shared bucket — see forgot-password/route.ts for why.
    const blocked = await sharedRateLimitOr429(RATE_LIMITS.AUTH_EMAIL, ip);
    if (blocked) return blocked;

    let body: unknown;
    try {
      body = await req.json();
    } catch {
      return apiError("invalid JSON body", 400);
    }
    const parsed = BodySchema.safeParse(body);
    if (!parsed.success) return apiError("invalid email", 400);

    const email = parsed.data.email.trim().toLowerCase();

    if (!isEmailDeliveryEnabled()) {
      console.info(
        "[auth:resend-verification] request suppressed — delivery unavailable",
      );
      return NextResponse.json(GENERIC_OK_BODY, { status: 200 });
    }

    try {
      await enqueueAuthEmailRequest({
        email,
        purpose: AuthEmailPurpose.EMAIL_VERIFICATION,
      });
    } catch {
      console.error("[auth:resend-verification] durable enqueue failed");
    }

    return NextResponse.json(GENERIC_OK_BODY, { status: 200 });
  },
  { exposeTimingHeaders: false },
);
