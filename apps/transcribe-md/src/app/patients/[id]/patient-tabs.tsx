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
 *  so the UI stays clean for the common case. */
export function PatientTabs({
  patientId,
  active,
  activeCount,
  trashCount,
}: Props) {
  return (
    <div className="mb-4 flex items-center gap-1 border-b border-border-subtle">
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
            ? 'border-warning text-text-primary'
            : 'border-violet-400 text-text-primary'
          : 'border-transparent text-text-tertiary hover:text-text-secondary'
      )}
    >
      <span>{label}</span>
      <span
        className={cn(
          'inline-flex min-w-[20px] items-center justify-center rounded-full px-1.5 py-0.5 text-[11px] font-semibold tracking-tight',
          active
            ? tone === 'warning'
              ? 'bg-warning/20 text-warning'
              : 'bg-violet-500/20 text-violet-200'
            : 'bg-bg-surface-2 text-text-muted'
        )}
      >
        {count}
      </span>
    </Link>
  );
}
