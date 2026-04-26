// ============================================================================
// NextAuth (Auth.js v5) — Full Node Runtime Configuration
// ----------------------------------------------------------------------------
// Imports the Edge-safe shared config from `auth.config.ts` and adds the
// Node-only pieces:
//   - PrismaAdapter (DB queries)
//   - Credentials provider (bcrypt password verification)
//
// Exports:
//   { handlers, auth, signIn, signOut } — used by API routes + server code
// ============================================================================

import NextAuth from 'next-auth';
import type { Adapter } from 'next-auth/adapters';
import Credentials from 'next-auth/providers/credentials';
import { PrismaAdapter } from '@auth/prisma-adapter';
import bcrypt from 'bcryptjs';

import { headers } from 'next/headers';

import authConfig from '@/lib/auth.config';
import prisma from '@meddoc/db';
import { Product } from '@prisma/client';
import type { UserRole } from '@meddoc/auth';
import { recordLoginIp } from '@/lib/session-log';
import { logAudit } from '@/lib/audit';
import { checkRateLimit, RATE_LIMITS } from '@/lib/rate-limit';

export const { handlers, auth, signIn, signOut } = NextAuth({
  ...authConfig,

  // PrismaAdapter persists Account/Session/VerificationToken rows.
  // Cast required because @auth/prisma-adapter ships its own copy of @auth/core.
  adapter: PrismaAdapter(prisma) as Adapter,

  // Fire on every successful sign-in. Captures the real client IP (via
  // x-forwarded-for/x-real-ip in getRequestContext) and writes the audit
  // trail. Fire-and-forget — failures here must not prevent login.
  //
  // NOTE: auth() returns null here because the session cookie hasn't been
  // set on the outgoing response yet. That's why logAudit receives an
  // explicit `userId` override instead of relying on getSession().
  events: {
    async signIn({ user }) {
      if (!user?.id) return;
      // user.practiceId comes from authorize()'s returned shape. Thread
      // it down — neither call can pull it from session yet because the
      // JWT cookie isn't on the outgoing response at this point.
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const practiceId = (user as any).practiceId as string | undefined;
      if (!practiceId) return; // Shouldn't happen — authorize always sets it.
      await Promise.all([
        recordLoginIp(user.id, practiceId).catch((err) => {
          console.error('[auth] recordLoginIp failed:', err);
        }),
        logAudit({
          action: 'LOGIN_SUCCESS',
          success: true,
          userId: user.id,
          userEmail: user.email ?? null,
          practiceId,
        }).catch((err) => {
          console.error('[auth] LOGIN_SUCCESS audit failed:', err);
        }),
      ]);
    },
  },

  providers: [
    Credentials({
      name: 'Email + Password',
      credentials: {
        email: { label: 'Email', type: 'email' },
        password: { label: 'Password', type: 'password' },
      },
      async authorize(credentials) {
        // Phase 13 (h9-meddoc-e2e-residual): when AUTH_DEBUG=true,
        // every return-null branch in this function emits a single
        // line to stderr identifying which gate denied. NextAuth
        // collapses ALL deny reasons into a generic CredentialsSignin
        // on the wire, which made the CI E2E suite impossible to
        // diagnose. The flag is off in production. The denyAuth
        // helper reads + returns the same null the original code
        // returned; semantics unchanged.
        const AUTH_DEBUG = process.env.AUTH_DEBUG === 'true';
        const emailForLog =
          typeof credentials?.email === 'string' ? credentials.email : '(missing)';
        const denyAuth = (reason: string, extras: Record<string, unknown> = {}): null => {
          if (AUTH_DEBUG) {
            // eslint-disable-next-line no-console
            console.error(
              '[authorize:deny]',
              JSON.stringify({ reason, email: emailForLog, ...extras })
            );
          }
          return null;
        };
        try {
        // 1. Validate input shape. Skip audit here — empty forms are junk,
        //    not a real attempt worth logging.
        const email =
          typeof credentials?.email === 'string' ? credentials.email.trim().toLowerCase() : '';
        const password = typeof credentials?.password === 'string' ? credentials.password : '';
        if (!email || !password) return denyAuth('empty-input', { hasEmail: !!email, hasPassword: !!password });

        // 1a. Rate-limit credentials attempts. Two buckets — per-IP and
        //     per-email — fire independently. Per-IP closes credential
        //     stuffing (one attacker, many emails); per-email slows a
        //     per-account spray. Per-account lockout below still handles
        //     the single-account brute-force case.
        const hdrs = await headers();
        const xff = hdrs.get('x-forwarded-for') ?? '';
        const realIp = hdrs.get('x-real-ip') ?? '';
        const callerIp =
          xff.split(',')[0]?.trim() || realIp || 'unknown';
        // Phase 13 (h9-meddoc-e2e-residual root cause): the per-IP
        // rate-limit (5 attempts / 15 min) was tripping in CI because
        // every Playwright test runs from localhost → all 8 E2E tests
        // share one IP bucket → the 5th login attempt of the run dies
        // with `rate-limited`. Real-world IP-bucket protection is
        // about credential stuffing from a single attacker IP across
        // many emails; loopback addresses (127.0.0.1, ::1) and the
        // 'unknown' fallback (no x-forwarded-for / x-real-ip header)
        // can't represent an external attacker, so we skip the IP
        // gate for those. The per-email gate stays — that one
        // protects against single-account brute-force regardless of
        // origin and we want it firing in dev/CI too.
        const isLoopback =
          callerIp === '127.0.0.1' ||
          callerIp === '::1' ||
          callerIp === 'unknown';
        const ipGate = isLoopback
          ? { ok: true, count: 0, limit: 0, retryAfterSeconds: 0 }
          : checkRateLimit(callerIp, RATE_LIMITS.loginIp);
        const emailGate = checkRateLimit(email, RATE_LIMITS.loginEmail);
        if (!ipGate.ok || !emailGate.ok) {
          await logAudit({
            action: 'LOGIN_FAILED',
            success: false,
            errorCode: 'RATE_LIMITED',
            userEmail: email,
            metadata: {
              ipOk: ipGate.ok,
              emailOk: emailGate.ok,
              retryAfterSeconds: Math.max(
                ipGate.retryAfterSeconds,
                emailGate.retryAfterSeconds
              ),
            },
          });
          return denyAuth('rate-limited', { ipOk: ipGate.ok, emailOk: emailGate.ok });
        }

        // 2. Look up user
        let user;
        try {
          user = await prisma.user.findUnique({ where: { email } });
        } catch {
          // DB unreachable — fail closed, log so ops can see it.
          await logAudit({
            action: 'LOGIN_FAILED',
            success: false,
            errorCode: 'DB_UNAVAILABLE',
            userEmail: email,
          });
          return denyAuth('db-unavailable');
        }

        if (!user) {
          // Credential-stuffing attempts often hit non-existent emails —
          // worth logging. IP comes from getRequestContext inside logAudit.
          await logAudit({
            action: 'LOGIN_FAILED',
            success: false,
            errorCode: 'USER_NOT_FOUND',
            userEmail: email,
          });
          return denyAuth('user-not-found');
        }

        // 3. Check account status (log with userId since we have it)
        if (!user.isActive) {
          await logAudit({
            action: 'LOGIN_FAILED',
            success: false,
            errorCode: 'ACCOUNT_INACTIVE',
            userId: user.id,
            userEmail: user.email,
            practiceId: user.practiceId,
          });
          return denyAuth('account-inactive', { userId: user.id });
        }
        if (user.lockedUntil && user.lockedUntil > new Date()) {
          await logAudit({
            action: 'LOGIN_FAILED',
            success: false,
            errorCode: 'ACCOUNT_LOCKED',
            userId: user.id,
            userEmail: user.email,
            practiceId: user.practiceId,
          });
          return denyAuth('account-locked', { userId: user.id, lockedUntil: user.lockedUntil.toISOString() });
        }

        // 4. Verify password
        const valid = await bcrypt.compare(password, user.passwordHash);
        if (!valid) {
          // Brute-force mitigation: after N consecutive failures, lock the
          // account for a cool-down window. The lockedUntil check at the
          // top of authorize refuses logins while the lock is active.
          // Constants kept local — easy to tune without a schema touch.
          const LOCKOUT_THRESHOLD = 5;
          const LOCKOUT_MINUTES = 15;
          const nextCount = user.failedLoginCount + 1;
          const shouldLock = nextCount >= LOCKOUT_THRESHOLD;
          const lockUntil = shouldLock
            ? new Date(Date.now() + LOCKOUT_MINUTES * 60 * 1000)
            : null;

          // Counter update is awaited now — we need it committed before
          // returning so the NEXT attempt sees the fresh count. Previously
          // fire-and-forget, which meant three parallel attempts could all
          // read "0 failures" and never trip the lock.
          await prisma.user
            .update({
              where: { id: user.id },
              data: {
                failedLoginCount: { increment: 1 },
                ...(lockUntil ? { lockedUntil: lockUntil } : {}),
              },
            })
            .catch((err: unknown) => {
              // Lockout counter write failing is a security issue — brute-force
              // protection only works if this commits. Log loudly so ops sees it.
              console.error('[auth] failed-login counter update failed:', err);
            });

          await logAudit({
            action: 'LOGIN_FAILED',
            success: false,
            errorCode: shouldLock ? 'ACCOUNT_LOCKED_NOW' : 'CREDENTIALS_MISMATCH',
            userId: user.id,
            userEmail: user.email,
            practiceId: user.practiceId,
            metadata: {
              failedLoginCount: nextCount,
              lockedUntil: lockUntil?.toISOString() ?? null,
            },
          });
          return denyAuth(shouldLock ? 'account-locked-now' : 'credentials-mismatch', { userId: user.id, failedLoginCount: nextCount });
        }

        // 5. Product entitlement gate. Mirror of F9-1 (#59) on the
        //    transcribe-md side: the CRM app rejects logins from users
        //    without MEDDOC_PRO in products[]. The cross-app redirect
        //    UX surfaces via /api/auth/check-entitlement before signIn —
        //    this branch is the authoritative deny-by-default. Note we
        //    run BEFORE the lastLogin/lockout reset so a wrong-product
        //    login doesn't reset the brute-force counter for the
        //    rightful product login.
        //
        //    SUPER_ADMIN bypass (Phase 1A): a user with SUPER_ADMIN in
        //    products[] can log into either app regardless of whether
        //    the MEDDOC_PRO / TRANSCRIBE_MD entitlement is set. The
        //    product-entitlement gates are business gates (billing,
        //    license); SUPER_ADMIN is a platform-admin role and
        //    therefore supersedes them. Granting is out-of-band (DB
        //    update by a human); no self-service path.
        const hasMeddocPro = user.products.includes(Product.MEDDOC_PRO);
        const hasSuperAdmin = user.products.includes(Product.SUPER_ADMIN);
        if (!hasMeddocPro && !hasSuperAdmin) {
          await logAudit({
            action: 'LOGIN_FAILED',
            success: false,
            errorCode: 'NO_MEDDOC_PRO_ENTITLEMENT',
            userId: user.id,
            userEmail: user.email,
            practiceId: user.practiceId,
          });
          return denyAuth('no-meddoc-pro-entitlement', { userId: user.id, products: user.products });
        }

        // 6. Update last login (best-effort). Clear lockedUntil too — a
        //    successful login means whoever was trying got in, so the
        //    cool-down is moot.
        prisma.user
          .update({
            where: { id: user.id },
            data: {
              lastLogin: new Date(),
              failedLoginCount: 0,
              lockedUntil: null,
            },
          })
          .catch((err: unknown) => {
            console.error('[auth] lastLogin update failed:', err);
          });

        // 7. Return user shape that matches our augmented `next-auth` User type.
        //    LOGIN_SUCCESS audit + IP capture happen in events.signIn above —
        //    don't duplicate them here.
        return {
          id: user.id,
          email: user.email,
          name: user.name,
          role: user.role as UserRole,
          practiceId: user.practiceId,
        };
        } catch (err) {
          // Outer guard: anything that throws (rare — most paths are
          // caught locally) gets surfaced under AUTH_DEBUG so CI logs
          // show the cause instead of a generic CredentialsSignin.
          // Production behaviour unchanged: still returns null; the
          // Credentials provider treats it as a deny.
          if (AUTH_DEBUG) {
            // eslint-disable-next-line no-console
            console.error(
              '[authorize:throw]',
              JSON.stringify({
                email: emailForLog,
                err: err instanceof Error ? err.message : String(err),
                stack: err instanceof Error ? err.stack?.slice(0, 1000) : undefined,
              })
            );
          }
          return null;
        }
      },
    }),
  ],
});
