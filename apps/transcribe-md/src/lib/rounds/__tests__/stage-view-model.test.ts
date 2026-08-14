// ============================================================================
// Screen 2's view model — the live overlay and the "where do I send them" pick.
// ============================================================================

import { describe, expect, it } from 'vitest';

import type { SignGate } from '@/lib/sign-gates';
import {
  applyGateOverlay,
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
    queue: { position: 1, total: 1, nextVisitId: null, prevVisitId: null, headVisitId: null },
    gates,
    n: gates.reduce((s, g) => s + g.unresolved, 0),
    emArtifact: false,
    trail: { emAcknowledgedAt: null },
  };
}

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

// ⚠️ THE `applyRxResolved` DESCRIBE WAS REMOVED HERE — owner ruling #109 took
// the function with the surface that fed it. Seven tests went; the properties
// they pinned are all still pinned by `applyGateOverlay` below, which is what
// `applyRxResolved` was the narrow case of: identity on no signal, recount from
// the gates, keep a cleared gate PRESENT at zero, invent nothing, no mutation.

describe('firstBlockingGateTarget', () => {
  it('returns the first server-enforced gate that still blocks, in order', () => {
    expect(firstBlockingGateTarget([EM(1), ATTEST])).toBe('em_gate');
    expect(firstBlockingGateTarget([EM(0), ATTEST])).toBeNull();
  });

  it('NEVER returns attestation — it has no control to scroll to in B1', () => {
    // It is counted in N, and it is a real term in the contract with the
    // doctor. But there is nothing on this page to take them to, and scrolling
    // to nothing while reporting a successful navigation is the exact lie the
    // deferred-scroll seam exists to prevent.
    expect(firstBlockingGateTarget([ATTEST])).toBeNull();
    expect(firstBlockingGateTarget([EM(0), ATTEST])).toBeNull();
  });

  it('ignores a gate that applies but is already clear', () => {
    expect(firstBlockingGateTarget([EM(0), ATTEST])).toBeNull();
  });

  it('NEGATIVE CONTROL — it is capable of returning each target', () => {
    // Without this, "always null" would pass every assertion above except two,
    // and a refactor that broke the lookup table would look like a stricter
    // gate rather than a dead one.
    expect(firstBlockingGateTarget([EM(1)])).toBe('em_gate');
    expect(firstBlockingGateTarget([])).toBeNull();
  });
});

describe('applyGateOverlay', () => {
  it('returns the SAME OBJECT when no term applies', () => {
    // The result feeds a useMemo whose identity is handed to the stage; a fresh
    // object for a no-op overlay hands every consumer a new identity for
    // nothing.
    const d = data([EM(1), ATTEST]);
    expect(applyGateOverlay(d, {})).toBe(d);
    expect(applyGateOverlay(d, { emConfirmed: false, attested: false })).toBe(d);
  });

  it('zeroes the E/M and attestation terms independently', () => {
    // ⚠️ ASSERTED PER-GATE, NOT VIA `n`, AND THAT IS THE WHOLE POINT OF THE
    // WORD "INDEPENDENTLY". With exactly two gates left after ruling #109, `n`
    // reads 1 whichever one was zeroed — so an `n`-only version of this test
    // passes with the two arms SWAPPED. Mutation-proved: swapping them leaves
    // 1491 tests green, and the product failure that ships is a doctor
    // confirming the E/M level, the attestation term zeroing instead, and the
    // gate flow staying locked on a step they just cleared. That is an
    // unclearable block — the exact failure class ruling #109 exists to avoid.
    const d = data([EM(1), ATTEST]);

    const emOnly = applyGateOverlay(d, { emConfirmed: true });
    expect(emOnly.gates.find((g) => g.id === 'em')?.unresolved).toBe(0);
    expect(emOnly.gates.find((g) => g.id === 'attestation')?.unresolved).toBe(1);
    expect(emOnly.n).toBe(1);

    const attestOnly = applyGateOverlay(d, { attested: true });
    expect(attestOnly.gates.find((g) => g.id === 'attestation')?.unresolved).toBe(0);
    expect(attestOnly.gates.find((g) => g.id === 'em')?.unresolved).toBe(1);
    expect(attestOnly.n).toBe(1);

    expect(applyGateOverlay(d, { emConfirmed: true, attested: true }).n).toBe(0);
  });

  it('never removes a gate, and never invents one', () => {
    // "This visit has no E/M gate" and "this visit's E/M gate is clear" are
    // different claims and the strip draws them differently, so a cleared gate
    // stays PRESENT at zero. Filtering instead of mapping would collapse them.
    const out = applyGateOverlay(data([EM(1), ATTEST]), {
      emConfirmed: true,
      attested: true,
    });
    expect(out.gates.map((g) => g.id)).toEqual(['em', 'attestation']);
  });

  it('does not mutate its input', () => {
    const d = data([EM(1), ATTEST]);
    applyGateOverlay(d, { emConfirmed: true, attested: true });
    expect(d.gates.find((g) => g.id === 'em')?.unresolved).toBe(1);
    expect(d.n).toBe(2);
  });
});

describe('firstOpenStep', () => {
  it('is the first gate that still blocks', () => {
    expect(firstOpenStep([EM(1), ATTEST])).toBe('em');
    expect(firstOpenStep([EM(0), ATTEST])).toBe('attestation');
  });

  it('NEVER NULL on a non-empty set — with nothing outstanding it is the LAST gate', () => {
    // A flow that opened on "nothing" would be a full-screen dialog with no
    // content and no way forward. The last gate is where the signature is
    // taken, so that is the honest destination.
    expect(firstOpenStep([EM(0), { ...ATTEST, unresolved: 0 }])).toBe(
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

describe('the host-ref factory contract (regression: React #185)', () => {
  // Not a test of stage-view-model, but of the SHAPE the flow's hostRef must
  // have — recorded here because the defect it prevents is invisible in every
  // unit test and cost a whole E2E pack to find.
  //
  // A factory that returns a fresh arrow per call gives React a new ref
  // identity every render, so it detaches (ref ← null) and reattaches
  // (ref ← element) forever. The "bail when unchanged" guard cannot help: the
  // value really does alternate.
  function cachedFactory() {
    const cache: Record<string, (el: unknown) => void> = {};
    const sets: unknown[] = [];
    const factory = (id: string) => {
      cache[id] ??= (el: unknown) => sets.push(el);
      return cache[id];
    };
    return { factory, sets };
  }

  it('returns the SAME function for the same id', () => {
    const { factory } = cachedFactory();
    expect(factory('rx')).toBe(factory('rx'));
  });

  it('returns DIFFERENT functions for different ids', () => {
    const { factory } = cachedFactory();
    expect(factory('rx')).not.toBe(factory('em'));
  });

  it('NEGATIVE CONTROL — the naive factory does NOT hold the property', () => {
    // This is the exact code that shipped and looped. Kept so the difference
    // is visible rather than asserted.
    const naive = (id: string) => (el: unknown) => void [id, el];
    expect(naive('rx')).not.toBe(naive('rx'));
  });
});
