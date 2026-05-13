// ============================================================================
// POST /api/mfa/verify-enrollment — complete MFA enrollment
// ----------------------------------------------------------------------------
// Body: { token: string }   // 6-digit TOTP code
// Response (success):
//   { ok: true, recoveryCodes: string[] }   // 10 plaintext codes — shown ONCE
// Response (failure): apiError 400 with code IN_VALID_TOKEN
//
// Validates the user-supplied 6-digit code against the staged
// `mfaSecret`. On success:
//   - Flips `mfaEnabled = true`
//   - Sets `mfaVerifiedAt = NOW()`
//   - Generates 10 fresh recovery codes; stores their SHA-256 hashes
//     in `mfaBackupCodes`
//   - Returns the plaintext codes to the user ONCE (the only time the
//     server will ever expose them — they cannot be re-shown later)
//   - Emits MFA_ENABLED audit row
// ============================================================================

import { NextResponse } from 'next/server';
import { z } from 'zod';

import prisma from '@meddoc/db';
import { auth } from '@/lib/nextauth';
import { apiError, withApiHandler } from '@/lib/api-error';
import {
  verifyTotpToken,
  generateRecoveryCodes,
  hashRecoveryCodes,
} from '@/lib/mfa';
import { logAudit } from '@/lib/audit';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

const BodySchema = z.object({
  token: z.string().min(6).max(8), // strip-whitespace happens in verifyTotpToken
});

export const POST = withApiHandler(
  'api:mfa:verify-enrollment',
  async (req) => {
    const session = await auth();
    const userId = session?.user?.id;
    if (!userId) return apiError('unauthorized', 401);

    let body: unknown;
    try {
      body = await req.json();
    } catch {
      return apiError('invalid JSON body', 400);
    }
    const parsed = BodySchema.safeParse(body);
    if (!parsed.success) return apiError('invalid token payload', 400);

    const user = await prisma.user.findUnique({
      where: { id: userId },
      select: {
        id: true,
        email: true,
        practiceId: true,
        mfaSecret: true,
        mfaEnabled: true,
      },
    });
    if (!user) return apiError('not found', 404);

    if (!user.mfaSecret) {
      // No staged secret — caller must hit /api/mfa/enroll first.
      return apiError(
        'No staged MFA secret. Start enrollment first.',
        400,
        { code: 'NO_STAGED_SECRET' },
      );
    }

    if (!verifyTotpToken(user.mfaSecret, parsed.data.token)) {
      void logAudit({
        action: 'MFA_CHALLENGE_FAILED',
        userId: user.id,
        userEmail: user.email,
        practiceId: user.practiceId,
        success: false,
        errorCode: 'INVALID_TOKEN',
        metadata: { stage: 'enrollment_verification' },
      });
      return apiError('Invalid 6-digit code. Try again.', 400, {
        code: 'INVALID_TOKEN',
      });
    }

    // Generate + hash recovery codes BEFORE writing to DB so we have
    // the plaintext to return.
    const plaintextCodes = generateRecoveryCodes(10);
    const hashedCodes = hashRecoveryCodes(plaintextCodes);

    // Security audit P1-J — flipping mfaEnabled=true while sibling
    // sessions stay live means "MFA-enabled" no longer implies "this
    // session went through an MFA challenge". Revoke every OTHER
    // UserSession on enrollment so any pre-MFA tab/device must
    // re-authenticate AND complete the new MFA challenge. Keep the
    // current session (the user just finished a TOTP challenge in
    // this tab — kicking them off the page that confirmed enrollment
    // is poor UX). Legacy tokens have no sessionId — fall back to
    // revoking ALL sessions, which is correct-but-strict.
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const currentSessionId = (session?.user as any)?.sessionId as
      | string
      | undefined;

    await prisma.$transaction([
      prisma.user.update({
        where: { id: userId },
        data: {
          mfaEnabled: true,
          mfaVerifiedAt: new Date(),
          mfaBackupCodes: hashedCodes,
        },
      }),
      prisma.userSession.deleteMany({
        where: currentSessionId
          ? { userId, NOT: { sessionToken: currentSessionId } }
          : { userId },
      }),
    ]);

    void logAudit({
      action: 'MFA_ENABLED',
      userId: user.id,
      userEmail: user.email,
      practiceId: user.practiceId,
      success: true,
      metadata: {
        stage: 'enrollment_completed',
        recoveryCodesIssued: 10,
        keptCurrentSession: !!currentSessionId,
      },
    });

    return NextResponse.json(
      { ok: true, recoveryCodes: plaintextCodes },
      { status: 200 },
    );
  },
);
