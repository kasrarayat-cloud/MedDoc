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

function pillFor(
  status: TranscribeVisitStatus,
  needsReview: boolean,
  signedAt: string | null,
): { cls: string; label: string; suffix?: string } {
  // Batch H — signedAt overrides every other lifecycle signal.
  if (signedAt !== null) {
    return {
      cls: 'qm-lin-pill qm-lin-pill--signed',
      label: 'Signed',
      suffix: formatLocalDate(signedAt),
    };
  }
  if (status === 'SIGNED')
    return { cls: 'qm-lin-pill qm-lin-pill--signed', label: 'Signed' };
  if (status === 'READY') {
    return needsReview
      ? { cls: 'qm-lin-pill qm-lin-pill--review', label: 'Needs review' }
      : { cls: 'qm-lin-pill qm-lin-pill--ready', label: 'Ready' };
  }
  if (status === 'FAILED')
    return { cls: 'qm-lin-pill qm-lin-pill--review', label: 'Error' };
  return { cls: 'qm-lin-pill qm-lin-pill--processing', label: 'Drafting' };
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
  return (
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
                    <span className={pill.cls}>
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
}
