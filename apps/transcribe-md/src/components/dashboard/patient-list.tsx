// ============================================================================
// Phase 5 — Linear V1 Faithful patient list.
// ----------------------------------------------------------------------------
// Reference: dashboard-v1.html `.row-list` (Linear-density 32-40px row
// pattern; mono timestamps; specialty pill with colored dot; quiet
// status pill on the right edge).
//
// The Phase 3 cream-card grid is gone. Linear V1 patient list is a flat
// hairline-divided row stack on the dark canvas. Each row carries:
//
//   ▎ time/date in mono
//   ▎ patient name + meta
//   ▎ specialty pill
//   ▎ last-visit chief-complaint snippet
//   ▎ status pill
//   ▎ chev hint on hover
//
// Server component — no local state, all data is loaded upstream.
// ============================================================================

import Link from 'next/link';
import type { TranscribeVisitStatus } from '@prisma/client';

import { Ic } from '@/components/ui/icon';
import { LocalTime } from '@/components/ui/local-time';

export type DashboardListPatient = {
  id: string;
  name: string;
  dateOfBirth: string | null;
  visitCount: number;
  lastVisitAt: string | null;
  lastVisitSpecialty: string | null;
  lastVisitStatus: TranscribeVisitStatus | null;
  lastVisitNeedsReview: boolean;
  /** Batch H signal — non-null means the most recent visit has been
   *  signed; drives the "Signed" pill regardless of status enum. */
  lastVisitSignedAt: string | null;
  /** Optional one-line chief-complaint snippet (server-clipped to ~80 chars). */
  lastVisitChiefComplaint: string | null;
};

function pillFor(
  status: TranscribeVisitStatus | null,
  needsReview: boolean,
  signedAt: string | null,
): { cls: string; label: string } {
  // Batch H — signedAt overrides every other lifecycle signal.
  if (signedAt !== null)
    return { cls: 'qm-lin-pill qm-lin-pill--signed', label: 'Signed' };
  if (!status) return { cls: 'qm-lin-pill qm-lin-pill--draft', label: 'No visits yet' };
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

interface PatientListProps {
  patients: DashboardListPatient[];
}

export function PatientList({ patients }: PatientListProps) {
  return (
    <section style={{ padding: '8px 24px 32px' }}>
      <header
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          margin: '14px 0 6px',
          paddingBottom: 6,
          borderBottom: '1px solid var(--color-linear-hairline)',
        }}
      >
        <div
          style={{
            fontFamily: 'var(--font-sans)',
            fontSize: 12.5,
            color: 'var(--color-linear-text)',
            fontWeight: 500,
            letterSpacing: '-0.005em',
          }}
        >
          Patients
        </div>
        <div
          style={{
            fontFamily: 'var(--font-mono)',
            fontSize: 11,
            color: 'var(--color-linear-text-3)',
          }}
        >
          {patients.length} on the schedule
        </div>
      </header>

      <div style={{ display: 'flex', flexDirection: 'column' }}>
        {patients.map((p) => (
          <PatientRow key={p.id} patient={p} />
        ))}
      </div>
    </section>
  );
}

function PatientRow({ patient }: { patient: DashboardListPatient }) {
  const pill = pillFor(
    patient.lastVisitStatus,
    patient.lastVisitNeedsReview,
    patient.lastVisitSignedAt,
  );
  const birthYear = patient.dateOfBirth
    ? Number.parseInt(patient.dateOfBirth.slice(0, 4), 10)
    : null;
  const ageNow = birthYear ? new Date().getFullYear() - birthYear : null;

  return (
    <Link
      href={`/patients/${patient.id}`}
      style={{
        display: 'grid',
        gridTemplateColumns: '110px 1fr 110px 1fr 140px 24px',
        alignItems: 'center',
        gap: 12,
        padding: '0 6px',
        height: 36,
        borderBottom: '1px solid var(--color-linear-hairline)',
        color: 'inherit',
        textDecoration: 'none',
        fontSize: 13,
        transition: 'background-color 100ms ease',
      }}
      className="qm-lin-row"
    >
      {/* Last visit / new */}
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
        {patient.lastVisitAt ? (
          <LocalTime iso={patient.lastVisitAt} variant="date" />
        ) : (
          <span style={{ color: 'var(--color-linear-text-3)' }}>—</span>
        )}
      </div>

      {/* Patient name + meta */}
      <div style={{ minWidth: 0 }}>
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
          {patient.name}
        </div>
        <div
          style={{
            color: 'var(--color-linear-text-3)',
            fontSize: 11,
            fontFamily: 'var(--font-mono)',
            fontVariantNumeric: 'tabular-nums',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
          }}
        >
          {ageNow !== null ? `${ageNow}` : null}
          {ageNow !== null && patient.visitCount > 0 ? ' · ' : ''}
          {patient.visitCount > 0
            ? `${patient.visitCount} visit${patient.visitCount === 1 ? '' : 's'}`
            : ''}
        </div>
      </div>

      {/* Specialty */}
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
        {patient.lastVisitSpecialty ?? '—'}
      </div>

      {/* Chief-complaint snippet */}
      <div
        style={{
          fontFamily: 'var(--font-sans)',
          fontSize: 12.5,
          color: 'var(--color-linear-text-2)',
          overflow: 'hidden',
          textOverflow: 'ellipsis',
          whiteSpace: 'nowrap',
        }}
      >
        {patient.lastVisitChiefComplaint ?? ''}
      </div>

      {/* Status pill */}
      <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
        <span className={pill.cls}>{pill.label}</span>
      </div>

      {/* Chev */}
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
}
