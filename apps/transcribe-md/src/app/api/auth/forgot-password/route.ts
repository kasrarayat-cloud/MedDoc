// ============================================================================
// POST /api/auth/forgot-password (T-M16.2)
// ----------------------------------------------------------------------------
// Body:  { email: string }
// Status: 200 always (anti-enumeration — no way to tell whether the
//         address exists on the account side).
//
// Success side-effects (when the email resolves to a real account):
//   1. Invalidate prior PASSWORD_RESET tokens for the user.
//   2. Mint a new PASSWORD_RESET AuthToken with 1-hour TTL.
//   3. Email the reset link via Resend.
//
// If RESEND_API_KEY is unset, we log the link at warn level instead of
// emailing it. That's the dev-escape-hatch — production deploys MUST
// have Resend configured (enforced by RESEND_FROM_VERIFIED=true elsewhere).
//
// Rate limit: 5 requests / hour / IP via the inline limiter. This is the
// same bucket as /api/auth/resend-verification because they're both
// "email me a token" — an attacker mixing the two against one user's
// address shouldn't bypass the cap.
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
import { sendPasswordResetEmail } from '@/lib/email';
import { MARKETING_URL, APP_URL } from '@/lib/constants';
import { redactPhi } from '@meddoc/ai';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

const BodySchema = z.object({
  email: z.string().email().max(254),
});

const RESET_TTL_MS = 60 * 60 * 1000; // 1 hour
const RATE_LIMIT = 5;
const RATE_WINDOW_MS = 60 * 60 * 1000; // 1 hour
// Single bucket name — shared with resend-verification, see header comment.
const RATE_KEY_PREFIX = 'auth-email:';

void MARKETING_URL; // kept for future "link to marketing from email" copy

export const POST = withApiHandler('api:auth:forgot-password', async (req) => {
  const ip = clientIpFromRequest(req);
  const rl = tryConsume(
    `${RATE_KEY_PREFIX}${ip}`,
    RATE_LIMIT,
    RATE_WINDOW_MS
  );
  if (!rl.allowed) {
    // 429 is the honest answer. We don't worry about enumeration here
    // because the rate limit is keyed by IP, not by email.
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
  // Bad JSON → 400. Unknown email → 200 (see below).
  if (!parsed.success) return apiError('invalid email', 400);

  const email = parsed.data.email.trim().toLowerCase();

  // Anti-enumeration: we DON'T branch our response based on whether
  // the user exists. The lookup + email send happens async in the
  // same handler so an attacker times no difference between
  // "existing account" and "no account here" requests. Both return
  // 200 with the same copy.
  try {
    const user = await prisma.user.findUnique({
      where: { email },
      select: { id: true, email: true, name: true, isActive: true },
    });

    if (user && user.isActive) {
      const { token } = await createAuthToken({
        userId: user.id,
        purpose: AuthTokenPurpose.PASSWORD_RESET,
        expiresInMs: RESET_TTL_MS,
      });

      const resetUrl = `${APP_URL}/reset-password?token=${encodeURIComponent(token)}`;

      if (process.env.RESEND_API_KEY) {
        await sendPasswordResetEmail({
          toEmail: user.email,
          resetUrl,
          userName: user.name,
        });
        console.info(
          `[auth:forgot-password] reset email sent ip=${ip} user=${user.id}`
        );
      } else {
        // Dev-escape: log the link so local testing doesn't need
        // a real Resend account. NEVER log the full URL in prod
        // (production has the key set).
        console.warn(
          `[auth:forgot-password] RESEND_API_KEY unset — not sending email. dev-only link: ${resetUrl}`
        );
      }
    } else {
      console.info(
        `[auth:forgot-password] no matching active user ip=${ip}`
      );
    }
  } catch (err) {
    // Catch-and-log so the failure mode doesn't leak through the
    // 200. redactPhi masks the email if it appears in the error
    // message (Resend errors often quote the recipient).
    console.error(
      `[auth:forgot-password] unhandled error ip=${ip}:`,
      redactPhi(err instanceof Error ? err.message : err)
    );
  }

  return NextResponse.json(
    {
      ok: true,
      message:
        "If an account exists for that email, we've sent a reset link. Check your inbox.",
    },
    { status: 200 }
  );
});
