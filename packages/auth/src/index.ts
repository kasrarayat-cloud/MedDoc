// T-M2: single-session tracking helpers. Node-only; don't import these
// from edge middleware — the shared authConfig below uses dynamic
// import() so the edge bundle never pulls them in.
export {
  recordSessionLogin,
  validateSession,
  revokeSession,
  revokeAllUserSessions,
  getUserSessions,
  randomSessionToken,
  computeDeviceFingerprint,
} from './user-session';
export type { RecordSessionLoginInput } from './user-session';

// ============================================================================
// @meddoc/auth — shared auth surface for apps/meddoc-pro and apps/scribe
// ----------------------------------------------------------------------------
// Minimal lift per M1 plan §D5(a): types + edge-safe NextAuth config +
// tenant helpers. The full NextAuth instance (Credentials provider, signIn
// events that write audit rows) stays inside apps/meddoc-pro because it's
// tightly coupled to that app's audit + session-log modules. apps/scribe
// reuses this config to read the same JWT sessions without a sign-in flow.
// ============================================================================

import type { NextAuthConfig } from 'next-auth';
// Bring the jwt submodule into this compilation unit so the
// `declare module 'next-auth/jwt'` augmentation at the bottom of this file
// can resolve it. Without this, tsc (NodeNext/bundler resolution) reports
// TS2664 on the augmentation in downstream apps.
import type {} from 'next-auth/jwt';
import prisma from '@meddoc/db';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type UserRole = 'DOCTOR' | 'ADMIN' | 'STAFF' | 'SUPER_ADMIN';

export interface Session {
  user: {
    id: string;
    email: string;
    /** Display name (mapped from NextAuth's `name` field) */
    fullName: string;
    role: UserRole;
    /** Multi-tenancy: the practice this user belongs to. Used to scope
     *  every query/action to a single tenant. */
    practiceId: string;
  };
}

export class AuthError extends Error {
  code: 'UNAUTHENTICATED' | 'FORBIDDEN';

  constructor(code: 'UNAUTHENTICATED' | 'FORBIDDEN', message: string) {
    super(message);
    this.name = 'AuthError';
    this.code = code;
  }
}

// ---------------------------------------------------------------------------
// Shared edge-safe NextAuth config
// ----------------------------------------------------------------------------
// Imported by BOTH apps' middleware/proxy (edge runtime — no Node APIs
// allowed here) AND by each app's own `nextauth.ts` which spreads this
// config and adds its node-only providers/events on top.
//
// Rules (same as before M1):
//   ✗ no @meddoc/db / Prisma
//   ✗ no bcryptjs
//   ✗ no next/headers
//
// New in M1: `cookies.sessionToken.options.domain` is driven by
// AUTH_COOKIE_DOMAIN env var so both apps on different subdomains
// (meddoc-pro.domain + scribe.domain) share the same session cookie.
// Leave AUTH_COOKIE_DOMAIN unset to keep the current host-only behavior.
// ---------------------------------------------------------------------------

const cookieDomain = process.env.AUTH_COOKIE_DOMAIN?.trim();

