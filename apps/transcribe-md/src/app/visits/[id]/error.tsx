'use client';

// Visit-detail error boundary — Phase 2 (Clinician remodel) opts the
// route into the Clinician chrome via `<AppFrame theme="clinician">`,
// but Next renders error.tsx OUTSIDE that boundary. Wrap directly in
// `.qm-cl-app` so the cream canvas + warm charcoal ink resolve, and
// pass `theme="clinician"` to ErrorFallback (already dual-theme from
// Batch A). Scope label + reset semantics unchanged.

import { ErrorFallback } from '@/components/error-fallback';

export default function VisitIdError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <div className="qm-cl-app min-h-screen bg-clinician-cream">
      <ErrorFallback
        error={error}
        reset={reset}
        scope="visits:id"
        theme="clinician"
      />
    </div>
  );
}
