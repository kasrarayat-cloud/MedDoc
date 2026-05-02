// ============================================================================
// CodingRailSkeleton — mono "computing..." placeholder during SSR fail-soft
// ----------------------------------------------------------------------------
// Server component (no 'use client') used by /visits/[id] when scoring
// throws on initial render. Renders the rail's container shell with a
// centered mono message — never blocks Sign & Send, never colored red.
//
// Per spec §4.1 fail-soft path: if scoring throws, render the rail with
// `—` for the suggested code and a small mono "Scoring unavailable —
// try refresh" text-3 message.
// ============================================================================

interface CodingRailSkeletonProps {
  /** Optional override message — e.g. for a `Scoring unavailable` state. */
  message?: string;
}

export function CodingRailSkeleton({
  message = 'Computing coding feedback…',
}: CodingRailSkeletonProps) {
  return (
    <aside
      className="qm-lin-coding-rail qm-lin-coding-rail--skeleton"
      aria-label="Billing support — loading"
    >
      <div className="qm-lin-coding-rail-head">
        <div className="qm-lin-coding-rail-head-top">
          <span className="qm-lin-coding-rail-label">Billing support</span>
          <span className="qm-lin-coding-rail-label qm-lin-coding-rail-label--ghost">
            AMA 2021
          </span>
        </div>
        <div className="qm-lin-coding-rail-code-row">
          <span className="qm-lin-coding-code">—</span>
          <span className="qm-lin-coding-rail-skeleton-msg">{message}</span>
        </div>
      </div>
    </aside>
  );
}
