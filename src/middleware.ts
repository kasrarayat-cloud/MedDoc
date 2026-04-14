// ============================================================================
// Next.js Edge Middleware — Route Protection
// ----------------------------------------------------------------------------
// Runs on the Edge for every request matching the `config.matcher` below.
// Uses NextAuth's lightweight `auth.config.ts` (no Prisma / Node deps) to
// check whether the user is logged in. The `authorized` callback in that
// config returns false → NextAuth automatically redirects to `pages.signIn`
// (/login) with a `callbackUrl` query param so the user lands back on the
// page they tried to visit after signing in.
// ============================================================================

import NextAuth from 'next-auth';
import authConfig from '@/lib/auth.config';

const { auth } = NextAuth(authConfig);

// Next.js expects a default function export. Wrapping `auth` here ensures
// the static analyzer recognizes it as a middleware function regardless
// of whether NextAuth returns a function directly or a higher-order wrapper.
export default auth;

export const config = {
  matcher: [
    '/dashboard/:path*',
    '/system-admin/:path*',
  ],
};
