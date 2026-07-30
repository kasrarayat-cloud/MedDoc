// ============================================================================
// The applicable-unresolved-gate set for a visit — one derivation, two readers
// ----------------------------------------------------------------------------
// Rounds Screen 2 puts a number on the Signed node: "N blockers before Signed".
// That number is a PROMISE about what `POST /api/visits/[id]/sign` will do, and
// a promise the server does not keep is worse than no number at all — a doctor
// who reads "0 blockers" and is then refused has been told the wrong thing by
// the surface whose whole job is to be believed.
//
// So the count is not computed in the component. It is computed here, from the
// same primitives the sign route validates against, and both the page (server,
// baseline) and the strip (client, live overlay) call this one function.
//
// THREE THINGS THE ROUTE DOES THAT A PLAIN READING OF THE SPEC GETS WRONG.
// Each was read off `sign/route.ts` rather than assumed:
//
//  1. **`emStale` is NOT a blocker.** The route RE-SCORES a stale level and
//     carries on; it only refuses when the re-score itself fails. Counting
//     stale as +1 would make the strip claim a blocker the server does not
//     have. It renders as a `needs_recheck` note on the E/M node instead.
//
//  2. **Attestation is not server-enforced at all.** The sign body schema is
//     `{destinations, emailTo?, acknowledgedEmChange?}` — there is no
//     attestation field and no refusal keyed on one. It is a real gate in the
//     UI's contract with the doctor, and it is counted, but it is marked
//     `serverEnforced: false` so that anyone reconciling this strip against a
//     422 is told which term the server cannot see.
//
//  3. **The route's E/M refusal is NOT conditioned on the specialty.** Only the
//     stale re-score branch checks `emAppliesToSpecialty`; the unacknowledged-
//     change refusal fires on any visit carrying such a record. The Rounds
//     invariant is that an imaging visit has no E/M gate — "absent, not hidden,
//     not disabled" — so this returns no `em` gate for imaging. That is correct
//     AND it opens a gap: an imaging visit that somehow holds an unacknowledged
//     E/M change would show no gate while the server returns 400.
//
//     That combination is not hypothetical. Five imaging visits acquired office
//     E/M state in production and sat there for two days
//     (`scripts/check-imaging-em-artifacts.sh` exists because of it). So rather
//     than silently promise a sign that will be refused, the gap is NAMED:
//     `emArtifact` goes true, and the caller renders an anomaly instead of a
//     clean zero. "I cannot establish this" must never render as "fine" —
//     the same rule the post-reboot proof learned the hard way.
//
// PURE. No React, no Prisma, no I/O — so the client can re-run it on every
// keystroke of state and the server can run it during render.
//
// Deliberately NOT under `src/lib/rounds/`. The sign route imports the Rx
// half, and item F deletes the skin namespace; a route must not import from a
// directory scheduled for deletion.
// ============================================================================

import { emAppliesToSpecialty } from '@meddoc/shared/specialties';

import { unacknowledgedEmChange } from './em-pending-change';
import { criticalWarningRefs } from './rx-warnings';

export type SignGateId = 'rx' | 'em' | 'attestation';

export interface SignGate {
  id: SignGateId;
  /**
   * How many distinct things the doctor must still do for THIS gate.
   *
   * A gate that does not apply to the visit is ABSENT from the array — never
   * present with `unresolved: 0`. The two are different claims: "this visit
   * has no E/M level" and "this visit's E/M level is confirmed" must not
   * render the same, because an imaging report can only ever be the first.
   */
  unresolved: number;
  /**
   * Whether `POST /sign` can refuse on this gate.
   *
   * `false` for `attestation` only. Everything else in this array corresponds
   * to a real server-side refusal with a status code.
   */
  serverEnforced: boolean;
  /**
   * `needs_recheck` when the level is stale and E/M applies. The route
   * re-scores rather than refusing, so this is a STATE, never a count.
   */
  note?: 'needs_recheck';
}

export interface SignGateInput {
  /** The raw `TranscribeVisit.rxDrafts` jsonb. Shape-checked downstream. */
  rxDrafts: unknown;
  /**
   * `warningId`s that already carry a persisted `RxWarningOverride` row with
   * `severity: 'critical'`. The server keys coverage on these same real ids —
   * a fabricated id clears nothing, here or there.
   */
  overriddenWarningIds: readonly string[];
  /**
   * The RAW `specialty` column off Prisma — an **id**, never a display label.
   * `findSpecialty('Ultrasound').id` is `'unspecified'`: quietly the wrong
   * specialty, no throw. That exact mistake made every ultrasound visit
   * compute an office E/M level once already.
   */
  specialty: string | null | undefined;
  /** The raw `emPendingChange` jsonb. Coerced here, fail-closed. */
  emPendingChange: unknown;
  /** The `emStale` column. Renders as a note; never a count. */
  emStale?: boolean;
  /**
   * Client-only overlay: the doctor confirmed the level in THIS session and
   * the page has not been refetched. Server callers pass nothing.
   */
  emConfirmedThisSession?: boolean;
  /** Client-only overlay: the attestation checkbox. */
  attested?: boolean;
}

