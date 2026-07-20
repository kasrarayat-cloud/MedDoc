// ============================================================================
// /api/auth/verify-email (T-M16.2; 2026-05-13 GET → interstitial POST)
// ----------------------------------------------------------------------------
// Consumer for the signup-time EMAIL_VERIFICATION flow.
//
// Flow:
//   GET ?token=…   — renders an HTML interstitial that auto-POSTs the
//                    token back to this same endpoint. NO DB mutation
//                    on GET, so a leaked Referer (or a link
//                    prefetcher) cannot side-effect the account.
//   POST           — consumes the token + sets emailVerified + 303s
//                    to /login. Form body carries the token; the
//                    interstitial submits a same-origin POST so the
//                    Referer header lands on this app, not a third
//                    party.
//
// Security audit P1-K (2026-05-13): pre-fix, GET mutated and the
// token leaked via Referer if the user clicked the email link while
// another tab held a hostile origin. The interstitial POST + the
// same-origin-only Referer policy closes that vector.
// ============================================================================

import { NextResponse } from "next/server";
import { z } from "zod";

import prisma from "@meddoc/db";
import { AuthTokenPurpose, type Prisma } from "@prisma/client";

import { apiError, withApiHandler } from "@/lib/api-error";
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
import { APP_URL } from "@/lib/constants";
import { log } from "@/lib/log";
import { emailLinkInterstitialHtml } from "@/lib/email-link-interstitial";
import { appendAuthMutationAuditInTransaction } from "@/lib/audit";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const VerificationMetadataSchema = z.object({
  email: z.string().email().max(254),
});

function redirectToLogin(reason: string): NextResponse {
  // Strip the Referer so the spent token doesn't land in /login
  // access logs / analytics. `no-referrer` is appropriate here
  // because the destination is internal and doesn't need the
  // origin signal. Audit P1-K WARN follow-up.
  return NextResponse.redirect(
    `${APP_URL}/login?verify=${encodeURIComponent(reason)}`,
    { status: 303, headers: { "Referrer-Policy": "no-referrer" } },
  );
}

export const GET = withApiHandler("api:auth:verify-email", async (req) => {
  // GET is read-only — no rate-limit consumption, no DB mutation,
  // just renders the interstitial page that will POST the token.
  // The token is copied into the form body, so the browser never needs to
  // retain the credential-bearing GET URL as a Referer.
  const url = new URL(req.url);
  const token = url.searchParams.get("token");
  if (!token) return apiError("missing token", 400);

  const html = emailLinkInterstitialHtml({
    actionPath: "/api/auth/verify-email",
    token,
    headline: "Verifying your email…",
    detail:
      "Hold on — we're finishing your email verification. This will only take a moment.",
  });
  return new NextResponse(html, {
    status: 200,
    headers: {
      "Content-Type": "text/html; charset=utf-8",
      "Referrer-Policy": "no-referrer",
      // Email-link interstitials are not indexable.
      "X-Robots-Tag": "noindex, nofollow",
    },
  });
});

export const POST = withApiHandler(
  "api:auth:verify-email",
  async (req) => {
    const blocked = await sharedRateLimitOr429(
      RATE_LIMITS.AUTH_EMAIL,
      clientIpFromRequest(req),
    );
    if (blocked) return blocked;

    // Accept either a JSON body or the interstitial's HTML form post.
    let token: string | null = null;
    const contentType = req.headers.get("content-type") ?? "";
    if (contentType.includes("application/json")) {
      try {
        const body = (await req.json()) as { token?: unknown };
        if (typeof body.token === "string") token = body.token;
      } catch {
        return apiError("invalid JSON body", 400);
      }
    } else {
      const form = await req.formData().catch(() => null);
      const raw = form?.get("token");
      if (typeof raw === "string") token = raw;
    }
    if (!token) return apiError("missing token", 400);

    const candidate = await findAuthTokenCandidate({
      token,
      purpose: AuthTokenPurpose.EMAIL_VERIFICATION,
    });
    if (!candidate) {
      return redirectToLogin("invalid-or-expired");
    }

    let userId: string;
    try {
      userId = await prisma.$transaction(
        async (tx: Prisma.TransactionClient) => {
          const locked = await lockCurrentAuthTokenForMutation(tx, {
            token,
            purpose: AuthTokenPurpose.EMAIL_VERIFICATION,
            candidate,
          });
          const metadata = VerificationMetadataSchema.safeParse(
            locked.token.metadata,
          );
          if (!metadata.success || metadata.data.email !== locked.user.email) {
            throw new AuthTokenAuthorityError();
          }

          // Consume before setting emailVerified: the account-security
          // trigger retires every still-unused verification bearer. A later
          // failure rolls both operations back atomically.
          await consumeLockedAuthToken(tx, locked.token.id, locked.now);
          await tx.user.update({
            where: { id: locked.user.id },
            data: { emailVerified: locked.now },
          });
          await tx.userSession.deleteMany({
            where: { userId: locked.user.id },
          });
          await tx.authToken.updateMany({
            where: {
              userId: locked.user.id,
              purpose: AuthTokenPurpose.EMAIL_VERIFICATION,
              usedAt: null,
            },
            data: { usedAt: locked.now },
          });
          await appendAuthMutationAuditInTransaction(tx, {
            action: "EMAIL_VERIFIED",
            userId: locked.user.id,
            userEmail: locked.user.email,
            practiceId: locked.user.practiceId,
            metadata: { via: "verification_token" },
          });
          return locked.user.id;
        },
      );
    } catch (error) {
      if (error instanceof AuthTokenAuthorityError) {
        return redirectToLogin("invalid-or-expired");
      }
      console.error("[api:auth:verify-email] verification mutation failed");
      return redirectToLogin("error");
    }

    log.info("api:auth:verify-email", "email verified", { userId });
    return redirectToLogin("ok");
  },
  { exposeTimingHeaders: false },
);
