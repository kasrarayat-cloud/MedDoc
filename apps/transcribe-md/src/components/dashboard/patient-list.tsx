// ============================================================================
// Phase 3 Wave 2 (dashboard density) — Mockup-fidelity patient list.
// ----------------------------------------------------------------------------
// Renders up to 11 patient rows in the generous list shape that the
// dashboard mockup specifies (docs/design-directions-v3/clinician/
// dashboard.html L584–830). Each row has:
//
//   ▎  avatar (specialty color)  ▎  name + meta line  ▎  last-visit
//                                                        meta column  ▎
//      status pill  ▎  italic snippet from chief complaint  ▎  chev
//
// Designed to live alongside the existing `<PatientCard>` grid (which
// /patients/[id] still uses). The dashboard page swaps the grid for
// this list when there are patients to show; the empty state keeps
// using the existing <EmptyPatients> banner upstream.
//
// Server component because all the data it consumes (names, DOB,
// last-visit dates, status, chief complaint, visit count) is already
// loaded in the page's existing Prisma query — we just project it
// into a list-friendly shape. No local UI state, so 'use client' would
// just bloat the bundle.
//
// Reuses tokens from globals.css:
//   .qm-cl-card / .qm-cl-patient-row / .qm-cl-avatar(-{tone})
//   .qm-cl-pill(-{tone}) / .qm-cl-pill-dot / .qm-cl-serif
// No new utility classes needed.
//
// Status-pill mapping is kept aligned with the existing visit-list +
// patient-card helpers (`clinicianPillFor`) so the same lifecycle
// signals always read the same color across the dashboard. Batch H's
// `signedAt`-overrides-status rule is honoured here too: once a visit
// is signed, the row pill never reads "Ready" or "Drafting" again.
// ============================================================================

import Link from 'next/link';
import type { TranscribeVisitStatus } from '@prisma/client';

import { Ic } from '@/components/ui/icon';
import {
  clinicianInitials,
  clinicianToneForSpecialty,
  type ClinicianAvatarTone,
} from '@/lib/clinician-specialty-color';
import { LocalTime } from '@/components/ui/local-time';

export type DashboardListPatient = {
  id: string;
  name: string;
  /** YYYY-MM-DD or null. DOB is a date — flattened on the server to
   *  avoid timezone drift on "2026-01-01" → "2025-12-31" in UTC-8. */
  dateOfBirth: string | null;
  visitCount: number;
  /** ISO 8601 UTC. Formatted in the viewer's local TZ via <LocalDate>. */
  lastVisitAt: string | null;
  lastVisitSpecialty: string | null;
  lastVisitStatus: TranscribeVisitStatus | null;
  lastVisitNeedsReview: boolean;
  /** Batch H signal — non-null means the most recent visit has been
   *  signed by the doctor; drives the sage-deep "Signed" pill. */
  lastVisitSignedAt: string | null;
  /** Optional one-line snippet for the right column. Sourced from the
   *  most recent visit's `chiefComplaint`. Server should clip this to
   *  ~80 chars before sending — the row truncates anything longer
   *  with ellipsis but no word-aware clip happens in the client. */
  lastVisitChiefComplaint: string | null;
};

type ClinicianPillTone =
  | 'sage'
  | 'sage-deep'
  | 'amber'
  | 'coral'
  | 'soft'
  | 'teal';

function pillFor(
  status: TranscribeVisitStatus | null,
  needsReview: boolean,
  signedAt: string | null
): { label: string; tone: ClinicianPillTone } {
  // Batch H — signedAt overrides every other lifecycle signal so a
  // signed visit row never re-renders as "Ready"/"Drafting".
  if (signedAt !== null) return { label: 'Signed', tone: 'sage-deep' };
  if (!status) return { label: 'No visits yet', tone: 'soft' };
  if (status === 'SIGNED') return { label: 'Signed', tone: 'sage-deep' };
  if (status === 'READY') {
    return needsReview
      ? { label: 'Needs review', tone: 'amber' }
      : { label: 'Ready', tone: 'sage' };
  }
  if (status === 'FAILED') return { label: 'Error', tone: 'coral' };
  return { label: 'Drafting', tone: 'teal' };
}

interface PatientListProps {
  patients: DashboardListPatient[];
}

export function PatientList({ patients }: PatientListProps) {
  return (
    <section style={{ padding: '8px 40px 40px' }}>
      {/* Section heading row — matches mockup L562–582 (eyebrow + serif
          headline). The "Eleven faces on the schedule." copy in the
          mockup is bespoke; we use the actual count so a single-patient
          practice doesn't read as "Eleven faces" forever. */}
      <header
        style={{
          display: 'flex',
          alignItems: 'flex-end',
          justifyContent: 'space-between',
          marginBottom: 16,
          flexWrap: 'wrap',
          gap: 12,
        }}
      >
        <div>
          <div className="qm-cl-eyebrow" style={{ marginBottom: 8 }}>
            Today&rsquo;s patients
          </div>
          <h2
            className="qm-cl-serif"
            style={{
              margin: 0,
              fontSize: 28,
              fontWeight: 400,
              letterSpacing: '-0.01em',
              lineHeight: 1.2,
              color: 'var(--ink)',
            }}
          >
            {headlineFor(patients.length)}
          </h2>
        </div>
      </header>

      <div className="qm-cl-card" style={{ overflow: 'hidden', padding: 8 }}>
        {patients.map((p) => (
          <PatientRow key={p.id} patient={p} />
        ))}
      </div>
    </section>
  );
}

