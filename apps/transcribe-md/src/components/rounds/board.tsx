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

function LaneCard({ lane }: { lane: BoardLane }) {
  const critical = lane.criticalCount > 0;

  const border = critical
    ? `1px solid var(--rounds-critical)`
    : lane.kind === 'failed'
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

  const fg =
    lane.kind === 'ready'
      ? 'var(--rounds-ink)'
      : lane.kind === 'signed'
        ? 'var(--rounds-signed)'
        : 'var(--rounds-text-1)';

  return (
    <Link
      href={`/visits/${lane.id}`}
      data-testid={`rounds-lane-card-${lane.id}`}
      data-lane-kind={lane.kind}
      data-critical={critical ? 'true' : 'false'}
      aria-label={`${lane.patientLabel}, ${lane.kind}${critical ? ', critical interaction' : ''}`}
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
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
        {critical ? (
          // The glyph is part of the text, not an icon-only signal — a screen
          // reader gets "warning" in the label above, and a greyscale printout
          // still shows it.
          <span aria-hidden style={{ color: 'var(--rounds-critical)' }}>
            ⚠
          </span>
        ) : null}
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

      {/* ONE line, and only when there is a real one to show. A critical card
          with nothing readable in the payload renders no line rather than a
          composed summary. */}
      {critical && lane.topInteraction ? (
        <div
          style={{
            marginTop: 4,
            fontFamily: 'var(--rounds-font-mono)',
            fontSize: 11,
            color: 'var(--rounds-critical)',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
          }}
        >
          {lane.topInteraction}
        </div>
      ) : null}
    </Link>
  );
}

export function RoundsBoard({
  lanes,
  emptyHref = '/visits/new',
}: {
  lanes: BoardLane[];
  emptyHref?: string;
}) {
  if (lanes.length === 0) {
    // An invitation to record, not a mood. No illustration, no "nothing here
    // yet" shrug — the one thing a doctor would want to do next.
    return (
      <div
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
        <Link
          href={emptyHref}
          style={{
            display: 'inline-block',
            padding: '9px 16px',
            borderRadius: 'var(--rounds-radius-sm)',
            background: 'var(--rounds-accent)',
            color: '#fff',
            fontFamily: 'var(--rounds-font-ui)',
            fontWeight: 600,
            fontSize: 13.5,
            textDecoration: 'none',
          }}
        >
          Start a visit
        </Link>
      </div>
    );
  }

  const counts = ROUNDS_STAGES.map(
    (s) => lanes.filter((l) => cardColumn(l) === s.n).length,
  );

  return (
    <div data-testid="rounds-board">
      {/* Numbered stage columns, with counts from the lanes actually present. */}
      <div
        className="qm-rounds-board-grid qm-rounds-board-head"
        role="row"
        style={{ display: 'grid', gap: 8, alignItems: 'end', marginBottom: 6 }}
      >
        {ROUNDS_STAGES.map((s, i) => (
          <div key={s.id} role="columnheader" style={{ minWidth: 0 }}>
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
        {lanes.map((lane) => {
          const col = cardColumn(lane);
          return (
            <li
              key={lane.id}
              data-testid={`rounds-lane-${lane.id}`}
              style={{
                position: 'relative',
                // The critical lane ROW tints, not just the card — it is what
                // makes a red lane findable while scanning a long board.
                background:
                  lane.criticalCount > 0
                    ? 'rgba(201,58,46,.06)'
                    : 'transparent',
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
                    {s.n === col ? <LaneCard lane={lane} /> : null}
                  </div>
                ))}
              </div>

              {lane.kind === 'failed' ? (
                <form
                  action={`/api/visits/${lane.id}/retry`}
                  method="post"
                  style={{ marginTop: 6 }}
                >
                  <button
                    type="submit"
                    data-testid={`rounds-retry-${lane.id}`}
                    style={{
                      fontFamily: 'var(--rounds-font-ui)',
                      fontSize: 12,
                      fontWeight: 600,
                      color: 'var(--rounds-critical)',
                      background: 'transparent',
                      border: '1px solid var(--rounds-critical)',
                      borderRadius: 'var(--rounds-radius-sm)',
                      padding: '4px 10px',
                      cursor: 'pointer',
                    }}
                  >
                    Retry
                  </button>
                </form>
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
    { key: 'critical', label: 'Critical', swatch: { border: '2px solid var(--rounds-critical)' } },
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
