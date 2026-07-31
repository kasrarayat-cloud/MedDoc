// ============================================================================
// ROUNDS — how a gate is NAMED, in one place.
// ----------------------------------------------------------------------------
// The pipeline strip says "2 blockers before Signed — critical interaction,
// documentation level". Screen 3 heads each step with the same words. Those are
// the same claim rendered twice, and two copies of a label map is how a doctor
// ends up told "documentation level" on one surface and "E/M" on the next.
//
// Deliberately NOT under components/: both a component and a view-model read
// these, and item F deletes the skin's component namespace.
// ============================================================================

import type { SignGateId } from '@/lib/sign-gates';

/** The doctor-facing name of each gate. Plain words, sentence case. */
export const GATE_LABEL: Record<string, string> = {
  rx: 'critical interaction',
  em: 'documentation level',
  attestation: 'attestation',
};

/** The heading Screen 3 puts on each step. */
export const GATE_HEADING: Record<SignGateId, string> = {
  rx: 'Critical interactions',
  em: 'Documentation level',
  attestation: 'Sign & lock',
};

export function gateLabel(id: string): string {
  return GATE_LABEL[id] ?? id;
}

/** "1 blocker before Signed" / "3 blockers before Signed". */
export function blockerPhrase(n: number): string {
  return n === 1 ? '1 blocker before Signed' : `${n} blockers before Signed`;
}
