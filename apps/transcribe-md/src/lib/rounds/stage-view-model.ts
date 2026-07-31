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
  /**
   * Screen 4's safety trail — ONLY what a persisted fact can prove.
   *
   * Each field is a real column read, not an inference from "the visit is
   * signed, so the gates must have been cleared". A card with no field behind it
   * is not rendered, and its absence means the step did not apply — which is the
   * whole claim the trail makes.
   *
   * ⚠️ THERE IS NO `attested` FIELD, AND THAT IS THE FINDING. Attestation is
   * never persisted: the sign body schema has no such field, there is no column,
   * no audit action, and `signGates` marks the gate `serverEnforced: false` for
   * exactly this reason. The only signal is a `useState(false)` that dies with
   * the page. An "Attested ✓" card would re-assert on every reload a fact
   * nothing recorded — and would contradict Screen 3's own sentence, which tells
   * the doctor the server does not check it. PARKED; un-park when an
   * `attestedAt` exists in the sign body and a column or audit action receives
   * it. That is a schema and route change, not a reskin.
   */
  trail: SignedTrail;
}

export interface SignedTrail {
  /**
   * CRITICAL Rx overrides recorded at or before the signature.
   *
   * Counted from real `RxWarningOverride` rows, each of which carries a
   * server-validated reason, a signer and a timestamp, and each correlated
   * against the visit's persisted warnings before it could be written.
   *
   * Filtered on severity in the READER, never in the query — that array is also
   * the coverage input to `signGates`, and narrowing it there would narrow the
   * gate. And compared against `signedAt` rather than assumed: `recordOverride`
   * guards ownership, not visit status, so nothing structurally prevents a row
   * postdating the signature. A card that says "before signing" must mean it.
   *
   * 0 ⇒ no card. The visit had no critical interaction to clear.
   */
  criticalOverridesBeforeSign: number;
  /**
   * When an E/M change was acknowledged, off the RAW `emPendingChange` column,
   * stamped by the winning READY→SIGNED transition.
   *
   * null ⇒ no card, and that is correct rather than a gap: with no pending
   * change the sign route skips the E/M branch entirely and succeeds, so there
   * is no record of a doctor "agreeing" to an unchanged level, because no such
   * act happened.
   *
   * Read from the raw column, NOT from the coerced display pair — that one is
   * null on every signed visit by construction. A delta field is not a display
   * field.
   */
  emAcknowledgedAt: string | null;
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
  // The narrow case of applyGateOverlay, kept because B1's callers and tests
  // speak in this shape. `undefined` means "no in-session signal", which is
  // different from 0 and must not collapse into it.
  return applyGateOverlay(data, { rxUnresolved: rxResolved ? 0 : undefined });
}

/**
 * Every in-session signal the gate flow can supply, applied at once.
 *
 * THIS IS THE WIDENING `applyRxResolved` ASKED FOR. Its residual was named
 * rather than hidden: one boolean could not express partial Rx progress, and
 * nothing carried the in-session E/M confirm or the attestation checkbox, so N
 * over-stated by up to one on both. Screen 3 owns all three signals, so it can
 * now report them — and the error direction stays the safe one, because every
 * term still comes from the gate set the server's own primitives produced.
 *
 * A field left `undefined` means "no signal", NOT "zero". Passing 0 for an
 * unknown would clear a blocker nobody cleared.
 */
export function applyGateOverlay(
  data: RoundsStageData,
  overlay: {
    /** Unmet critical Rx warnings, counted — partial credit is the point. */
    rxUnresolved?: number;
    /** The doctor confirmed the level in this session. */
    emConfirmed?: boolean;
    /** The attestation checkbox. UI-only, exactly as the gate says. */
    attested?: boolean;
  }
): RoundsStageData {
  // NO SIGNAL ⇒ THE SAME OBJECT BACK, referentially. This is consumed through a
  // `useMemo` whose result is passed to the stage, so returning a fresh object
  // for a no-op overlay would hand every consumer a new identity on every
  // recompute for no reason. B1's tests pin this with `toBe`.
  const touchesNothing =
    overlay.rxUnresolved === undefined && !overlay.emConfirmed && !overlay.attested;
  if (touchesNothing) return data;

  // Map, never filter. A gate that applies stays present at zero — "this visit
  // has no Rx gate" and "this visit's Rx gate is clear" are different claims
  // and the strip draws them differently.
  const gates = data.gates.map((g) => {
    if (g.id === 'rx' && overlay.rxUnresolved !== undefined) {
      return { ...g, unresolved: Math.max(0, overlay.rxUnresolved) };
    }
    if (g.id === 'em' && overlay.emConfirmed) return { ...g, unresolved: 0 };
    if (g.id === 'attestation' && overlay.attested) return { ...g, unresolved: 0 };
    return g;
  });

  return {
    ...data,
    gates,
    n: blockerCount(gates),
    // OFF THE GATE SET, always. Two derivations of one number is what makes the
    // critical band and the padlock contradict each other on one screen.
    criticalUnresolved: gates.find((g) => g.id === 'rx')?.unresolved ?? 0,
  };
}

/**
 * Which step the gate flow opens on: the first gate that still blocks.
 *
 * NEVER NULL. The flow always opens somewhere — with nothing outstanding that
 * is the last gate (attestation), which is where the signature is taken. An
 * "open on nothing" state would be a full-screen dialog with no content and no
 * way forward.
 *
 * Deliberately NOT `firstBlockingGateTarget`, which answers a different
 * question — which DOM anchor the CHAT should scroll to — and correctly
 * excludes attestation because it has no anchor to scroll to.
 */
export function firstOpenStep(gates: readonly SignGate[]): SignGateId | null {
  if (gates.length === 0) return null;
  return (
    gates.find((g) => g.unresolved > 0)?.id ?? gates[gates.length - 1].id
  );
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
