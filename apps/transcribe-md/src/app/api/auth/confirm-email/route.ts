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
import { sendEmailChangedNotification } from '@/lib/email';
import { APP_URL } from '@/lib/constants';
import { redactPhi } from '@meddoc/ai';
import { log } from '@/lib/log';
import { logAudit } from '@/lib/audit';
import { emailLinkInterstitialHtml } from '@/lib/email-link-interstitial';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

function redirectToSettings(reason: string): NextResponse {
  // See verify-email's matching helper — strip Referer so the spent
  // token doesn't land in /settings access logs.
  return NextResponse.redirect(
    `${APP_URL}/settings?emailChange=${encodeURIComponent(reason)}`,
    { status: 303, headers: { 'Referrer-Policy': 'no-referrer' } }
  );
}

export const GET = withApiHandler('api:auth:confirm-email', async (req) => {
  // GET is read-only — see verify-email's matching handler.
  const url = new URL(req.url);
  const token = url.searchParams.get('token');
  if (!token) return apiError('missing token', 400);

  const html = emailLinkInterstitialHtml({
    actionPath: '/api/auth/confirm-email',
    token,
    headline: 'Confirming your email change…',
    detail:
      "Hold on — we're finishing the email change. This will only take a moment.",
  });
  return new NextResponse(html, {
    status: 200,
    headers: {
      'Content-Type': 'text/html; charset=utf-8',
      'Referrer-Policy': 'same-origin',
      'X-Robots-Tag': 'noindex, nofollow',
    },
  });
});

export const POST = withApiHandler('api:auth:confirm-email', async (req) => {
  const blocked = rateLimitOr429(
    RATE_LIMITS.AUTH_EMAIL,
    clientIpFromRequest(req)
  );
  if (blocked) return blocked;

  // Accept either a JSON body or the interstitial's HTML form post.
  let token: string | null = null;
  const contentType = req.headers.get('content-type') ?? '';
  if (contentType.includes('application/json')) {
    try {
      const body = (await req.json()) as { token?: unknown };
      if (typeof body.token === 'string') token = body.token;
    } catch {
      return apiError('invalid JSON body', 400);
    }
  } else {
    const form = await req.formData().catch(() => null);
    const raw = form?.get('token');
    if (typeof raw === 'string') token = raw;
  }
  if (!token) return apiError('missing token', 400);

  const consumed = await consumeAuthToken({
    token,
    purpose: AuthTokenPurpose.EMAIL_CHANGE,
  });
  if (!consumed) {
    return redirectToSettings('invalid-or-expired');
  }

  const meta = consumed.metadata as
    | { newEmail?: string; oldEmail?: string }
    | null;
  const newEmail = typeof meta?.newEmail === 'string' ? meta.newEmail : null;
  const oldEmail = typeof meta?.oldEmail === 'string' ? meta.oldEmail : null;
  if (!newEmail) {
    console.warn(
      `[api:auth:confirm-email] token consumed but metadata.newEmail missing user=${consumed.userId}`
    );
    return redirectToSettings('invalid-or-expired');
  }

  // Race guard: someone may have signed up with this email in the 24-hour
  // window since the change was requested. Early return (no update) and
  // let the user try again with a different address.
  const conflict = await prisma.user.findUnique({
    where: { email: newEmail },
    select: { id: true },
  });
  if (conflict && conflict.id !== consumed.userId) {
    console.warn(
      `[api:auth:confirm-email] target email now taken user=${consumed.userId}`
    );
    return redirectToSettings('conflict');
  }

  try {
    const updated = await prisma.user.update({
      where: { id: consumed.userId },
      data: {
        email: newEmail,
        // If email-verification gate is enforced, the new email is
        // already "verified" by virtue of having received and clicked
        // this link — stamp it so the login gate doesn't re-require it.
        emailVerified: new Date(),
      },
      select: { name: true },
    });

    log.info('api:auth:confirm-email', 'email updated', {
      userId: consumed.userId,
    });
    // The confirm endpoint runs from the NEW email's click — there's
    // typically no active session yet, so override the userId/email
    // explicitly from the consumed token.
    void logAudit({
      action: 'EMAIL_CHANGE_CONFIRMED',
      targetType: 'User',
      targetId: consumed.userId,
      userId: consumed.userId,
      userEmail: newEmail,
      metadata: {
        newEmailDomain: newEmail.split('@')[1] ?? 'unknown',
        oldEmailDomain: oldEmail?.split('@')[1] ?? 'unknown',
      },
    });

    // Fire-and-forget notification to the old address. Never fail the
    // redirect on email hiccup.
    if (oldEmail && process.env.RESEND_API_KEY) {
      void sendEmailChangedNotification({
        toEmail: oldEmail,
        newEmail,
        userName: updated.name,
      }).catch((err) => {
        console.error(
          `[api:auth:confirm-email] old-email notification failed user=${consumed.userId}:`,
          redactPhi(err instanceof Error ? err.message : err)
        );
      });
    }
  } catch (err) {
    console.error(
      `[api:auth:confirm-email] update failed user=${consumed.userId}:`,
      redactPhi(err instanceof Error ? err.message : err)
    );
    return redirectToSettings('error');
  }

  return redirectToSettings('ok');
});
