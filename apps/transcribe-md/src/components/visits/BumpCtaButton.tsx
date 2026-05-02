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
//   2. ALSO emits `qm:soap-highlight-criteria` so Subagent A's body applies
//      the sage edge-glow + auto-scrolls to the first missing criterion.
//      Loose coupling — no shared store.
// ============================================================================

import { useCallback } from 'react';
import { cn } from '@/lib/cn';
import { formatDelta } from '@/lib/em-coding-ui/revenueDelta';
import {
  SOAP_HIGHLIGHT_CRITERIA_EVENT,
  type SoapHighlightCriteriaDetail,
  type EmCode,
} from '@/lib/em-coding-ui/types';

interface BumpCtaButtonProps {
  /** Currently suggested CPT (e.g. '99213'). */
  current: EmCode;
  /** Target bump CPT (e.g. '99214'). */
  bumpTo: EmCode;
  /** Dollar delta for the badge. */
  revenueDelta: number;
  /** Human-readable gap descriptors — drives the secondary line. */
  gaps: string[];
  /** Criterion ids of the gaps — emitted via the highlight event. */
  gapCriterionIds: string[];
  /** Open the BumpModal. */
  onClick: () => void;
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
  disabled,
}: BumpCtaButtonProps) {
  const handleClick = useCallback(() => {
    if (disabled) return;
    if (typeof window !== 'undefined' && gapCriterionIds.length > 0) {
      const detail: SoapHighlightCriteriaDetail = {
        criterionIds: gapCriterionIds,
      };
      window.dispatchEvent(
        new CustomEvent(SOAP_HIGHLIGHT_CRITERIA_EVENT, { detail })
      );
    }
    onClick();
  }, [onClick, disabled, gapCriterionIds]);

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
