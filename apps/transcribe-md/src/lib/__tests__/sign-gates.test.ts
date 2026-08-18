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

import { readFileSync } from 'node:fs';

import { afterEach, beforeEach, describe, expect, it } from 'vitest';

import {
  blockerCount,
  signGates,
  type SignGateInput,
  type SignGateId,
} from '../sign-gates';

const PRIMARY = 'primary-care';
const IMAGING = 'ultrasound';

const PENDING_EM = { from: '99213', to: '99214', cause: 'note_edited', at: '2026-07-30T00:00:00Z' };

function input(over: Partial<SignGateInput> = {}): SignGateInput {
  return {
    specialty: PRIMARY,
    // F12 / ruling #123 — the note-SHAPE axis. `null` is "no template", which
    // is explicitly NOT an operative note, so every existing arm below keeps
    // the exact behaviour it asserted before the axis existed.
    templateSections: null,
    // F12-a / ruling #126 — the note-text fallback. An empty body carries no
    // headings and therefore no markers, so every existing arm below keeps the
    // exact behaviour it asserted before the fallback existed.
    noteText: '',
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

// ⚠️ THE `critical Rx coverage` DESCRIBE WAS REMOVED HERE — owner ruling #109
// retired the gate. It proved the thing worth remembering if the gate ever
// returns: coverage was keyed on REAL positional ids, so a fabricated or
// duplicated override id cleared nothing. That property is what made the gate
// meaningful, and it is the property to rebuild first.

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

  it('IS server-enforced — POST /sign refuses without an attestation', () => {
    // ⚠️ THIS TEST INVERTED ON 2026-08-02, AND THE OLD ASSERTION WAS THE
    // WARNING LABEL ON A REAL HOLE. It read "is marked NOT server-enforced —
    // POST /sign has no attestation field" and it was accurate: nothing on the
    // server could see this gate. Then a second sign control shipped that did
    // not count it either, and a signature could pass the attestation with no
    // refusal and no audit row. Measured on production.
    // Gates only gain requirements. The route now carries the field.
    expect(gate(input(), 'attestation')?.serverEnforced).toBe(true);

    // AND THE ROUTE REALLY HAS IT — a flag flipped in this file with no term
    // behind it would be the same lie in the other direction.
    const route = readFileSync(
      'src/app/api/visits/[id]/sign/route.ts',
      'utf8',
    );
    expect(route).toMatch(/attestation:\s*z$/m);
    expect(route).toContain("code: 'ATTESTATION_REQUIRED'");
    expect(route).toContain("action: 'SIGN_BLOCKED_NO_ATTESTATION'");
  });

  it('NEGATIVE CONTROL — the other gate IS server-enforced', () => {
    expect(gate(input(), 'em')?.serverEnforced).toBe(true);
  });

  it('clears when attested', () => {
    expect(gate(input({ attested: true }), 'attestation')?.unresolved).toBe(0);
  });
});

// ── N ─────────────────────────────────────────────────────────────────────
describe('N — the number on the padlocked Signed node', () => {
  it('sums every applicable unresolved gate', () => {
    // 1 unconfirmed E/M + 1 attestation
    const set = signGates(input({ emPendingChange: PENDING_EM }));
    expect(set.n).toBe(2);
  });

  it('ticks down as each gate clears', () => {
    const base = { emPendingChange: PENDING_EM };
    expect(signGates(input(base)).n).toBe(2);
    expect(
      signGates(input({ ...base, emConfirmedThisSession: true })).n
    ).toBe(1);
    expect(
      signGates(
        input({ ...base, emConfirmedThisSession: true, attested: true })
      ).n
    ).toBe(0);
  });

  it('an imaging visit never carries the E/M term', () => {
    const common = { emPendingChange: null };
    const care = signGates(input({ ...common, specialty: PRIMARY })).n;
    const imaging = signGates(input({ ...common, specialty: IMAGING })).n;
    // Both 1 attestation; primary-care's E/M gate is satisfied (nothing
    // pending) so the totals match here — the difference is that imaging has
    // no gate to satisfy in the first place.
    expect(care).toBe(1);
    expect(imaging).toBe(1);
    expect(gateIds(input({ ...common, specialty: IMAGING }))).toEqual([
      'attestation',
    ]);
    expect(gateIds(input({ ...common, specialty: PRIMARY }))).toEqual([
      'em',
      'attestation',
    ]);
  });

  it('an unconfirmed E/M change is worth exactly one, and imaging cannot have it', () => {
    const withPending = { emPendingChange: PENDING_EM };
    expect(signGates(input({ ...withPending, specialty: PRIMARY })).n).toBe(2);
    expect(signGates(input({ ...withPending, specialty: IMAGING })).n).toBe(1);
  });

  it('blockerCount is the sum of the array it is given', () => {
    expect(blockerCount([])).toBe(0);
    expect(
      blockerCount([
        { id: 'em', unresolved: 3, serverEnforced: true },
        { id: 'attestation', unresolved: 1, serverEnforced: false },
      ])
    ).toBe(4);
  });

  it('gate order is the order Screen 3 presents them', () => {
    expect(gateIds(input())).toEqual(['em', 'attestation']);
  });
});

