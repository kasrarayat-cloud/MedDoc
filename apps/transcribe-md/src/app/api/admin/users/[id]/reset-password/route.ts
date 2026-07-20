// ============================================================================
// POST /api/admin/users/[id]/reset-password — trigger reset email
// ----------------------------------------------------------------------------
// Mints a one-time PASSWORD_RESET token (1-hour TTL) and emails it to
// the user. Same flow as /forgot-password — the admin variant just
// skips the user-typed-their-email step.
//
// We deliberately do NOT change the user's password here; we only
// trigger the email. The user follows the link, sets their own new
// password, and the token is consumed.
// ============================================================================

import { NextResponse } from "next/server";

import prisma from "@meddoc/db";
import { AuthTokenPurpose } from "@prisma/client";

import { adminApi } from "@/lib/admin-api-gate";
import { logAudit } from "@/lib/audit";
import { createAuthToken } from "@/lib/auth-tokens";
import { sendPasswordResetEmail } from "@/lib/email";
import { isEmailDeliveryEnabled } from "@/lib/email-enabled";
import { APP_URL } from "@/lib/constants";

export const dynamic = "force-dynamic";

export const POST = adminApi("users:reset-password", async (req, ctx) => {
  const segs = new URL(req.url).pathname.split("/").filter(Boolean);
  const id = segs[segs.indexOf("users") + 1];
  if (!id) return NextResponse.json({ error: "Bad path" }, { status: 400 });

  // Security audit P1-E: an admin emailing themselves a reset link
  // via this admin-only route is a self-service end-run around the
  // public /forgot-password flow. Block by symmetry with the other
  // self-targeting admin actions.
  if (id === ctx.session.user.id) {
    return NextResponse.json(
      { error: "Use /forgot-password for your own password reset." },
      { status: 403 },
    );
  }

  const user = await prisma.user.findUnique({
    where: { id },
    select: { id: true, email: true, name: true, practiceId: true },
  });
  if (!user) return NextResponse.json({ error: "Not found" }, { status: 404 });

  let emailSent = false;
  let errorCode: string | null = null;
  if (!isEmailDeliveryEnabled()) {
    errorCode = "EMAIL_DELIVERY_UNAVAILABLE";
  } else {
    try {
      const { token } = await createAuthToken({
        userId: user.id,
        purpose: AuthTokenPurpose.PASSWORD_RESET,
        expiresInMs: 60 * 60 * 1000,
        expectedUserEmail: user.email,
      });
      const resetUrl = `${APP_URL}/reset-password?token=${encodeURIComponent(token)}`;
      await sendPasswordResetEmail({
        toEmail: user.email,
        resetUrl,
        userName: user.name ?? null,
      });
      emailSent = true;
    } catch {
      errorCode = "EMAIL_DELIVERY_FAILED";
      console.error("[admin:reset-password] delivery failed");
    }
  }

  await logAudit({
    action: "USER_PASSWORD_RESET_TRIGGERED",
    targetType: "User",
    targetId: id,
    success: emailSent,
    errorCode,
    metadata: {
      targetEmail: user.email,
      actorEmail: ctx.session.user.email,
    },
    practiceId: user.practiceId,
  });

  if (!emailSent) {
    return NextResponse.json(
      { ok: false, error: "Email send failed", errorCode },
      { status: 502 },
    );
  }
  return NextResponse.json({ ok: true });
});
