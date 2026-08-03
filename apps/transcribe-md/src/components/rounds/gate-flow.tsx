'use client';

// ============================================================================
// ROUNDS — Screen 3, THE GATES.
// ----------------------------------------------------------------------------
// A full-screen sequential flow over the EXISTING gate logic. SPEC.md's binding
// constraint is the shape of this whole file:
//
//   "Server refusals remain the sole source of truth — the gates are UI over
//    them; existing sign-block E2Es pass with semantics unchanged."
//
// SO THIS COMPONENT RENDERS NOTHING CLINICAL. It draws headings, step
// indicators, blocker language and a lock affordance. The real gates arrive
// from outside, by two different mechanisms — and which mechanism a gate uses
// is a fact about its STATE, not about its clinical weight:
//
//   · `rx` and `em` are ADOPTED — their live DOM is borrowed out of the paper
//     (`ADOPTED_SLOTS`, below). Both hold lazily-seeded local React state with
//     no `router.refresh()` behind it — `RxTab`'s `overriddenIds` and
//     `ReviewDocumentView`'s `emConfirmed` — so a flow that RE-MOUNTED them
//     would silently un-clear a gate: the doctor sent back to re-justify a
//     warning already written to `rx_warning_overrides`, and the blocker count
//     ticking back up. Stepping forward and back is the *normal* interaction
//     here, so that is not an edge case. Moving the node touches React's tree
//     not at all; a portal would not do, because `createPortal(node, host)` and
//     a bare node are different element TYPES to React and flipping between
//     them remounts.
//
//   · the SIGN BAR is an ordinary React child (`signbar`), passed in by the
//     route wiring. ⚠️ R2 CHANGED THIS, and the old arrangement is why the
//     legacy footer could not be removed for four attempts: `attestation` used
//     to adopt too, so the bar had to stay mounted on the stage all session for
//     this component to come and fetch it. It holds no local state — every
//     input is a prop — so it never needed moving, only a home.
//
// The rule that falls out: a gate is adopted only if a remount would LOSE
// something. Everything else is a child.
//
// THE STEPS ARE `gates.map(...)`. There is no `emApplies` here, no specialty
// name, and no equality branch on a gate id anywhere in this component's own
// logic — `ADOPTED_SLOTS` is a declared set, consulted by membership, precisely
// so that stays true. An inapplicable gate is ABSENT from the array upstream,
// so on an imaging visit this renders two steps and there is nothing to hide or
// disable. Guard tests assert both: that this file names no specialty, and that
// it branches on no gate id.
// ============================================================================

import { useCallback, useEffect, useId, useMemo, useRef } from 'react';

import type { SignGate, SignGateId } from '@/lib/sign-gates';
import { GATE_HEADING, gateLabel } from '@/lib/rounds/gate-labels';

/**
 * The gates whose UI arrives by DOM ADOPTION rather than as a React child.
 *
 * ⚠️ THIS IS A FACT ABOUT THE MECHANISM, NOT ABOUT MEDICINE, and it is declared
 * once as data because this file is forbidden to branch on a gate id. The guard
 * (`gate-flow.test.tsx` → "branches on no gate id of its own") bans equality
 * comparisons against a gate id for a good reason: which gates EXIST is the
 * server's answer, arriving in the `gates` array, and a component that
 * hard-codes one is one edit away from deciding a clinical question.
 * (The banned comparisons are described rather than spelled — a source grep
 * reads this comment too, and a guard that trips on its own explanation is a
 * defect this repo has paid for twice.)
 *
 * Membership here says something different: these two slots hold lazily-seeded
 * local React state (`RxTab.overriddenIds`, `ReviewDocumentView.emConfirmed`)
 * that a remount would silently un-clear — so their live DOM is borrowed rather
 * than re-rendered. `attestation` was in this set until R2, which is what kept a
 * second sign control permanently mounted on the stage: the node had to exist
 * down there for the effect to come and fetch it. Its bar holds no state, so it
 * is now an ordinary React child (`signbar`) and adopts nothing.
 *
 * Adding an id here means that gate's UI is rendered elsewhere and moved in.
 */
const ADOPTED_SLOTS: ReadonlySet<SignGateId> = new Set<SignGateId>(['rx', 'em']);

