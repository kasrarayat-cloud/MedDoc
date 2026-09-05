// ============================================================================
// icd-row-state — which of the Receipt's five row states a code is in
// ----------------------------------------------------------------------------
// The owner's frame `icd-code-row-states` (24:2, file Zvgz37i6jVoNYy9BzAAtoQ)
// approves exactly five, and they map one-for-one onto the five buckets the
// coding surface already distinguishes — which is the reason the redesign is
// not a loss of information:
//
//     1 · PRE-ACCEPTED           accepted   (explicitly, or auto at sign time)
//     2 · HELD FOR REVIEW        undecided
//     3 · REJECTED BY DOCTOR     rejected   (+ the reason, as a second line)
//     4 · NO LONGER SUGGESTED    orphaned   — a decision for a code the
//                                             suggester no longer proposes
//     5 · SUGGESTED, NOT CARRIED the amber drops
//
// ⚠️ STATE 5 IS DERIVED FROM A DIFFERENT SOURCE AND CAN NEVER BE ACTED ON.
// Ruling #149(g) makes "a dropped code can never be accepted" a property of the
// DATA (`icd-drops.ts:261`), not of the UI. It is included here so the renderer
// has one vocabulary, and the caller supplies it from `amberIcdDrops` — never
// from the decision projection, which does not contain it.
//
// ⚠️ THIS FILE DECIDES APPEARANCE, NEVER PERMISSION. Whether a control may be
// offered is `props.readonly` and the three independent gates in the view;
// whether the server accepts it is the decision route. A row state is a label on
// something already decided elsewhere — canon: a write-time decision is
// re-derived where it is used, and this is the "used" end.
// ============================================================================

import type { IcdDecisionProjection } from '@/lib/icd-decisions';
import { normalizeIcdCode } from '@/lib/icd-decisions';

export type IcdRowState =
  | 'pre-accepted'
  | 'held'
  | 'rejected'
  | 'orphaned'
  | 'not-carried';

/** The frame's own label for each state, for the section headers and for
 *  anything that needs to say the state in words. */
export const ICD_ROW_STATE_LABEL: Record<IcdRowState, string> = {
  'pre-accepted': 'Pre-accepted',
  held: 'Held for review',
  rejected: 'Rejected by doctor',
  orphaned: 'No longer suggested',
  'not-carried': 'Suggested, not carried',
};

/**
 * The state of one code, from the projection the server already computed.
 *
 * ⚠️ ORDER OF TESTS IS LOAD-BEARING. `orphaned` must be tested BEFORE
 * `accepted`/`rejected`: an orphaned code IS one carrying a decision, so a
 * decision-first test would render it as an ordinary accept and hide the fact
 * that the suggester has withdrawn it.
 */
export function icdRowState(code: string, projection: IcdDecisionProjection): IcdRowState {
  const c = normalizeIcdCode(code);
  const has = (xs: readonly string[]) => xs.some((x) => normalizeIcdCode(x) === c);
  if (has(projection.orphaned)) return 'orphaned';
  if (has(projection.accepted)) return 'pre-accepted';
  if (has(projection.rejected)) return 'rejected';
  return 'held';
}
