// ============================================================================
// GET /api/auth/verify-email?token=... (T-M16.2)
// ----------------------------------------------------------------------------
// Consumer for the signup-time EMAIL_VERIFICATION flow. Clicking the
// link from the verification email lands here.
//
// Steps:
//   1. Consume the EMAIL_VERIFICATION token.
//   2. UPDATE users.emailVerified = now().
//   3. Redirect to /login?verified=1. The login page shows a "your
//      email is verified — sign in" toast and the user signs in as
//      normal. We do NOT auto-login from a clicked email link because
//      the link may have come from a different browser (desktop email
//      → phone) and we don't want to transfer a session across UAs.
// ============================================================================

import { NextResponse } from 'next/server';

import prisma from '@meddoc/db';
import { AuthTokenPurpose } from '@prisma/client';

import { apiError, withApiHandler } from '@/lib/api-error';
import { consumeAuthToken } from '@/lib/auth-tokens';
import {
  RATE_LIMITS,
  clientIpFromRequest,
  rateLimitOr429,
} from '@/lib/rate-limit';
import { APP_URL } from '@/lib/constants';
import { redactPhi } from '@meddoc/ai';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

function redirectToLogin(reason: string): NextResponse {
  return NextResponse.redirect(
    `${APP_URL}/login?verify=${encodeURIComponent(reason)}`,
    { status: 303 }
  );
}

export const GET = withApiHandler('api:auth:verify-email', async (req) => {
  const blocked = rateLimitOr429(
    RATE_LIMITS.AUTH_EMAIL,
    clientIpFromRequest(req)
  );
  if (blocked) return blocked;

  const url = new URL(req.url);
  const token = url.searchParams.get('token');
  if (!token) return apiError('missing token', 400);

  const consumed = await consumeAuthToken({
    token,
    purpose: AuthTokenPurpose.EMAIL_VERIFICATION,
  });
  if (!consumed) {
    return redirectToLogin('invalid-or-expired');
  }

  try {
    await prisma.user.update({
      where: { id: consumed.userId },
      data: { emailVerified: new Date() },
    });
    console.info(
      `[api:auth:verify-email] verified user=${consumed.userId}`
    );
  } catch (err) {
    console.error(
      `[api:auth:verify-email] update failed user=${consumed.userId}:`,
      redactPhi(err instanceof Error ? err.message : err)
    );
    return redirectToLogin('error');
  }

  return redirectToLogin('ok');
});
