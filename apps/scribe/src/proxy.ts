// ============================================================================
// apps/scribe — Next 16 edge proxy (formerly middleware)
// ----------------------------------------------------------------------------
// Gates /visits and any other protected routes on an authenticated session.
// The `authorized` callback in @meddoc/auth's shared authConfig matches
// /visits/* and returns false when there's no session → NextAuth auto-
// redirects to `pages.signIn` ("/login"). Since Scribe doesn't have its
// own /login, we handle the cross-subdomain bounce to MedDoc Pro here.
// ============================================================================

import { NextResponse, type NextRequest } from 'next/server';
import NextAuth from 'next-auth';
import { authConfig } from '@meddoc/auth';

const { auth } = NextAuth(authConfig);

const MEDDOC_PRO_URL =
  process.env.MEDDOC_PRO_PUBLIC_URL?.trim() || 'http://meddoc-pro.localhost';

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export default (auth as any)((req: NextRequest & { auth: unknown }) => {
  const isLoggedIn = !!req.auth;
  if (isLoggedIn) return NextResponse.next();

  // Cross-subdomain redirect to MedDoc Pro sign-in. Preserve the URL the
  // user was trying to hit so they bounce back after signing in.
  const callbackUrl = req.nextUrl.toString();
  const loginUrl = new URL('/login', MEDDOC_PRO_URL);
  loginUrl.searchParams.set('callbackUrl', callbackUrl);
  return NextResponse.redirect(loginUrl);
});

export const config = {
  matcher: ['/visits/:path*'],
};
