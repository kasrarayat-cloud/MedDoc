'use client';

// Root error boundary — catches anything that slips past the
// per-segment error boundaries. Should rarely fire in production.

import { ErrorFallback } from '@/components/error-fallback';
import { SessionUnverifiable } from '@/components/session-unverifiable';

/** Kept in sync with `SessionUnverifiableError.DIGEST` in `@meddoc/auth`.
 *  ⚠️ It is a LITERAL here on purpose: importing the server-side auth package
 *  into a `'use client'` boundary would pull prisma into the client bundle.
 *  `gate-182` asserts the two strings match, so they cannot drift silently. */
const SESSION_UNVERIFIABLE_DIGEST = 'SESSION_UNVERIFIABLE';

export default function RootError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  // ⚠️ #182(1) — a session that could not be VERIFIED is not a crash, and it is
  // not a sign-out. It gets its own surface, which says so and offers a retry.
  if (error.digest === SESSION_UNVERIFIABLE_DIGEST) {
    return <SessionUnverifiable reset={reset} />;
  }
  return <ErrorFallback error={error} reset={reset} scope="root" />;
}
