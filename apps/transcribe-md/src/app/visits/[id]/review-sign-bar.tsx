'use client';

// ============================================================================
// THE SIGN BAR — one renderer, two homes, never both at once.
// ----------------------------------------------------------------------------
// ⚠️ R2 EXTRACTED THIS FROM `review-document-view.tsx` TO RE-HOME IT, AND THE
// RE-HOME IS THE WHOLE POINT. Read this before changing where it mounts.
//
// Under Rounds the stage draws an action rail whose primary NAVIGATES to the
// gate flow. This bar SIGNS. Both were on screen at once, and on 2026-08-02
// they contradicted each other on a live visit:
//
//     action rail   "Review & sign · 1 blocker"
//     this bar      "Reviewed"    Sign & Download   disabled=false
//
// R1 closed the BYPASS by feeding the rail's own gate count in
// (`signGateBlockers`), so the two could no longer disagree. It did NOT close
// the DUPLICATION — R1's own note called that "cosmetic" and said re-homing the
// bar was its own piece of work. This file is that work.
//
// ⚠️ WHY REMOVAL FAILED FOUR TIMES, AND WHY THIS IS NOT A FIFTH ATTEMPT AT IT.
// `gate-flow.tsx` used to ADOPT this bar by `appendChild` — physically moving
// the live DOM node into the active gate step. Making React conditionally
// unmount a node another component has relocated puts React's tree and the real
// DOM in disagreement: on close, React removed a node that was no longer where
// it thought it was, and the entire paper subtree went with it
// (`review-document-view` → 0). That is a real architectural conflict.
//
// The cure is not better conditional unmounting. It is to stop moving the node:
//   · The DOM adoption in `gate-flow.tsx` now covers `rx` and `em` ONLY, which
//     are the slots that genuinely need it — both hold lazily-seeded local
//     React state (`RxTab.overriddenIds`, `ReviewDocumentView.emConfirmed`) that
//     a remount would silently un-clear, sending a doctor back to re-justify a
//     warning already written to `rx_warning_overrides`.
//   · THIS bar holds no such state. Every input is a prop, so it can be
//     rendered by whoever owns the surface it belongs to, and mounting or
//     unmounting it costs nothing. It is passed into the gate flow as a React
//     node and rendered there, at the attestation step.
//
// So the invariant "exactly one control can start a signature" is now
// STRUCTURAL rather than coordinated: off Rounds it is the review surface's own
// footer; under Rounds it exists only inside Gate 3. There is no moment when
// both are mounted, because there is one element and one parent.
// ============================================================================

import { AlertTriangle, Check, FileSignature } from 'lucide-react';

import { SignAndSendModal } from './sign-and-send-modal';

export interface ReviewSignBarProps {
  visitId: string;
  doctorEmail: string;
  /** Required, not optional — `SignAndSendModal` takes a `boolean` and an
   *  `undefined` here would silently hide the email destination rather than
   *  reflect the server's RESEND configuration. */
  emailEnabled: boolean;
  /** The SAME shape `ReviewDocumentView` and `SignAndSendModal` use. Typed
   *  rather than `unknown`: a widened type here would have compiled while
   *  passing the wrong thing through to the modal that performs the signature. */
  emPendingChange: { from: string; to: string } | null;
  /** The doctor's Gate-3 attestation. `POST /sign` REQUIRES it and answers
   *  400 ATTESTATION_REQUIRED without it — see `sign-gates.ts`. */
  attested?: boolean;
  /** Anything outstanding. Computed by the caller so there is one number. */
  blocked: boolean;
  /** Named reasons, for the status line. Only used by the `footer` variant. */
  rxBlocking?: boolean;
  emBlocking?: boolean;
  emStale?: boolean;
  onRescoreEm?: () => void | Promise<void>;
  /**
   * `footer` — the legacy sticky bar at the foot of the review surface, with
   *   its status line. This is the flag-OFF path and it is BYTE-FOR-BYTE what
   *   shipped before R2; nothing about the old skin changes.
   * `gate`  — inside Gate 3. No status line: the gate flow already renders the
   *   lock affordance ("Complete blockers to advance"), the blocker count and
   *   the cleared-gate summary, so a second sentence saying the same thing in
   *   different words is noise on the one screen that must be unambiguous. And
   *   the footer's copy is written for the paper — "Resolve the prescription
   *   warning ABOVE" points at nothing from inside a full-screen overlay.
   */
  variant: 'footer' | 'gate';
}