export const authConfig: NextAuthConfig = {
  providers: [],

  pages: {
    signIn: '/login',
  },

  session: {
    strategy: 'jwt',
    maxAge: 60 * 60 * 8, // 8 hours — short for HIPAA
  },

  // T-M16.3: hard-fail in production if AUTH_SECRET is unset. The dev
  // fallback below stays for local development (NODE_ENV !== production)
  // so `npm run dev` without an env file still works. In prod a missing
  // value would silently sign every JWT with the hardcoded literal —
  // identical across deployments — which is a forgeable-session class
  // bug. Fail fast + loud instead.
  //
  // NEXT_PHASE guard: `next build` sets NODE_ENV=production but doesn't
  // need a real secret (no actual auth happens during prerender / page-
  // data collection, and the build-time env typically lacks .env). Skip
  // the throw during the build phase — we only want to fail at
  // container-start time, not at build time.
  secret:
    process.env.NODE_ENV === 'production' &&
    process.env.NEXT_PHASE !== 'phase-production-build' &&
    !process.env.AUTH_SECRET
      ? (() => {
          throw new Error(
            'AUTH_SECRET is required in production. Set it in /opt/meddoc-pro/.env (openssl rand -base64 32) and recreate the app containers.'
          );
        })()
      : process.env.AUTH_SECRET || 'dev_secret_change_in_production_min_32_chars_xyz',

  trustHost: true,

  // Security audit P1-H (2026-05-13): always emit the cookie
  // hardening flags. Previously this whole block was gated on
  // `cookieDomain` being set; with AUTH_COOKIE_DOMAIN unset (the
  // default), the app silently inherited NextAuth defaults. Auth.js
  // v5 ships sensible defaults in production, but the only thing
  // pinning httpOnly/sameSite/secure for THIS app was that
  // assumption. Emitting the block unconditionally pins the posture
  // explicitly. The `domain` option is the only field that varies
  // by env — it's added only when AUTH_COOKIE_DOMAIN is set so the
  // app retains host-only behaviour by default.
  cookies: {
    sessionToken: {
      name:
        process.env.NODE_ENV === 'production'
          ? '__Secure-authjs.session-token'
          : 'authjs.session-token',
      options: {
        httpOnly: true,
        sameSite: 'lax' as const,
        path: '/',
        secure: process.env.NODE_ENV === 'production',
        ...(cookieDomain ? { domain: cookieDomain } : {}),
      },
    },
  },

  callbacks: {
    /**
     * Runs on EVERY request that matches the middleware matcher.
     * Returning `true` allows the request through; returning `false`
     * triggers an automatic redirect to `pages.signIn`.
     */
    authorized({ auth, request: { nextUrl } }) {
      if (process.env.AUTH_USE_MOCK === 'true') return true;

      const isLoggedIn = !!auth?.user;
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const role = (auth?.user as any)?.role as string | undefined;
      const path = nextUrl.pathname;
      const isOnDashboard = path.startsWith('/dashboard');
      const isOnAdmin = path.startsWith('/system-admin');
      const isOnVisits = path.startsWith('/visits');

      // Require login for protected areas (meddoc-pro + scribe both).
      if ((isOnDashboard || isOnAdmin || isOnVisits) && !isLoggedIn) return false;

      if (isLoggedIn && role) {
        const isAdminRole = role === 'ADMIN' || role === 'SUPER_ADMIN';
        if (isOnAdmin && !isAdminRole) {
          return new Response(null, {
            status: 302,
            headers: {
              Location: new URL('/dashboard', nextUrl).toString(),
              'Cache-Control': 'no-store, no-cache, must-revalidate',
            },
          });
        }
      }

      return true;
    },

    async jwt({ token, user }) {
      // ── Sign-in path — `user` is the object returned by authorize() ──
      if (user) {
        token.id = user.id as string;
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        token.role = (user as any).role;
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        token.practiceId = (user as any).practiceId;

        // T-M2: record this login as a UserSession row, revoking any
        // prior rows for the user so older JWTs stop resolving. Done via
        // dynamic import so the edge middleware bundle (which loads
        // authConfig at module parse time) doesn't pull next/headers or
        // @meddoc/db for this callback's body.
        try {
          const [headersMod, sessionMod] = await Promise.all([
            import('next/headers'),
            import('./user-session'),
          ]);
          const h = await headersMod.headers();
          const ipAddress =
            h.get('x-forwarded-for')?.split(',')[0]?.trim() ??
            h.get('x-real-ip') ??
            null;
          const userAgent = h.get('user-agent') ?? null;
          const acceptLanguage = h.get('accept-language') ?? null;
          const sessionToken = sessionMod.randomSessionToken();
          await sessionMod.recordSessionLogin({
            userId: user.id as string,
            sessionToken,
            ipAddress,
            userAgent,
            deviceFingerprint: sessionMod.computeDeviceFingerprint(
              userAgent,
              acceptLanguage
            ),
          });
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          (token as any).sessionId = sessionToken;

          // ⚠️ #182(4) — THE RECOVERY CODE IS CONSUMED HERE, AFTER THE SESSION
          // ROW EXISTS, AND NOWHERE ELSE. `authorize()` used to burn it on a
          // match, which is BEFORE this callback can refuse the sign-in — so a
          // session-tracking failure destroyed a single-use code and then told
          // the doctor it was invalid, and every retry burned another.
          //
          // Reaching this line means `recordSessionLogin` succeeded, so the
          // sign-in is completing. ⚠️ The hash is never copied onto the token:
          // a recovery-code hash must not travel in a JWT.
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          const pendingHash = (user as any).pendingRecoveryHash as string | null | undefined;
          if (pendingHash) {
            // eslint-disable-next-line @typescript-eslint/no-explicit-any
            const codes = ((user as any).mfaBackupCodes ?? []) as string[];
            const { default: prisma } = await import('@meddoc/db');
            await prisma.user
              .update({
                where: { id: user.id as string },
                data: { mfaBackupCodes: { set: codes.filter((h) => h !== pendingHash) } },
              })
              .catch((e: unknown) => {
                // Best effort, and deliberately non-fatal: the sign-in HAS
                // completed by now. Failing here would refuse a login that
                // already has a valid session row, and the worst case is a
                // recovery code that can be used once more — strictly better
                // than the previous worst case, which was a code destroyed by
                // a sign-in that never happened.
                console.error(
                  '[auth] RECOVERY_CODE_CONSUME_FAILED: the code remains usable.',
                  { error: e instanceof Error ? e.message : String(e) },
                );
              });
          }
        } catch (err) {
          // ⚠️ #181(c) — THIS FAILS CLOSED NOW. The line that died promised
          // that a login would still succeed when session tracking did not.
          //
          // That trade read as a kindness — don't block a doctor on a DB
          // hiccup — and its real effect was to mint a token with NO
          // `sessionId` claim. Every revocation gate in this callback lives
          // behind `if (sessionId)`: sign-out, sign-out-all-devices,
          // `isActive`, `suspendedAt`, `softDeletedAt`, `forceLogoutAt`. A
          // claim-less token skipped ALL of them, for its entire 7-day life,
          // and nothing could revoke it by any mechanism.
          //
          // The availability we were buying was one login. The price was a
          // session nobody could end. Refusing the login is the cheaper
          // failure by a wide margin: the doctor retries and it works.
          console.error('[auth] UserSession record on sign-in failed:', err);
          throw new Error(
            'SESSION_TRACKING_FAILED: refusing to mint a session token that ' +
              'could never be revoked. Sign-in was not completed; retry.',
          );
        }
        return token;
      }

      // ── Subsequent-request path — validate the existing sessionId ──
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const sessionId = (token as any).sessionId as string | undefined;

      // ⚠️ #181(e) — A TOKEN WITHOUT A sessionId IS REJECTED. It used to fall
      // through to `return token` under a comment about legacy pre-T-M2 JWTs,
      // which made "minted before the claim existed" and "minted while session
      // tracking was broken" INDISTINGUISHABLE — and waved both through
      // unvalidated. There is no longer a way to reach production without the
      // claim, because (c) refuses to mint one, so the only tokens that can
      // land here are stale. Every user signs in once more; the release note
      // says so plainly.
      if (!sessionId) {
        console.warn(
          '[auth] SESSION_NO_ID: a token carrying no sessionId claim was ' +
            'REJECTED. Pre-#181 tokens are invalid by design; the user signs ' +
            'in again once.',
        );
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        return null as any;
      }

      {
        try {
          const { validateSession } = await import('./user-session');
          const valid = await validateSession(sessionId);
          if (!valid) {
            // ⚠️ A DEFINITIVE ANSWER — ruling #182(1). The database replied and
            // the row is gone, expired, inactive, suspended, soft-deleted or
            // past forceLogoutAt. The session IS invalid, so returning null is
            // right AND clearing the cookie is right: there is nothing to
            // re-validate later.
            // eslint-disable-next-line @typescript-eslint/no-explicit-any
            return null as any;
          }
          // A clean verification clears any prior unverified marker, so one
          // blip does not persist into a token that later validates fine.
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          delete (token as any).sessionVerifyFailed;
        } catch (err) {
          // ⚠️ THE DATABASE COULD NOT ANSWER — ruling #182(1), AND THIS IS THE
          // CASE #181(d) GOT WRONG IN BOTH DIRECTIONS BEFORE IT.
          //
          // Before #181(d) this failed OPEN: the JWT was honoured and every
          // revocation gate was skipped. #181(d) made it `return null`, which
          // fixed the honouring and introduced a second defect the pass caught:
          // `@auth/core` responds to a null token with `sessionStore.clean()`,
          // so a TRANSIENT pool timeout DELETED the browser's cookie and
          // ejected a working doctor permanently rather than for one request.
          //
          // Neither is right, because "revoked" and "cannot tell" are different
          // answers. This branch is CANNOT TELL:
          //   · the token is RETAINED, so the cookie survives and the very next
          //     request re-validates — a blip costs a retry, not a re-login;
          //   · it is MARKED, and `getSession` refuses the request 503 rather
          //     than serving anything from JWT claims alone.
          //
          // ⚠️ THE MARKER IS LOAD-BEARING AND MUST NOT BE READ AS A SESSION.
          // Returning the token here is NOT "the session is fine"; it is "ask
          // again". Any consumer that reads this token without checking the
          // marker has reintroduced the original fail-open.
          console.error(
            '[auth] SESSION_UNVERIFIABLE: validateSession threw — the database ' +
              'could not answer, so revocation, expiry, isActive, suspendedAt, ' +
              'softDeletedAt and forceLogoutAt are UNKNOWN. The request will be ' +
              'REFUSED (503) and the cookie KEPT for re-validation. This is not ' +
              'a sign-out and must not be served as a session.',
            { sessionId, error: err instanceof Error ? err.message : String(err) }
          );
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          (token as any).sessionVerifyFailed = true;
        }
      }
      return token;
    },

    async session({ session, token }) {
      if (session.user && token) {
        session.user.id = token.id as string;
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        session.user.role = token.role as any;
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        session.user.practiceId = (token as any).practiceId;
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        (session.user as any).sessionId = (token as any).sessionId;
        // ⚠️ #182(1) — THE MARKER MUST CROSS INTO THE SESSION, OR THE REFUSAL
        // NEVER HAPPENS. The jwt callback sets `sessionVerifyFailed` when the
        // database could not answer; `getSession` refuses the request on it.
        // If it were not propagated here, the jwt half would be a no-op and the
        // session would be served exactly as it was under the old fail-open —
        // a two-part fix that silently applies only its first half.
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        (session.user as any).sessionVerifyFailed = (token as any).sessionVerifyFailed === true;
      }
      return session;
    },

    async redirect({ url, baseUrl }) {
      if (url.startsWith(baseUrl)) return url;
      if (url.startsWith('/')) return `${baseUrl}${url}`;
      return baseUrl;
    },
  },
};

