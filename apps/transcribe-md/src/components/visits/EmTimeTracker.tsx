'use client';

// ============================================================================
// EmTimeTracker — visit-time meter w/ AMA threshold band
// ----------------------------------------------------------------------------
// Mirrors `.coach-time` (soap-v6.html lines 379-408 + body 929-939):
//   [clock]  Visit time: 24m  ████████░░░░  99213 · 20–29m
//
// Per rubric §1.3:
//   - Display LOWER bound prominently (`Visit time: 24m`)
//   - Sage gradient meter: fill % = visitTimeSec / thresholdBand.max
//   - Mono micro-meta `99213 · 20-29m` right-aligned
//   - Tooltip on hover shows estimated total via 1.7× multiplier
//     (informational only; never auto-bumps)
// ============================================================================

import { useMemo } from 'react';
import type { EmTimeBand } from '@/lib/em-coding-ui/types';

interface EmTimeTrackerProps {
  /** Lower-bound visit time (recorded face-to-face) in seconds. */
  visitTimeSec: number;
  /** Multiplier-extrapolated total in seconds, optional — tooltip only. */
  estimatedTotalSec?: number;
  /** Threshold band of the currently-suggested code. */
  thresholdBand: EmTimeBand;
}

function formatMinutes(seconds: number): string {
  const minutes = Math.max(0, Math.round(seconds / 60));
  return `${minutes}m`;
}

function formatBandRange(band: EmTimeBand): string {
  const min = Math.round(band.min / 60);
  const max = Math.round(band.max / 60);
  return `${band.code} · ${min}–${max}m`;
}

export function EmTimeTracker({
  visitTimeSec,
  estimatedTotalSec,
  thresholdBand,
}: EmTimeTrackerProps) {
  // Fill ratio capped at 100 % — we never overflow the gradient bar visually.
  const fillPercent = useMemo(() => {
    if (thresholdBand.max <= 0) return 0;
    const raw = (visitTimeSec / thresholdBand.max) * 100;
    return Math.min(100, Math.max(0, raw));
  }, [visitTimeSec, thresholdBand.max]);

  const tooltip = useMemo(() => {
    if (typeof estimatedTotalSec === 'number' && estimatedTotalSec > visitTimeSec) {
      return `Estimated total ≈ ${formatMinutes(estimatedTotalSec)} (1.7× face-to-face)`;
    }
    return undefined;
  }, [estimatedTotalSec, visitTimeSec]);

  return (
    <div
      className="qm-lin-coding-time"
      title={tooltip}
      role="group"
      aria-label="Visit time tracker"
    >
      <span className="qm-lin-coding-time-clock" aria-hidden="true">
        <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.4">
          <circle cx="8" cy="8" r="6" />
          <path d="M8 4.5V8l2.5 1.5" strokeLinecap="round" />
        </svg>
      </span>
      <span className="qm-lin-coding-time-label">
        Visit time:{' '}
        <span className="qm-lin-coding-time-num">{formatMinutes(visitTimeSec)}</span>
      </span>
      <span
        className="qm-lin-coding-time-meter"
        aria-hidden="true"
        style={{ '--fill': `${fillPercent}%` } as React.CSSProperties}
      >
        <span className="qm-lin-coding-time-meter-fill" />
      </span>
      <span className="qm-lin-coding-time-rule">{formatBandRange(thresholdBand)}</span>
    </div>
  );
}
