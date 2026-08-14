// ============================================================================
// ROUNDS — Screen 1, THE BOARD.
// ----------------------------------------------------------------------------
// Ward Board's patient-lanes × stage-columns matrix on the dark stage.
// docs/rounds/SPEC.md is the contract; docs/design-tokens.md is the authority
// for every colour, face and radius used here.
//
// THE SHAPE: one row per patient encounter (a "lane"), five numbered stage
// columns, and a hairline TRACK running the width of each lane. The card sits
// at the column the visit currently occupies, and the track behind it says how
// it got there — which is the whole reason this is a matrix and not a list.
//
// TRACK SEMANTICS, because they carry meaning a colour alone would not:
//   signed      solid GREEN the full run → muted card, "signed 8:52 AM"
//   failed      RED stopping at the failure stage → dashed card + RETRY in-lane
//   processing  dashed border, amber kicker
//   recording   dashed border, pulsing red REC kicker
//   ready       solid white card
//   critical    red border + ⚠ + one interaction line, and the LANE ROW tints
//
// DATA HONESTY: every value here comes from `BoardLane`, which derives from the
// real queue. Nothing on this screen is computed to look plausible — see
// lib/rounds/board-data.ts for what is parked rather than faked.
// ============================================================================

import Link from 'next/link';

import { ROUNDS_STAGES } from '@/lib/rounds/stages';
import type { BoardLane } from '@/lib/rounds/board-data';
import { RoundsNewVisitCta } from './new-visit-cta';
import { RoundsRetryButton } from './retry-button';

/** The board's modality word. There is NO `modality` column — the honest
 *  source is `specialty`, which is what decides imaging-vs-office everywhere
 *  else in the product. Rendered as a short label rather than the raw id so a
 *  marker reads like a marker. */
function modalityLabel(specialty: string): string {
  const s = specialty.trim().toLowerCase();
  if (!s) return '—';
  return s.replace(/[-_]+/g, ' ');
}

function hhmm(iso: string | null): string {
  if (!iso) return '';
  const d = new Date(iso);
  return d.toLocaleTimeString('en-US', {
    hour: 'numeric',
    minute: '2-digit',
    hour12: true,
  });
}

/** Column index a lane's card sits in, 1..5. A signed lane parks at the end;
 *  a failed one at the stage it died in. */
function cardColumn(lane: BoardLane): number {
  if (lane.kind === 'signed') return ROUNDS_STAGES.length;
  if (lane.kind === 'failed') return lane.failedAt?.n ?? 1;
  return lane.stage?.n ?? 1;
}

// ── The lane track ────────────────────────────────────────────────────────
// Drawn as a background layer behind the card so the run reads as continuous
// rather than as a series of segments between cards.
function LaneTrack({ lane }: { lane: BoardLane }) {
  const total = ROUNDS_STAGES.length;
  const pct = Math.max(0, Math.min(lane.runTo / total, 1)) * 100;

  // Green for a completed run, red for a failed one, and the quiet line colour
  // for everything still in flight. NOTE the asymmetry with the signed CARD,
  // which is grey: the card is finished business and recedes, the line is a
  // successful journey and should read as one across the whole board.
  const runColor =
    lane.kind === 'signed'
      ? 'var(--rounds-ready)'
      : lane.kind === 'failed'
        ? 'var(--rounds-critical)'
        : 'var(--rounds-line-2)';

  return (
    <div
      aria-hidden
      className="qm-rounds-lane-track"
      style={{
        position: 'absolute',
        insetInline: 0,
        top: '50%',
        height: 1,
        background: 'var(--rounds-line-1)',
      }}
    >
      <div
        style={{
          width: `${pct}%`,
          height: '100%',
          background: runColor,
          // A failed run is dashed so it reads as interrupted even in
          // greyscale — colour alone is not an accessible signal.
          ...(lane.kind === 'failed'
            ? {
                backgroundImage:
                  'repeating-linear-gradient(90deg, var(--rounds-critical) 0 6px, transparent 6px 10px)',
                background: 'none',
              }
            : null),
        }}
      />
    </div>
  );
}

/** R2 — the entrance stagger, capped.
 *
 * ⚠️ THE CAP IS THE POINT, NOT THE STEP. At 28ms a 60-lane board would make the
 * last card wait 1.68s before appearing, and a doctor scrolling to the bottom
 * of a busy morning would find an empty column and read it as a load failure.
 * Ten steps (280ms) is the whole run; every card past the tenth starts with the
 * tenth. Real boards on this product routinely exceed ten lanes, so this is the
 * ordinary path, not a defensive edge case. */
