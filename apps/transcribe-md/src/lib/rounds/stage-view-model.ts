// ============================================================================
// ROUNDS — Screen 2's serialisable prop, and the one live overlay on it.
// ----------------------------------------------------------------------------
// The gate set is computed on the SERVER, in `VisitBody`, and handed down as
// data. That placement is not incidental — it is the fix for two defects that
// have already been paid for once each:
//
//   * `signGates` needs the RAW `specialty` id. `VisitReadyView` has the display
//     LABEL in scope, and `findSpecialty('Ultrasound').id` is `'unspecified'`
//     with no throw. Computing on the client puts the wrong value within reach;
//     computing on the server puts only the right one there.
//   * `signGates` needs the RAW `emPendingChange` jsonb. The page has already
//     coerced it to a `{from, to}` display pair by the time the client sees it,
//     and `unacknowledgedEmChange` FAILS CLOSED on that shape — a phantom
//     blocker on every visit with a pending change, silently.
//
// Both are the same lesson: a value that is only correct on one side of a
// boundary should be consumed on that side.
//
// PURE — imported by a server component and a client component alike. No React,
// no Prisma.
// ============================================================================

import { blockerCount, type SignGate, type SignGateId } from '@/lib/sign-gates';
import type { StageIdentity, StageQueuePosition } from './stage-data';

/**
 * Everything Screen 2 needs, in a shape that crosses the RSC boundary.
 *
 * Dates are ISO strings rather than `Date`s because a `Date` does not survive
 * serialisation as a `Date`, and a silently-stringified one is worse than an
 * explicit string: it type-checks and then formats wrong.
 */
export interface RoundsStageData {
  status: string;
  signedAt: string | null;
  identity: StageIdentity;
  queue: StageQueuePosition;
  gates: SignGate[];
  /** Σ of every gate's unresolved count — the N on the padlocked Signed node. */
  n: number;
  emArtifact: boolean;
  /**
   * Unmet critical Rx warnings, for the band across the sheet.
   *
   * READ OFF THE GATE SET, never derived a second time. It is the same number
   * as the rx gate's `unresolved`, and two derivations of one number is the
   * exact defect `sign-gates.ts` was written to prevent for N. If they ever
   * disagree, the band and the padlock contradict each other on the same
   * screen.
   */
  criticalUnresolved: number;
}

/**
 * The single live overlay B1 has a signal for.
 *
 * `RxTab.onResolvedChange` reports one boolean — `allCriticalResolved` — and
 * nothing finer. So this can zero the Rx term when every critical warning is
 * cleared in-session, and it cannot do partial credit.
 *
 * THE RESIDUAL IS NAMED RATHER THAN HIDDEN: on partial Rx resolution, and after
 * an in-session E/M confirm (which is private to `ReviewDocumentView`), N
 * OVER-STATES by up to one. The error direction is always "more blockers than
 * the server will enforce" — never a promise the server then breaks, which is
 * the direction that would make the number worse than no number. B2 owns
 * closing it, by widening the channel rather than by guessing here.
 */
export function applyRxResolved(
  data: RoundsStageData,
  rxResolved: boolean
): RoundsStageData {
  if (!rxResolved) return data;

  // Map, never filter. A gate that applies stays present at zero — "this visit
  // has no Rx gate" and "this visit's Rx gate is clear" are different claims
  // and the strip draws them differently.
  const gates = data.gates.map((g) =>
    g.id === 'rx' ? { ...g, unresolved: 0 } : g
  );

  return {
    ...data,
    gates,
    n: blockerCount(gates),
    criticalUnresolved: 0,
  };
}

/**
 * Where "Review & sign" should take the doctor when something still blocks.
 *
 * SERVER-ENFORCED GATES ONLY, and in gate order. Attestation is excluded on
 * purpose: it is a real term in the UI's contract and it is counted in N, but
 * in B1 it has no on-page control to scroll to, and scrolling to nothing while
 * reporting a successful navigation is the precise lie this project keeps
 * finding. Returning null lets the caller fall through to the signing bar.
 */
export function firstBlockingGateTarget(
  gates: readonly SignGate[]
): 'rx_gate' | 'em_gate' | null {
  const TARGETS: Partial<Record<SignGateId, 'rx_gate' | 'em_gate'>> = {
    rx: 'rx_gate',
    em: 'em_gate',
  };

  for (const gate of gates) {
    if (!gate.serverEnforced || gate.unresolved <= 0) continue;
    const target = TARGETS[gate.id];
    if (target) return target;
  }
  return null;
}
