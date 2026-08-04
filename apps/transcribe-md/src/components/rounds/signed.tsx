'use client';

// ============================================================================
// ROUNDS — Screen 4, SIGNED & LOCKED.
// ----------------------------------------------------------------------------
// The strip fully checked, a lock banner, the safety trail, the read-only paper
// below with the addendum footer, and the deck advancing to the next encounter.
//
// THE SAFETY TRAIL IS THE HARD PART, AND IT IS AN HONESTY PROBLEM, NOT A LAYOUT
// ONE. "Only what applied" cannot be inferred from "the visit is signed, so the
// gates must have been cleared" — that reasoning would put a green tick on a
// step nothing recorded. Every card here is backed by a column:
//
//   • "Critical interaction overridden"  ← real RxWarningOverride rows, each
//     with a server-validated reason, a signer and a timestamp, each correlated
//     against the visit's persisted warnings before it could be written, and
//     each compared against `signedAt` so "before signing" means it.
//   • "Documentation level confirmed"    ← `emPendingChange.acknowledgedAt`,
//     stamped by the winning READY→SIGNED transition.
//
// AND THERE IS NO "ATTESTED" CARD. Attestation is never persisted: the sign body
// schema has no such field, there is no column and no audit action, and
// `signGates` marks the gate `serverEnforced: false` for exactly that reason.
// The only signal is a `useState(false)` that dies with the page. A tick here
// would re-assert on every reload something nothing recorded — and would
// contradict Screen 3, which tells the doctor in as many words that the server
// does not check it. Two cards, not three-with-one-greyed: a greyed card is
// still a claim about attestation on a surface whose job is to list what
// happened.
//
// AN ABSENT CARD MEANS THE STEP DID NOT APPLY. That is the trail's whole claim,
// so nothing here renders a placeholder for a card it cannot fill.
// ============================================================================

import type { StageIdentity, StageQueuePosition } from '@/lib/rounds/stage-data';
import type { SignedTrail } from '@/lib/rounds/stage-view-model';
import { RoundsPipelineStrip } from './pipeline-strip';

export interface RoundsSignedProps {
  status: string;
  /** ISO. Required here — this screen exists only for a signed visit. */
  signedAt: string;
  identity: StageIdentity;
  queue: StageQueuePosition;
  trail: SignedTrail;
  /** The signer's display name. */
  signedByLabel: string;
  /**
   * The frozen documentation level, already projected by the caller.
   *
   * null when E/M does not apply — an imaging report has no office level, and
   * that invariant is absolute. Absent renders as ABSENT: no row, no "not
   * applicable" chrome, no blank slot.
   */
  emCode: string | null;
  /** The existing signed paper. This screen composes it; it renders no note. */
  children: React.ReactNode;
  /** Open the next encounter to review. Absent when there is none. */
  onContinue?: () => void;
  /**
   * The visit's lifecycle actions — for a SIGNED visit that is the **Archive**
   * control, and it is the only one there is.
   *
   * ⚠️ THIS PROP EXISTS BECAUSE ARCHIVE WAS UNREACHABLE IN PRODUCTION FOR A
   * DAY, ON EVERY SIGNED NOTE.
   *
   * R2 removed a page-foot overflow that was gated on `roundsChrome` **alone,
   * with no status condition** — so it rendered for SIGNED visits too — and
   * moved it into `RoundsStage`. Signed visits never mount `RoundsStage`; they
   * mount THIS component, which had no way to receive it. The commit's own
   * comment said *"Same node, same actions, same `data-testid` — only the
   * position moved."* That was true for unsigned visits and false for signed
   * ones, which is precisely the class of comment the R3 census kept finding.
   *
   * Nothing was corrupted and no gate weakened; the control simply was not in
   * the DOM, with no error. HIPAA retention forbids deleting a signed note, so
   * archiving is the only disposal a doctor has — and 16 signed visits in
   * production had no path to it.
   *
   * Mount coverage is asserted by `gate-rounds-visit-overflow`, not kept
   * correct by hand. AGENTS.md § "Shared components": put the behaviour where
   * it cannot be forgotten, and where a per-caller list is unavoidable, make
   * the missing case fail a test rather than render quietly.
   */
  visitActions?: React.ReactNode;
}

