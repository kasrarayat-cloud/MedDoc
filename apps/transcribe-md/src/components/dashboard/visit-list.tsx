'use client';

// HANDOFF §2.2 VisitList — grouped by day (Today / Yesterday / This
// week / Earlier). Each row is a glass-surface grid linking to the
// visit page with time · avatar+name · specialty chip · duration ·
// status chip.
//
// Client component so grouping + time formatting use the VIEWER's
// timezone, not the Node container's. Callers pass ISO 8601 UTC
// strings for createdAt; everything downstream resolves locally.
//
// Phase 2 (Clinician remodel) — Strategy A dual-theme via additive
// `theme` prop. Default `'legacy'` keeps the dark .qm-glass +
// .qm-sectlabel rendering verbatim. Pages opt in to the Clinician
// chrome by passing `theme="clinician"`, which renders a generous
// `.qm-cl-patient-row` (76px-tall, 2px right slide on hover) inside
// a paper-on-cream `.qm-cl-card`.

import Link from 'next/link';
import type { TranscribeVisitStatus } from '@prisma/client';

import { Avatar } from '@/components/ui/avatar';
import { Ic } from '@/components/ui/icon';
import { LocalTime } from '@/components/ui/local-time';
import { SpecChip, type SpecialtyKind } from '@/components/ui/spec-chip';
import { bucketForLocalDay, type DayBucket } from '@/lib/format-time';

type VisitListTheme = 'legacy' | 'clinician';

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

/** Clinician status pill — same status/needsReview signals → the
 *  .qm-cl-pill-* catalog. SIGNED → sage-deep, READY clean → sage,
 *  READY+needsReview → amber, FAILED → coral, else (DRAFT/PROCESSING)
 *  → teal. Labels match the legacy chip. */
type ClinicianPillTone = 'sage' | 'sage-deep' | 'amber' | 'coral' | 'teal';
function clinicianPillFor(
  status: TranscribeVisitStatus,
  needsReview: boolean
): { label: string; tone: ClinicianPillTone } {
  if (status === 'SIGNED') return { label: 'Signed', tone: 'sage-deep' };
  if (status === 'READY') {
    return needsReview
      ? { label: 'Needs review', tone: 'amber' }
      : { label: 'Ready', tone: 'sage' };
  }
  if (status === 'FAILED') return { label: 'Error', tone: 'coral' };
  return { label: 'Drafting', tone: 'teal' };
}

const CLINICIAN_AVATAR_TONES = ['sage', 'teal', 'amber', 'coral', 'sky'] as const;
type ClinicianAvatarTone = (typeof CLINICIAN_AVATAR_TONES)[number];
function pickClinicianAvatarTone(name: string): ClinicianAvatarTone {
  const code = name.charCodeAt(0) || 0;
  return CLINICIAN_AVATAR_TONES[code % CLINICIAN_AVATAR_TONES.length]!;
}
function clinicianInitials(name: string): string {
  return name
    .split(/\s+/)
    .slice(0, 2)
    .map((s) => s[0] ?? '')
    .join('')
    .toUpperCase();
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

interface VisitListProps {
  visits: DashboardVisit[];
  theme?: VisitListTheme;
}

export function VisitList({ visits, theme = 'legacy' }: VisitListProps) {
  if (theme === 'clinician') {
    return <ClinicianVisitList visits={visits} />;
  }
  return <LegacyVisitList visits={visits} />;
}

function LegacyVisitList({ visits }: { visits: DashboardVisit[] }) {
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

function ClinicianVisitList({ visits }: { visits: DashboardVisit[] }) {
  const groups = groupByDay(visits);
  return (
    <div style={{ padding: '22px 32px 32px' }}>
      {groups.map((group) => (
        <div key={group.label} style={{ marginBottom: 28 }}>
          <div
            className="qm-cl-section-label"
            style={{
              marginBottom: 12,
              display: 'flex',
              alignItems: 'center',
              gap: 10,
            }}
          >
            <span>{group.label}</span>
            <span
              style={{ flex: 1, height: 1, background: 'var(--line)' }}
            />
            <span style={{ color: 'var(--ink-4)' }}>{group.rows.length}</span>
          </div>
          {/* `.qm-cl-card` matches the patient-list shell from the
             dashboard mockup. Inner rows are `.qm-cl-patient-row`,
             which set their own grid template + 76px-feel padding +
             2px right-slide on hover. We override grid-template here
             only to add a duration column the mockup doesn't show. */}
          <div className="qm-cl-card" style={{ overflow: 'hidden', padding: 8 }}>
            {group.rows.map((v) => {
              const pill = clinicianPillFor(v.status, v.needsReview);
              const displayName =
                v.patientName ?? v.patientFallback ?? 'Patient';
              const avatarTone = pickClinicianAvatarTone(displayName);
              const initials = clinicianInitials(displayName) || '?';
              return (
                <Link
                  key={v.id}
                  href={`/visits/${v.id}`}
                  className="qm-cl-patient-row"
                  style={{
                    color: 'inherit',
                    textDecoration: 'none',
                    // Override the catalog default (avatar-1fr-200-140-140-36)
                    // to a 6-column shape that fits the visit-row data
                    // (time / avatar+name / specialty / duration / status / chev).
                    gridTemplateColumns: '92px 1fr 160px 96px 160px 28px',
                  }}
                >
                  <div
                    style={{
                      fontFamily: 'var(--mono)',
                      fontSize: 12.5,
                      color: 'var(--ink-3)',
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
                      gap: 12,
                      minWidth: 0,
                    }}
                  >
                    <div
                      aria-hidden
                      className={`qm-cl-avatar qm-cl-avatar-${avatarTone}`}
                      style={{
                        width: 36,
                        height: 36,
                        borderRadius: 10,
                        fontSize: 13,
                      }}
                    >
                      {initials}
                    </div>
                    <div
                      className="qm-cl-serif"
                      style={{
                        fontSize: 17,
                        letterSpacing: '-0.01em',
                        color: 'var(--ink)',
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
                      fontSize: 12.5,
                      color: 'var(--ink-3)',
                    }}
                  >
                    {formatDuration(v.audioDurationSec)}
                  </div>
                  <span
                    className={`qm-cl-pill qm-cl-pill-${pill.tone}`}
                    style={{ justifySelf: 'start' }}
                  >
                    <span className="qm-cl-pill-dot" />
                    {pill.label}
                  </span>
                  <Ic.chevRight
                    width={16}
                    height={16}
                    style={{ color: 'var(--ink-4)' }}
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
