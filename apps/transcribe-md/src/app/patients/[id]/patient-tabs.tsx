import Link from 'next/link';
import { cn } from '@/lib/cn';

type TabKey = 'active' | 'trash';

interface Props {
  patientId: string;
  active: TabKey;
  activeCount: number;
  trashCount: number;
}

/** Tab header for /patients/[id]. Server component — both tabs are
 *  <Link>s so the server re-renders with the new ?tab= on click.
 *  The Trash tab is hidden when the patient has zero trashed visits
 *  so the UI stays clean for the common case.
 *
 *  Currently unused — page.tsx renders its own inline <TabBar> with
 *  the full tab catalog (visits / notes / files / trash). Kept here
 *  in case future server-only entry points need a slimmer variant. */
export function PatientTabs({
  patientId,
  active,
  activeCount,
  trashCount,
}: Props) {
  return (
    <div className="mb-4 flex items-center gap-1 border-b border-linear-border">
      <TabLink
        href={`/patients/${patientId}`}
        label="Active"
        count={activeCount}
        active={active === 'active'}
        tone="neutral"
      />
      {trashCount > 0 && (
        <TabLink
          href={`/patients/${patientId}?tab=trash`}
          label="Trash"
          count={trashCount}
          active={active === 'trash'}
          tone="warning"
        />
      )}
    </div>
  );
}

function TabLink({
  href,
  label,
  count,
  active,
  tone,
}: {
  href: string;
  label: string;
  count: number;
  active: boolean;
  tone: 'neutral' | 'warning';
}) {
  return (
    <Link
      href={href}
      prefetch={false}
      className={cn(
        'relative -mb-px flex items-center gap-2 border-b-2 px-4 py-3 text-[14px] font-medium transition-colors',
        active
          ? tone === 'warning'
            ? 'border-linear-warning text-linear-text'
            : 'border-linear-sage text-linear-text'
          : 'border-transparent text-linear-text-3 hover:text-linear-text-2'
      )}
    >
      <span>{label}</span>
      <span
        className={cn(
          'inline-flex min-w-[20px] items-center justify-center rounded-full px-1.5 py-0.5 font-mono text-[10px] font-medium tracking-tight tabular-nums',
          active
            ? tone === 'warning'
              ? 'bg-[rgba(212,164,55,0.18)] text-linear-warning'
              : 'bg-linear-sage-tint text-linear-sage-bright'
            : 'bg-linear-surface-2 text-linear-text-3'
        )}
      >
        {count}
      </span>
    </Link>
  );
}
