// ============================================================================
// Screen 2's view model — the live overlay and the "where do I send them" pick.
// ============================================================================

import { describe, expect, it } from 'vitest';

import type { SignGate } from '@/lib/sign-gates';
import {
  applyGateOverlay,
  applyRxResolved,
  firstBlockingGateTarget,
  firstOpenStep,
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

describe('applyGateOverlay — the widening applyRxResolved asked for', () => {
  it('takes a COUNT, so partial Rx progress is expressible', () => {
    // The residual `applyRxResolved` named: one boolean could not say "2 of 3
    // overridden", so N over-stated until the very last critical cleared.
    const out = applyGateOverlay(data([RX(3), EM(1), ATTEST]), { rxUnresolved: 1 });
    expect(out.gates.find((g) => g.id === 'rx')?.unresolved).toBe(1);
    expect(out.n).toBe(3); // rx 1 + em 1 + attestation 1
    expect(out.criticalUnresolved).toBe(1);
  });

  it('UNDEFINED IS NOT ZERO — an absent signal clears nothing', () => {
    // Passing 0 for "I do not know yet" would clear a blocker nobody cleared,
    // which is the one direction this module must never fail in.
    const d = data([RX(2), ATTEST]);
    expect(applyGateOverlay(d, {}).n).toBe(3);
    expect(applyGateOverlay(d, { rxUnresolved: undefined }).n).toBe(3);
    expect(applyGateOverlay(d, { rxUnresolved: 0 }).n).toBe(1);
  });

  it('returns the SAME OBJECT when no term applies', () => {
    // The result feeds a useMemo whose identity is handed to the stage; a fresh
    // object for a no-op overlay hands every consumer a new identity for
    // nothing.
    const d = data([RX(2), ATTEST]);
    expect(applyGateOverlay(d, {})).toBe(d);
    expect(applyGateOverlay(d, { emConfirmed: false, attested: false })).toBe(d);
  });

  it('zeroes the E/M and attestation terms independently', () => {
    const d = data([RX(1), EM(1), ATTEST]);
    expect(applyGateOverlay(d, { emConfirmed: true }).n).toBe(2);
    expect(applyGateOverlay(d, { attested: true }).n).toBe(2);
    expect(
      applyGateOverlay(d, { rxUnresolved: 0, emConfirmed: true, attested: true }).n
    ).toBe(0);
  });

  it('never removes a gate, and never invents one', () => {
    const out = applyGateOverlay(data([RX(2), EM(1), ATTEST]), {
      rxUnresolved: 0,
      emConfirmed: true,
      attested: true,
    });
    expect(out.gates.map((g) => g.id)).toEqual(['rx', 'em', 'attestation']);
  });

  it('clamps a negative count rather than crediting it', () => {
    const out = applyGateOverlay(data([RX(1), ATTEST]), { rxUnresolved: -5 });
    expect(out.gates.find((g) => g.id === 'rx')?.unresolved).toBe(0);
    expect(out.n).toBe(1);
  });

  it('keeps criticalUnresolved equal to the rx gate — one number, one source', () => {
    for (const c of [0, 1, 4]) {
      const out = applyGateOverlay(data([RX(4), ATTEST]), { rxUnresolved: c });
      expect(out.criticalUnresolved).toBe(
        out.gates.find((g) => g.id === 'rx')?.unresolved
      );
    }
  });
});

describe('firstOpenStep', () => {
  it('is the first gate that still blocks', () => {
    expect(firstOpenStep([RX(1), EM(1), ATTEST])).toBe('rx');
    expect(firstOpenStep([RX(0), EM(1), ATTEST])).toBe('em');
  });

  it('NEVER NULL on a non-empty set — with nothing outstanding it is the LAST gate', () => {
    // A flow that opened on "nothing" would be a full-screen dialog with no
    // content and no way forward. The last gate is where the signature is
    // taken, so that is the honest destination.
    expect(firstOpenStep([RX(0), EM(0), { ...ATTEST, unresolved: 0 }])).toBe(
      'attestation'
    );
  });

  it('is not firstBlockingGateTarget — it does NOT skip attestation', () => {
    // The two answer different questions. The chat scrolls to a DOM anchor and
    // attestation has none; the flow opens on a STEP and attestation is one.
    expect(firstOpenStep([ATTEST])).toBe('attestation');
    expect(firstBlockingGateTarget([ATTEST])).toBeNull();
  });

  it('returns null only for an empty set', () => {
    expect(firstOpenStep([])).toBeNull();
  });
});
