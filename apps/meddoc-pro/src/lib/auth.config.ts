// ============================================================================
// NextAuth Edge-Safe Shared Config
// ----------------------------------------------------------------------------
// This file is imported by BOTH:
//  1. The middleware (Edge runtime — no Node APIs allowed)
//  2. The full nextauth.ts (Node runtime — adds Prisma adapter + providers)
//
// IMPORTANT: do NOT import anything that uses Node-only APIs here:
//   ✗ @meddoc/db (Prisma)
//   ✗ bcryptjs
//   ✗ @auth/prisma-adapter
//   ✗ next/headers (only OK in server components, not Edge middleware)
//
// The shared `authorized` callback runs in Edge middleware to protect routes.
// ============================================================================

import type { NextAuthConfig } from 'next-auth';

const authConfig: NextAuthConfig = {
  // Providers are populated in nextauth.ts (Node runtime).
  // Empty here so middleware can read the config without instantiating provider modules.
  providers: [],

  pages: {
    signIn: '/login',
  },

  session: {
    strategy: 'jwt',
    maxAge: 60 * 60 * 8, // 8 hours — short for HIPAA
  },

  // JWT signing secret — must match across middleware and route handlers
  secret: process.env.AUTH_SECRET || 'dev_secret_change_in_production_min_32_chars_xyz',

  trustHost: true,

  callbacks: {
    /**
     * Runs on EVERY request that matches the middleware matcher.
     * Returning `true` allows the request through; returning `false`
     * triggers an automatic redirect to `pages.signIn` (with callbackUrl).
     */
    authorized({ auth, request: { nextUrl } }) {
      if (process.env.AUTH_USE_MOCK === 'true') return true;

      const isLoggedIn = !!auth?.user;
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const role = (auth?.user as any)?.role as string | undefined;
      const path = nextUrl.pathname;
      const isOnDashboard = path.startsWith('/dashboard');
      const isOnAdmin = path.startsWith('/system-admin');

      // Require login for protected areas
      if ((isOnDashboard || isOnAdmin) && !isLoggedIn) return false;

      // Role isolation policy:
      //   ADMIN   — may use BOTH /system-admin and /dashboard (so the
      //             "Clinician view" escape hatch in the admin sidebar
      //             actually works).
      //   DOCTOR/STAFF — blocked from /system-admin, bounced to /dashboard.
      //
      // Explicit 302 + no-store so browsers don't cache the redirect and
      // cause sticky routing on the client.
      //
      // IMPORTANT: only redirect when `role` is DEFINITIVELY set. If role is
      // undefined (e.g., brief window immediately after signin while the JWT
      // is being decoded at the edge), let the request through and let the
      // full-Node-runtime layout's getSession() do the authoritative check.
      if (isLoggedIn && role) {
        // Non-admin (neither ADMIN nor SUPER_ADMIN) trying to access
        // /system-admin → redirect to /dashboard.
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

    /**
     * Persist `id`, `role`, and `practiceId` into the JWT after sign-in.
     */
    async jwt({ token, user }) {
      if (user) {
        token.id = user.id as string;
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        token.role = (user as any).role;
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        token.practiceId = (user as any).practiceId;
      }
      return token;
    },

    /**
     * Expose `id`, `role`, and `practiceId` on `session.user` so client /
     * server code can read them.
     */
    async session({ session, token }) {
      if (session.user && token) {
        session.user.id = token.id as string;
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        session.user.role = token.role as any;
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        session.user.practiceId = (token as any).practiceId;
      }
      return session;
    },

    async redirect({ url, baseUrl }) {
      // After login, route based on role stored in the URL hash or default
      if (url.startsWith(baseUrl)) return url;
      if (url.startsWith('/')) return `${baseUrl}${url}`;
      return baseUrl;
    },
  },
};

export default authConfig;
