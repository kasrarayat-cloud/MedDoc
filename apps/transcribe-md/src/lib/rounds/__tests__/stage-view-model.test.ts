// ============================================================================
// Screen 2's view model — the live overlay and the "where do I send them" pick.
// ============================================================================

import { describe, expect, it } from 'vitest';

import type { SignGate } from '@/lib/sign-gates';
import {
  applyRxResolved,
  firstBlockingGateTarget,
  type RoundsStageData,
} from '../stage-view-model';

function data(gates: SignGate[]): RoundsStageData {
  return {
    status: 'READY',
    signedAt: null,
    identity: {
      visitId: 'v1',
      patientLabel: 'A Patient',
      mrn: null,
      ageYears: null,
      dob: null,
      reason: null,
      recordedAtIso: '2026-07-30T10:00:00.000Z',
      durationLabel: null,
    },
    queue: { position: 1, total: 1, nextVisitId: null, prevVisitId: null },
    gates,
    n: gates.reduce((s, g) => s + g.unresolved, 0),
    emArtifact: false,
    criticalUnresolved: gates.find((g) => g.id === 'rx')?.unresolved ?? 0,
  };
}

const RX = (unresolved: number): SignGate => ({
  id: 'rx',
  unresolved,
  serverEnforced: true,
});
const EM = (unresolved: number): SignGate => ({
  id: 'em',
  unresolved,
  serverEnforced: true,
});
const ATTEST: SignGate = {
  id: 'attestation',
  unresolved: 1,
  serverEnforced: false,
};

describe('applyRxResolved', () => {
  it('is the identity when nothing has been resolved', () => {
    const d = data([RX(2), EM(1), ATTEST]);
    expect(applyRxResolved(d, false)).toBe(d);
  });

  it('zeroes the Rx term and RECOUNTS n from the gates', () => {
    const out = applyRxResolved(data([RX(2), EM(1), ATTEST]), true);

    expect(out.gates.find((g) => g.id === 'rx')?.unresolved).toBe(0);
    expect(out.n).toBe(2); // em 1 + attestation 1
  });

  it('KEEPS the rx gate present at zero — absent and clear are different claims', () => {
    // "This visit has no prescriptions" and "this visit's interactions are all
    // cleared" must not render the same. Filtering instead of mapping would
    // make an all-clear visit indistinguishable from one that never had a
    // gate, and the strip draws those differently.
    const out = applyRxResolved(data([RX(2), ATTEST]), true);
    expect(out.gates.map((g) => g.id)).toEqual(['rx', 'attestation']);
  });

  it('never invents a gate it was not given', () => {
    const out = applyRxResolved(data([ATTEST]), true);
    expect(out.gates.map((g) => g.id)).toEqual(['attestation']);
    expect(out.n).toBe(1);
  });

  it('keeps criticalUnresolved equal to the rx gate — one number, one source', () => {
    // The band across the sheet and the padlock's N must never disagree. They
    // do if anyone derives this a second time.
    for (const resolved of [false, true]) {
      const out = applyRxResolved(data([RX(3), EM(1), ATTEST]), resolved);
      expect(out.criticalUnresolved).toBe(
        out.gates.find((g) => g.id === 'rx')?.unresolved
      );
    }
  });

  it('does not mutate its input', () => {
    const d = data([RX(2), ATTEST]);
    applyRxResolved(d, true);
    expect(d.gates.find((g) => g.id === 'rx')?.unresolved).toBe(2);
    expect(d.n).toBe(3);
  });
});

describe('firstBlockingGateTarget', () => {
  it('returns the first server-enforced gate that still blocks, in order', () => {
    expect(firstBlockingGateTarget([RX(1), EM(1), ATTEST])).toBe('rx_gate');
    expect(firstBlockingGateTarget([RX(0), EM(1), ATTEST])).toBe('em_gate');
  });

  it('NEVER returns attestation — it has no control to scroll to in B1', () => {
    // It is counted in N, and it is a real term in the contract with the
    // doctor. But there is nothing on this page to take them to, and scrolling
    // to nothing while reporting a successful navigation is the exact lie the
    // deferred-scroll seam exists to prevent.
    expect(firstBlockingGateTarget([ATTEST])).toBeNull();
    expect(firstBlockingGateTarget([RX(0), EM(0), ATTEST])).toBeNull();
  });

  it('ignores a gate that applies but is already clear', () => {
    expect(firstBlockingGateTarget([RX(0), ATTEST])).toBeNull();
  });

  it('NEGATIVE CONTROL — it is capable of returning each target', () => {
    // Without this, "always null" would pass every assertion above except two,
    // and a refactor that broke the lookup table would look like a stricter
    // gate rather than a dead one.
    expect(firstBlockingGateTarget([RX(1)])).toBe('rx_gate');
    expect(firstBlockingGateTarget([EM(1)])).toBe('em_gate');
    expect(firstBlockingGateTarget([])).toBeNull();
  });
});
