// ============================================================================
// /api/auth/confirm-email (T-M16.2; 2026-05-13 GET → interstitial POST)
// ----------------------------------------------------------------------------
// Consumer for the EMAIL_CHANGE flow started in
// /api/settings/change-email.
//
// Flow:
//   GET ?token=…   — renders an HTML interstitial that auto-POSTs the
//                    token back to this same endpoint. NO DB mutation
//                    on GET so a leaked Referer (or a link prefetcher)
//                    cannot side-effect the account.
//   POST           — consumes the token + updates the email + 303s to
//                    /settings.
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
import { sendEmailChangedNotification } from "@/lib/email";
import { isEmailDeliveryEnabled } from "@/lib/email-enabled";
import { APP_URL } from "@/lib/constants";
import { log } from "@/lib/log";
import { appendAuthMutationAuditInTransaction } from "@/lib/audit";
import { emailLinkInterstitialHtml } from "@/lib/email-link-interstitial";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const EmailChangeMetadataSchema = z
  .object({
    newEmail: z.string().email().max(254),
    oldEmail: z.string().email().max(254),
  })
  .strict();

class EmailChangeConflictError extends Error {}

function isUniqueConstraintError(error: unknown): boolean {
  return (
    typeof error === "object" &&
    error !== null &&
    "code" in error &&
    (error as { code?: unknown }).code === "P2002"
  );
}

function redirectToSettings(reason: string): NextResponse {
  // See verify-email's matching helper — strip Referer so the spent
  // token doesn't land in /settings access logs.
  return NextResponse.redirect(
    `${APP_URL}/settings?emailChange=${encodeURIComponent(reason)}`,
    { status: 303, headers: { "Referrer-Policy": "no-referrer" } },
  );
}

export const GET = withApiHandler("api:auth:confirm-email", async (req) => {
  // GET is read-only — see verify-email's matching handler.
  const url = new URL(req.url);
  const token = url.searchParams.get("token");
  if (!token) return apiError("missing token", 400);

  const html = emailLinkInterstitialHtml({
    actionPath: "/api/auth/confirm-email",
    token,
    headline: "Confirming your email change…",
    detail:
      "Hold on — we're finishing the email change. This will only take a moment.",
  });
  return new NextResponse(html, {
    status: 200,
    headers: {
      "Content-Type": "text/html; charset=utf-8",
      "Referrer-Policy": "no-referrer",
      "X-Robots-Tag": "noindex, nofollow",
    },
  });
});

export const POST = withApiHandler(
  "api:auth:confirm-email",
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
      purpose: AuthTokenPurpose.EMAIL_CHANGE,
    });
    if (!candidate) {
      return redirectToSettings("invalid-or-expired");
    }

    let updated: {
      userId: string;
      name: string | null;
      oldEmail: string;
      newEmail: string;
    };
    try {
      updated = await prisma.$transaction(
        async (tx: Prisma.TransactionClient) => {
          const locked = await lockCurrentAuthTokenForMutation(tx, {
            token,
            purpose: AuthTokenPurpose.EMAIL_CHANGE,
            candidate,
          });
          const metadata = EmailChangeMetadataSchema.safeParse(
            locked.token.metadata,
          );
          if (!metadata.success) throw new AuthTokenAuthorityError();

          const oldEmail = metadata.data.oldEmail;
          const newEmail = metadata.data.newEmail.trim().toLowerCase();
          if (
            metadata.data.newEmail !== newEmail ||
            oldEmail !== locked.user.email ||
            newEmail === oldEmail
          ) {
            throw new AuthTokenAuthorityError();
          }

          // Recheck the target only after locking the exact token owner. The
          // unique index remains the final cross-user race arbiter.
          const conflict = await tx.user.findUnique({
            where: { email: newEmail },
            select: { id: true },
          });
          if (conflict && conflict.id !== locked.user.id) {
            throw new EmailChangeConflictError();
          }

          // Mark the exact bearer used before changing security state. The
          // database security-state trigger retires every still-unused email
          // authority; consuming first lets this one transaction complete
          // while any rollback restores both the bearer and identity.
          await consumeLockedAuthToken(tx, locked.token.id, locked.now);
          const current = await tx.user.update({
            where: { id: locked.user.id },
            data: {
              email: newEmail,
              emailVerified: locked.now,
            },
            select: { name: true },
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
                  AuthTokenPurpose.EMAIL_VERIFICATION,
                  AuthTokenPurpose.EMAIL_CHANGE,
                ],
              },
              usedAt: null,
            },
            data: { usedAt: locked.now },
          });
          await appendAuthMutationAuditInTransaction(tx, {
            action: "EMAIL_CHANGE_CONFIRMED",
            userId: locked.user.id,
            userEmail: newEmail,
            practiceId: locked.user.practiceId,
            metadata: {
              newEmailDomain: newEmail.split("@")[1] ?? "unknown",
              oldEmailDomain: oldEmail.split("@")[1] ?? "unknown",
            },
          });
          return {
            userId: locked.user.id,
            name: current.name,
            oldEmail,
            newEmail,
          };
        },
      );
    } catch (error) {
      if (error instanceof AuthTokenAuthorityError) {
        return redirectToSettings("invalid-or-expired");
      }
      if (
        error instanceof EmailChangeConflictError ||
        isUniqueConstraintError(error)
      ) {
        return redirectToSettings("conflict");
      }
      console.error("[api:auth:confirm-email] identity mutation failed");
      return redirectToSettings("error");
    }

    log.info("api:auth:confirm-email", "email updated", {
      userId: updated.userId,
    });
    // Delivery is deliberately outside the database transaction. A failure
    // cannot roll the identity change back; it is recorded without provider
    // response content, recipient data, or URL/token material.
    if (isEmailDeliveryEnabled()) {
      void sendEmailChangedNotification({
        toEmail: updated.oldEmail,
        newEmail: updated.newEmail,
        userName: updated.name,
      }).catch(() => {
        console.error(
          "[api:auth:confirm-email] old-email notification delivery failed",
        );
      });
    }

    return redirectToSettings("ok");
  },
  { exposeTimingHeaders: false },
);
