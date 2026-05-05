'use client';

// ============================================================================
// BumpCtaButton — sage primary "Bump to 99214 · +$32" CTA
// ----------------------------------------------------------------------------
// Mirrors `.cta-bump` from soap-v6.html lines 1095-1102:
//   ┌──────────────────────────────────────────────┐
//   │ Bump to 99214 →                       + $32  │
//   │ close 2 gaps · 30 sec                        │
//   └──────────────────────────────────────────────┘
//
// On click:
//   1. Calls `onClick` so the parent rail opens BumpModal (3-step apply)
//   2. ALSO calls `onHighlight(criterionIds)` so the parent SoapEditor
//      can flash the SOAP sections that contain the missing criteria.
//      Direct prop coupling (replaces the orphan
//      qm:soap-highlight-criteria CustomEvent — see
//      em-coding-ui/types.ts header for the removal context).
// ============================================================================

import { useCallback } from 'react';
import { cn } from '@/lib/cn';
import { formatDelta } from '@/lib/em-coding-ui/revenueDelta';
import { type EmCode } from '@/lib/em-coding-ui/types';

interface BumpCtaButtonProps {
  /** Currently suggested CPT (e.g. '99213'). */
  current: EmCode;
  /** Target bump CPT (e.g. '99214'). */
  bumpTo: EmCode;
  /** Dollar delta for the badge. */
  revenueDelta: number;
  /** Human-readable gap descriptors — drives the secondary line. */
  gaps: string[];
  /** Criterion ids of the gaps — passed to onHighlight so the parent
   *  can map them to SOAP sections. */
  gapCriterionIds: string[];
  /** Open the BumpModal. */
  onClick: () => void;
  /** Optional — parent uses this to pulse the SOAP sections that
   *  contain the gap criteria. Silently no-ops when undefined. */
  onHighlight?: (criterionIds: string[]) => void;
  /** Disabled in readonly (signed) visits. */
  disabled?: boolean;
}

export function BumpCtaButton({
  current,
  bumpTo,
  revenueDelta,
  gaps,
  gapCriterionIds,
  onClick,
  onHighlight,
  disabled,
}: BumpCtaButtonProps) {
  const handleClick = useCallback(() => {
    if (disabled) return;
    if (gapCriterionIds.length > 0) {
      onHighlight?.(gapCriterionIds);
    }
    onClick();
  }, [onClick, onHighlight, disabled, gapCriterionIds]);

  // Sub-line uses gap count — language stays close to the mockup.
  const subLine =
    gaps.length === 0
      ? 'ready to confirm'
      : `close ${gaps.length} gap${gaps.length === 1 ? '' : 's'} · 30 sec`;

  return (
    <button
      type="button"
      className={cn('qm-lin-coding-bump', disabled && 'qm-lin-coding-bump--disabled')}
      onClick={handleClick}
      disabled={disabled}
      aria-label={`Bump from ${current} to ${bumpTo}, revenue delta ${formatDelta(revenueDelta)}`}
    >
      <span className="qm-lin-coding-bump-lhs">
        <span className="qm-lin-coding-bump-top">
          <span>Bump to {bumpTo}</span>
          <span className="qm-lin-coding-bump-arrow" aria-hidden="true">
            →
          </span>
        </span>
        <span className="qm-lin-coding-bump-sub">{subLine}</span>
      </span>
      <span className="qm-lin-coding-bump-delta">{formatDelta(revenueDelta)}</span>
    </button>
  );
}