const STAGGER_STEP_MS = 28;
const STAGGER_MAX_STEPS = 10;

export function cardEntranceDelayMs(index: number): number {
  return Math.min(index, STAGGER_MAX_STEPS) * STAGGER_STEP_MS;
}

function LaneCard({ lane, index }: { lane: BoardLane; index: number }) {
  // ⚠️ The `critical` border, the interaction line and the row tint were
  // REMOVED here with the prescription-safety surface (owner ruling #109).
  const border = lane.kind === 'failed'
      ? `1px dashed var(--rounds-critical)`
      : lane.kind === 'processing' || lane.kind === 'recording'
        ? `1px dashed var(--rounds-line-2)`
        : lane.kind === 'signed'
          ? `1px solid var(--rounds-line-1)`
          : `1px solid var(--rounds-paper-2)`;

  const bg =
    lane.kind === 'ready'
      ? 'var(--rounds-paper-1)'
      : lane.kind === 'signed'
        ? 'var(--rounds-surface-1)'
        : 'var(--rounds-surface-2)';

  // A signed lane RECEDES, but the patient's name still has to be readable:
  // --rounds-signed (#6B7480) on --rounds-surface-1 fails AA as small text, and
  // axe caught exactly that. The muting belongs on the timestamp kicker, not on
  // the name — "quieter" must not mean "not legible", which is the failure mode
  // of every muted-state design that was never contrast-checked.
  const fg =
    lane.kind === 'ready'
      ? 'var(--rounds-ink)'
      : lane.kind === 'signed'
        ? 'var(--rounds-text-2)'
        : 'var(--rounds-text-1)';

  return (
    <Link
      href={`/visits/${lane.id}`}
      data-testid={`rounds-lane-card-${lane.id}`}
      data-lane-kind={lane.kind}
      aria-label={`${lane.patientLabel}, ${lane.kind}`}
      /* R2. Hover lift, pressed, focus-visible and the entrance live in
         `rounds-tokens.css` — a pseudo-class cannot be expressed inline, which
         is why this element gained a class rather than more `style` keys. The
         colour properties below stay inline: they are computed per lane kind
         and each pairing is contrast-checked against the ground THAT card
         paints. */
      className="qm-rounds-lane-card"
      style={{
        position: 'relative',
        display: 'block',
        padding: '10px 12px',
        borderRadius: 'var(--rounds-radius-md)',
        border,
        background: bg,
        color: fg,
        textDecoration: 'none',
        minWidth: 0,
        animationDelay: `${cardEntranceDelayMs(index)}ms`,
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
        <span
          style={{
            fontFamily: 'var(--rounds-font-ui)',
            fontWeight: 600,
            fontSize: 13.5,
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
          }}
        >
          {lane.patientLabel}
        </span>
      </div>

      {lane.kind === 'recording' ? (
        <span className="qm-rounds-kicker qm-rounds-kicker--rec">REC</span>
      ) : null}
      {lane.kind === 'processing' ? (
        <span className="qm-rounds-kicker qm-rounds-kicker--processing">
          {lane.stage?.label ?? 'Working'}
        </span>
      ) : null}
      {lane.kind === 'signed' ? (
        <span className="qm-rounds-kicker">signed {hhmm(lane.signedAt)}</span>
      ) : null}

      {/* ── R1 — THE MARKER'S META, AND ONLY WHAT THE MODEL TRULY HAS ───────
          SPEC: "every datum derives from the real queue source. Park visibly
          anything with no real data. NEVER FAKE."

          MODALITY and RECORDED TIME were already on `BoardLane` and rendered
          nowhere — `specialty` was read only by the filter, `createdAt` only by
          the sort. Nothing new is queried for them.

          ⚠️ MRN IS PARKED, DELIBERATELY, and this is the note that stops the
          next reader "just adding it". The board's patient select is
          `{ name: true }`, so the datum is not in this query at all — and there
          are TWO candidate columns: `TranscribeMdPatient.externalId` (which the
          Rounds STAGE labels MRN today) and a separate `mrn` column the stage
          does not read. Rendering one of them here would silently make the
          board and the stage disagree about what "MRN" means on the same
          patient. That is a decision to take on purpose, not in passing.
          The slot is reserved the way SPEC reserves the vitals chip: named,
          empty, and honest about why. */}
      <div
        data-testid={`rounds-lane-meta-${lane.id}`}
        style={{
          marginTop: 4,
          display: 'flex',
          alignItems: 'center',
          gap: 6,
          fontFamily: 'var(--rounds-font-mono)',
          fontSize: 10.5,
          letterSpacing: '0.04em',
          textTransform: 'uppercase',
          /* ⚠️ `--rounds-text-2`/`-3` FAILED AXE HERE, on all four card
             variants, and the reason is the ground rather than the ink: a lane
             card paints its OWN background (surface-2, or the critical tint),
             so the faint on-stage tiers are being read against a lighter
             surface than the one they were checked on. This is the ninth
             instance of that shape in this project. `--rounds-text-1` is the
             tier that holds on every card ground the board draws. */
          /* ⚠️ THE CARD'S OWN `fg`, NOT AN ON-STAGE TOKEN — and it took axe
             printing the pair to see why. Two guesses failed here
             (`--rounds-text-2/-3`, then `--rounds-text-1` at reduced opacity),
             both because I was reasoning about the ink while the GROUND was the
             variable: a READY lane card is `--rounds-paper-1` — SPEC's track
             semantics make it "solid white" — so a near-white on-stage token
             lands white-on-white. Measured: `#e7ebf1` on `#fcfcfa` = **1.16:1**
             against a 4.5 requirement.
             `fg` is computed a few lines above per lane kind and is already the
             checked pairing for this card's background. Reusing it means this
             line cannot drift from the patient name above it, on any kind. */
          color: fg,
          overflow: 'hidden',
          textOverflow: 'ellipsis',
          whiteSpace: 'nowrap',
        }}
      >
        <span data-testid={`rounds-lane-modality-${lane.id}`}>
          {modalityLabel(lane.specialty)}
        </span>
        <span aria-hidden>·</span>
        {/* "recorded" is `createdAt` — the same aliasing the stage already
            makes (`stage-data.ts` → `recordedAtIso`). Naming it the same thing
            in both places is the point. */}
        <span data-testid={`rounds-lane-recorded-${lane.id}`}>
          {hhmm(lane.createdAt)}
        </span>
      </div>

    </Link>
  );
}

/** ⚠️ R2 REMOVED `emptyHref`, and removing it was the point rather than tidying.
 *  The empty state's CTA is now `<RoundsNewVisitCta>`, which owns the
 *  destination (`NEW_VISIT_HREF`) so the board and the top bar cannot disagree
 *  about where "New visit" goes. Left in place, the prop would have been
 *  declared, defaulted and IGNORED — a caller could pass one and be silently
 *  overruled, which is the same shape as `emStale`'s falsy default: an option
 *  that reads as supported and does nothing. Nobody passed it (grepped: zero
 *  call sites outside the declaration). */
export function RoundsBoard({ lanes }: { lanes: BoardLane[] }) {
  if (lanes.length === 0) {
    // An invitation to record, not a mood. No illustration, no "nothing here
    // yet" shrug — the one thing a doctor would want to do next.
    return (
      <div
        /* C2 — anchored so the gate can see it. This state is only reachable
           by a doctor with zero visits, which is exactly the doctor nobody
           tests with: the a11y pack seeds three. */
        className="qm-rounds-board-empty"
        data-testid="rounds-board-empty"
        style={{
          padding: '48px 24px',
          textAlign: 'center',
          border: '1px dashed var(--rounds-line-1)',
          borderRadius: 'var(--rounds-radius-lg)',
          background: 'var(--rounds-surface-1)',
        }}
      >
        <p
          style={{
            fontFamily: 'var(--rounds-font-display)',
            fontSize: 18,
            color: 'var(--rounds-text-1)',
            margin: 0,
          }}
        >
          No visits yet today
        </p>
        <p
          style={{
            fontFamily: 'var(--rounds-font-ui)',
            fontSize: 13.5,
            color: 'var(--rounds-text-2)',
            margin: '6px 0 16px',
          }}
        >
          Record a visit and the note writes itself while you move on.
        </p>
        {/* ⚠️ R2 — "New visit", NOT "Start a visit", and the rename is the
            point. SPEC.md's copy register is "actions keep their names
            end-to-end"; this was the only surface in the product calling
            `/visits/new` anything else, so a doctor met a fourth name for the
            action on the one screen where they had never seen the other three.
            Shortcut deliberately NOT registered here — the top bar's copy owns
            it, and two listeners on one key double-navigate. */}
        <RoundsNewVisitCta variant="empty" />
      </div>
    );
  }

  const counts = ROUNDS_STAGES.map(
    (s) => lanes.filter((l) => cardColumn(l) === s.n).length,
  );

  return (
    <div data-testid="rounds-board">
      {/* Numbered stage columns, with counts from the lanes actually present. */}
      {/* NO role="row"/"columnheader" here. axe flagged aria-required-parent
          (critical) on the first cut: those roles need a table/grid ancestor,
          and this is a VISUAL matrix, not tabular data. Half-applied table
          semantics announce a structure that does not exist, which is worse
          for a screen reader than plain content. */}
      <div
        className="qm-rounds-board-grid qm-rounds-board-head"
        style={{ display: 'grid', gap: 8, alignItems: 'end', marginBottom: 6 }}
      >
        {ROUNDS_STAGES.map((s, i) => (
          <div key={s.id} style={{ minWidth: 0 }}>
            <span
              style={{
                fontFamily: 'var(--rounds-font-mono)',
                fontSize: 10.5,
                letterSpacing: '.08em',
                color: 'var(--rounds-text-3)',
              }}
            >
              {s.n}
            </span>{' '}
            <span
              style={{
                fontFamily: 'var(--rounds-font-ui)',
                fontSize: 12,
                fontWeight: 600,
                color: 'var(--rounds-text-2)',
              }}
            >
              {s.label}
            </span>{' '}
            <span
              data-testid={`rounds-stage-count-${s.id}`}
              style={{
                fontFamily: 'var(--rounds-font-mono)',
                fontSize: 11,
                color: 'var(--rounds-text-3)',
              }}
            >
              {counts[i]}
            </span>
          </div>
        ))}
      </div>

      <ul style={{ listStyle: 'none', margin: 0, padding: 0 }}>
        {lanes.map((lane, laneIndex) => {
          const col = cardColumn(lane);
          return (
            <li
              key={lane.id}
              data-testid={`rounds-lane-${lane.id}`}
              style={{
                position: 'relative',
                background: 'transparent',
                borderRadius: 'var(--rounds-radius-sm)',
                padding: '8px 4px',
              }}
            >
              <LaneTrack lane={lane} />
              <div
                className="qm-rounds-board-grid"
                style={{ display: 'grid', gap: 8, position: 'relative' }}
              >
                {ROUNDS_STAGES.map((s) => (
                  <div key={s.id} style={{ minWidth: 0 }}>
                    {s.n === col ? <LaneCard lane={lane} index={laneIndex} /> : null}
                  </div>
                ))}
              </div>

              {/* Retry is a CLIENT fetch, not a form POST: /api/visits/[id]/retry
                  is a JSON route, and a native form submit would navigate the
                  browser to a JSON blob — a failure that looks like success in
                  a screenshot. See retry-button.tsx. */}
              {lane.kind === 'failed' ? (
                <div style={{ marginTop: 6 }}>
                  <RoundsRetryButton visitId={lane.id} />
                </div>
              ) : null}
            </li>
          );
        })}
      </ul>

      <BoardLegend />
    </div>
  );
}

function BoardLegend() {
  const items: { key: string; label: string; swatch: React.CSSProperties }[] = [
    { key: 'ready', label: 'Ready', swatch: { background: 'var(--rounds-paper-1)' } },
    { key: 'recording', label: 'Recording', swatch: { background: 'var(--rounds-critical)' } },
    { key: 'processing', label: 'Processing', swatch: { background: 'var(--rounds-em)' } },
    { key: 'signed', label: 'Signed', swatch: { background: 'var(--rounds-ready)' } },
  ];
  return (
    <div
      data-testid="rounds-board-legend"
      style={{
        display: 'flex',
        flexWrap: 'wrap',
        gap: 14,
        marginTop: 18,
        paddingTop: 12,
        borderTop: '1px solid var(--rounds-line-1)',
      }}
    >
      {items.map((i) => (
        <span
          key={i.key}
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: 6,
            fontFamily: 'var(--rounds-font-ui)',
            fontSize: 11.5,
            color: 'var(--rounds-text-3)',
          }}
        >
          <span
            aria-hidden
            style={{ width: 9, height: 9, borderRadius: 2, ...i.swatch }}
          />
          {i.label}
        </span>
      ))}
    </div>
  );
}
