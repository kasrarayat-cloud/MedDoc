'use client';

// Visit-detail error boundary — Phase 5 (Linear V1) renders on the
// dark canvas. error.tsx is outside the AppFrame boundary, so wrap
// directly in the linear-bg color. Scope label + reset semantics
// unchanged.

import { ErrorFallback } from '@/components/error-fallback';

export default function VisitIdError({
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
      <ErrorFallback error={error} reset={reset} scope="visits:id" />
    </div>
  );
}
