import Link from 'next/link';
import { cn } from '@/lib/cn';

type TabKey = 'patients' | 'visits' | 'trash';

interface Props {
  active: TabKey;
  patientCount: number;
  visitCount: number;
  /** T-M18.2 A12: global trash count across the whole account.
   *  When 0, the Trash tab is hidden so the default view stays
   *  clean for a healthy account; when non-zero, doctors have a
   *  single-click discovery path. */
  trashCount: number;
}

/** Tab header for /dashboard. Server component — tabs are <Link>s
 *  so switching navigates in the Next 16 way (URL updates, the
 *  server component re-renders with the new query). No client
 *  state needed. */
export function TabNav({
  active,
  patientCount,
  visitCount,
  trashCount,
}: Props) {
  return (
    <div className="mb-6 flex items-center gap-1 border-b border-border-subtle">
      <TabLink
        href="/dashboard"
        label="Patients"
        count={patientCount}
        active={active === 'patients'}
        tone="primary"
      />
      <TabLink
        href="/dashboard?tab=visits"
        label="All visits"
        count={visitCount}
        active={active === 'visits'}
        tone="primary"
      />
      {trashCount > 0 && (
        <TabLink
          href="/dashboard?tab=trash"
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
  tone: 'primary' | 'warning';
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