export interface RoundsGateFlowProps {
  open: boolean;
  /** Applicable gates, in the order the doctor meets them. From `signGates()`. */
  gates: readonly SignGate[];
  /** The live N, after in-session overlays. */
  n: number;
  /** An imaging visit holding office E/M state — the server WILL refuse. */
  emArtifact?: boolean;
  /** Which step is showing. */
  step: SignGateId | null;
  onStepChange: (step: SignGateId) => void;
  onClose: () => void;
  attested: boolean;
  onAttestedChange: (attested: boolean) => void;
  /** "Jane Doe" — named in the attestation sentence. */
  patientLabel: string;
  /** The encounter date, already formatted by the caller. */
  visitDateLabel: string;
  /**
   * The sign bar, rendered at the attestation step.
   *
   * ⚠️ R2. A SLOT, not a control this component builds — the file's standing
   * rule is that it renders nothing clinical, and that still holds: the node is
   * `<ReviewSignBar variant="gate">`, composed by the route wiring which owns
   * the visit's props. What changed is the delivery mechanism, from a DOM
   * `appendChild` adoption to an ordinary React child. The bar carries no local
   * state, so nothing is lost by mounting it here and unmounting it on close —
   * which is precisely why it, alone of the three slots, could be re-homed.
   *
   * Optional so the component still renders on a surface that has no signature
   * to offer; absent means the step shows the attestation and summary only.
   */
  signbar?: React.ReactNode;
}