// ---------------------------------------------------------------------------
// Tenant helpers
// ----------------------------------------------------------------------------
// Role semantics:
//   DOCTOR, STAFF  — scoped to their own practice, and within that, only
//                    patients they created/are assigned to.
//   ADMIN          — scoped to their own practice, but sees EVERY patient
//                    and user within it.
//   SUPER_ADMIN    — bypass all tenant scoping. Platform ops only.
// ---------------------------------------------------------------------------

/**
 * The database could not answer whether this session is still valid.
 *
 * ⚠️ THIS IS "CANNOT TELL", NOT "INVALID", AND THE DIFFERENCE IS THE WHOLE OF
 * RULING #182(1). An invalid session is ended and its cookie cleared. An
 * unverifiable one is REFUSED for this request — 503 — with the cookie kept, so
 * the next request re-validates. Serving it from JWT claims admits a revoked
 * account; clearing the cookie ejects a working doctor on a transient blip.
 * Both were shipped before, in that order.
 */
export class SessionUnverifiableError extends Error {
  readonly status = 503;
  /**
   * ⚠️ A STABLE MARKER, BECAUSE `message` DOES NOT SURVIVE THE BOUNDARY.
   * Next.js strips server error messages before they reach a client error
   * boundary in production — deliberately, so internals do not leak. A boundary
   * that branches on `error.message` therefore works in dev and silently falls
   * through to the generic "something went wrong" in production, which is the
   * one environment this refusal has to be legible in.
   *
   * `digest` IS forwarded, so the marker rides on that.
   */
  static readonly DIGEST = 'SESSION_UNVERIFIABLE';
  readonly digest = SessionUnverifiableError.DIGEST;
  constructor(readonly detail: string) {
    super(
      'SESSION_UNVERIFIABLE: the session could not be verified against the ' +
        'database. The request is refused; the session is NOT ended.',
    );
    this.name = 'SessionUnverifiableError';
  }
}