export interface SignGateSet {
  /** Applicable gates only. An inapplicable gate is absent, not zeroed. */
  gates: SignGate[];
  /** Σ `unresolved`. This is the N on the padlocked Signed node. */
  n: number;
  /**
   * An imaging visit is carrying an unacknowledged E/M change — a data
   * artifact. There is no E/M gate to show (the invariant forbids one), but
   * the server WILL refuse the sign, so the caller must surface this rather
   * than render a clean zero. Expected to be `false` for every real visit;
   * `scripts/check-imaging-em-artifacts.sh` is the standing watch on it.
   */
  emArtifact: boolean;
}

/**
 * Unmet critical Rx warnings: every persisted critical warning without a
 * matching override, keyed by real id.
 *
 * Exported so `POST /sign` can adopt it and the two cannot diverge — the
 * inline version there predates this module and is otherwise a second copy of
 * an identity that has already been got wrong once (the override-count
 * inflation bypass, fix/rx-override-gate-correlation).
 */
export function unmetCriticalWarnings(
  rxDrafts: unknown,
  overriddenWarningIds: readonly string[]
): ReturnType<typeof criticalWarningRefs> {
  const covered = new Set(overriddenWarningIds);
  return criticalWarningRefs(rxDrafts).filter((ref) => !covered.has(ref.id));
}

/**
 * The gates that apply to this visit, and how many things each still needs.
 *
 * Order is the order the doctor meets them in Screen 3: Rx, then E/M, then
 * attestation. Screen 2's strip renders the same order.
 */
export function signGates(input: SignGateInput): SignGateSet {
  const gates: SignGate[] = [];

  // ── Gate 1 — critical Rx ────────────────────────────────────────────────
  // Present whenever the visit HAS critical warnings. A visit with none has no
  // Rx gate to clear, which is not the same as having cleared one.
  const criticalCount = criticalWarningRefs(input.rxDrafts).length;
  if (criticalCount > 0) {
    gates.push({
      id: 'rx',
      unresolved: unmetCriticalWarnings(input.rxDrafts, input.overriddenWarningIds)
        .length,
      serverEnforced: true,
    });
  }

  // ── Gate 2 — E/M ────────────────────────────────────────────────────────
  // THE ONE SWITCH decides whether this gate exists at all. Never re-type the
  // conjunction; it has been spelled wrong before and the failure was silent.
  const emApplies = emAppliesToSpecialty(input.specialty);
  const pendingEm = unacknowledgedEmChange(input.emPendingChange);
  const emUnconfirmed = pendingEm !== null && !input.emConfirmedThisSession;

  let emArtifact = false;
  if (emApplies) {
    const stale = input.emStale === true;
    // The gate EXISTS on every applicable visit — Screen 3 shows the level and
    // asks about it — but it only COUNTS when there is something the server
    // will refuse without: an unacknowledged pending change.
    //
    // ⚠️ B2 OWNS THE OPEN HALF OF THIS. SPEC.md:101–104 ("critical Rx count +
    // E/M where emApplies + attestation") can be read as +1 on every applicable
    // visit, and SPEC.md:143–146 describes Gate 2 as a CONFIRM step that exists
    // whenever E/M applies. If B2 decides the doctor must actively confirm a
    // level that nothing changed, that is a UI-only term exactly like
    // attestation, and it belongs here with `serverEnforced: false` — not
    // folded into this branch, which is the server's term.
    //
    // B1 deliberately does not guess: counting a blocker the route will not
    // enforce makes the strip lie in the safe-looking direction, and "0
    // blockers" that the server then refuses is the same defect mirrored. The
    // shape below carries existence and count separately so B2 can settle it
    // without redesigning the type.
    gates.push({
      id: 'em',
      unresolved: emUnconfirmed ? 1 : 0,
      serverEnforced: true,
      ...(stale ? { note: 'needs_recheck' as const } : {}),
    });
  } else if (pendingEm !== null) {
    // Imaging, carrying office-visit E/M state. No gate — the invariant is
    // absolute — but the server does not share the invariant and will refuse.
    // Say so rather than promise a sign that cannot happen.
    emArtifact = true;
  }

  // ── Gate 3 — attestation ────────────────────────────────────────────────
  // Always applicable, never server-enforced. See the header.
  gates.push({
    id: 'attestation',
    unresolved: input.attested ? 0 : 1,
    serverEnforced: false,
  });

  return { gates, n: blockerCount(gates), emArtifact };
}

/** Σ of every applicable gate's unresolved count. */
export function blockerCount(gates: readonly SignGate[]): number {
  return gates.reduce((sum, g) => sum + g.unresolved, 0);
}
