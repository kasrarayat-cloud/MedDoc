'use client';

// ============================================================================
// Phase 5 — Linear V1 Faithful visit list.
// ----------------------------------------------------------------------------
// Reference: dashboard-v1.html `.row-list .stream` (visit row pattern).
//
// Grouped by day (Today / Yesterday / This week / Earlier) with a section
// header above each group (mono count chip on the right). Rows are
// flat 32-px Linear-density entries with hairline dividers.
//
// Client component so grouping + time formatting use the VIEWER's
// timezone, not the Node container's. Callers pass ISO 8601 UTC strings
// for createdAt/signedAt.
// ============================================================================

import Link from 'next/link';
import type { TranscribeVisitStatus } from '@prisma/client';

import { Ic } from '@/components/ui/icon';
import { LocalTime } from '@/components/ui/local-time';
import {
  bucketForLocalDay,
  formatLocalDate,
  type DayBucket,
} from '@/lib/format-time';

type VisitListTheme = 'legacy' | 'clinician';

export type DashboardVisit = {
  id: string;
  patientName: string | null;
  patientFallback: string | null;
  specialty: string;
  status: TranscribeVisitStatus;
  needsReview: boolean;
  /** ISO 8601 UTC. */
  createdAt: string;
  /** ISO 8601 UTC for sign timestamp, or null if unsigned. */
  signedAt: string | null;
  audioDurationSec: number | null;
};

/** R3 — `key` joins `cls`/`label` so a caller can express status as a
 *  TREATMENT instead of a chip. `key` is what this list renders, as a
 *  `data-status` attribute; `cls` is the legacy chip class, kept on the
 *  return shape but no longer read here. */
function pillFor(
  status: TranscribeVisitStatus,
  needsReview: boolean,
  signedAt: string | null,
): { cls: string; label: string; suffix?: string; key: string } {
  // Batch H — signedAt overrides every other lifecycle signal.
  if (signedAt !== null) {
    return {
      cls: 'qm-lin-pill qm-lin-pill--signed',
      label: 'Signed',
      suffix: formatLocalDate(signedAt),
      key: 'signed',
    };
  }
  if (status === 'SIGNED')
    return { cls: 'qm-lin-pill qm-lin-pill--signed', label: 'Signed', key: 'signed' };
  if (status === 'READY') {
    return needsReview
      ? { cls: 'qm-lin-pill qm-lin-pill--review', label: 'Needs review', key: 'ready' }
      : { cls: 'qm-lin-pill qm-lin-pill--ready', label: 'Ready', key: 'ready' };
  }
  if (status === 'FAILED')
    return { cls: 'qm-lin-pill qm-lin-pill--review', label: 'Error', key: 'failed' };
  return { cls: 'qm-lin-pill qm-lin-pill--processing', label: 'Drafting', key: 'processing' };
}

function formatDuration(sec: number | null): string {
  if (sec == null) return '—';
  const m = Math.floor(sec / 60);
  const s = sec % 60;
  return `${m}:${s.toString().padStart(2, '0')}`;
}

/** Group visits by local-day bucket. Empty groups are dropped. */
function groupByDay(visits: DashboardVisit[]): {
  label: DayBucket;
  withDow: boolean;
  rows: DashboardVisit[];
}[] {
  const buckets: Record<DayBucket, DashboardVisit[]> = {
    Today: [],
    Yesterday: [],
    'This week': [],
    Earlier: [],
  };
  for (const v of visits) {
    const bucket = bucketForLocalDay(v.createdAt) ?? 'Earlier';
    buckets[bucket].push(v);
  }
  const orderedLabels: DayBucket[] = [
    'Today',
    'Yesterday',
    'This week',
    'Earlier',
  ];
  return orderedLabels
    .filter((label) => buckets[label].length > 0)
    .map((label) => ({
      label,
      withDow: label === 'This week' || label === 'Earlier',
      rows: buckets[label],
    }));
}

interface VisitListProps {
  visits: DashboardVisit[];
  /** @deprecated kept for back-compat; Linear V1 is single-theme. */
  theme?: VisitListTheme;
}

