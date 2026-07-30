// ============================================================================
// The applicable-unresolved-gate set — units + negative controls
// ----------------------------------------------------------------------------
// Every assertion here that says "X is absent" is paired with one that says
// "X is present", because an absence test passes against a function that
// returns nothing at all. That is the defect this suite exists downstream of:
// the post-reboot proof printed "every container is up" against ZERO
// containers, three times over, because each check asked "is anything wrong?"
// of a set whose size it never established.
//
// The flag matters: `emAppliesToSpecialty` is
// `!(ultrasoundSpecialtyEnabled() && isImagingReportSpecialty(id))`, so with
// NEXT_PUBLIC_ULTRASOUND_SPECIALTY unset EVERY specialty applies and the
// imaging cases below would pass for the wrong reason. It is set explicitly.
// ============================================================================

import { afterEach, beforeEach, describe, expect, it } from 'vitest';

import {
  blockerCount,
  signGates,
  unmetCriticalWarnings,
  type SignGateInput,
} from '../sign-gates';

const PRIMARY = 'primary-care';
const IMAGING = 'ultrasound';

/** Two critical warnings and one non-critical, in the shape L7c persists. */
const RX_TWO_CRITICAL = {
  warnings: [
    { severity: 'critical', rx_drug: 'warfarin', message: 'interaction' },
    { severity: 'major', rx_drug: 'aspirin', message: 'advisory' },
    { severity: 'critical', rx_drug: 'amiodarone', message: 'interaction' },
  ],
};

/** Positional ids for the two critical warnings above (indices 0 and 2). */
const CRIT_A = 'rx-warning-0';
const CRIT_B = 'rx-warning-2';

const PENDING_EM = { from: '99213', to: '99214', cause: 'note_edited', at: '2026-07-30T00:00:00Z' };

function input(over: Partial<SignGateInput> = {}): SignGateInput {
  return {
    rxDrafts: null,
    overriddenWarningIds: [],
    specialty: PRIMARY,
    emPendingChange: null,
    ...over,
  };
}

const gateIds = (i: SignGateInput) => signGates(i).gates.map((g) => g.id);
const gate = (i: SignGateInput, id: string) =>
  signGates(i).gates.find((g) => g.id === id);

let priorFlag: string | undefined;
beforeEach(() => {
  priorFlag = process.env.NEXT_PUBLIC_ULTRASOUND_SPECIALTY;
  process.env.NEXT_PUBLIC_ULTRASOUND_SPECIALTY = 'true';
});
afterEach(() => {
  if (priorFlag === undefined) delete process.env.NEXT_PUBLIC_ULTRASOUND_SPECIALTY;
  else process.env.NEXT_PUBLIC_ULTRASOUND_SPECIALTY = priorFlag;
});

// ── Rx ────────────────────────────────────────────────────────────────────
describe('critical Rx coverage', () => {
  it('counts every critical warning without an override', () => {
    const g = gate(input({ rxDrafts: RX_TWO_CRITICAL }), 'rx');
    expect(g?.unresolved).toBe(2);
  });

  it('a real override id clears exactly one', () => {
    const g = gate(
      input({ rxDrafts: RX_TWO_CRITICAL, overriddenWarningIds: [CRIT_A] }),
      'rx'
    );
    expect(g?.unresolved).toBe(1);
  });

  it('a FABRICATED override id clears nothing', () => {
    for (const fake of ['x1', 'rx-warning-abc', 'rx-warning-99', CRIT_A + ' ']) {
      const g = gate(
        input({ rxDrafts: RX_TWO_CRITICAL, overriddenWarningIds: [fake] }),
        'rx'
      );
      expect(g?.unresolved, `fabricated id ${fake}`).toBe(2);
    }
  });

  it('NEGATIVE CONTROL — the same shape with a REAL id does clear it', () => {
    // Without this, the test above passes against a function that never
    // clears anything at all.
    const g = gate(
      input({ rxDrafts: RX_TWO_CRITICAL, overriddenWarningIds: [CRIT_A, CRIT_B] }),
      'rx'
    );
    expect(g?.unresolved).toBe(0);
  });

  it('is ABSENT when the visit has no critical warnings', () => {
    expect(gateIds(input({ rxDrafts: { warnings: [{ severity: 'major' }] } })))
      .not.toContain('rx');
  });

  it('NEGATIVE CONTROL — present when it does have one', () => {
    expect(gateIds(input({ rxDrafts: RX_TWO_CRITICAL }))).toContain('rx');
  });

  it('non-critical warnings never count', () => {
    const g = gate(input({ rxDrafts: RX_TWO_CRITICAL }), 'rx');
    // three warnings persisted, only two are critical
    expect(g?.unresolved).toBe(2);
  });

  it('unmetCriticalWarnings returns the refs the 422 body is built from', () => {
    const unmet = unmetCriticalWarnings(RX_TWO_CRITICAL, [CRIT_A]);
    expect(unmet.map((r) => r.id)).toEqual([CRIT_B]);
    expect(unmet[0]?.warning.rx_drug).toBe('amiodarone');
  });

  it('tolerates a malformed rxDrafts blob', () => {
    for (const blob of [null, undefined, {}, { warnings: 'nope' }, 42]) {
      expect(() => signGates(input({ rxDrafts: blob }))).not.toThrow();
      expect(gateIds(input({ rxDrafts: blob }))).not.toContain('rx');
    }
  });
});