export class TenantScopeError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'TenantScopeError';
  }
}

// ⚠️ `canBypassTenantScope` IS GONE — RULED 2026-08-06 (RULINGS.md).
//
// It returned true for `role === 'SUPER_ADMIN'`, and `tenantScope` then returned
// `{}` — which as a Prisma `where` is not "no results", it is EVERY TENANT. One
// role could read across the practice wall by construction.
//
// ⚠️ WHAT THE ENUMERATION FOUND, because the blast radius was not what it looked
// like. All four consumers lived in `apps/meddoc-pro` — the legacy CRM, which
// has been STOPPED since the 2026-08-04 security block (`pro.quillmd.com` 410,
// container not running). They read `auditLog` ×2, `user` and `apiUsage`:
// **no clinical table**, and `apps/meddoc-pro` reads no clinical table at all.
// `apps/transcribe-md` — the live clinical app — had ZERO consumers (measured
// against a positive control of 15 in meddoc-pro).
//
// So this removal does not close an active leak. It closes the DOOR to one:
// nothing stops a future admin surface from reaching for a helper named
// "bypass tenant scope", and the next such surface will be in the app that does
// hold charts. `gate-no-tenant-bypass.test.ts` keeps it shut.
//
// Platform-operator needs route through the ADMIN phase, which already rules
// ZERO clinical content in admin.

