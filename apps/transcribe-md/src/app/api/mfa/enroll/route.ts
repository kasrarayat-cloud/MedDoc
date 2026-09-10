// ============================================================================
// POST /api/mfa/enroll — start MFA enrollment
// ----------------------------------------------------------------------------
// Body: {} (no payload — the user is identified by their session)
// Response: { ok: true, otpauthUri, qrPngDataUrl }
// Refusal:  409 { code: 'MFA_ALREADY_ENABLED' } when the account is enrolled
//
// Generates a fresh TOTP secret and returns the otpauth URI + QR image so the
// user can scan it with their authenticator app. The secret is staged in
// `users.mfaSecret` ONLY while `users.mfaEnabled` is false, and this route
// never sets mfaEnabled. Enrollment is "complete" once the user submits a
// valid 6-digit code via /api/mfa/verify-enrollment, which flips mfaEnabled to
// true and generates the recovery codes.
//
// ⚠️ AN ENROLLED ACCOUNT IS REFUSED. This header used to say "re-enrolling an
// already-enrolled user is allowed … the user must complete verification
// again". Nothing enforced the second half. The route overwrote mfaSecret,
// left mfaEnabled=true, and asked for nothing but a session cookie. Login then
// checked TOTP against the CALLER's new secret, and both admin gates, which
// admit on mfaEnabled, kept admitting. A password plus any live cookie
// replaced the owner's factor (PR #952 refutation round, bypass[1]).
// Replacing a factor now goes through /api/mfa/disable, which requires the
// password AND the current factor, and then back through here.
//
// ⚠️ FIRST-TIME ENROLMENT IS STILL TRUST-ON-FIRST-USE: an un-enrolled
// account's session is all this route asks for. That is the admin page gate's
// intended recovery path, and a recorded residual:
// docs/foundation/board/SUPER-ADMIN-MFA-TOFU.md.
// ============================================================================

import { NextResponse } from 'next/server';

import prisma from '@meddoc/db';
import { auth } from '@/lib/nextauth';
import { apiError, withApiHandler } from '@/lib/api-error';
import { generateMfaEnrollment } from '@/lib/mfa';
import { logAudit } from '@/lib/audit';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

export const POST = withApiHandler(
  'api:mfa:enroll',
  async () => {
    const session = await auth();
    const userId = session?.user?.id;
    if (!userId) return apiError('unauthorized', 401);

    const user = await prisma.user.findUnique({
      where: { id: userId },
      select: { id: true, email: true, practiceId: true },
    });
    if (!user) return apiError('not found', 404);

    const enrollment = await generateMfaEnrollment(user.email);

    // ⚠️ ONE ATOMIC GUARD, IN THE WRITE ITSELF. The secret is staged only if
    // the row is STILL un-enrolled at the moment of writing. A read-then-write
    // check would lose a race: verify-enrollment could commit mfaEnabled=true
    // between the read and this write, and the write would then replace a
    // factor that had just been verified. On a refusal nothing is written, so
    // the owner's secret, mfaVerifiedAt and recovery codes are untouched, and
    // the freshly generated secret is discarded without being returned.
    const staged = await prisma.user.updateMany({
      where: { id: userId, mfaEnabled: false },
      data: {
        mfaSecret: enrollment.secret,
        // Clears a stale stamp left by an abandoned earlier attempt.
        mfaVerifiedAt: null,
      },
    });
    if (staged.count !== 1) {
      void logAudit({
        action: 'MFA_ENABLED',
        userId: user.id,
        userEmail: user.email,
        practiceId: user.practiceId,
        success: false,
        errorCode: 'MFA_ALREADY_ENABLED',
        metadata: { stage: 'enrollment_refused' },
      });
      return apiError(
        'Two-factor authentication is already on. To use a new authenticator, turn it off first (password and current code), then enrol again.',
        409,
        { code: 'MFA_ALREADY_ENABLED' },
      );
    }

    void logAudit({
      action: 'MFA_ENABLED',
      userId: user.id,
      userEmail: user.email,
      practiceId: user.practiceId,
      success: true,
      metadata: { stage: 'enrollment_started' },
    });

    return NextResponse.json(
      {
        ok: true,
        otpauthUri: enrollment.otpauthUri,
        qrPngDataUrl: enrollment.qrPngDataUrl,
      },
      { status: 200 },
    );
  },
);
