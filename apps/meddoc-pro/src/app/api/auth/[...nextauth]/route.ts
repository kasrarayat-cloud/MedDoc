// ============================================================================
// NextAuth Catch-all Route Handler
// ----------------------------------------------------------------------------
// Re-exports the GET/POST handlers from the NextAuth config so the
// /api/auth/* endpoints (signin, signout, callback, csrf, etc.) just work.
// ============================================================================

import { handlers } from '@/lib/nextauth';

export const { GET, POST } = handlers;
