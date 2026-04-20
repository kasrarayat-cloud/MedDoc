// ============================================================================
// GET /api/auth/confirm-email?token=... (T-M16.2)
// ----------------------------------------------------------------------------
// Consumer for the EMAIL_CHANGE flow started in
// /api/settings/change-email. Clicking the link in the confirmation
// email lands here.
//
// Steps:
//   1. Consume the EMAIL_CHANGE token.
//   2. Check the target email isn't now taken by someone else (race
//      guard: someone could have signed up with that address in the
//      24-hour window between request and confirm).
//   3. UPDATE users.email = metadata.newEmail.
//   4. Fire-and-forget a heads-up email to the OLD address.
//   5. Redirect back to /settings with a `?emailChanged=1` flag the
//      page can show as a toast.
//
// GET instead of POST because the browser is following a link from
// an email — POST-via-link needs JS. The token itself is single-use
// and high-entropy, so read-only-GET-side-effects is OK here.
// ============================================================================

import { NextResponse } from 'next/server';

import prisma from '@meddoc/db';
import { AuthTokenPurpose } from '@prisma/client';

import { apiError, withApiHandler } from '@/lib/api-error';
import { consumeAuthToken } from '@/lib/auth-tokens';
import { sendEmailChangedNotification } from '@/lib/email';
import { APP_URL } from '@/lib/constants';
import { redactPhi } from '@meddoc/ai';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

function redirectToSettings(reason: string): NextResponse {
  return NextResponse.redirect(
    `${APP_URL}/settings?emailChange=${encodeURIComponent(reason)}`,
    { status: 303 }
  );
}

export const GET = withApiHandler('api:auth:confirm-email', async (req) => {
  const url = new URL(req.url);
  const token = url.searchParams.get('token');
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

    console.info(
      `[api:auth:confirm-email] email updated user=${consumed.userId}`
    );

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
