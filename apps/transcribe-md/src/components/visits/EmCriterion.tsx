'use client';

// ============================================================================
// EmCriterion — single criterion row inside an EmCheckList group
// ----------------------------------------------------------------------------
// Mirrors the v6 mockup `.crit-item` block (soap-v6.html lines 440-490):
//   ┌────────────────────────────────────────────────────────────┐
//   │ [✓/⚠]  head text (Inter 12.5px, weight 500)                │
//   │        sub text (text-3, 11.5px)                           │
//   │        [+ add 1 line]  ← optional warn-state nudge button  │
//   └────────────────────────────────────────────────────────────┘
//
// Visual rules (per spec §3.3):
//   - status='ok' → sage check icon, head white, sub text-3
//   - status='warn' → amber triangle, head warning-bright, sub warning, nudge
//
// Interaction:
//   - Nudge button is the ONLY interactive element. Click / keyboard /
//     screen-reader focus all flow through that one explicit control.
//
// HISTORICAL §P5.2 a11y restore: the row used to be `role="button"` with
// its own onClick that fired a `qm:soap-jump` window CustomEvent. axe-core
// flagged that as `nested-interactive` because the nudge `<button>` lives
// inside the row. The whole-row click was a nice-to-have; doctors
// interact with the explicit nudge button. The constant + interface for
// that event were removed in the Phase-5.2 orphan-completion PR (see
// em-coding-ui/types.ts header). The jump-to-section affordance can
// come back as a separate action later (a sibling button next to the
// nudge, or a SoapSection click rather than EmCriterion → SoapSection
// coupling).
// ============================================================================

import { useCallback } from 'react';
import { cn } from '@/lib/cn';
import type { EmCriterion as EmCriterionType } from '@/lib/em-coding-ui/types';

interface EmCriterionProps {
  criterion: EmCriterionType;
  /** Optional nudge handler — called when "+ add 1 line" is clicked. */
  onNudge?: (suggestion: string) => void;
  /** Optimistic "applying..." state — adds a subtle pulse before server confirms. */
  applying?: boolean;
}

export function EmCriterion({
  criterion,
  onNudge,
  applying,
}: EmCriterionProps) {
  const handleNudge = useCallback(() => {
    if (onNudge && criterion.nudge) {
      onNudge(criterion.nudge.suggestion);
    }
  }, [onNudge, criterion.nudge]);

  const isWarn = criterion.status === 'warn';

  return (
    <div
      className={cn(
        'qm-lin-em-criterion',
        isWarn && 'qm-lin-em-criterion--warn',
        applying && 'qm-lin-em-criterion--applying'
      )}
      data-criterion-id={criterion.id}
    >
      <span
        className={cn(
          'qm-lin-em-criterion-icon',
          isWarn ? 'qm-lin-em-criterion-icon--warn' : 'qm-lin-em-criterion-icon--ok'
        )}
        aria-hidden="true"
      >
        {isWarn ? (
          <svg viewBox="0 0 8 8" fill="none" stroke="currentColor" strokeWidth="1.4">
            <path d="M4 1.4L7 6.6H1L4 1.4z" strokeLinejoin="round" />
            <path d="M4 3.4v1.7M4 5.7v.3" strokeLinecap="round" />
          </svg>
        ) : (
          <svg viewBox="0 0 8 8" fill="none" stroke="currentColor" strokeWidth="1.6">
            <path
              d="M1.5 4l1.8 1.8L6.5 2.2"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        )}
      </span>
      <span className="qm-lin-em-criterion-text">
        <span className="qm-lin-em-criterion-head">{criterion.head}</span>
        <span className="qm-lin-em-criterion-sub">{criterion.sub}</span>
        {criterion.nudge ? (
          <button
            type="button"
            className="qm-lin-em-nudge"
            onClick={handleNudge}
            title={criterion.nudge.suggestion}
            aria-label={`Suggested addition: ${criterion.nudge.suggestion}`}
          >
            {criterion.nudge.text}
          </button>
        ) : null}
      </span>
    </div>
  );
}