export function ReviewSignBar({
  visitId,
  doctorEmail,
  emailEnabled,
  emPendingChange,
  attested,
  blocked,
  rxBlocking = false,
  emBlocking = false,
  emStale = false,
  onRescoreEm,
  variant,
}: ReviewSignBarProps) {
  // ⚠️ THE TESTID IS THE SAME IN BOTH HOMES, DELIBERATELY. It is the anchor for
  // "there is exactly ONE thing that can start a signature", and that assertion
  // is only meaningful if both homes answer to the same name — a `-gate` suffix
  // would make `toHaveCount(1)` true by making the two invisible to each other.
  const signButton = (
    <span
      onClickCapture={() => {
        // Re-check before the modal opens. The gate render IS a moment the
        // doctor is looking at the level, so they meet the confirm card rather
        // than a refusal they have to interpret.
        if (emStale) void onRescoreEm?.();
      }}
    >
      <SignAndSendModal
        visitId={visitId}
        doctorEmail={doctorEmail}
        emailEnabled={emailEnabled}
        signOnSubmit
        emPendingChange={emPendingChange}
        attested={attested}
        triggerLabel="Sign &amp; Download"
        triggerIcon={<FileSignature className="h-3.5 w-3.5" aria-hidden />}
        disabled={blocked}
      />
    </span>
  );

  if (variant === 'gate') {
    return (
      <div className="qm-rounds-gate-signbar" data-testid="review-doc-signbar">
        {signButton}
      </div>
    );
  }

  return (
    <div className="qm-c3-rev2-signbar" data-testid="review-doc-signbar">
      <div className="qm-c3-rev2-signbar-in">
        <div className="qm-c3-rev2-sign-status">
          {blocked ? (
            <>
              <AlertTriangle
                className="h-3.5 w-3.5 flex-none"
                aria-hidden
                style={{ color: 'var(--color-linear-amber)' }}
              />
              <span className="qm-c3-rev2-sign-msg" data-testid="review-doc-bar-msg">
                {/* ⚠️ NAME THE REASON THAT ACTUALLY APPLIES. This used to be a
                    two-way `rxBlocking ? … : 'Confirm the documentation level
                    above'`, which was safe only while `blocked` meant exactly
                    rx-or-E/M. Feeding the rail's gate count in broke that
                    assumption immediately: an IMAGING visit — where `emApplies`
                    is false and no E/M surface may appear anywhere — started
                    printing "Confirm the documentation level above" because its
                    one open gate was the attestation. The imaging pack caught
                    it. E/M is named only when E/M is genuinely the blocker. */}
                {rxBlocking
                  ? 'Resolve the prescription warning above'
                  : emBlocking
                    ? 'Confirm the documentation level above'
                    : 'Open Review & sign to clear the remaining steps'}
              </span>
            </>
          ) : emStale ? (
            <>
              <AlertTriangle
                className="h-3.5 w-3.5 flex-none"
                aria-hidden
                style={{ color: 'var(--color-linear-amber)' }}
              />
              <span className="qm-c3-rev2-sign-msg" data-testid="review-doc-bar-msg">
                Re-check the documentation level above
              </span>
            </>
          ) : (
            <>
              <Check
                className="h-3.5 w-3.5 flex-none"
                aria-hidden
                style={{ color: 'var(--color-linear-sage-bright)' }}
              />
              <span className="qm-c3-rev2-sign-msg" data-testid="review-doc-bar-msg">
                Reviewed
              </span>
            </>
          )}
        </div>

        <div className="qm-c3-rev2-sign-action qm-rdoc-bar-actions">{signButton}</div>
      </div>
    </div>
  );
}
