// ============================================================================
// NextAuth Catch-all Route Handler (apps/transcribe-md)
// ----------------------------------------------------------------------------
// Re-exports the GET/POST handlers from our NextAuth config so
// /api/auth/* (signin, signout, callback, csrf, session) just works.
// ============================================================================

import { handlers } from '@/lib/nextauth';

export const { GET, POST } = handlers;
