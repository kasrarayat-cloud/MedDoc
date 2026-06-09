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
import * as Sentry from '@sentry/nextjs';

import authConfig from '@/lib/auth.config';
import prisma from '@meddoc/db';
import { revokeSession, revokeAllUserSessions, type UserRole } from '@meddoc/auth';
import { Product } from '@prisma/client';
import { redactPhi } from '@meddoc/ai';
import { isEmailDeliveryEnabled } from '@/lib/email-enabled';
import { logAudit } from '@/lib/audit';

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
        // MFA — set when the user has mfaEnabled=true. Either a 6-digit
        // TOTP token OR a one-time recovery code is required (validated
        // below after the password check). loginAction handles the
        // two-step UX; authorize re-validates here as defense in depth
        // — even a direct signIn() call from somewhere else has to
        // include the second factor or it fails.
        totpToken: { label: 'TOTP', type: 'text' },
        recoveryCode: { label: 'Recovery', type: 'text' },
      },
      async authorize(credentials) {
        const email =
          typeof credentials?.email === 'string'
            ? credentials.email.trim().toLowerCase()
            : '';
        const password =
          typeof credentials?.password === 'string' ? credentials.password : '';
        if (!email || !password) return null;
        const totpToken =
          typeof credentials?.totpToken === 'string'
            ? credentials.totpToken
            : '';
        const recoveryCode =
          typeof credentials?.recoveryCode === 'string'
            ? credentials.recoveryCode
            : '';

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
        // Phase 6Z (PHASE-6Z-08): reject suspended/soft-deleted users at the
        // login form rather than letting them complete authorize() and then
        // having validateSession reject their first authenticated request.
        // The fields exist on the User row already (no extra select needed —
        // findUnique above selects everything by default).
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        if ((user as any).suspendedAt) {
          void logAudit({
            action: 'LOGIN_FAILED',
            userId: user.id,
            userEmail: user.email,
            practiceId: user.practiceId,
            success: false,
            errorCode: 'ACCOUNT_SUSPENDED',
          });
          return null;
        }
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        if ((user as any).softDeletedAt) {
          void logAudit({
            action: 'LOGIN_FAILED',
            userId: user.id,
            userEmail: user.email,
            practiceId: user.practiceId,
            success: false,
            errorCode: 'ACCOUNT_SOFT_DELETED',
          });
          return null;
        }
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
          void logAudit({
            action: 'LOGIN_FAILED',
            userId: user.id,
            userEmail: user.email,
            practiceId: user.practiceId,
            success: false,
            errorCode: shouldLock ? 'ACCOUNT_LOCKED_NOW' : 'CREDENTIALS_MISMATCH',
            metadata: {
              failedLoginCount: nextCount,
              lockedUntil: lockUntil?.toISOString() ?? null,
            },
          });
          return null;
        }

        // F9-1: Entitlement gate. Pre-fix this branch silently granted
        // TRANSCRIBE_MD to any MEDDOC_PRO user who logged in here, which
        // was an entitlement bypass — any valid account could promote
        // itself. Now we require the product to already be on the user
        // before issuing a session. Granting must go through an admin
        // surface or billing webhook (not auto on first login).
        //
        // Phase 1A: SUPER_ADMIN bypasses the entitlement check —
        // platform admins need access to the scribe surface to
        // debug incidents for customer tickets. Symmetric with the
        // meddoc-pro side.
        const tmHasTranscribe = user.products.includes(Product.TRANSCRIBE_MD);
        const tmHasSuperAdmin = user.products.includes(Product.SUPER_ADMIN);
        if (!tmHasTranscribe && !tmHasSuperAdmin) {
          void logAudit({
            action: 'LOGIN_FAILED',
            userId: user.id,
            userEmail: user.email,
            practiceId: user.practiceId,
            success: false,
            errorCode: 'NO_TRANSCRIBE_MD_ENTITLEMENT',
          });
          return null;
        }

        // MFA gate (closes shadow-audit HIPAA_FINDING_001). When a user
        // has mfaEnabled=true, the password alone is not sufficient —
        // they must provide either a valid 6-digit TOTP token OR a
        // one-time recovery code. loginAction's MFA preflight is the
        // primary path users take; this block is defense-in-depth for
        // any direct signIn() that bypasses the action layer.
        if (user.mfaEnabled && user.mfaSecret) {
          // Lazy-import the MFA verifier so the edge bundle never pulls
          // it in (mfa.ts uses node:crypto + otplib).
          const {
            verifyTotpToken,
            findMatchingRecoveryHash,
          } = await import('@/lib/mfa');

          let mfaPassed = false;
          let usedRecovery = false;
          if (totpToken) {
            mfaPassed = verifyTotpToken(user.mfaSecret, totpToken);
          } else if (recoveryCode) {
            const matched = findMatchingRecoveryHash(
              recoveryCode,
              user.mfaBackupCodes,
            );
            if (matched) {
              mfaPassed = true;
              usedRecovery = true;
              // Drop the consumed recovery code from the array. Best
              // effort — if this update fails we still let the login
              // proceed (the alternative is locking the user out
              // because we couldn't update the audit trail).
              await prisma.user
                .update({
                  where: { id: user.id },
                  data: {
                    mfaBackupCodes: {
                      set: user.mfaBackupCodes.filter(
                        (h: string) => h !== matched,
                      ),
                    },
                  },
                })
                .catch((err: unknown) => {
                  console.error(
                    '[auth] recovery-code consumption failed:',
                    redactPhi(err instanceof Error ? err.message : err),
                  );
                });
            }
          }

          if (!mfaPassed) {
            void logAudit({
              action: 'MFA_CHALLENGE_FAILED',
              userId: user.id,
              userEmail: user.email,
              practiceId: user.practiceId,
              success: false,
              errorCode: totpToken
                ? 'INVALID_TOTP'
                : recoveryCode
                  ? 'INVALID_RECOVERY_CODE'
                  : 'TOTP_REQUIRED',
              metadata: { stage: 'login' },
            });
            return null;
          }

          void logAudit({
            action: 'MFA_CHALLENGE_PASSED',
            userId: user.id,
            userEmail: user.email,
            practiceId: user.practiceId,
            success: true,
            metadata: { method: usedRecovery ? 'recovery_code' : 'totp' },
          });
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

  events: {
    async signIn({ user }) {
      if (!user?.id) return;
      // user.practiceId comes from authorize()'s returned shape. We
      // pass it through explicitly because auth() inside logAudit
      // returns null here — the session cookie isn't on the outgoing
      // response yet. Same pattern as apps/meddoc-pro/src/lib/nextauth.ts.
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const practiceId = (user as any).practiceId as string | undefined;
      void logAudit({
        action: 'LOGIN_SUCCESS',
        userId: user.id,
        userEmail: user.email ?? null,
        practiceId: practiceId ?? null,
      });
      // Round 3 PR-H — A11-P1 Sentry user context.
      // PHI guard: pass IDs only — never email, name, MRN, DOB. Sentry
      // is BAA-pending (compliance register) and the redactPhi
      // beforeSend hook will scrub strings, but the right defense is
      // never sending PHI in the first place. user.id is a UUID; it
      // can be cross-referenced server-side via /api/admin if ops
      // needs to map an event back to a user.
      Sentry.setUser({ id: user.id });
      if (practiceId) Sentry.setTag('practiceId', practiceId);
    },
    async signOut(message) {
      // next-auth v5's signOut event fires with a discriminated union.
      // Pull userId when it's available; tolerate the other shapes.
      const token =
        'token' in message ? message.token : null;
      const userId =
        token && typeof token === 'object' && 'sub' in token
          ? ((token as { sub?: string }).sub ?? null)
          : null;
      // Revoke the server-side UserSession row on sign-out. Without this only
      // the cookie is cleared and the row survives — so a JWT that lingers
      // in-flight (e.g. the post-sign-out /login redirect load racing the
      // cookie-clear) re-validates the session and re-mints the cookie,
      // intermittently leaving the user signed in. Revoke by the token's
      // sessionId claim, with a userId fallback. Fires for EVERY sign-out path
      // (TopNav signOut(), the menu, the API route).
      const sessionId =
        token && typeof token === 'object' && 'sessionId' in token
          ? ((token as { sessionId?: string }).sessionId ?? null)
          : null;
      try {
        if (sessionId) await revokeSession(sessionId);
        else if (userId) await revokeAllUserSessions(userId);
      } catch (err) {
        console.error(
          '[auth:signOut] session revoke failed',
          redactPhi(err instanceof Error ? err.message : String(err)),
        );
      }
      if (userId) {
        void logAudit({ action: 'LOGOUT', userId });
      }
      // Round 3 PR-H — clear Sentry user scope on signout so a
      // subsequent error from this process doesn't carry the
      // departed user's id.
      Sentry.setUser(null);
    },
  },
});