export function RoundsSigned({
  status,
  signedAt,
  identity,
  queue,
  trail,
  visitActions,
  signedByLabel,
  emCode,
  children,
  onContinue,
}: RoundsSignedProps) {
  const cards: { id: string; label: string }[] = [];
  if (trail.criticalOverridesBeforeSign > 0) {
    cards.push({
      id: 'rx',
      label:
        trail.criticalOverridesBeforeSign === 1
          ? '1 critical interaction overridden, with a recorded reason'
          : `${trail.criticalOverridesBeforeSign} critical interactions overridden, each with a recorded reason`,
    });
  }
  if (trail.emAcknowledgedAt) {
    cards.push({ id: 'em', label: 'Documentation level change confirmed' });
  }

  return (
    <div className="qm-rounds-signed" data-testid="rounds-signed" data-status={status}>
      {/* Fully checked. The strip derives this from `signedAt` itself — it is
          NOT fed the gate set, because the attestation gate reports unresolved
          forever (nothing sets it server-side), so a signed note would draw
          with an outstanding blocker. */}
      <RoundsPipelineStrip status={status} signedAt={signedAt} n={0} />

      <section
        className="qm-rounds-signed-lock"
        data-testid="rounds-signed-lock"
        role="status"
      >
        <h2 className="qm-rounds-signed-lock-title">Signed &amp; locked</h2>
        <dl className="qm-rounds-signed-lock-fields">
          <div>
            <dt>Patient</dt>
            <dd data-testid="rounds-signed-patient">{identity.patientLabel}</dd>
          </div>
          <div>
            <dt>Signed by</dt>
            <dd data-testid="rounds-signed-by">{signedByLabel}</dd>
          </div>
          <div>
            <dt>Signed at</dt>
            {/* `<time>` carries machine-readable UTC. The caller formats, so
                this component does not reintroduce the timezone hydration
                mismatch B1 already fixed on the identity header. */}
            <dd>
              <time dateTime={signedAt} data-testid="rounds-signed-at">
                {signedAt}
              </time>
            </dd>
          </div>
          {/* ABSENT when E/M does not apply. An imaging report has no office
              level, so there is no row — not a row saying "n/a". */}
          {emCode ? (
            <div>
              <dt>Documentation level</dt>
              <dd data-testid="rounds-signed-em">{emCode}</dd>
            </div>
          ) : null}
        </dl>
      </section>

      {/* ── The safety trail. Only what a column proves. ─────────────────── */}
      {cards.length > 0 ? (
        <ul className="qm-rounds-signed-trail" data-testid="rounds-signed-trail">
          {cards.map((c) => (
            <li
              key={c.id}
              className="qm-rounds-signed-trail-card"
              data-testid={`rounds-signed-trail-${c.id}`}
            >
              <span aria-hidden>✓</span> {c.label}
            </li>
          ))}
        </ul>
      ) : null}

      <div className="qm-rounds-signed-paper rounds-paper" data-testid="rounds-signed-paper">
        {children}
      </div>

      {/* A SENTENCE, NOT A CONTROL. There is no addendum model, route or UI
          anywhere in the repo, so a link would lead nowhere. What the sentence
          describes IS enforced — the save actions refuse a signed note and name
          addendum as the remedy — so the claim is true and the remedy simply
          does not exist yet. */}
      <p className="qm-rounds-signed-foot" data-testid="rounds-signed-addendum">
        This note is locked. Corrections require a dated addendum.
      </p>

      {/* ── Lifecycle actions — Archive, and only Archive ─────────────────
          Same anatomy as the stage's overflow (`stage.tsx:146`): a collapsed
          `<details>` carrying the same `data-testid`, so one selector finds it
          on both surfaces and a doctor meets the same control in the same
          shape wherever they are. Collapsed on purpose — a destructive action
          should cost a deliberate click, which is the reasoning R2 recorded
          when it moved the control out of the page foot.

          It sits AFTER the addendum notice and BEFORE the deck: filing the
          note away is the last thing you do with this note, and advancing to
          the next encounter is the first thing you do with the next one. */}
      {visitActions ? (
        <details className="qm-rounds-overflow" data-testid="rounds-visit-overflow">
          <summary className="qm-rounds-overflow-summary">Visit actions</summary>
          <div className="qm-rounds-overflow-body qm-rounds-host">{visitActions}</div>
        </details>
      ) : null}

      {/* ── The deck advances ────────────────────────────────────────────── */}
      {onContinue ? (
        <div className="qm-rounds-signed-deck" data-testid="rounds-signed-deck">
          <span className="qm-rounds-signed-deck-done" aria-hidden>
            ✓
          </span>
          <span className="qm-rounds-signed-deck-arrow" aria-hidden>
            →
          </span>
          <button
            type="button"
            onClick={onContinue}
            data-testid="rounds-signed-continue"
            className="qm-rounds-signed-continue"
          >
            Continue to the next encounter
          </button>
        </div>
      ) : null}

      {/* NOTHING renders when the queue is empty. Not a disabled button, and
          emphatically not "all done for today": the queue is a 200-row window,
          so a still-to-review visit outside it produces the same empty result.
          Honest silence beats a completion claim the data cannot support.
          `queue.total` is deliberately not rendered either — it counts over that
          window while /board's own counter counts over a 20-row page, and two
          differing numbers both labelled "to review" is exactly what the stage
          queue was built to avoid. */}
    </div>
  );
}
