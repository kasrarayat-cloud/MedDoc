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
//  2. **Attestation IS server-enforced, since 2026-08-02.** It was not, and the
//     cost of that arrived exactly as this note predicted it could: the sign
//     body schema was `{destinations, emailTo?, acknowledgedEmChange?}` with no
//     attestation field and no refusal keyed on one, so the gate lived only in
//     the UI's contract with the doctor. A second sign control then shipped
//     that did not count the gate — and with nothing on the server counting it
//     either, a signature could pass it without refusal and without an audit
//     row. Measured on production 2026-08-02.
//     The body schema now carries `attestation: { acknowledged: true }`, and a
//     request without it is refused 400 `ATTESTATION_REQUIRED` with a
//     `SIGN_BLOCKED_NO_ATTESTATION` audit row. **A gate that nothing enforces
//     is one alternate path away from not existing.**
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

/**
 * ⚠️ `'rx'` WAS REMOVED FROM THIS UNION BY OWNER RULING #109, AND THE UNION IS
 * WHY THE REMOVAL COULD BE ENUMERATED AT ALL.
 *
 * The Prescription Safety SURFACE was deleted — the tab, the advisory rail, the
 * ADD RX affordance — and the gate came out WITH the face, deliberately, in the
 * same change. **A doctor blocked by a warning with no surface is the
 * invisible-refusal class we never ship**: a 422 they cannot act on, pointing at
 * a screen that no longer exists.
 *
 * ⚠️ GATES ONLY SHED REQUIREMENTS BY OWNER RULING. This is one (#109). The E/M
 * and attestation gates are UNTOUCHED — their packs re-run with expected sets
 * re-declared, and the retired rx arms carry notes rather than vanishing.
 *
 * ⚠️ AND THE OTHER DEFINITION DIED IN THE SAME COMMIT. `sign/route.ts` carried
 * its own independent coverage check. Removing one and not the other produces
 * the exact failure this ruling forbids, in its purest form: no surface, no gate
 * chip, and the server still refusing.
 *
 * PIPELINE EXTRACTION IS UNTOUCHED: `lib/rx-warnings.ts`, L7c's drafting and
 * `rx-warning-audit.ts` all survive. The owner removed the panel that DISPLAYS
 * prescriptions, not the layer that produces them, and that data path's
 * disposition is its own later decision.
 */
export type SignGateId = 'em' | 'attestation';

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
  // ⚠️ `rxDrafts` and `overriddenWarningIds` WERE REMOVED HERE (#109), and the
  // removal is what let `tsc` enumerate the callers rather than a hand-kept
  // list. They fed the retired Rx gate and nothing else in this module reads
  // them. Leaving them as accepted-but-ignored inputs would have been the
  // quieter change and a worse one: every caller would keep computing and
  // passing an override set for a gate that no longer exists, and the next
  // reader would have no way to tell live plumbing from dead.
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
 * The gates that apply to this visit, and how many things each still needs.
 *
 * Order is the order the doctor meets them in Screen 3: E/M, then attestation.
 * Screen 2's strip renders the same order.
 *
 * ⚠️ Rx used to be FIRST. Its removal leaves the surviving order intact — and
 * that is worth stating because `sign/route.ts` records what happened when the
 * order last moved: attestation sat first, "jumped the queue", and a visit with
 * a moved E/M level answered ATTESTATION_REQUIRED instead of naming the level.
 * Removing the head of a list is safe in a way that reordering its tail is not.
 */
export function signGates(input: SignGateInput): SignGateSet {
  const gates: SignGate[] = [];

  // ── Gate 1 — E/M ────────────────────────────────────────────────────────
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
    // ✅ SETTLED BY B2, and the shape below is unchanged by the ruling.
    //
    // THE QUESTION B1 LEFT OPEN: does this gate count +1 on EVERY applicable
    // visit (a confirm step the doctor must always clear), or only when there
    // is something the server will refuse without?
    //
    // **Only when the server will refuse.** Three readings agree:
    //
    //  1. SPEC.md:101–104 — "N = this visit's applicable UNRESOLVED gates:
    //     critical Rx COUNT + E/M where `emApplies` + attestation". "where
    //     `emApplies`" scopes WHICH gates are applicable; "unresolved" and
    //     "count" are what each contributes. Under a +1-always reading,
    //     "critical Rx count" would have to mean +1-always too — and it plainly
    //     does not.
    //  2. SPEC.md:143–146 describes Gate 2's CONTENT (the level, confidence,
    //     rationale, the amber CONFIRM, "Change code"). That establishes the
    //     gate EXISTS, which it does, on every applicable visit. Existence is
    //     membership in this array; the count is `unresolved`. The type already
    //     carried both separately, which is why the ruling needs no redesign.
    //  3. The route decides it. With no pending record `unacknowledgedEmChange`
    //     returns null, the refusal branch in `sign/route.ts` is skipped
    //     entirely, and the sign SUCCEEDS. A +1 here would be a blocker the
    //     server does not have — the strip lying in the safe-looking direction,
    //     which is the one thing this module exists to prevent.
    //
    // SPEC.md's binding constraint settles any residual doubt: "Server refusals
    // remain the sole source of truth — the gates are UI over them."
    //
    // STILL TRUE, and still the instruction: if a future item decides the doctor
    // must actively confirm a level that NOTHING changed, that is a UI-only term
    // exactly like attestation. It belongs as its own entry with
    // `serverEnforced: false` — never folded into this branch, which is the
    // server's term and must keep meaning "the route will refuse without this".
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

  // ── Gate 2 — attestation ────────────────────────────────────────────────
  // Always applicable, and SERVER-ENFORCED since 2026-08-02. See the header.
  gates.push({
    id: 'attestation',
    unresolved: input.attested ? 0 : 1,
    // ⚠️ TRUE SINCE 2026-08-02, AND THE CHANGE IS A STRENGTHENING.
    // This was `false`, and the comment above still called the gate "never
    // server-enforced". That was accurate and it was the problem: a second
    // sign control shipped that did not count this gate, and because nothing
    // on the server did either, the attestation could be walked past with no
    // refusal and no audit row. `POST /sign` now requires an explicit
    // `attestation` and answers SIGN_BLOCKED_NO_ATTESTATION without it.
    // Gates only ever gain requirements — see SPEC.
    serverEnforced: true,
  });

  return { gates, n: blockerCount(gates), emArtifact };
}

/** Σ of every applicable gate's unresolved count. */
export function blockerCount(gates: readonly SignGate[]): number {
  return gates.reduce((sum, g) => sum + g.unresolved, 0);
}