export function RoundsGateFlow({
  open,
  gates,
  n,
  emArtifact = false,
  step,
  onStepChange,
  onClose,
  attested,
  onAttestedChange,
  patientLabel,
  visitDateLabel,
  signbar,
}: RoundsGateFlowProps) {
  const titleId = useId();
  const panelRef = useRef<HTMLDivElement | null>(null);
  const hostElRef = useRef<HTMLDivElement | null>(null);

  const ids = useMemo(() => gates.map((g) => g.id), [gates]);
  const activeIndex = step ? ids.indexOf(step) : -1;
  const active = activeIndex >= 0 ? gates[activeIndex] : null;
  const isLast = activeIndex === gates.length - 1;

  // A step with anything outstanding does not advance. SPEC.md: the
  // locked-until-clear affordance reads "Complete blockers to advance."
  const blocked = !!active && active.unresolved > 0;

  const goNext = useCallback(() => {
    if (blocked || isLast || activeIndex < 0) return;
    onStepChange(gates[activeIndex + 1].id);
  }, [blocked, isLast, activeIndex, gates, onStepChange]);

  const goBack = useCallback(() => {
    if (activeIndex <= 0) return;
    onStepChange(gates[activeIndex - 1].id);
  }, [activeIndex, gates, onStepChange]);

  useEffect(() => {
    if (!open) return;
    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape') {
        e.preventDefault();
        onClose();
      }
    }
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [open, onClose]);

  // Focus INTO the panel when it opens, so the next Tab lands on the gate and
  // not on the page behind an opaque overlay.
  useEffect(() => {
    if (!open) return;
    panelRef.current?.focus();
  }, [open]);

  // ── ADOPT THE LIVE GATE, BY MOVING ITS DOM ───────────────────────────────
  // The gate is rendered by the read-only paper into a stable
  // `[data-gate-slot]` wrapper and it STAYS mounted there for the whole
  // session. This effect borrows that DOM node into the active step's host and
  // puts it back on the way out.
  //
  // Why not a portal: `createPortal(node, host)` and a bare `node` are
  // different element types to React, so flipping between them unmounts and
  // remounts the subtree — which reset `RxTab.overriddenIds` to the stale
  // server prop and un-cleared a gate the doctor had already justified.
  // Changing a portal's container remounts for the same reason. Moving the DOM
  // node touches React's tree not at all: it keeps rendering into the same
  // wrapper and never learns it has moved.
  //
  // The restore is not optional. React will remove this wrapper from its
  // ORIGINAL parent when the paper unmounts, and a node adopted elsewhere at
  // that moment throws. Effect cleanup runs before unmount, so putting it back
  // here is what keeps that safe.
  //
  // ⚠️ R2 — `attestation` NO LONGER ADOPTS ANYTHING, and the narrowing is the
  // point rather than a tidy-up. This used to map `attestation` → the paper's
  // `signbar` slot, which is what kept a permanent second sign control mounted
  // on the stage: the bar had to exist down there for this effect to come and
  // fetch it. It now arrives as `signbar`, an ordinary React node rendered
  // below, and the paper does not render one at all.
  //
  // Adoption survives for `rx` and `em` because those two genuinely need it —
  // both hold lazily-seeded local state (`RxTab.overriddenIds`,
  // `ReviewDocumentView.emConfirmed`) that a remount would silently un-clear.
  // The sign bar held no state, so it never needed moving; it only needed a
  // home. See `review-sign-bar.tsx`.
  useEffect(() => {
    if (!open || !active || emArtifact) return;
    // Only the two stateful gates are relocated. An `attestation` step has no
    // `[data-gate-slot]` to find, and asking for one would silently match
    // nothing — so it is excluded by name rather than by a failed lookup.
    if (!ADOPTED_SLOTS.has(active.id)) return;
    const host = hostElRef.current;
    const slot = document.querySelector<HTMLElement>(`[data-gate-slot="${active.id}"]`);
    if (!host || !slot) return;

    const home = slot.parentElement;
    const nextSibling = slot.nextSibling;
    host.appendChild(slot);

    return () => {
      // Back exactly where it was, so the paper's own order is unchanged when
      // the flow closes.
      if (home) home.insertBefore(slot, nextSibling);
    };
  }, [open, active, emArtifact]);

  if (!open) return null;

  return (
    <div
      className="qm-rounds-gateflow"
      data-testid="rounds-gate-flow"
      data-step={step ?? ''}
      role="dialog"
      aria-modal="true"
      aria-labelledby={titleId}
    >
      {/* ── Step rail — one entry per APPLICABLE gate, in the server's order ── */}
      <ol className="qm-rounds-gateflow-rail" data-testid="rounds-gate-steps">
        {gates.map((g, i) => (
          <li
            key={g.id}
            data-testid={`rounds-gate-step-${g.id}`}
            data-state={
              g.id === step ? 'current' : g.unresolved === 0 ? 'done' : 'pending'
            }
            className="qm-rounds-gateflow-step"
          >
            <span className="qm-rounds-gateflow-step-n">{i + 1}</span>
            <span className="qm-rounds-gateflow-step-label">
              {GATE_HEADING[g.id] ?? g.id}
            </span>
          </li>
        ))}
      </ol>

      <div
        className="qm-rounds-gateflow-panel"
        ref={panelRef}
        tabIndex={-1}
        data-blocked={blocked ? 'true' : 'false'}
      >
        <header className="qm-rounds-gateflow-head">
          <h2 id={titleId} className="qm-rounds-gateflow-title">
            {active ? (GATE_HEADING[active.id] ?? active.id) : 'Sign & lock'}
          </h2>
          <button
            type="button"
            onClick={onClose}
            data-testid="rounds-gate-close"
            className="qm-rounds-gateflow-close"
          >
            Back to the note
          </button>
        </header>

        {/* ── THE ANOMALY. An imaging visit carrying office E/M state has no E/M
            gate — the invariant is absolute — but the sign route is not
            specialty-conditioned and WILL refuse. Saying so beats rendering a
            clean zero and letting the doctor meet a 400 they were not warned
            about. "I cannot establish this" must never render as "fine". */}
        {emArtifact ? (
          <div
            className="qm-rounds-gateflow-anomaly"
            data-testid="rounds-gate-em-artifact"
            role="alert"
          >
            This imaging report carries an office documentation level. There is
            no level to confirm here, and signing will be refused until the data
            is corrected. Nothing on this screen can clear it.
          </div>
        ) : null}

        {/* ── THE GATE ITSELF ARRIVES HERE, BY ADOPTION. Empty on purpose: this
            component never renders a clinical control of its own. ──
            ⚠️ R2 — ONLY FOR THE STEPS THAT ACTUALLY ADOPT. This used to render
            for any `active` gate, which after the signature was re-homed left an
            EMPTY host on the attestation step: a div named
            `rounds-gate-host-attestation`, wired to `hostElRef`, that nothing
            could ever move into, because the effect above no longer looks up a
            `[data-gate-slot]` for that id.
            It rendered nothing and broke nothing, which is exactly why it is
            worth deleting rather than leaving: a landmark that advertises a
            mechanism it no longer participates in is how the next reader
            concludes the adoption still covers three slots. Caught by the pack
            asserting the host was gone — the assertion was right and the markup
            had not followed the effect. */}
        {active && !emArtifact && ADOPTED_SLOTS.has(active.id) ? (
          <div
            className="qm-rounds-gateflow-host"
            data-testid={`rounds-gate-host-${active.id}`}
            ref={hostElRef}
          />
        ) : null}

        {/* ── Gate 3 also carries the attestation and the summary ─────────── */}
        {active && active.id === 'attestation' && !emArtifact ? (
          <div className="qm-rounds-gateflow-attest">
            {/* ONLY WHAT APPLIED. The rows come from the gate array, so a visit
                that never had an Rx gate shows no Rx row — a fabricated
                "cleared" row for a gate that never existed would be a claim
                about work nobody did. */}
            <ul className="qm-rounds-gateflow-summary" data-testid="rounds-gate-summary">
              {gates
                .filter((g) => g.id !== 'attestation')
                .map((g) => (
                  <li
                    key={g.id}
                    data-testid={`rounds-gate-summary-${g.id}`}
                    data-cleared={g.unresolved === 0 ? 'true' : 'false'}
                  >
                    {gateLabel(g.id)}
                    {g.unresolved === 0 ? ' — cleared' : ` — ${g.unresolved} outstanding`}
                  </li>
                ))}
            </ul>

            <label className="qm-rounds-gateflow-checkbox">
              <input
                type="checkbox"
                checked={attested}
                onChange={(e) => onAttestedChange(e.target.checked)}
                data-testid="rounds-gate-attest"
              />
              <span>
                I have reviewed this note for {patientLabel}, dated{' '}
                {visitDateLabel}, and it is accurate and complete.
              </span>
            </label>

            {/* ⚠️ THIS SENTENCE WAS FALSE AND A TEST WAS HOLDING IT TRUE.
                It read: "This attestation is recorded on this screen. The
                server does not check it." That was accurate when B2 wrote it —
                `signGates` marked the gate `serverEnforced: false`.

                It stopped being accurate on 2026-08-02, when the attestation
                became server-enforced: `sign-gates.ts:247` is now
                `serverEnforced: true`, `POST /sign` refuses without
                `attestation: { acknowledged: true }`, and the refusal writes a
                `SIGN_BLOCKED_NO_ATTESTATION` audit row. The strengthening
                landed; this copy did not move with it, and
                `rounds-gates.spec.ts` asserted `/server does not check/i`, so
                the stale claim had a green check standing behind it.

                A UI that tells a doctor a clinical gate is unenforced, when it
                is enforced, is worse than saying nothing: it invites them to
                treat the tick as paperwork. Corrected in R2 because R2 is
                already rebuilding this step, and leaving a knowingly false
                safety statement in a file being edited is not an option. */}
            <p className="qm-rounds-gateflow-note" data-testid="rounds-gate-attest-note">
              Signing without this attestation is refused by the server, and the
              refusal is recorded.
            </p>

            <p className="qm-rounds-gateflow-foot">
              Signing locks the note. Later changes require a dated addendum.
            </p>

            {/* ── THE SIGNATURE ──────────────────────────────────────────────
                R2: an ordinary React child, not an adopted DOM node. Last on
                the step, after the summary, the attestation and the warning —
                the order in which a doctor should meet them. */}
            {signbar ? (
              <div className="qm-rounds-gateflow-sign" data-testid="rounds-gate-signbar-host">
                {signbar}
              </div>
            ) : null}
          </div>
        ) : null}

        {/* ── Locked-until-clear ─────────────────────────────────────────── */}
        {blocked ? (
          <p className="qm-rounds-gateflow-lock" data-testid="rounds-gate-lock" role="status">
            🔒 Complete blockers to advance —{' '}
            {active!.unresolved === 1
              ? `1 ${gateLabel(active!.id)} outstanding`
              : `${active!.unresolved} ${gateLabel(active!.id)}s outstanding`}
          </p>
        ) : null}

        <footer className="qm-rounds-gateflow-nav">
          <button
            type="button"
            onClick={goBack}
            disabled={activeIndex <= 0}
            data-testid="rounds-gate-back"
            className="qm-rounds-gateflow-nav-back"
          >
            Back
          </button>
          {!isLast ? (
            <button
              type="button"
              onClick={goNext}
              disabled={blocked}
              data-testid="rounds-gate-next"
              className="qm-rounds-gateflow-nav-next"
            >
              Next
            </button>
          ) : null}
          <span className="qm-rounds-gateflow-count" data-testid="rounds-gate-n" data-blockers={String(n)}>
            {n === 0 ? 'Nothing outstanding' : n === 1 ? '1 blocker' : `${n} blockers`}
          </span>
        </footer>
      </div>
    </div>
  );
}
