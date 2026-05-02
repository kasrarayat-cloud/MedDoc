// ============================================================================
// revenueDelta — Static AMA 2024 reference table for Bump CTA UI display
// ----------------------------------------------------------------------------
// Mirrors the rubric §5 reference table verbatim. Numbers come from the 2024
// Medicare Physician Fee Schedule (national average); they are illustrative
// anchors for the CTA — actual reimbursement varies by payer.
//
// The rail uses these values to render "+ $32" / "+ $44" deltas inside the
// `.qm-lin-coding-bump` button. Annual savings ("$7,800/yr · avg PCP") is
// derived from a typical PCP volume assumption documented in the rubric and
// surfaced in `.qm-lin-coding-cta-foot`.
// ============================================================================

import type { EmCode } from './types';

/** Static 2024 reference table — see rubric §5. */
const REVENUE_DELTA_TABLE: Array<{
  from: EmCode;
  to: EmCode;
  delta: number;
}> = [
  { from: '99213', to: '99214', delta: 32 },
  { from: '99214', to: '99215', delta: 44 },
  { from: '99203', to: '99204', delta: 52 },
  { from: '99204', to: '99205', delta: 76 },
  { from: '99212', to: '99213', delta: 20 },
  { from: '99202', to: '99203', delta: 28 },
];

/**
 * Look up the dollar delta between a pair of codes per the rubric §5 table.
 * Returns 0 if the pair is not represented (e.g. across new/established
 * ladders, or the codes match). Defensive default — never throws.
 */
export function revenueDelta(from: EmCode, to: EmCode): number {
  if (from === to) return 0;
  const row = REVENUE_DELTA_TABLE.find((r) => r.from === from && r.to === to);
  return row ? row.delta : 0;
}

/** Annual savings line shown in the CTA footer (illustrative; AMA reference). */
export const ANNUAL_SAVINGS_FOOTER = 'Saves $7,800/yr · avg PCP';

/** Format a delta value as "+ $32" for the bump CTA. */
export function formatDelta(delta: number): string {
  if (delta <= 0) return '';
  return `+ $${delta}`;
}