describe('THE B2 RULING — the E/M gate exists always, counts only when the server refuses', () => {
  // B1 left this open in a comment; B2 settled it. The ruling matters because
  // it is otherwise INVISIBLE: the primary-care E2E fixture already carries a
  // pending change and the imaging one has no E/M gate at all, so a build that
  // switched to "+1 on every applicable visit" would redden nothing. These are
  // the assertions that can only pass under the ruling.
  beforeEach(() => {
    process.env.NEXT_PUBLIC_ULTRASOUND_SPECIALTY = 'true';
  });
  afterEach(() => {
    delete process.env.NEXT_PUBLIC_ULTRASOUND_SPECIALTY;
  });

  it('a QUIET applicable level contributes ZERO — the route would not refuse', () => {
    // With no pending record the route skips the E/M branch entirely and the
    // sign SUCCEEDS. Counting it would be a blocker the server does not have,
    // which makes the padlock lie in the safe-looking direction.
    const set = signGates(input({ specialty: PRIMARY, emPendingChange: null }));
    const em = set.gates.find((g) => g.id === 'em');
    expect(em, 'the gate must still EXIST — Screen 3 shows the level').toBeTruthy();
    expect(em!.unresolved).toBe(0);
  });

  it('so a clean primary-care visit is attestation-only', () => {
    // 1, not 2. This is the number a "+1 always" build would change.
    const set = signGates(input({ specialty: PRIMARY, emPendingChange: null }));
    expect(set.n).toBe(1);
    expect(set.gates.filter((g) => g.unresolved > 0).map((g) => g.id)).toEqual([
      'attestation',
    ]);
  });

  it('NEGATIVE CONTROL — an unacknowledged change DOES count', () => {
    // Without this, "always zero" would satisfy the two assertions above and
    // the gate would be dead rather than correct.
    const set = signGates(
      input({ specialty: PRIMARY, emPendingChange: PENDING_EM })
    );
    expect(set.gates.find((g) => g.id === 'em')!.unresolved).toBe(1);
    expect(set.n).toBe(2);
  });

  it('existence and count stay SEPARATE — that is what carried the ruling', () => {
    // Existence is membership in the array; the count is `unresolved`. A future
    // "confirm a quiet level" term is UI-only and belongs as its own entry with
    // serverEnforced:false, never folded into this one.
    const quiet = signGates(input({ specialty: PRIMARY, emPendingChange: null }));
    const pending = signGates(
      input({ specialty: PRIMARY, emPendingChange: PENDING_EM })
    );
    expect(quiet.gates.map((g) => g.id)).toEqual(pending.gates.map((g) => g.id));
    expect(quiet.n).not.toBe(pending.n);
  });

  it('every gate reported as server-enforced corresponds to a real refusal', () => {
    // The contract that makes N a promise about POST /sign. Since 2026-08-02
    // there is no exception: EVERY gate the strip counts has a refusal behind
    // it, attestation included.
    const set = signGates(input({ specialty: PRIMARY, emPendingChange: PENDING_EM }));
    // This fixture has no critical Rx, so the applicable set is {em, attestation}.
    expect(set.gates.length, 'no gates — this loop would assert nothing').toBeGreaterThanOrEqual(2);
    for (const g of set.gates) {
      expect(g.serverEnforced, `${g.id} claims a refusal the route may not have`).toBe(true);
    }

    // Each one names a refusal code in the route. A gate whose enforcement is
    // asserted here but absent there is the exact drift this test exists for.
    //
    // ⚠️ TWO DEFECTS WERE FIXED HERE AT ONCE, BOTH FOUND BY REFUTATION, AND
    // BOTH ARE THIS REPO'S OWN NAMED CLASSES.
    //
    //  1. THE LIST WAS HAND-KEPT. It was frozen at three codes while the loop
    //     above iterates the LIVE gate set. Ruling #109 took the gate set to
    //     two and the list stayed at three, so the test demanded a refusal code
    //     for a gate that no longer exists. The list is now DERIVED from the
    //     same `set.gates` the loop uses — one source, so it cannot go stale
    //     again. ("A gate's WATCHED SET is diffed against the spec's NAMED
    //     set", arriving through a stale constant.)
    //
    //  2. IT MATCHED AGAINST PROSE. `OVERRIDE_REQUIRED` still occurs EXACTLY
    //     ONCE in the route — inside the comment recording the gate's removal.
    //     So the assertion passed on the strength of a sentence describing the
    //     absence of the very thing it claims to verify, and rewording that
    //     comment would have turned the suite red for a documentation edit.
    //     Comments are stripped first, exactly as `gate-flow.test.tsx` does.
    const CODE_FOR: Record<SignGateId, string> = {
      em: 'EM_CHANGE_UNACKNOWLEDGED',
      attestation: 'ATTESTATION_REQUIRED',
    };
    const routeSrc = readFileSync('src/app/api/visits/[id]/sign/route.ts', 'utf8');
    const routeCode = routeSrc
      .replace(/\/\*[\s\S]*?\*\//g, ' ')
      .replace(/^\s*\/\/.*$/gm, ' ');

    // NON-VACUITY: the stripper must not have eaten the file. Without this, a
    // regex that removed everything would pass every assertion below by
    // finding nothing to contradict — and this test would be measuring a blank
    // string.
    expect(routeCode).toContain('export const POST = withApiHandler');

    for (const g of set.gates) {
      expect(routeCode, `${g.id} is not refused by the route`).toContain(CODE_FOR[g.id]);
    }

    // …and the retired code is gone from the CODE, while surviving in the
    // prose that explains its removal. Both halves asserted, because a bare
    // `not.toContain` over the raw file would fail on the comment.
    expect(routeCode).not.toContain('OVERRIDE_REQUIRED');
    expect(routeSrc).toContain('OVERRIDE_REQUIRED');
  });
});
