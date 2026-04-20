'use client';

import Link from 'next/link';
import { TiltCard } from '@/components/tilt-card';
import { cn } from '@/lib/cn';

export interface VisitCardData {
  id: string;
  patientName: string | null;
  specialty: string;
  status: string;
  createdAt: Date;
  /** T-M17.3: set when the visit has been archived (SIGNED-only
   *  lifecycle state). Drives the muted card treatment + the
   *  "Archived" chip in place of the status chip. Undefined when
   *  the caller doesn't surface archived visits (all default
   *  views). */
  archivedAt?: Date | null;
}

interface VisitCardProps {
  visit: VisitCardData;
}

/** Maps TranscribeVisit.status to a status dot + label. Statuses that
 *  don't ship in T-M2 ("processing", "ready") get sensible placeholders
 *  so the pipeline milestones don't need to touch this file. */
function statusChip(status: string): { dot: string; label: string; pulse: boolean } {
  switch (status) {
    case 'draft':
      return { dot: 'bg-text-muted', label: 'Draft', pulse: false };
    case 'processing':
      return { dot: 'bg-warning', label: 'Processing', pulse: true };
    case 'ready':
      return { dot: 'bg-cyan-400', label: 'Ready for review', pulse: false };
    case 'signed':
      return { dot: 'bg-success', label: 'Signed', pulse: false };
    default:
      return { dot: 'bg-text-muted', label: status, pulse: false };
  }
}

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

export function VisitCard({ visit }: VisitCardProps) {
  const displayName = visit.patientName?.trim() || 'Anonymous';
  const initial = displayName.charAt(0).toUpperCase();
  const { dot, label, pulse } = statusChip(visit.status);
  const isArchived = visit.archivedAt != null;

  return (
    <Link
      href={`/visits/${visit.id}`}
      className="block focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500 focus-visible:ring-offset-2 focus-visible:ring-offset-bg-base rounded-xl"
    >
      <TiltCard className="h-full">
        <div
          className={cn(
            'group glow-violet relative flex h-full flex-col gap-4 rounded-xl border border-border-default bg-bg-surface-1/60 p-5 transition-colors duration-300 ease-[cubic-bezier(0.4,0,0.2,1)] hover:border-border-emphasis',
            // T-M17.3: archived rows render dimmed with a faint
            // ring-on-hover — they're on the dashboard only when
            // the "Show archived" toggle is on, and the visual
            // muting signals "this is history, not current work".
            isArchived && 'opacity-70 hover:opacity-100'
          )}
        >
          <div className="flex items-start gap-3">
            <div
              aria-hidden
              className={cn(
                'flex h-10 w-10 flex-none items-center justify-center rounded-full bg-[linear-gradient(135deg,#4C1D95_0%,#7C3AED_50%,#A855F7_100%)] text-[14px] font-semibold text-white shadow-[0_0_0_1px_rgba(167,139,250,0.3)]',
                isArchived && 'grayscale-[30%]'
              )}
            >
              {initial}
            </div>
            <div className="min-w-0">
              <div className="truncate text-[14px] font-medium text-text-primary">
                {displayName}
              </div>
              <div className="mt-0.5 text-[12px] text-text-muted">
                {relativeTime(visit.createdAt)}
              </div>
            </div>
          </div>

          <div className="mt-auto flex items-center justify-between gap-3">
            <span className="inline-flex items-center gap-1.5 rounded-full border border-border-subtle bg-bg-surface-2 px-2.5 py-0.5 text-[11px] font-medium tracking-tight text-text-tertiary">
              {visit.specialty}
            </span>
            {isArchived ? (
              <span className="inline-flex items-center gap-1.5 rounded-full bg-bg-surface-2 px-2.5 py-0.5 text-[11px] font-medium tracking-tight text-text-muted">
                Archived
              </span>
            ) : (
              <span className="inline-flex items-center gap-1.5 text-[11px] text-text-tertiary">
                <span
                  aria-hidden
                  className={cn(
                    'inline-block h-1.5 w-1.5 rounded-full',
                    dot,
                    pulse && 'animate-pulse'
                  )}
                />
                {label}
              </span>
            )}
          </div>
        </div>
      </TiltCard>
    </Link>
  );
}
