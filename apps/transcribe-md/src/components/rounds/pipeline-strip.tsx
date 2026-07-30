// ============================================================================
// ROUNDS — Screen 2, THE PIPELINE STRIP.
// ----------------------------------------------------------------------------
// Five nodes from the real statuses, then a padlocked Signed node carrying the
// blocker count. It is Ward Board's position-awareness carried onto the stage:
// the doctor should know where this note sits in the run without going back to
// the board.
//
// IT DERIVES NOTHING. The stage model comes from `lib/rounds/stages.ts` — the
// same mapping the board's columns use — and the blocker count comes from
// `lib/sign-gates.ts`, which both this strip and the server-rendered page call.
// A strip that computed its own five names, or its own N, would be a second
// source of truth for two things that already have one, and the E/M half has
// already been spelled wrong once in seven places.
//
// THREE THINGS THAT LOOK LIKE DETAILS AND ARE NOT:
//
//  1. **`completedStageCount()` is deliberately NOT used.** It returns 5 for a
//     READY visit, which is right for a board lane (the run finished, it is
//     waiting on a human) and wrong here: it would draw the Ready node as DONE
//     on the very screen where the doctor is standing on it. The done-set is
//     `n < current.n`, matching the board's `runTo`/`cardColumn`.
//
//  2. **No animated text.** "NOW REVIEWING" is a label a clinician has to read;
//     a pulsing opacity on it fails axe, which samples mid-cycle, and text at
//     35% opacity really is unreadable at that instant. The motion lives on a
//     dot. This is A2's defect 4, and it cost a contrast failure to learn.
//
//  3. **No borrowed ARIA.** A strip is a visual diagram, not a table, a list of
//     interactive things, or a progressbar. Half-applied table semantics were
//     an axe CRITICAL on the board (`role="row"` with no table ancestor). State
//     lives in `data-*`; the accessible name says it in words, because colour
//     alone is invisible to a screen reader and to greyscale.
// ============================================================================

import { ROUNDS_STAGES, stageOf } from '@/lib/rounds/stages';
import type { SignGate } from '@/lib/sign-gates';

export type StripNodeState = 'done' | 'current' | 'pending';

export interface PipelineStripProps {
  /** The visit's raw status. Only READY and SIGNED reach Screen 2 — the page
   *  fans QUEUED, the processing states and FAILED away before this renders. */
  status: string;
  /** ISO timestamp, or null when unsigned. */
  signedAt?: string | null;
  /** Applicable gates from `signGates()`. Used for the per-gate breakdown. */
  gates?: readonly SignGate[];
  /** N — the number on the padlocked Signed node. From `blockerCount()`. */
  n: number;
  /** An imaging visit holding office E/M state; the server will refuse. */
  emArtifact?: boolean;
}

const GATE_LABEL: Record<string, string> = {
  rx: 'critical interaction',
  em: 'documentation level',
  attestation: 'attestation',
};

function blockerPhrase(n: number): string {
  return n === 1 ? '1 blocker before Signed' : `${n} blockers before Signed`;
}

/** The done/current/pending state of each of the five stage nodes.
 *
 *  SIGNED is an outcome, not a stage, so `stageOf` returns null for it and the
 *  whole run reads as done. Anything else that reaches this screen is READY. */
function nodeStates(status: string): StripNodeState[] {
  const current = stageOf(status);
  if (!current) {
    // SIGNED (or any outcome): the run completed.
    return ROUNDS_STAGES.map(() => 'done' as const);
  }
  return ROUNDS_STAGES.map((s) =>
    s.n < current.n ? 'done' : s.n === current.n ? 'current' : 'pending'
  );
}

