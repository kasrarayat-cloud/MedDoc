// ============================================================================
// POST /api/auth/reset-password (T-M16.2)
// ----------------------------------------------------------------------------
// Body: { token: string, password: string, confirmPassword: string }
//
// Validates the token, updates the password, revokes every UserSession
// for the account so any logged-in device logs out immediately.
// Returns 200 on success, 400 on invalid token / weak password /
// mismatch. No rate limiting here because attackers need a valid
// 32-byte token to proceed — guessing is infeasible without the email
// link. The preceding /forgot-password route IS rate-limited.
// ============================================================================

import { z } from 'zod';
import { NextResponse } from 'next/server';
import bcrypt from 'bcryptjs';

import prisma from '@meddoc/db';
import { AuthTokenPurpose } from '@prisma/client';

import { apiError, withApiHandler } from '@/lib/api-error';
import { consumeAuthToken } from '@/lib/auth-tokens';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

// Mirror signupAction's policy — same regex, same minimum length, so
// a user coming via password-reset gets the same strength guarantee
// as a fresh signup.
const PasswordSchema = z
  .string()
  .min(10, 'Password must be at least 10 characters')
  .regex(/[a-z]/, 'Password must contain a lowercase letter')
  .regex(/[A-Z]/, 'Password must contain an uppercase letter')
  .regex(/\d/, 'Password must contain a digit');

const BodySchema = z
  .object({
    token: z.string().min(20).max(200),
    password: PasswordSchema,
    confirmPassword: z.string(),
  })
  .refine((d) => d.password === d.confirmPassword, {
    message: 'Passwords do not match',
    path: ['confirmPassword'],
  });

export const POST = withApiHandler('api:auth:reset-password', async (req) => {
  let body: unknown;
  try {
    body = await req.json();
  } catch {
    return apiError('invalid JSON body', 400);
  }
  const parsed = BodySchema.safeParse(body);
  if (!parsed.success) {
    // Collapse Zod's detailed message to a single field-shaped error.
    const first = parsed.error.issues[0];
    const field = first?.path.join('.') || '_form';
    return NextResponse.json(
      { error: first?.message || 'invalid payload', field },
      { status: 400 }
    );
  }

  const consumed = await consumeAuthToken({
    token: parsed.data.token,
    purpose: AuthTokenPurpose.PASSWORD_RESET,
  });
  if (!consumed) {
    // Generic message — don't distinguish expired vs already-used vs
    // not-found so an attacker fishing for reset tokens gets the same
    // answer regardless.
    return apiError(
      'This reset link is invalid or has expired. Request a new one.',
      400
    );
  }

  const passwordHash = await bcrypt.hash(parsed.data.password, 12);

  // Update password + clear lockout counters + revoke every active
  // session in one transaction. "Every session" rather than "all but
  // the current one" because the user just proved ownership via the
  // token; kicking them off whatever stale session might exist (on a
  // lost/stolen device) is the whole point of the reset.
  await prisma.$transaction([
    prisma.user.update({
      where: { id: consumed.userId },
      data: {
        passwordHash,
        failedLoginCount: 0,
        lockedUntil: null,
      },
    }),
    prisma.userSession.deleteMany({
      where: { userId: consumed.userId },
    }),
  ]);

  console.info(
    `[auth:reset-password] password reset + sessions revoked user=${consumed.userId}`
  );

  return NextResponse.json({ ok: true }, { status: 200 });
});
