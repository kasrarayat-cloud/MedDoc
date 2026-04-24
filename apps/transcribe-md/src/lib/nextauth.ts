// ============================================================================
// NextAuth (Auth.js v5) — Full Node Runtime Configuration (apps/transcribe-md)
// ----------------------------------------------------------------------------
// Imports the edge-safe shared config from `./auth.config.ts` and layers on:
//   - A Credentials provider (email + bcrypt password)
//   - A 7-day session.maxAge override (vs. 8 hours on the shared config).
//     The longer TTL is fine for a solo-doctor consumer app; the clinical
//     apps (meddoc-pro, scribe) keep 8 hours for HIPAA reasons.
//   - Silent product-grant: an existing MedDoc Pro user logging in here
//     who doesn't yet have TRANSCRIBE_MD gets it appended to `products`
//     before the sign-in flow returns.
//
// Single-session enforcement + UserSession tracking is already wired up
// by the shared jwt() callback in @meddoc/auth — we inherit it by
// spreading authConfig below.
// ============================================================================

import NextAuth from 'next-auth';
import Credentials from 'next-auth/providers/credentials';
import bcrypt from 'bcryptjs';

import authConfig from '@/lib/auth.config';
import prisma from '@meddoc/db';
import type { UserRole } from '@meddoc/auth';
import { Product } from '@prisma/client';
import { redactPhi } from '@meddoc/ai';
import { isEmailDeliveryEnabled } from '@/lib/email-enabled';

/** 7 days. Longer than meddoc-pro (8hr) because TranscribeMD is a solo
 *  consumer surface, not a PHI-heavy clinical tool. */
const SESSION_MAX_AGE_SECONDS = 7 * 24 * 60 * 60;

/** T-M18.3 A18: pre-computed dummy bcrypt hash used to equalize the
 *  wall-clock time of paths that would otherwise short-circuit before
 *  running the real `bcrypt.compare` below. The specific plaintext
 *  doesn't matter — bcrypt.compare against this hash returns false for
 *  every realistic input. Computed once at module load (~100 ms). */
const DUMMY_PASSWORD_HASH = bcrypt.hashSync(
  'timing-equalizer-never-matches',
  12
);

export const { handlers, auth, signIn, signOut } = NextAuth({
  ...authConfig,

  session: {
    strategy: 'jwt',
    maxAge: SESSION_MAX_AGE_SECONDS,
    // Refresh the JWT on activity — when the user is active within this
    // window, their cookie is re-signed with a bumped expiry. 1 day picked
    // so active users don't suddenly get logged out on day 7.
    updateAge: 24 * 60 * 60,
  },

  providers: [
    Credentials({
      name: 'Email + Password',
      credentials: {
        email: { label: 'Email', type: 'email' },
        password: { label: 'Password', type: 'password' },
      },
      async authorize(credentials) {
        const email =
          typeof credentials?.email === 'string'
            ? credentials.email.trim().toLowerCase()
            : '';
        const password =
          typeof credentials?.password === 'string' ? credentials.password : '';
        if (!email || !password) return null;

        let user;
        try {
          user = await prisma.user.findUnique({ where: { email } });
        } catch (err) {
          // T-M18.3 A17: Prisma errors can echo column values.
          console.error(
            '[auth] user lookup failed:',
            redactPhi(err instanceof Error ? err.message : err)
          );
          return null;
        }
        if (!user) return null;
        if (!user.isActive) return null;
        if (user.lockedUntil && user.lockedUntil > new Date()) return null;

        // T-M16.2 defense-in-depth: the email-verification gate is
        // primarily enforced in loginAction (which can return a
        // dedicated "needsVerificationFor" state to surface the resend
        // affordance to the user). If someone bypasses the action and
        // hits NextAuth signIn directly, we still block here. No
        // counter increment — this isn't a failed credential, it's a
        // state gate.
        //
        // T-M18.3 A18: run a no-op bcrypt.compare before early-return
        // so this path takes the same wall-clock time as the verified
        // path (which hits the real bcrypt below). Prevents an attacker
        // from distinguishing "email exists + unverified" via response
        // timing.
        if (isEmailDeliveryEnabled() && user.emailVerified === null) {
          await bcrypt.compare(password, DUMMY_PASSWORD_HASH).catch(() => false);
          return null;
        }

        const valid = await bcrypt.compare(password, user.passwordHash);
        if (!valid) {
          // Mirror meddoc-pro's brute-force guard so a shared email can't
          // be attacked at the TranscribeMD surface to bypass the guard.
          const LOCKOUT_THRESHOLD = 5;
          const LOCKOUT_MINUTES = 15;
          const nextCount = user.failedLoginCount + 1;
          const shouldLock = nextCount >= LOCKOUT_THRESHOLD;
          const lockUntil = shouldLock
            ? new Date(Date.now() + LOCKOUT_MINUTES * 60 * 1000)
            : null;
          await prisma.user
            .update({
              where: { id: user.id },
              data: {
                failedLoginCount: { increment: 1 },
                ...(lockUntil ? { lockedUntil: lockUntil } : {}),
              },
            })
            .catch((err: unknown) => {
              console.error(
                '[auth] failed-login counter update failed:',
                redactPhi(err instanceof Error ? err.message : err)
              );
            });
          return null;
        }

        // F9-1: Entitlement gate. Pre-fix this branch silently granted
        // TRANSCRIBE_MD to any MEDDOC_PRO user who logged in here, which
        // was an entitlement bypass — any valid account could promote
        // itself. Now we require the product to already be on the user
        // before issuing a session. Granting must go through an admin
        // surface or billing webhook (not auto on first login).
        if (!user.products.includes(Product.TRANSCRIBE_MD)) {
          return null;
        }

        // Successful login — clear lockout + brute-force counters.
        await prisma.user
          .update({
            where: { id: user.id },
            data: {
              lastLogin: new Date(),
              failedLoginCount: 0,
              lockedUntil: null,
            },
          })
          .catch((err: unknown) => {
            console.error(
              '[auth] lastLogin update failed:',
              redactPhi(err instanceof Error ? err.message : err)
            );
          });

        return {
          id: user.id,
          email: user.email,
          name: user.name,
          role: user.role as UserRole,
          practiceId: user.practiceId,
        };
      },
    }),
  ],
});
