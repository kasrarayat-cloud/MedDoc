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

  secret: process.env.AUTH_SECRET || 'dev_secret_change_in_production_min_32_chars_xyz',

  trustHost: true,

  // Only set `cookies` when a domain override is actually configured so
  // we don't accidentally shadow NextAuth's sensible defaults.
  ...(cookieDomain
    ? {
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
              domain: cookieDomain,
            },
          },
        },
      }
    : {}),

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
        } catch (err) {
          // Fail OPEN: login succeeds even if session tracking fails.
          // The alternative (blocking login on a DB hiccup) would be a
          // worse UX than a temporarily-unenforced single-session rule.
          console.error('[auth] UserSession record on sign-in failed:', err);
        }
        return token;
      }

      // ── Subsequent-request path — validate the existing sessionId ──
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const sessionId = (token as any).sessionId as string | undefined;
      if (sessionId) {
        try {
          const { validateSession } = await import('./user-session');
          const valid = await validateSession(sessionId);
          if (!valid) {
            // Row is gone (revoked by a newer login on another device)
            // or expired. Returning null invalidates the JWT — the next
            // request sees no session and the authorized() middleware
            // redirects to /login.
            // eslint-disable-next-line @typescript-eslint/no-explicit-any
            return null as any;
          }
        } catch (err) {
          // Fail OPEN on DB errors — don't kick users off for a transient
          // outage; the row will be re-validated on the next request.
          console.error('[auth] UserSession validate failed:', err);
        }
      }
      // Legacy tokens (minted before T-M2) have no sessionId — they pass
      // through until their natural JWT expiry, then re-login gains one.
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

export function canBypassTenantScope(session: Session): boolean {
  return session.user.role === 'SUPER_ADMIN';
}

export function tenantScope(session: Session): { practiceId?: string } {
  if (canBypassTenantScope(session)) return {};
  return { practiceId: session.user.practiceId };
}

export class TenantScopeError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'TenantScopeError';
  }
}

export async function assertSamePracticeUser(
  session: Session,
  targetUserId: string
): Promise<void> {
  if (canBypassTenantScope(session)) return;
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