// ── E/M ───────────────────────────────────────────────────────────────────
describe('E/M applicability — the one switch', () => {
  it('an IMAGING visit has NO E/M gate', () => {
    expect(gateIds(input({ specialty: IMAGING }))).not.toContain('em');
  });

  it('NEGATIVE CONTROL — a primary-care visit DOES have one', () => {
    // Without this, the test above passes against a function returning [].
    expect(gateIds(input({ specialty: PRIMARY }))).toContain('em');
  });

  it('the gate is absent, not present-and-zero', () => {
    // "no E/M level exists" and "the E/M level is confirmed" are different
    // claims and must not render the same.
    const set = signGates(input({ specialty: IMAGING }));
    expect(set.gates.find((g) => g.id === 'em')).toBeUndefined();
  });

  it('counts 1 only when a pending change is unacknowledged', () => {
    expect(gate(input({ emPendingChange: PENDING_EM }), 'em')?.unresolved).toBe(1);
    expect(gate(input({ emPendingChange: null }), 'em')?.unresolved).toBe(0);
  });

  it('an already-acknowledged change does not count', () => {
    const acked = { ...PENDING_EM, acknowledgedAt: '2026-07-30T01:00:00Z' };
    expect(gate(input({ emPendingChange: acked }), 'em')?.unresolved).toBe(0);
  });

  it('a session confirm clears it without a refetch', () => {
    expect(
      gate(input({ emPendingChange: PENDING_EM, emConfirmedThisSession: true }), 'em')
        ?.unresolved
    ).toBe(0);
  });

  it('FAILS CLOSED on a malformed pending change', () => {
    // unacknowledgedEmChange coerces present-but-malformed to the
    // unknown→unknown sentinel rather than null, so the sign stays blocked.
    for (const junk of [{ nonsense: true }, 'garbage', 7, []]) {
      expect(gate(input({ emPendingChange: junk }), 'em')?.unresolved, String(junk))
        .toBe(1);
    }
  });

  it('staleness is a NOTE, never a count — the route re-scores, it does not refuse', () => {
    const g = gate(input({ emStale: true }), 'em');
    expect(g?.note).toBe('needs_recheck');
    expect(g?.unresolved).toBe(0);
  });

  it('NEGATIVE CONTROL — no note when not stale', () => {
    expect(gate(input({ emStale: false }), 'em')?.note).toBeUndefined();
  });

  it('staleness on an imaging visit produces nothing at all', () => {
    // A staleness gate over a level that does not exist would make an
    // ultrasound report permanently unsignable.
    expect(gateIds(input({ specialty: IMAGING, emStale: true }))).not.toContain('em');
  });
});

// ── The imaging artifact gap ──────────────────────────────────────────────
describe('imaging carrying office E/M state — the named gap', () => {
  it('reports emArtifact instead of a silent clean zero', () => {
    // The route's unacknowledged-change refusal is NOT conditioned on
    // specialty, so this visit WILL be refused while the invariant forbids
    // showing an E/M gate. Never promise a sign that cannot happen.
    const set = signGates(input({ specialty: IMAGING, emPendingChange: PENDING_EM }));
    expect(set.emArtifact).toBe(true);
    expect(set.gates.find((g) => g.id === 'em')).toBeUndefined();
  });

  it('NEGATIVE CONTROL — false for a clean imaging visit', () => {
    expect(signGates(input({ specialty: IMAGING })).emArtifact).toBe(false);
  });

  it('NEGATIVE CONTROL — false for primary care, which has a real gate instead', () => {
    const set = signGates(input({ specialty: PRIMARY, emPendingChange: PENDING_EM }));
    expect(set.emArtifact).toBe(false);
    expect(set.gates.find((g) => g.id === 'em')?.unresolved).toBe(1);
  });
});

