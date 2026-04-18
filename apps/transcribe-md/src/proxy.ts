// ============================================================================
// Next.js Edge Middleware — TranscribeMD route protection
// ----------------------------------------------------------------------------
// Runs on the Edge for every request matching `config.matcher`. Uses the
// edge-safe auth.config (no Prisma / Node deps) to check the session
// cookie. On `authorized` returning false, NextAuth redirects to /login
// with a callbackUrl query param.
//
// Prisma-backed session validation (single-session enforcement) happens
// later in the jwt() callback, which only runs in Node — the edge tier
// is for cheap cookie gating.
// ============================================================================

import NextAuth from 'next-auth';
import authConfig from '@/lib/auth.config';

const { auth } = NextAuth(authConfig);

export default auth;

export const config = {
  matcher: [
    '/dashboard/:path*',
    '/visits/:path*',
    '/settings/:path*',
  ],
};
