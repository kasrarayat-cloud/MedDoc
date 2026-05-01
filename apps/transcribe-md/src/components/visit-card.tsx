'use client';

import Link from 'next/link';
import { cn } from '@/lib/cn';

/**
 * Phase 5 — Linear V1 Faithful visit card.
 *
 * Reference: dashboard-v1.html `.row` (visit list row pattern). The
 * Phase 4 violet-glow tilt-card is gone — Linear V1 uses a flat
 * hairline-bordered card on linear-surface-1 with row-hover lift.
 *
 * Used by /patients/[id] (Subagent 5's surface) — we keep the JSX
 * contract the same so that page renders correctly when subagent 5
 * migrates around it.
 */
export interface VisitCardData {
  id: string;
  patientName: string | null;
  specialty: string;
  status: string;
  createdAt: Date;
  /** T-M17.3: set when the visit has been archived. Drives the muted
   *  card treatment + the "Archived" chip in place of the status chip. */
  archivedAt?: Date | null;
}

interface VisitCardProps {
  visit: VisitCardData;
}

/** Maps TranscribeVisit.status to a status pill class + label. */
function statusClass(status: string): { cls: string; label: string } {
  switch (status) {
    case 'draft':
      return { cls: 'qm-lin-pill qm-lin-pill--draft', label: 'Draft' };
    case 'processing':
      return { cls: 'qm-lin-pill qm-lin-pill--processing', label: 'Processing' };
    case 'ready':
      return { cls: 'qm-lin-pill qm-lin-pill--ready', label: 'Ready' };
    case 'signed':
      return { cls: 'qm-lin-pill qm-lin-pill--signed', label: 'Signed' };
    default:
      return { cls: 'qm-lin-pill', label: status };
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
  const { cls, label } = statusClass(visit.status);
  const isArchived = visit.archivedAt != null;

  return (
    <Link
      href={`/visits/${visit.id}`}
      className={cn(
        'block rounded-lg outline-none focus-visible:ring-2 focus-visible:ring-linear-sage/55 focus-visible:ring-offset-2 focus-visible:ring-offset-linear-bg',
      )}
    >
      <div
        className={cn(
          'group relative flex h-full flex-col gap-4 rounded-lg border border-linear-border bg-linear-surface-1 p-5 transition-colors duration-150',
          'hover:border-linear-border-strong',
          isArchived && 'opacity-70 hover:opacity-100',
        )}
      >
        <div className="flex items-start gap-3">
          <div
            aria-hidden
            className={cn(
              'flex h-9 w-9 flex-none items-center justify-center rounded-md text-[13px] font-semibold text-white',
              isArchived && 'grayscale-[30%]',
            )}
            style={{
              background:
                'linear-gradient(135deg, var(--color-linear-sage-deep) 0%, var(--color-linear-sage) 100%)',
            }}
          >
            {initial}
          </div>
          <div className="min-w-0">
            <div className="truncate text-[13px] font-medium text-linear-text">
              {displayName}
            </div>
            <div
              className="mt-0.5 text-[11.5px] text-linear-text-3"
              style={{ fontFamily: 'var(--font-mono)' }}
            >
              {relativeTime(visit.createdAt)}
            </div>
          </div>
        </div>

        <div className="mt-auto flex items-center justify-between gap-3">
          <span className="qm-lin-pill">{visit.specialty}</span>
          {isArchived ? (
            <span className="qm-lin-pill qm-lin-pill--signed">Archived</span>
          ) : (
            <span className={cls}>{label}</span>
          )}
        </div>
      </div>
    </Link>
  );
}