function headlineFor(count: number): string {
  if (count === 0) return 'No patients on the schedule.';
  if (count === 1) return 'One face on the schedule.';
  // Spelled-out small numbers up to 12 — matches the mockup's
  // "Eleven faces" voice. Falls back to numerals beyond that.
  const SPELLED = [
    'Zero',
    'One',
    'Two',
    'Three',
    'Four',
    'Five',
    'Six',
    'Seven',
    'Eight',
    'Nine',
    'Ten',
    'Eleven',
    'Twelve',
  ];
  const word = SPELLED[count] ?? String(count);
  return `${word} faces on the schedule.`;
}

function PatientRow({ patient }: { patient: DashboardListPatient }) {
  const tone: ClinicianAvatarTone = clinicianToneForSpecialty(
    patient.lastVisitSpecialty,
    patient.name
  );
  const initials = clinicianInitials(patient.name);
  const pill = pillFor(
    patient.lastVisitStatus,
    patient.lastVisitNeedsReview,
    patient.lastVisitSignedAt
  );

  // DOB → birth year (avoid Date() to dodge TZ shifts on YYYY-MM-DD).
  const birthYear = patient.dateOfBirth
    ? Number.parseInt(patient.dateOfBirth.slice(0, 4), 10)
    : null;
  const ageNow = birthYear
    ? new Date().getFullYear() - birthYear
    : null;

  return (
    <Link
      href={`/patients/${patient.id}`}
      className="qm-cl-patient-row"
      style={{
        color: 'inherit',
        textDecoration: 'none',
        // Override the catalog default (avatar 56 / name 1fr / 200 / 140 /
        // 140 / 36) only as needed — keep the avatar + name + status
        // columns identical to the mockup, slot the remaining columns to
        // last-visit-meta / italic-snippet / chev.
        gridTemplateColumns: '56px 1fr 180px 160px 1fr 28px',
      }}
    >
      <div
        aria-hidden
        className={`qm-cl-avatar qm-cl-avatar-${tone}`}
        style={{ width: 44, height: 44 }}
      >
        {initials}
      </div>
      <div style={{ minWidth: 0 }}>
        <div
          className="qm-cl-serif"
          style={{
            fontSize: 19,
            fontStyle: 'italic',
            letterSpacing: '-0.005em',
            lineHeight: 1.2,
            color: 'var(--ink)',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
          }}
        >
          {patient.name}
        </div>
        <div
          style={{
            color: 'var(--ink-3)',
            fontSize: 12.5,
            marginTop: 3,
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
          }}
        >
          {ageNow !== null ? `${ageNow}` : null}
          {ageNow !== null && patient.lastVisitSpecialty
            ? ' · '
            : null}
          {patient.lastVisitSpecialty ?? ''}
          {(ageNow !== null || patient.lastVisitSpecialty) &&
          patient.visitCount > 0
            ? ' · '
            : ''}
          {patient.visitCount > 0 ? (
            <span style={{ fontFamily: 'var(--mono)', fontSize: 12 }}>
              {patient.visitCount} visit{patient.visitCount === 1 ? '' : 's'}
            </span>
          ) : (
            ''
          )}
        </div>
      </div>
      <div>
        <div style={{ fontSize: 13, color: 'var(--ink-2)' }}>
          {patient.lastVisitAt ? (
            <>
              Last visit{' '}
              <LocalTime iso={patient.lastVisitAt} variant="date" />
            </>
          ) : (
            <span style={{ color: 'var(--ink-3)' }}>No visits yet</span>
          )}
        </div>
      </div>
      <div>
        <span
          className={`qm-cl-pill ${
            pill.tone === 'sage-deep'
              ? 'qm-cl-pill-sage'
              : `qm-cl-pill-${pill.tone}`
          }`}
          style={{
            justifySelf: 'start',
            ...(pill.tone === 'sage-deep'
              ? {
                  background: 'var(--sage-tint-strong)',
                  color: 'var(--sage-deep)',
                }
              : null),
          }}
        >
          <span className="qm-cl-pill-dot" />
          {pill.label}
        </span>
      </div>
      <div
        style={{
          fontSize: 12.5,
          color: 'var(--ink-3)',
          minWidth: 0,
          overflow: 'hidden',
        }}
      >
        {patient.lastVisitChiefComplaint ? (
          <span
            className="qm-cl-serif"
            style={{
              fontStyle: 'italic',
              color: 'var(--ink-2)',
              display: '-webkit-box',
              WebkitLineClamp: 1,
              WebkitBoxOrient: 'vertical',
              overflow: 'hidden',
              wordBreak: 'break-word',
            }}
          >
            &ldquo;{patient.lastVisitChiefComplaint}&rdquo;
          </span>
        ) : null}
      </div>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end' }}>
        <Ic.chevRight
          width={16}
          height={16}
          style={{ color: 'var(--ink-4)' }}
        />
      </div>
    </Link>
  );
}