function StageNode({
  label,
  n,
  state,
}: {
  label: string;
  n: number;
  state: StripNodeState;
}) {
  const done = state === 'done';
  const current = state === 'current';

  return (
    <li
      data-testid={`rounds-strip-node-${n}`}
      data-stage-state={state}
      className="qm-rounds-strip-node"
      // The state is in the text, not only in the colour and the tick.
      aria-label={`Step ${n} of ${ROUNDS_STAGES.length}, ${label}, ${
        done ? 'done' : current ? 'now reviewing' : 'not started'
      }`}
    >
      <span
        aria-hidden
        className="qm-rounds-strip-dot"
        data-stage-state={state}
        style={{
          background: done
            ? 'var(--rounds-ready)'
            : current
              ? 'var(--rounds-accent)'
              : 'var(--rounds-surface-3)',
          border: done || current ? 'none' : '1px solid var(--rounds-line-2)',
          color: 'var(--rounds-paper-1)',
        }}
      >
        {done ? '✓' : ''}
      </span>
      <span aria-hidden className="qm-rounds-strip-label" data-stage-state={state}>
        {label}
      </span>
      {current ? (
        // Static text. The only thing that moves is the dot above.
        <span aria-hidden className="qm-rounds-strip-now" data-testid="rounds-strip-now">
          NOW REVIEWING
        </span>
      ) : null}
    </li>
  );
}

export function RoundsPipelineStrip({
  status,
  signedAt = null,
  gates = [],
  n,
  emArtifact = false,
}: PipelineStripProps) {
  const states = nodeStates(status);
  const signed = !!signedAt;

  // The breakdown behind N, so the padlock is not a bare number. Only gates
  // that still need something appear — a satisfied gate is not a blocker, and
  // an inapplicable one is not in `gates` at all.
  const outstanding = gates.filter((g) => g.unresolved > 0);

  return (
    // NOT <nav>. A nav landmark promises a block of navigation, and this strip
    // contains no links — a screen-reader user cycling landmarks would land in
    // a diagram looking for somewhere to go. `role="group"` is the honest
    // reading: related elements with one label, and unlike role="row" it needs
    // no particular parent to be valid.
    <div
      role="group"
      data-testid="rounds-pipeline-strip"
      aria-label="Note progress"
      className="qm-rounds-strip"
    >
      <ol className="qm-rounds-strip-list">
        {ROUNDS_STAGES.map((s, i) => (
          <StageNode key={s.id} label={s.label} n={s.n} state={states[i]!} />
        ))}

        {/* The Signed node. Not one of ROUNDS_STAGES — SIGNED is an outcome,
            and adding it to that array would put a sixth column on the board. */}
        <li
          data-testid="rounds-strip-signed"
          data-stage-state={signed ? 'done' : 'locked'}
          data-blockers={signed ? '0' : String(n)}
          className="qm-rounds-strip-node qm-rounds-strip-signed"
          aria-label={
            signed
              ? 'Signed and locked'
              : n === 0
                ? 'Signed, not yet — no blockers remaining'
                : `Signed, locked, ${blockerPhrase(n)}${
                    outstanding.length
                      ? `: ${outstanding
                          .map((g) => GATE_LABEL[g.id] ?? g.id)
                          .join(', ')}`
                      : ''
                  }`
          }
        >
          <span
            aria-hidden
            className="qm-rounds-strip-dot"
            data-stage-state={signed ? 'done' : 'locked'}
            style={{
              background: signed ? 'var(--rounds-ready)' : 'var(--rounds-surface-3)',
              border: signed ? 'none' : '1px dashed var(--rounds-line-2)',
              color: signed ? 'var(--rounds-paper-1)' : 'var(--rounds-text-3)',
            }}
          >
            {signed ? '✓' : '🔒'}
          </span>
          <span aria-hidden className="qm-rounds-strip-label">
            Signed
          </span>
          {!signed && n > 0 ? (
            <span
              aria-hidden
              className="qm-rounds-strip-blockers"
              data-testid="rounds-strip-blockers"
            >
              {blockerPhrase(n)}
            </span>
          ) : null}
        </li>
      </ol>

      {emArtifact ? (
        // An imaging visit carrying office E/M state. There is no E/M gate to
        // show — the invariant is absolute — but the sign WILL be refused, and
        // a clean "0 blockers" here would be a promise the server breaks.
        <p
          data-testid="rounds-strip-em-artifact"
          className="qm-rounds-strip-artifact"
          style={{ color: 'var(--rounds-critical-on-dark)' }}
        >
          This imaging report is carrying an office-visit documentation level.
          Signing will be refused until it is cleared.
        </p>
      ) : null}
    </div>
  );
}
