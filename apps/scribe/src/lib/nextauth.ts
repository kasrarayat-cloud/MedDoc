// ============================================================================
// NextAuth instance for apps/scribe — READ-ONLY session access
// ----------------------------------------------------------------------------
// No providers. Scribe doesn't own a sign-in flow; users authenticate on
// apps/meddoc-pro and the JWT cookie is shared across subdomains via
// AUTH_COOKIE_DOMAIN (see @meddoc/auth authConfig).
//
// The `auth()` export below verifies the existing cookie against the
// shared AUTH_SECRET and returns the decoded session. Same semantics as
// apps/meddoc-pro's `auth()` but with no way to create a new session.
// ============================================================================

import NextAuth from 'next-auth';
import { authConfig } from '@meddoc/auth';

export const { auth, handlers, signIn, signOut } = NextAuth(authConfig);
