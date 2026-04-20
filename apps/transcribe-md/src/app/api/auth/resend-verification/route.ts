// ============================================================================
// POST /api/auth/resend-verification (T-M16.2)
// ----------------------------------------------------------------------------
// Body: { email: string }
//
// Re-mints an EMAIL_VERIFICATION token + emails the link, same shape
// as /api/auth/forgot-password: anti-enumeration always-200 response,
// shared 5/hour/IP rate-limit bucket ("auth-email:<ip>"), dev-escape
// when RESEND_API_KEY is unset.
//
// Behavior matrix:
//   - User exists + unverified: issue token + send email.
//   - User exists + already verified: silently succeed (no email —
//     there's nothing to resend, and we don't want to reveal that
//     this address is verified).
//   - User doesn't exist: silently succeed.
// ============================================================================

import { z } from 'zod';
import { NextResponse } from 'next/server';

import prisma from '@meddoc/db';
import { AuthTokenPurpose } from '@prisma/client';

import { apiError, withApiHandler } from '@/lib/api-error';
import { createAuthToken } from '@/lib/auth-tokens';
import {
  clientIpFromRequest,
  tryConsume,
} from '@/lib/rate-limit-inline';
import { sendEmailVerification } from '@/lib/email';
import { APP_URL } from '@/lib/constants';
import { redactPhi } from '@meddoc/ai';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

const BodySchema = z.object({
  email: z.string().email().max(254),
});

const VERIFY_TTL_MS = 24 * 60 * 60 * 1000; // 24 hours
const RATE_LIMIT = 5;
const RATE_WINDOW_MS = 60 * 60 * 1000;
const RATE_KEY_PREFIX = 'auth-email:'; // shared with forgot-password

export const POST = withApiHandler(
  'api:auth:resend-verification',
  async (req) => {
    const ip = clientIpFromRequest(req);
    const rl = tryConsume(
      `${RATE_KEY_PREFIX}${ip}`,
      RATE_LIMIT,
      RATE_WINDOW_MS
    );
    if (!rl.allowed) {
      return NextResponse.json(
        { error: 'Too many requests. Try again later.' },
        {
          status: 429,
          headers: { 'Retry-After': String(rl.retryAfterSec) },
        }
      );
    }

    let body: unknown;
    try {
      body = await req.json();
    } catch {
      return apiError('invalid JSON body', 400);
    }
    const parsed = BodySchema.safeParse(body);
    if (!parsed.success) return apiError('invalid email', 400);

    const email = parsed.data.email.trim().toLowerCase();

    try {
      const user = await prisma.user.findUnique({
        where: { email },
        select: {
          id: true,
          name: true,
          email: true,
          isActive: true,
          emailVerified: true,
        },
      });

      if (user?.isActive && user.emailVerified === null) {
        const { token } = await createAuthToken({
          userId: user.id,
          purpose: AuthTokenPurpose.EMAIL_VERIFICATION,
          expiresInMs: VERIFY_TTL_MS,
        });
        const verifyUrl = `${APP_URL}/api/auth/verify-email?token=${encodeURIComponent(token)}`;

        if (process.env.RESEND_API_KEY) {
          await sendEmailVerification({
            toEmail: user.email,
            verifyUrl,
            userName: user.name,
          });
          console.info(
            `[auth:resend-verification] sent ip=${ip} user=${user.id}`
          );
        } else {
          console.warn(
            `[auth:resend-verification] RESEND_API_KEY unset — dev-only link: ${verifyUrl}`
          );
        }
      } else {
        // Either no matching user, user is inactive, or already
        // verified. All three map to "silent success" so the caller
        // can't enumerate accounts or verification states.
        console.info(
          `[auth:resend-verification] no-op (unknown/verified/inactive) ip=${ip}`
        );
      }
    } catch (err) {
      console.error(
        `[auth:resend-verification] unhandled ip=${ip}:`,
        redactPhi(err instanceof Error ? err.message : err)
      );
    }

    return NextResponse.json(
      {
        ok: true,
        message:
          "If an unverified account exists for that email, we've sent a new verification link.",
      },
      { status: 200 }
    );
  }
);
