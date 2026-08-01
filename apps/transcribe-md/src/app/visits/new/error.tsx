'use client';

// New-visit error boundary — renders on the dark canvas.
//
// ⚠️ THE 100vh `--color-linear-bg` WRAPPER WAS REMOVED — same seam, same fix as
// `visits/[id]/error.tsx`, and the full note lives there (including why this
// comment must not spell the bridge class out). In short: the wrapper sat
// outside the bridged `<main>` that `ErrorFallback` renders, so under Rounds it
// painted the old skin's #08090a beneath a #12161e band that stops at 60vh.
// `body` already supplies the ground, which is why the root, dashboard and
// settings boundaries never needed a wrapper.

import { ErrorFallback } from '@/components/error-fallback';

export default function VisitsNewError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return <ErrorFallback error={error} reset={reset} scope="visits:new" />;
}
