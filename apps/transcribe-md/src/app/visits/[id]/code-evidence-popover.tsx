'use client';

// ============================================================================
// CodeEvidencePopover — Phase 5.1 Linear V1 V2 Power Table
// ----------------------------------------------------------------------------
// Renders the inline expand row that surfaces the full transcript
// quote backing an ICD/CPT code. Lives inside <CodesTable>; the codes
// table toggles the popover via `expandedRow` state.
//
// Surgical: this component does NOT fetch the underlying transcript
// turn (that wire-up arrives when the worker emits `evidence_turn_ix`).
// Today it surfaces the `evidence_quote` already attached to each code.
// ============================================================================

import type { ReactNode } from 'react';

interface CodeEvidencePopoverProps {
  quote: string;
  /** Optional severity tone (low-confidence rows get a warning rail). */
  tone?: 'sage' | 'warning';
  /** Action row (Edit / View transcript / Remove etc.). */
  actions?: ReactNode;
  /** Override label for the evidence section. Defaults to "Evidence · transcript". */
  label?: string;
  /** Optional preface line above the quote, e.g. low-confidence callout. */
  preface?: ReactNode;
}

export function CodeEvidencePopover({
  quote,
  tone = 'sage',
  actions,
  label = 'Evidence · transcript',
  preface,
}: CodeEvidencePopoverProps) {
  const railColor =
    tone === 'warning'
      ? 'var(--color-linear-warning)'
      : 'var(--color-linear-sage)';
  const dotColor = railColor;
  return (
    <div className="qm-lin-code-evidence">
      <div
        className="qm-lin-code-evidence-label"
        style={
          tone === 'warning'
            ? { color: 'var(--color-linear-warning)' }
            : undefined
        }
      >
        <span
          aria-hidden
          className="qm-lin-code-evidence-dot"
          style={{ background: dotColor }}
        />
        {label}
      </div>
      {preface}
      <blockquote
        className="qm-lin-code-evidence-quote"
        style={{ borderLeftColor: railColor }}
      >
        {quote ? `“${quote}”` : (
          <span className="text-linear-text-3 not-italic">
            No transcript quote captured.
          </span>
        )}
      </blockquote>
      {actions && <div className="qm-lin-code-evidence-actions">{actions}</div>}
    </div>
  );
}
