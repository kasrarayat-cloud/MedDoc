'use client';

// ============================================================================
// ROUNDS — Screen 2, THE STAGE.
// ----------------------------------------------------------------------------
// Focus Flow's spotlit layout carrying Ward Board's position-awareness: the
// pipeline strip says where the note is, the elevated sheet is the note, and
// the peek at the edges says what is on either side of it in the queue.
//
// IT COMPOSES; IT DOES NOT RENDER THE NOTE. The sheet is a SLOT — the caller
// passes the existing paper component through as `children`, restyled by
// `.rounds-paper` rather than reimplemented. That is the whole reason the
// read-only invariant survives this screen: there is no second note renderer
// here to accidentally grow an edit affordance, and the one that exists is
// already pinned by `review-read-only-paper.test.ts`.
//
// THE VITALS SLOT IS RESERVED AND EMPTY. The spec asks for the reservation and
// forbids the content: L3 has a `measurements` slot but no vitals shape, so
// there is nothing real to put in it. It renders as an empty landmark the
// layout accounts for, and the test asserts it has no text — parked, never
// faked. Filling it with plausible numbers on a clinical header is the one
// thing this screen must never do.
//
// THE ACTION RAIL'S PRIMARY CARRIES THE COUNT, from the same `n` the strip's
// padlock shows. Two numbers derived separately would eventually disagree, and
// the one a doctor acts on is the one on the button.
// ============================================================================

import type { SignGate } from '@/lib/sign-gates';
import type { StageIdentity, StageQueuePosition } from '@/lib/rounds/stage-data';
import { queueLabel } from '@/lib/rounds/stage-data';
import { RoundsPipelineStrip } from './pipeline-strip';
import { RoundsStageIdentity } from './stage-identity';
import { RoundsChatDrawer } from './chat-drawer';

export interface RoundsStageProps {
  /** Raw visit status. Only READY and SIGNED reach this screen. */
  status: string;
  signedAt?: string | null;
  identity: StageIdentity;
  queue: StageQueuePosition;
  gates: readonly SignGate[];
  n: number;
  emArtifact?: boolean;
  /** Unresolved CRITICAL Rx count, for the band across the sheet's top. */
  criticalUnresolved?: number;
  /** The existing paper component. */
  children: React.ReactNode;
  /** The existing `<ChatEditorPanel>`, dropped into the drawer. */
  chat?: React.ReactNode;
  /** Fires when the doctor asks to sign. The gate flow is B2's. */
  onReviewAndSign?: () => void;
  /** Navigate to the next encounter without signing this one. */
  onSkip?: () => void;
  /** Open the full queue list. */
  onOpenQueue?: () => void;
  /**
   * Runs just before the chat drawer closes.
   *
   * THE SEAM IS NAMED AND EMPTY ON PURPOSE. The review view's `onScrollTo`
   * resolves an element and calls `scrollIntoView`; with the chat OVER the
   * stage, "took you to the E/M gate" can scroll something the doctor cannot
   * see. Close first, then scroll — so the owner of that callback (the route
   * wiring) supplies this.
   *
   * B1 does NOT fake it. An earlier cut kept a private ref here and passed a
   * handler that could never fire, which reads as "handled" to anyone
   * skimming — the same pretend-success shape as a button that dispatches
   * nothing.
   */
  onChatBeforeClose?: () => void;
  /**
   * Fires whenever the chat drawer opens or closes.
   *
   * Deferring a scroll is only safe while something is guaranteed to flush it,
   * and the only flusher is the drawer closing. The owner of `onChatBeforeClose`
   * needs to know the drawer's state so it can scroll IMMEDIATELY when a reply
   * arrives after the doctor already closed it — otherwise that target sits
   * unreleased and fires on the next unrelated close.
   */
  onChatOpenChange?: (open: boolean) => void;
}

function signLabel(n: number, signed: boolean): string {
  if (signed) return 'Signed';
  if (n === 0) return 'Review & sign';
  return n === 1 ? 'Review & sign · 1 blocker' : `Review & sign · ${n} blockers`;
}

