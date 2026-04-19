'use client';

// Root error boundary — catches anything that slips past the
// per-segment error boundaries. Should rarely fire in production.

import { ErrorFallback } from '@/components/error-fallback';

export default function RootError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return <ErrorFallback error={error} reset={reset} scope="root" />;
}
