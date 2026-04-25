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
//   2. Require the new email to differ from current AND not already
//      belong to another user (early-fail — prevents confusing "email
//      taken" errors at confirm time).
//   3. Mint an EMAIL_CHANGE AuthToken with metadata={ newEmail,
//      oldEmail } — the consumer needs both to know what to change
//      AND where to send the "your email was changed" notification.
//   4. Send the confirmation link to the NEW address.
//
// If RESEND_API_KEY is unset we log the link (dev mode). Production
// relies on RESEND_FROM_VERIFIED=true elsewhere to enforce config.
// ============================================================================

import { z } from 'zod';
import { NextResponse } from 'next/server';
import bcrypt from 'bcryptjs';

import prisma from '@meddoc/db';
import { AuthTokenPurpose } from '@prisma/client';

import { apiError, withApiHandler } from '@/lib/api-error';
import { auth } from '@/lib/nextauth';
import { createAuthToken } from '@/lib/auth-tokens';
import { RATE_LIMITS, rateLimitOr429 } from '@/lib/rate-limit';
import { sendEmailChangeRequestEmail } from '@/lib/email';
import { APP_URL } from '@/lib/constants';
import { redactPhi } from '@meddoc/ai';
import { log } from '@/lib/log';
import { logAudit } from '@/lib/audit';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

const CHANGE_TTL_MS = 24 * 60 * 60 * 1000; // 24 hours

const BodySchema = z.object({
  newEmail: z.string().email().max(254),
  password: z.string().min(1),
});

export const POST = withApiHandler(
  'api:settings:change-email',
  async (req) => {
    const session = await auth();
    const userId = session?.user?.id;
    if (!userId) return apiError('unauthorized', 401);

    const blocked = rateLimitOr429(RATE_LIMITS.SETTINGS, userId);
    if (blocked) return blocked;

    let body: unknown;
    try {
      body = await req.json();
    } catch {
      return apiError('invalid JSON body', 400);
    }
    const parsed = BodySchema.safeParse(body);
    if (!parsed.success) {
      const first = parsed.error.issues[0];
      const field = first?.path.join('.') || '_form';
      return NextResponse.json(
        { error: first?.message || 'invalid payload', field },
        { status: 400 }
      );
    }

    const newEmail = parsed.data.newEmail.trim().toLowerCase();

    const user = await prisma.user.findUnique({
      where: { id: userId },
      select: { id: true, email: true, name: true, passwordHash: true },
    });
    if (!user) return apiError('user not found', 404);

    if (user.email === newEmail) {
      return NextResponse.json(
        {
          error: "That's already your current email.",
          field: 'newEmail',
        },
        { status: 400 }
      );
    }

    const ok = await bcrypt.compare(parsed.data.password, user.passwordHash);
    if (!ok) {
      return NextResponse.json(
        { error: 'Password is incorrect.', field: 'password' },
        { status: 400 }
      );
    }

    // T-M18.3 A19: probe the conflict but DON'T surface the outcome to
    // the caller — a logged-in attacker could otherwise fish for "is
    // X@Y a registered email" by flipping through candidate addresses
    // from an authenticated session. Instead, we return the same 200
    // "check your new email" response in both branches, and silently
    // skip the send + token mint when the address is taken. The user
    // who actually owns `newEmail` never sees a confirm link, so the
    // pending change never completes.
    const existing = await prisma.user.findUnique({
      where: { email: newEmail },
      select: { id: true },
    });

    const GENERIC_OK_BODY = {
      ok: true,
      message:
        "Check your new email for a confirmation link. Your email won't change until you click it.",
    } as const;

    if (existing) {
      log.info('api:settings:change-email', 'request suppressed — email taken', {
        userId: user.id,
      });
      return NextResponse.json(GENERIC_OK_BODY, { status: 200 });
    }

    const { token } = await createAuthToken({
      userId: user.id,
      purpose: AuthTokenPurpose.EMAIL_CHANGE,
      expiresInMs: CHANGE_TTL_MS,
      metadata: { newEmail, oldEmail: user.email },
    });

    const confirmUrl = `${APP_URL}/api/auth/confirm-email?token=${encodeURIComponent(token)}`;

    if (process.env.RESEND_API_KEY) {
      try {
        await sendEmailChangeRequestEmail({
          toEmail: newEmail,
          confirmUrl,
          userName: user.name,
        });
      } catch (err) {
        console.error(
          `[api:settings:change-email] send to new address failed user=${user.id}:`,
          redactPhi(err instanceof Error ? err.message : err)
        );
        return apiError(
          "We couldn't send the confirmation email. Check the address and try again.",
          502
        );
      }
    } else {
      console.warn(
        `[api:settings:change-email] RESEND_API_KEY unset — dev-only link: ${confirmUrl}`
      );
    }

    log.info('api:settings:change-email', 'request started', {
      userId: user.id,
    });
    void logAudit({
      action: 'EMAIL_CHANGE_REQUESTED',
      targetType: 'User',
      targetId: user.id,
      // newEmail domain only — full address is PHI-adjacent for audit
      // aggregation and would noise the compliance export.
      metadata: { newEmailDomain: newEmail.split('@')[1] ?? 'unknown' },
    });
    return NextResponse.json(GENERIC_OK_BODY, { status: 200 });
  }
);
