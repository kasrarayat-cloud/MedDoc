// HANDOFF §2.2 PatientCard — .qm-glass.hover card with avatar + serif
// name + b.YYYY / visits meta, status chip (from latest visit), and a
// specialty chip + last-visit timestamp footer.

import Link from 'next/link';
import type { TranscribeVisitStatus } from '@prisma/client';

import { Avatar } from '@/components/ui/avatar';
import { SpecChip, type SpecialtyKind } from '@/components/ui/spec-chip';

export type DashboardPatient = {
  id: string;
  name: string;
  dateOfBirth: Date | null;
  visitCount: number;
  lastVisitAt: Date | null;
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

/** Soft relative-time string used in the card footer (not crucial
 *  enough to pull in date-fns). */
function relTime(d: Date): string {
  const diffMs = Date.now() - d.getTime();
  const diffMin = diffMs / 60000;
  if (diffMin < 1) return 'just now';
  if (diffMin < 60) return `${Math.round(diffMin)}m ago`;
  const diffH = diffMin / 60;
  if (diffH < 24) return `${Math.round(diffH)}h ago`;
  if (diffH < 48) return 'yesterday';
  const diffD = diffH / 24;
  if (diffD < 7) return `${Math.round(diffD)}d ago`;
  if (diffD < 30) return `${Math.round(diffD / 7)}w ago`;
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
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
  const birthYear = patient.dateOfBirth
    ? patient.dateOfBirth.getUTCFullYear()
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
          {patient.lastVisitAt ? `Last: ${relTime(patient.lastVisitAt)}` : 'No visits yet'}
        </div>
      </div>
    </Link>
  );
}
