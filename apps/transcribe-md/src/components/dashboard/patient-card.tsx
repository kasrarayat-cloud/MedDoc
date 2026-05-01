'use client';

// Phase 5 — Linear V1 Faithful patient card.
// Reference: dashboard-v1.html `.row` (visit list pattern adapted to a
// patient grid card).
//
// The Phase 4 dual-theme legacy / clinician forks are collapsed onto a
// single Linear V1 render: hairline-bordered card on linear-surface-1,
// monochrome avatar (no per-specialty tint), Inter italic patient
// name dropped — Linear V1 has no Source Serif italics. Status pills
// map to the .qm-lin-pill-* family.
//
// Used by /patients/[id] (Subagent 5's surface). Keeps the prop shape
// exact so subagent 5's render path doesn't change.

import Link from 'next/link';
import type { TranscribeVisitStatus } from '@prisma/client';

import { Avatar } from '@/components/ui/avatar';
import { SpecChip, type SpecialtyKind } from '@/components/ui/spec-chip';
import { formatRelativeTime } from '@/lib/format-time';

type PatientCardTheme = 'legacy' | 'clinician';

export type DashboardPatient = {
  id: string;
  name: string;
  /** YYYY-MM-DD or null. */
  dateOfBirth: string | null;
  visitCount: number;
  /** ISO 8601 UTC or null. */
  lastVisitAt: string | null;
  lastVisitSpecialty: string | null;
  lastVisitStatus: TranscribeVisitStatus | null;
  lastVisitNeedsReview: boolean;
};

/** Linear V1 status pill class for the most-recent visit lifecycle. */
function pillFor(
  status: TranscribeVisitStatus | null,
  needsReview: boolean,
): { cls: string; label: string } | null {
  if (!status) return null;
  if (status === 'SIGNED') return { cls: 'qm-lin-pill qm-lin-pill--signed', label: 'Signed' };
  if (status === 'READY') {
    return needsReview
      ? { cls: 'qm-lin-pill qm-lin-pill--review', label: 'Needs review' }
      : { cls: 'qm-lin-pill qm-lin-pill--ready', label: 'Ready' };
  }
  if (status === 'FAILED')
    return { cls: 'qm-lin-pill qm-lin-pill--review', label: 'Error' };
  return { cls: 'qm-lin-pill qm-lin-pill--draft', label: 'Drafting' };
}

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

interface PatientCardProps {
  patient: DashboardPatient;
  /** @deprecated kept for back-compat; Linear V1 is single-theme. */
  theme?: PatientCardTheme;
}

export function PatientCard({ patient }: PatientCardProps) {
  const pill = pillFor(patient.lastVisitStatus, patient.lastVisitNeedsReview);
  const birthYear = patient.dateOfBirth
    ? Number.parseInt(patient.dateOfBirth.slice(0, 4), 10)
    : null;

  return (
    <Link
      href={`/patients/${patient.id}`}
      style={{
        display: 'flex',
        flexDirection: 'column',
        gap: 12,
        padding: '16px 18px 14px',
        background: 'var(--color-linear-surface-1)',
        border: '1px solid var(--color-linear-border)',
        borderRadius: 8,
        textDecoration: 'none',
        color: 'inherit',
        transition: 'border-color 100ms ease, background-color 100ms ease',
      }}
      onMouseEnter={(e) => {
        (e.currentTarget as HTMLAnchorElement).style.borderColor =
          'var(--color-linear-border-strong)';
      }}
      onMouseLeave={(e) => {
        (e.currentTarget as HTMLAnchorElement).style.borderColor =
          'var(--color-linear-border)';
      }}
    >
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: 12 }}>
        <Avatar name={patient.name} size={36} />
        <div style={{ flex: 1, minWidth: 0 }}>
          <div
            style={{
              fontFamily: 'var(--font-sans)',
              fontSize: 14,
              fontWeight: 500,
              letterSpacing: '-0.005em',
              lineHeight: 1.2,
              color: 'var(--color-linear-text)',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
            }}
          >
            {patient.name}
          </div>
          <div
            style={{
              color: 'var(--color-linear-text-3)',
              fontSize: 11.5,
              fontFamily: 'var(--font-mono)',
              marginTop: 2,
              fontVariantNumeric: 'tabular-nums',
            }}
          >
            {birthYear ? `b. ${birthYear} · ` : ''}
            {patient.visitCount} visit{patient.visitCount === 1 ? '' : 's'}
          </div>
        </div>
        {pill && <span className={pill.cls}>{pill.label}</span>}
      </div>
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: 8,
        }}
      >
        <SpecChip kind={toSpecKind(patient.lastVisitSpecialty)} size="sm" />
        <div
          style={{
            color: 'var(--color-linear-text-3)',
            fontSize: 11.5,
            fontFamily: 'var(--font-mono)',
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
