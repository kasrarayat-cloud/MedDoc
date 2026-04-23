'use client';

// HANDOFF §2.2 VisitList — grouped by day (Today / Yesterday / This
// week / Earlier). Each row is a glass-surface grid linking to the
// visit page with time · avatar+name · specialty chip · duration ·
// status chip.
//
// Client component so grouping + time formatting use the VIEWER's
// timezone, not the Node container's. Callers pass ISO 8601 UTC
// strings for createdAt; everything downstream resolves locally.

import Link from 'next/link';
import type { TranscribeVisitStatus } from '@prisma/client';

import { Avatar } from '@/components/ui/avatar';
import { Ic } from '@/components/ui/icon';
import { LocalTime } from '@/components/ui/local-time';
import { SpecChip, type SpecialtyKind } from '@/components/ui/spec-chip';
import { bucketForLocalDay, type DayBucket } from '@/lib/format-time';

export type DashboardVisit = {
  id: string;
  patientName: string | null;
  patientFallback: string | null;
  specialty: string;
  status: TranscribeVisitStatus;
  needsReview: boolean;
  /** ISO 8601 UTC — `createdAt.toISOString()` from the server. */
  createdAt: string;
  audioDurationSec: number | null;
};

const KNOWN: readonly SpecialtyKind[] = [
  'cardiology',
  'pain',
  'ortho',
  'primary',
  'pulmonology',
  'ophthalmology',
];
function toSpecKind(raw: string | null | undefined): SpecialtyKind {
  if (!raw) return 'primary';
  const lower = raw.toLowerCase() as SpecialtyKind;
  return KNOWN.includes(lower) ? lower : 'primary';
}

type StatusTone = 'mint' | 'amber' | 'coral' | 'accent';
function chipFor(
  status: TranscribeVisitStatus,
  needsReview: boolean
): { label: string; tone: StatusTone } {
  if (status === 'SIGNED') return { label: 'Signed', tone: 'mint' };
  if (status === 'READY') {
    return needsReview
      ? { label: 'Needs review', tone: 'amber' }
      : { label: 'Ready', tone: 'mint' };
  }
  if (status === 'FAILED') return { label: 'Error', tone: 'coral' };
  return { label: 'Drafting', tone: 'accent' };
}

function formatDuration(sec: number | null): string {
  if (sec == null) return '—';
  const m = Math.floor(sec / 60);
  const s = sec % 60;
  return `${m}:${s.toString().padStart(2, '0')}`;
}

/** Group visits by local-day bucket. Callers pass already-ordered
 *  (desc createdAt) visits. Empty groups are dropped so the UI
 *  doesn't render an empty "Yesterday" divider. */
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

export function VisitList({ visits }: { visits: DashboardVisit[] }) {
  const groups = groupByDay(visits);
  return (
    <div style={{ padding: '22px 32px 32px' }}>
      {groups.map((group) => (
        <div key={group.label} style={{ marginBottom: 22 }}>
          <div
            className="qm-sectlabel"
            style={{
              marginBottom: 10,
              display: 'flex',
              alignItems: 'center',
              gap: 10,
            }}
          >
            <span>{group.label}</span>
            <span style={{ flex: 1, height: 1, background: 'var(--line)' }} />
            <span style={{ color: 'var(--fg-4)' }}>{group.rows.length}</span>
          </div>
          <div className="qm-glass" style={{ overflow: 'hidden' }}>
            {group.rows.map((v, i) => {
              const chip = chipFor(v.status, v.needsReview);
              const displayName = v.patientName ?? v.patientFallback ?? 'Patient';
              return (
                <Link
                  key={v.id}
                  href={`/visits/${v.id}`}
                  style={{
                    display: 'grid',
                    gridTemplateColumns:
                      '90px 1fr 160px 110px 160px 40px',
                    alignItems: 'center',
                    gap: 14,
                    padding: '12px 16px',
                    borderBottom:
                      i === group.rows.length - 1
                        ? 'none'
                        : '1px solid var(--line)',
                    color: 'inherit',
                    textDecoration: 'none',
                    transition: 'background .12s',
                  }}
                  className="visit-list-row"
                >
                  <div
                    style={{
                      fontFamily: 'var(--mono)',
                      fontSize: 12,
                      color: 'var(--fg-3)',
                    }}
                  >
                    <LocalTime
                      iso={v.createdAt}
                      variant={group.withDow ? 'timeWithDay' : 'time'}
                    />
                  </div>
                  <div
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: 10,
                      minWidth: 0,
                    }}
                  >
                    <Avatar name={displayName} size={28} />
                    <div
                      className="qm-serif"
                      style={{
                        fontSize: 15,
                        letterSpacing: '-0.01em',
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                        whiteSpace: 'nowrap',
                      }}
                    >
                      {displayName}
                    </div>
                  </div>
                  <SpecChip kind={toSpecKind(v.specialty)} size="sm" />
                  <div
                    style={{
                      fontFamily: 'var(--mono)',
                      fontSize: 12,
                      color: 'var(--fg-3)',
                    }}
                  >
                    {formatDuration(v.audioDurationSec)}
                  </div>
                  <span
                    className={`qm-chip qm-chip-${chip.tone} dot`}
                    style={{ justifySelf: 'start' }}
                  >
                    {chip.label}
                  </span>
                  <Ic.chevRight
                    width={14}
                    height={14}
                    style={{ color: 'var(--fg-4)' }}
                  />
                </Link>
              );
            })}
          </div>
        </div>
      ))}
    </div>
  );
}
