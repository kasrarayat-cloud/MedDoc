'use client';

// New-visit error boundary — Phase 5 (Linear V1) renders on the
// dark canvas. error.tsx is outside the AppFrame boundary so the
// wrapper sets linear-bg directly.

import { ErrorFallback } from '@/components/error-fallback';

export default function VisitsNewError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <div
      style={{
        minHeight: '100vh',
        background: 'var(--color-linear-bg)',
      }}
    >
      <ErrorFallback error={error} reset={reset} scope="visits:new" />
    </div>
  );
}
