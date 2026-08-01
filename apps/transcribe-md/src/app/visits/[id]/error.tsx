'use client';

// Visit-detail error boundary — renders on the dark canvas. Scope label +
// reset semantics unchanged.
//
// ⚠️ THE 100vh `--color-linear-bg` WRAPPER WAS REMOVED, AND ITS ABSENCE IS THE
// FIX. `ErrorFallback` adopts the Rounds bridge on its own `<main>`, which is
// `min-height: 60vh` — so the wrapper sat OUTSIDE that bridge and resolved
// `--color-linear-bg` at `:root` (#08090a, the old skin) while the band inside
// it resolved to the Rounds stage (#12161e). A visible two-tone seam across the
// bottom ~40vh, on this route and on `visits/new`, and on no other error route:
// the root, dashboard and settings boundaries render `<ErrorFallback>` bare.
// The wrapper was never load-bearing — `body` already paints
// `var(--color-linear-bg)` (globals.css:112), and under Rounds it paints the
// radial stage, which is the correct ground for the remaining 40vh.
//
// ⚠️ AND THIS COMMENT MUST NOT SPELL THE BRIDGE CLASS OUT. `gate-rounds-bridge`
// decides "this file adopts the bridge" with a raw `.includes()` over file TEXT,
// so prose naming the class registers this file as an adopter and reds the gate
// — measured, not guessed. Recorded so the next reader does not helpfully
// re-add the name.

import { ErrorFallback } from '@/components/error-fallback';

export default function VisitIdError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return <ErrorFallback error={error} reset={reset} scope="visits:id" />;
}
