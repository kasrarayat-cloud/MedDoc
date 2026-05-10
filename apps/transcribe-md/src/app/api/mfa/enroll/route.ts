// ============================================================================
// POST /api/mfa/enroll — start MFA enrollment
// ----------------------------------------------------------------------------
// Body: {} (no payload — the user is identified by their session)
// Response: { ok: true, otpauthUri, qrPngDataUrl }
//
// Generates a fresh TOTP secret, returns the otpauth URI + QR image so
// the user can scan it with their authenticator app. The secret is
// staged in `users.mfaSecret` but `users.mfaEnabled` stays false —
// enrollment is only "complete" once the user submits a valid 6-digit
// code via /api/mfa/verify-enrollment, which flips mfaEnabled to true
// and generates the recovery codes.
//
// Re-enrolling an already-enrolled user is allowed; the new secret
// supersedes the old one and the user must complete verification
// again. (Equivalent to "rotate my MFA secret" UX.) Recovery codes
// are NOT regenerated here — that happens at verify-enrollment.
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

    // Stage the secret. mfaEnabled stays false — only verify-enrollment
    // flips it. If the user abandons enrollment (closes the tab), the
    // staged secret stays in mfaSecret but mfaEnabled remains false; a
    // future re-enrollment overwrites the stale secret cleanly.
    await prisma.user.update({
      where: { id: userId },
      data: {
        mfaSecret: enrollment.secret,
        // Defensive: ensure these are reset in case of re-enrollment
        // mid-stream. mfaEnabled stays false until verify-enrollment.
        mfaVerifiedAt: null,
      },
    });

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
