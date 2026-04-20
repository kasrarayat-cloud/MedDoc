'use client';

import Link from 'next/link';
import { TiltCard } from '@/components/tilt-card';
import type { PatientListItem } from '@/lib/patients-pagination';

function relativeTime(d: Date): string {
  const diffMs = Date.now() - d.getTime();
  const m = Math.floor(diffMs / 60_000);
  if (m < 1) return 'just now';
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  const days = Math.floor(h / 24);
  if (days < 7) return `${days}d ago`;
  return d.toLocaleDateString();
}

function formatDob(d: Date | null): string | null {
  if (!d) return null;
  // Same-day stability across zones — DB column is DATE.
  return d.toISOString().slice(0, 10);
}

interface Props {
  patient: PatientListItem;
}

export function PatientCard({ patient }: Props) {
  const initial = patient.name.charAt(0).toUpperCase() || '?';
  const dob = formatDob(patient.dateOfBirth);
  const visitLabel =
    patient.visitCount === 0
      ? 'No visits yet'
      : `${patient.visitCount} visit${patient.visitCount === 1 ? '' : 's'}`;

  return (
    <Link
      href={`/patients/${patient.id}`}
      className="block focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500 focus-visible:ring-offset-2 focus-visible:ring-offset-bg-base rounded-xl"
    >
      <TiltCard className="h-full">
        <div className="group glow-violet relative flex h-full flex-col gap-4 rounded-xl border border-border-default bg-bg-surface-1/60 p-5 transition-colors duration-300 ease-[cubic-bezier(0.4,0,0.2,1)] hover:border-border-emphasis">
          <div className="flex items-start gap-3">
            <div
              aria-hidden
              className="flex h-10 w-10 flex-none items-center justify-center rounded-full bg-[linear-gradient(135deg,#4C1D95_0%,#7C3AED_50%,#A855F7_100%)] text-[14px] font-semibold text-white shadow-[0_0_0_1px_rgba(167,139,250,0.3)]"
            >
              {initial}
            </div>
            <div className="min-w-0 flex-1">
              <div className="truncate text-[14px] font-medium text-text-primary">
                {patient.name}
              </div>
              <div className="mt-0.5 flex items-center gap-2 text-[12px] text-text-muted">
                {dob ? <span>b. {dob}</span> : <span>No DOB on file</span>}
                {patient.externalId && (
                  <>
                    <span aria-hidden className="text-text-muted">
                      ·
                    </span>
                    <span className="truncate">ID {patient.externalId}</span>
                  </>
                )}
              </div>
            </div>
          </div>

          <div className="mt-auto flex items-center justify-between gap-3">
            <span className="inline-flex items-center gap-1.5 rounded-full border border-border-subtle bg-bg-surface-2 px-2.5 py-0.5 text-[11px] font-medium tracking-tight text-text-tertiary">
              {visitLabel}
            </span>
            {patient.lastVisitAt && patient.lastVisitSpecialty ? (
              <span className="inline-flex items-center gap-1.5 text-[11px] text-text-tertiary">
                <span className="truncate">{patient.lastVisitSpecialty}</span>
                <span aria-hidden className="text-text-muted">
                  ·
                </span>
                <span>{relativeTime(patient.lastVisitAt)}</span>
              </span>
            ) : (
              <span className="text-[11px] text-text-muted">—</span>
            )}
          </div>
        </div>
      </TiltCard>
    </Link>
  );
}
