'use client';

// HANDOFF §2.2 PatientCard — .qm-glass.hover card with avatar + serif
// name + b.YYYY / visits meta, status chip (from latest visit), and a
// specialty chip + last-visit timestamp footer.
//
// Client component so the relative-time label ("2h ago", "Apr 14")
// renders in the viewer's local timezone. `lastVisitAt` and
// `dateOfBirth` arrive as ISO 8601 strings from the server — the
// server converts via `Date.toISOString()` / `.toISOString().slice(0,10)`.
//
// Phase 2 (Clinician remodel) — Strategy A dual-theme via additive
// `theme` prop. Default `'legacy'` keeps the existing dark .qm-glass
// rendering identical. Pages opt in to the Clinician chrome by passing
// `theme="clinician"`, which renders a warm cream `.qm-cl-card-soft`
// surface using the rounded-square `.qm-cl-avatar-{tone}` chip and
// status pills from the .qm-cl-pill-* catalog.

import Link from 'next/link';
import type { TranscribeVisitStatus } from '@prisma/client';

import { Avatar } from '@/components/ui/avatar';
import { SpecChip, type SpecialtyKind } from '@/components/ui/spec-chip';
import { formatRelativeTime } from '@/lib/format-time';

type PatientCardTheme = 'legacy' | 'clinician';

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

/** Clinician status pill — maps the same status/needsReview signals to
 *  the .qm-cl-pill-* catalog. SIGNED → sage-deep label, READY ready →
 *  sage, READY+needsReview → amber, FAILED → coral, else (DRAFT) →
 *  soft. Keeps the human-readable label identical to the legacy chip. */
type ClinicianPillTone = 'sage' | 'sage-deep' | 'amber' | 'coral' | 'soft' | 'teal';
function clinicianPillFor(
  status: TranscribeVisitStatus | null,
  needsReview: boolean
): { label: string; tone: ClinicianPillTone } | null {
  if (!status) return null;
  if (status === 'SIGNED') return { label: 'Signed', tone: 'sage-deep' };
  if (status === 'READY') {
    return needsReview
      ? { label: 'Needs review', tone: 'amber' }
      : { label: 'Ready', tone: 'sage' };
  }
  if (status === 'FAILED') return { label: 'Error', tone: 'coral' };
  return { label: 'Drafting', tone: 'teal' };
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

/** Pick a stable Clinician avatar tint from name (so the same patient
 *  always gets the same color across the app, just like Avatar). The
 *  five tones are sage/teal/amber/coral/sky per the dashboard mockup. */
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

interface PatientCardProps {
  patient: DashboardPatient;
  theme?: PatientCardTheme;
}

export function PatientCard({ patient, theme = 'legacy' }: PatientCardProps) {
  if (theme === 'clinician') {
    return <ClinicianPatientCard patient={patient} />;
  }
  return <LegacyPatientCard patient={patient} />;
}

function LegacyPatientCard({ patient }: { patient: DashboardPatient }) {
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

function ClinicianPatientCard({ patient }: { patient: DashboardPatient }) {
  const pill = clinicianPillFor(
    patient.lastVisitStatus,
    patient.lastVisitNeedsReview
  );
  const birthYear = patient.dateOfBirth
    ? Number.parseInt(patient.dateOfBirth.slice(0, 4), 10)
    : null;
  const avatarTone = pickClinicianAvatarTone(patient.name);
  const initials = clinicianInitials(patient.name) || '?';

  return (
    <Link
      href={`/patients/${patient.id}`}
      className="qm-cl-card-soft"
      style={{
        padding: '18px 18px 16px',
        display: 'flex',
        flexDirection: 'column',
        gap: 14,
        textDecoration: 'none',
        color: 'inherit',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: 12 }}>
        <div
          aria-hidden
          className={`qm-cl-avatar qm-cl-avatar-${avatarTone}`}
        >
          {initials}
        </div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div
            className="qm-cl-serif"
            style={{
              fontSize: 17,
              letterSpacing: '-0.01em',
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
            }}
          >
            {birthYear ? `b. ${birthYear} · ` : ''}
            {patient.visitCount} visit{patient.visitCount === 1 ? '' : 's'}
          </div>
        </div>
        {pill && (
          <span
            className={`qm-cl-pill qm-cl-pill-${pill.tone}`}
            style={{ fontSize: 10.5 }}
          >
            <span className="qm-cl-pill-dot" />
            {pill.label}
          </span>
        )}
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
            color: 'var(--ink-3)',
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