export function VisitList({ visits }: VisitListProps) {
  const groups = groupByDay(visits);
  // ⚠️ R3 — THE BRIDGE, NOT A REWRITE OF 300 LINES OF INLINE STYLE.
  // Every colour in this component is an inline `var(--color-linear-*)`, and
  // those resolve to the LEGACY values unless a `.qm-rounds-host` ancestor is
  // in scope — it is applied to settings, auth and the board, never here. That
  // is precisely what the census counted on `/visits` and `/patients/[id]`.
  //
  // `.qm-rounds-host` REDECLARES all 22 of those custom properties on a scoped
  // class, so hosting this subtree retints every inline token at once — which
  // is the mechanism the bridge exists for, and why the census reports hosted
  // nodes separately from islands. Rewriting the inline styles would buy
  // nothing the host wrapper below does not already do.
  const body = (
    <div style={{ padding: '14px 24px 32px' }}>
      {groups.map((group) => (
        <div key={group.label} style={{ marginBottom: 18 }}>
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              margin: '14px 0 6px',
              paddingBottom: 6,
              borderBottom: '1px solid var(--color-linear-hairline)',
            }}
          >
            <span
              style={{
                fontFamily: 'var(--font-sans)',
                fontSize: 12.5,
                color: 'var(--color-linear-text)',
                fontWeight: 500,
                letterSpacing: '-0.005em',
              }}
            >
              {group.label}
            </span>
            <span
              style={{
                fontFamily: 'var(--font-mono)',
                fontSize: 11,
                color: 'var(--color-linear-text-3)',
              }}
            >
              {group.rows.length}
            </span>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column' }}>
            {group.rows.map((v) => {
              const pill = pillFor(v.status, v.needsReview, v.signedAt);
              const displayName =
                v.patientName ?? v.patientFallback ?? 'Patient';
              return (
                <Link
                  key={v.id}
                  href={`/visits/${v.id}`}
                  style={{
                    display: 'grid',
                    gridTemplateColumns:
                      '92px 1fr 140px 80px 160px 24px',
                    alignItems: 'center',
                    gap: 12,
                    padding: '0 6px',
                    height: 36,
                    borderBottom:
                      '1px solid var(--color-linear-hairline)',
                    color: 'inherit',
                    textDecoration: 'none',
                    fontSize: 13,
                    transition: 'background-color 100ms ease',
                  }}
                  className="qm-lin-row"
                >
                  <div
                    style={{
                      fontFamily: 'var(--font-mono)',
                      fontSize: 11.5,
                      color: 'var(--color-linear-text-3)',
                      fontVariantNumeric: 'tabular-nums',
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                      whiteSpace: 'nowrap',
                    }}
                  >
                    <LocalTime
                      iso={v.createdAt}
                      variant={group.withDow ? 'timeWithDay' : 'time'}
                    />
                  </div>
                  <div
                    style={{
                      fontFamily: 'var(--font-sans)',
                      fontSize: 13,
                      fontWeight: 600,
                      letterSpacing: '-0.005em',
                      color: 'var(--color-linear-text)',
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                      whiteSpace: 'nowrap',
                    }}
                  >
                    {displayName}
                  </div>
                  <div
                    style={{
                      fontFamily: 'var(--font-sans)',
                      fontSize: 12,
                      color: 'var(--color-linear-text-2)',
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                      whiteSpace: 'nowrap',
                    }}
                  >
                    {v.specialty}
                  </div>
                  <div
                    style={{
                      fontFamily: 'var(--font-mono)',
                      fontSize: 11.5,
                      color: 'var(--color-linear-text-3)',
                      fontVariantNumeric: 'tabular-nums',
                    }}
                  >
                    {formatDuration(v.audioDurationSec)}
                  </div>
                  <div
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'flex-end',
                      gap: 6,
                    }}
                  >
                    {/* ⚠️ R3 — STATUS AS TREATMENT, NOT A CHIP.
                        The owner's ruling on /patients/[id] was "zero legacy
                        chips": `pill.cls` is `qm-lin-pill*`, the exact family
                        the census flags on this route AND on /visits, which
                        this same component renders. So the status renders as
                        the Rounds treatment carrying `pill.key`; `pill.label`
                        is unchanged. */}
                    <span
                      className="qm-rounds-vstatus"
                      data-status={pill.key}
                    >
                      {pill.label}
                      {pill.suffix && (
                        <span
                          style={{
                            marginLeft: 4,
                            opacity: 0.75,
                          }}
                        >
                          · {pill.suffix}
                        </span>
                      )}
                    </span>
                  </div>
                  <div
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'flex-end',
                      color: 'var(--color-linear-text-3)',
                    }}
                  >
                    <Ic.chevRight width={12} height={12} />
                  </div>
                </Link>
              );
            })}
          </div>
        </div>
      ))}
    </div>
  );

  return <div className="qm-rounds-host qm-rounds-vlist">{body}</div>;
}