// ── Attestation ───────────────────────────────────────────────────────────
describe('attestation', () => {
  it('is always applicable', () => {
    expect(gateIds(input({ specialty: IMAGING }))).toContain('attestation');
    expect(gateIds(input({ specialty: PRIMARY }))).toContain('attestation');
  });

  it('is marked NOT server-enforced — POST /sign has no attestation field', () => {
    expect(gate(input(), 'attestation')?.serverEnforced).toBe(false);
  });

  it('NEGATIVE CONTROL — the other gates ARE server-enforced', () => {
    expect(gate(input({ rxDrafts: RX_TWO_CRITICAL }), 'rx')?.serverEnforced).toBe(true);
    expect(gate(input(), 'em')?.serverEnforced).toBe(true);
  });

  it('clears when attested', () => {
    expect(gate(input({ attested: true }), 'attestation')?.unresolved).toBe(0);
  });
});

// ── N ─────────────────────────────────────────────────────────────────────
describe('N — the number on the padlocked Signed node', () => {
  it('sums every applicable unresolved gate', () => {
    // 2 unmet critical Rx + 1 unconfirmed E/M + 1 attestation
    const set = signGates(
      input({ rxDrafts: RX_TWO_CRITICAL, emPendingChange: PENDING_EM })
    );
    expect(set.n).toBe(4);
  });

  it('ticks down as each gate clears', () => {
    const base = { rxDrafts: RX_TWO_CRITICAL, emPendingChange: PENDING_EM };
    expect(signGates(input(base)).n).toBe(4);
    expect(signGates(input({ ...base, overriddenWarningIds: [CRIT_A] })).n).toBe(3);
    expect(
      signGates(input({ ...base, overriddenWarningIds: [CRIT_A, CRIT_B] })).n
    ).toBe(2);
    expect(
      signGates(
        input({ ...base, overriddenWarningIds: [CRIT_A, CRIT_B], emConfirmedThisSession: true })
      ).n
    ).toBe(1);
    expect(
      signGates(
        input({
          ...base,
          overriddenWarningIds: [CRIT_A, CRIT_B],
          emConfirmedThisSession: true,
          attested: true,
        })
      ).n
    ).toBe(0);
  });

  it('an imaging visit never carries the E/M term', () => {
    const common = { rxDrafts: RX_TWO_CRITICAL, emPendingChange: null };
    const care = signGates(input({ ...common, specialty: PRIMARY })).n;
    const imaging = signGates(input({ ...common, specialty: IMAGING })).n;
    // both 2 unmet Rx + 1 attestation; primary-care's E/M gate is satisfied
    // (nothing pending) so the totals match here — the difference is that
    // imaging has no gate to satisfy in the first place.
    expect(care).toBe(3);
    expect(imaging).toBe(3);
    expect(gateIds(input({ ...common, specialty: IMAGING }))).toEqual([
      'rx',
      'attestation',
    ]);
    expect(gateIds(input({ ...common, specialty: PRIMARY }))).toEqual([
      'rx',
      'em',
      'attestation',
    ]);
  });

  it('an unconfirmed E/M change is worth exactly one, and imaging cannot have it', () => {
    const withPending = { rxDrafts: null, emPendingChange: PENDING_EM };
    expect(signGates(input({ ...withPending, specialty: PRIMARY })).n).toBe(2);
    expect(signGates(input({ ...withPending, specialty: IMAGING })).n).toBe(1);
  });

  it('blockerCount is the sum of the array it is given', () => {
    expect(blockerCount([])).toBe(0);
    expect(
      blockerCount([
        { id: 'rx', unresolved: 3, serverEnforced: true },
        { id: 'attestation', unresolved: 1, serverEnforced: false },
      ])
    ).toBe(4);
  });

  it('gate order is the order Screen 3 presents them', () => {
    expect(gateIds(input({ rxDrafts: RX_TWO_CRITICAL }))).toEqual([
      'rx',
      'em',
      'attestation',
    ]);
  });
});
