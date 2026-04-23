'use client';

// HANDOFF §2.2 PatientCard — .qm-glass.hover card with avatar + serif
// name + b.YYYY / visits meta, status chip (from latest visit), and a
// specialty chip + last-visit timestamp footer.
//
// Client component so the relative-time label ("2h ago", "Apr 14")
// renders in the viewer's local timezone. `lastVisitAt` and
// `dateOfBirth` arrive as ISO 8601 strings from the server — the
// server converts via `Date.toISOString()` / `.toISOString().slice(0,10)`.

import Link from 'next/link';
import type { TranscribeVisitStatus } from '@prisma/client';

import { Avatar } from '@/components/ui/avatar';
import { SpecChip, type SpecialtyKind } from '@/components/ui/spec-chip';
import { formatRelativeTime } from '@/lib/format-time';

export type DashboardPatient = {
  id: string;
  name: string;
  /** YYYY-MM-DD or null. DOB is a date — timezone is irrelevant so we
   *  flatten it on the server. */
  dateOfBirth: string | null;
  visitCount: number;
  /** ISO 8601 UTC or null. Formatted locally via formatRelativeTime. */
  lastVisitAt: string | null;
  lastVisitSpecialty: string | null;
  lastVisitStatus: TranscribeVisitStatus | null;
  lastVisitNeedsReview: boolean;
};

/** Small status chip summarising the patient's most-recent visit. */
type StatusTone = 'mint' | 'amber' | 'coral' | 'accent' | 'blue';
function chipFor(
  status: TranscribeVisitStatus | null,
  needsReview: boolean
): { label: string; tone: StatusTone } | null {
  if (!status) return null;
  if (status === 'SIGNED') return { label: 'Signed', tone: 'mint' };
  if (status === 'READY') {
    return needsReview
      ? { label: 'Needs review', tone: 'amber' }
      : { label: 'Ready', tone: 'mint' };
  }
  if (status === 'FAILED') return { label: 'Error', tone: 'coral' };
  return { label: 'Drafting', tone: 'accent' };
}

/** The six-specialty enum (HANDOFF §4) is a closed list; anything the
 *  DB carries that doesn't match falls back to `primary` so the chip
 *  still renders. */
const KNOWN: readonly SpecialtyKind[] = [
  'cardiology',
  'pain',
  'ortho',
  'primary',
  'pulmonology',
  'ophthalmology',
];
function toSpecKind(raw: string | null): SpecialtyKind {
  if (!raw) return 'primary';
  const lower = raw.toLowerCase() as SpecialtyKind;
  return KNOWN.includes(lower) ? lower : 'primary';
}

export function PatientCard({ patient }: { patient: DashboardPatient }) {
  const chip = chipFor(patient.lastVisitStatus, patient.lastVisitNeedsReview);
  // DOB comes as YYYY-MM-DD — parse the year without going through
  // Date() so a browser in UTC-8 doesn't subtract a day on "2026-01-01".
  const birthYear = patient.dateOfBirth
    ? Number.parseInt(patient.dateOfBirth.slice(0, 4), 10)
    : null;

  return (
    <Link
      href={`/patients/${patient.id}`}
      className="qm-glass hover"
      style={{
        padding: '18px 18px 16px',
        display: 'flex',
        flexDirection: 'column',
        gap: 12,
        textDecoration: 'none',
        color: 'inherit',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: 12 }}>
        <Avatar name={patient.name} size={44} />
        <div style={{ flex: 1, minWidth: 0 }}>
          <div
            className="qm-serif"
            style={{
              fontSize: 17,
              letterSpacing: '-0.01em',
              lineHeight: 1.2,
              color: 'var(--fg)',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
            }}
          >
            {patient.name}
          </div>
          <div
            style={{
              color: 'var(--fg-3)',
              fontSize: 12,
              fontFamily: 'var(--mono)',
              marginTop: 2,
            }}
          >
            {birthYear ? `b. ${birthYear} · ` : ''}
            {patient.visitCount} visit{patient.visitCount === 1 ? '' : 's'}
          </div>
        </div>
        {chip && (
          <span
            className={`qm-chip qm-chip-${chip.tone} dot`}
            style={{ fontSize: 10 }}
          >
            {chip.label}
          </span>
        )}
      </div>
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
        }}
      >
        <SpecChip kind={toSpecKind(patient.lastVisitSpecialty)} size="sm" />
        <div
          style={{
            color: 'var(--fg-4)',
            fontSize: 11.5,
            fontFamily: 'var(--mono)',
          }}
        >
          {patient.lastVisitAt
            ? `Last: ${formatRelativeTime(patient.lastVisitAt)}`
            : 'No visits yet'}
        </div>
      </div>
    </Link>
  );
}