export function RoundsStage({
  status,
  signedAt = null,
  identity,
  queue,
  gates,
  n,
  emArtifact = false,
  criticalUnresolved = 0,
  children,
  chat,
  onReviewAndSign,
  onSkip,
  onOpenQueue,
  onChatBeforeClose,
  onChatOpenChange,
}: RoundsStageProps) {
  const signed = !!signedAt;
  const posLabel = queueLabel(queue);

  return (
    <div className="qm-rounds-stage" data-testid="rounds-stage" data-status={status}>
      <RoundsPipelineStrip
        status={status}
        signedAt={signedAt}
        gates={gates}
        n={n}
        emArtifact={emArtifact}
      />

      <RoundsStageIdentity identity={identity} />

      {/* RESERVED, DELIBERATELY EMPTY — structured vitals do not exist yet.
          Do not fill this. See the header. */}
      <div
        className="qm-rounds-vitals-slot"
        data-testid="rounds-vitals-slot"
        data-parked="true"
        aria-hidden
      />

      <div className="qm-rounds-stage-body">
        {/* ── Next-up peek, left edge ─────────────────────────────────── */}
        <aside className="qm-rounds-peek qm-rounds-peek-prev" aria-hidden={!queue.prevVisitId}>
          {queue.prevVisitId ? (
            <a
              href={`/visits/${queue.prevVisitId}`}
              data-testid="rounds-peek-prev"
              className="qm-rounds-peek-card"
            >
              Previous
            </a>
          ) : null}
        </aside>

        {/* A DIV, NOT A `<main>` — deliberately, and it must stay one.
            `AppFrame` already renders `<main id="main" tabIndex={-1}>` around
            every route, so a second one here is two main landmarks on the page
            (axe: `landmark-no-duplicate-main`). /board avoids the same trap by
            letting `RoundsBoardChrome` own the only one.

            It is also load-bearing beyond a11y: the sign bar is
            `position: sticky; bottom: 0` and resolves against AppFrame's
            `<main>`, which is documented there as the deliberate overflow
            parent. Introducing a nearer landmark ancestor is how a sticky
            control silently stops sticking. */}
        <div className="qm-rounds-sheet-wrap">
          {criticalUnresolved > 0 ? (
            // Across the TOP of the card, and it names where it gets cleared —
            // a warning that does not say what to do about it is decoration.
            <div
              className="qm-rounds-critical-band"
              data-testid="rounds-critical-band"
              role="status"
            >
              {criticalUnresolved === 1
                ? '1 critical interaction — you’ll clear it at Gate 1'
                : `${criticalUnresolved} critical interactions — you’ll clear them at Gate 1`}
            </div>
          ) : null}

          {/* THE SHEET. The existing paper component, restyled. */}
          <div className="rounds-paper qm-rounds-sheet" data-testid="rounds-sheet">
            {children}
          </div>
        </div>

        {/* ── Next-up peek, right edge ────────────────────────────────── */}
        <aside className="qm-rounds-peek qm-rounds-peek-next" aria-hidden={!queue.nextVisitId}>
          {queue.nextVisitId ? (
            <a
              href={`/visits/${queue.nextVisitId}`}
              data-testid="rounds-peek-next"
              className="qm-rounds-peek-card"
            >
              Next up
            </a>
          ) : null}
        </aside>
      </div>

      {/* ── Queue position ──────────────────────────────────────────────── */}
      {posLabel ? (
        <div className="qm-rounds-queue" data-testid="rounds-queue-position">
          <span className="qm-rounds-queue-label">{posLabel}</span>
          <span className="qm-rounds-queue-dots" aria-hidden>
            {Array.from({ length: Math.min(queue.total, 12) }, (_, i) => (
              <span
                key={i}
                className="qm-rounds-queue-dot"
                data-current={queue.position === i + 1 ? 'true' : 'false'}
              />
            ))}
          </span>
          {onOpenQueue ? (
            <button
              type="button"
              onClick={onOpenQueue}
              data-testid="rounds-queue-open"
              className="qm-rounds-queue-open"
            >
              Show queue
            </button>
          ) : null}
        </div>
      ) : null}

      {/* ── Action rail ─────────────────────────────────────────────────── */}
      <div className="qm-rounds-rail" data-testid="rounds-action-rail">
        <button
          type="button"
          onClick={onReviewAndSign}
          disabled={signed}
          data-testid="rounds-review-sign"
          data-blockers={String(n)}
          className="qm-rounds-rail-primary"
        >
          {signLabel(n, signed)}
        </button>

        {!signed && onSkip ? (
          <button
            type="button"
            onClick={onSkip}
            data-testid="rounds-skip"
            className="qm-rounds-rail-secondary"
          >
            Skip
          </button>
        ) : null}

        {chat ? (
          <RoundsChatDrawer
            onBeforeClose={onChatBeforeClose}
            onOpenChange={onChatOpenChange}
          >
            {chat}
          </RoundsChatDrawer>
        ) : null}

        <span className="qm-rounds-rail-kbd" aria-hidden>
          <kbd className="qm-rounds-kbd">E</kbd> edit
        </span>
      </div>
    </div>
  );
}
