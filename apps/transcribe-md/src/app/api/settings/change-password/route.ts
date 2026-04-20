// ============================================================================
// POST /api/settings/change-password (T-M16.2)
// ----------------------------------------------------------------------------
// Body: { currentPassword, newPassword, confirmPassword }
//
// Validates the current password, applies the same policy as signup on
// the new one, and revokes every OTHER UserSession (keeping the
// current session live so the user isn't booted out of the tab they
// just used to change their own password).
// ============================================================================

import { z } from 'zod';
import { NextResponse } from 'next/server';
import bcrypt from 'bcryptjs';

import prisma from '@meddoc/db';
import { apiError, withApiHandler } from '@/lib/api-error';
import { auth } from '@/lib/nextauth';
import { RATE_LIMITS, rateLimitOr429 } from '@/lib/rate-limit';
import { redactPhi } from '@meddoc/ai';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

const PasswordSchema = z
  .string()
  .min(10, 'Password must be at least 10 characters')
  .regex(/[a-z]/, 'Password must contain a lowercase letter')
  .regex(/[A-Z]/, 'Password must contain an uppercase letter')
  .regex(/\d/, 'Password must contain a digit');

const BodySchema = z
  .object({
    currentPassword: z.string().min(1, 'Enter your current password'),
    newPassword: PasswordSchema,
    confirmPassword: z.string(),
  })
  .refine((d) => d.newPassword === d.confirmPassword, {
    message: 'Passwords do not match',
    path: ['confirmPassword'],
  })
  .refine((d) => d.newPassword !== d.currentPassword, {
    message: 'New password must be different from current',
    path: ['newPassword'],
  });

export const POST = withApiHandler(
  'api:settings:change-password',
  async (req) => {
    const session = await auth();
    const userId = session?.user?.id;
    const currentSessionToken = session?.user?.sessionId;
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

    const user = await prisma.user.findUnique({
      where: { id: userId },
      select: { id: true, passwordHash: true },
    });
    if (!user) return apiError('user not found', 404);

    const ok = await bcrypt.compare(
      parsed.data.currentPassword,
      user.passwordHash
    );
    if (!ok) {
      return NextResponse.json(
        { error: 'Current password is incorrect.', field: 'currentPassword' },
        { status: 400 }
      );
    }

    const newHash = await bcrypt.hash(parsed.data.newPassword, 12);

    try {
      // Update password + revoke every session except the current one.
      // If the current sessionToken is unavailable (legacy JWT from
      // before T-M2 single-session tracking), revoke everything —
      // forcing one re-login is safer than ambiguity.
      await prisma.$transaction(async (tx: typeof prisma) => {
        await tx.user.update({
          where: { id: userId },
          data: {
            passwordHash: newHash,
            failedLoginCount: 0,
            lockedUntil: null,
          },
        });
        if (currentSessionToken) {
          await tx.userSession.deleteMany({
            where: {
              userId,
              NOT: { sessionToken: currentSessionToken },
            },
          });
        } else {
          await tx.userSession.deleteMany({ where: { userId } });
        }
      });
    } catch (err) {
      console.error(
        `[api:settings:change-password] update failed user=${userId}:`,
        redactPhi(err instanceof Error ? err.message : err)
      );
      return apiError('Could not update your password. Try again.', 500);
    }

    console.info(
      `[api:settings:change-password] password updated user=${userId} kept-session=${currentSessionToken ? 'yes' : 'no'}`
    );
    return NextResponse.json({ ok: true }, { status: 200 });
  }
);