/**
 * The tenant predicate for a session. There is no bypass and no caller-supplied
 * override — the practice comes from the session or the call throws.
 *
 * ⚠️ IT RETURNS A REQUIRED KEY, NOT AN OPTIONAL ONE. The old signature was
 * `{ practiceId?: string }`, and an optional key is exactly how this failed
 * open: Prisma DROPS a `where` key whose value is `undefined`, so a session
 * without a practice silently produced `{}` — every tenant — with no error.
 */
export function tenantScope(session: Session): { practiceId: string } {
  const practiceId = session.user.practiceId;
  if (typeof practiceId !== 'string' || practiceId.length === 0) {
    throw new TenantScopeError(
      'tenantScope: session has no practice. Refusing to build a predicate ' +
        'Prisma would treat as "all tenants".',
    );
  }
  return { practiceId };
}

export async function assertSamePracticeUser(
  session: Session,
  targetUserId: string
): Promise<void> {
  // No bypass. Ruled 2026-08-06: no role crosses the practice wall through the
  // app, and "same practice" is exactly what this function is named for.
  const target = await prisma.user.findUnique({
    where: { id: targetUserId },
    select: { practiceId: true },
  });
  if (!target) {
    throw new TenantScopeError('User not found.');
  }
  if (target.practiceId !== session.user.practiceId) {
    throw new TenantScopeError('User not found.');
  }
}

// ---------------------------------------------------------------------------
// NextAuth module augmentation
// ----------------------------------------------------------------------------
// Adds our custom fields (id, role, practiceId) to the NextAuth Session,
// User, and JWT types. Declared here (not in each app) so both apps and
// this package see the same shape as soon as they import from @meddoc/auth.
// Before M1 this lived at apps/meddoc-pro/src/types/next-auth.d.ts; that
// file is removed now — this block is the single source of truth.
// ---------------------------------------------------------------------------

declare module 'next-auth' {
  interface Session {
    user: {
      id: string;
      role: UserRole;
      practiceId: string;
      /** T-M2: opaque token matching a row in user_sessions. Absent on
       *  pre-T-M2 JWTs (those ride out their original TTL and re-enter
       *  the single-session regime on the next login). */
      sessionId?: string;
    } & import('next-auth').DefaultSession['user'];
  }

  interface User {
    id: string;
    email: string;
    name?: string | null;
    role: UserRole;
    practiceId: string;
  }
}

declare module 'next-auth/jwt' {
  interface JWT {
    id: string;
    role: UserRole;
    practiceId: string;
    /** T-M2: see Session.user.sessionId above. */
    sessionId?: string;
  }
}

// ---------------------------------------------------------------------------
// patientAccessWhere
// ---------------------------------------------------------------------------

/**
 * Returns a Prisma `where` predicate that scopes Patient queries to what
 * the given session can see. Exported so other data modules (appointments,
 * clinical notes, Scribe visits) can use it as a nested relation filter:
 *   prisma.appointment.findMany({
 *     where: { patient: patientAccessWhere(session) }
 *   })
 * — which pushes tenant isolation down to the Postgres join.
 */
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export function patientAccessWhere(session: Session): any {
  const base: Record<string, unknown> = { deletedAt: null };

  if (session.user.role === 'SUPER_ADMIN') {
    return base;
  }

  base.practiceId = session.user.practiceId;

  if (session.user.role === 'ADMIN') {
    return base;
  }

  // DOCTOR / STAFF — additionally constrained to their own patients.
  return {
    ...base,
    OR: [
      { createdById: session.user.id },
      { assignedDoctorId: session.user.id },
    ],
  };
}
