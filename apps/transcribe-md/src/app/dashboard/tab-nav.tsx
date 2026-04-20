import Link from 'next/link';
import { cn } from '@/lib/cn';

type TabKey = 'patients' | 'visits';

interface Props {
  active: TabKey;
  patientCount: number;
  visitCount: number;
}

/** Tab header for /dashboard. Server component — both tabs are
 *  <Link>s so switching navigates in the Next 16 way (URL updates,
 *  the server component re-renders with the new query). No client
 *  state needed for a 2-tab surface. */
export function TabNav({ active, patientCount, visitCount }: Props) {
  return (
    <div className="mb-6 flex items-center gap-1 border-b border-border-subtle">
      <TabLink
        href="/dashboard"
        label="Patients"
        count={patientCount}
        active={active === 'patients'}
      />
      <TabLink
        href="/dashboard?tab=visits"
        label="All visits"
        count={visitCount}
        active={active === 'visits'}
      />
    </div>
  );
}

function TabLink({
  href,
  label,
  count,
  active,
}: {
  href: string;
  label: string;
  count: number;
  active: boolean;
}) {
  return (
    <Link
      href={href}
      prefetch={false}
      className={cn(
        'relative -mb-px flex items-center gap-2 border-b-2 px-4 py-3 text-[14px] font-medium transition-colors',
        active
          ? 'border-violet-400 text-text-primary'
          : 'border-transparent text-text-tertiary hover:text-text-secondary'
      )}
    >
      <span>{label}</span>
      <span
        className={cn(
          'inline-flex min-w-[20px] items-center justify-center rounded-full px-1.5 py-0.5 text-[11px] font-semibold tracking-tight',
          active
            ? 'bg-violet-500/20 text-violet-200'
            : 'bg-bg-surface-2 text-text-muted'
        )}
      >
        {count}
      </span>
    </Link>
  );
}
