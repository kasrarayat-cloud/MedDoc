import { cn } from '@/lib/cn';

/**
 * Theme — `'legacy'` (App-redesign-v1 dark surfaces, drives the existing
 * `.shimmer` sweep) or `'clinician'` (Phase 2 warm cream palette, soft
 * `animate-pulse` instead of the linear sweep). Default `'legacy'` so
 * non-migrated callers keep their look. Migrated routes pass
 * `theme="clinician"`.
 */
type SkeletonTheme = 'legacy' | 'clinician';

/**
 * Base shimmer rectangle. Every other skeleton is a styled preset of
 * this. Pure CSS (no framer-motion) — the `.shimmer` class in globals.css
 * drives the sweep, so skeletons are streaming-friendly and don't add
 * JS to first paint.
 *
 * Clinician variant: warm cream surface (`--clinician-cream-2`) with
 * a gentle `animate-pulse` (no shimmer sweep). Matches the Clinician
 * commitment to restraint — no sweeping highlights.
 */
export function Skeleton({
  className,
  theme = 'legacy',
  ...rest
}: React.HTMLAttributes<HTMLDivElement> & { theme?: SkeletonTheme }) {
  return (
    <div
      aria-hidden
      className={cn(
        theme === 'clinician'
          ? 'animate-pulse rounded-md bg-clinician-cream-2'
          : 'shimmer rounded-md',
        className
      )}
      {...rest}
    />
  );
}

/** Avatar-sized circle — matches the NavBar user pill. */
export function SkeletonAvatar({
  className,
  theme = 'legacy',
}: {
  className?: string;
  theme?: SkeletonTheme;
}) {
  return (
    <Skeleton
      theme={theme}
      className={cn('h-9 w-9 rounded-full', className)}
    />
  );
}

/** A line of body text. Pass `className` to tune width; default 60%. */
export function SkeletonText({
  className,
  lines = 1,
  theme = 'legacy',
}: {
  className?: string;
  lines?: number;
  theme?: SkeletonTheme;
}) {
  return (
    <div className="space-y-2">
      {Array.from({ length: lines }).map((_, i) => (
        <Skeleton
          key={i}
          theme={theme}
          className={cn(
            'h-3',
            i === lines - 1 ? 'w-[50%]' : 'w-[80%]',
            className
          )}
        />
      ))}
    </div>
  );
}

/** Short pill for primary CTAs. */
export function SkeletonButton({
  className,
  theme = 'legacy',
}: {
  className?: string;
  theme?: SkeletonTheme;
}) {
  return (
    <Skeleton
      theme={theme}
      className={cn('h-10 w-28 rounded-full', className)}
    />
  );
}

/** Visit card placeholder — matches the shape of <VisitCard>. */
export function SkeletonVisitCard({
  theme = 'legacy',
}: {
  theme?: SkeletonTheme;
} = {}) {
  return (
    <div
      className={cn(
        'flex h-full flex-col gap-4 rounded-xl p-5',
        theme === 'clinician'
          ? 'border border-clinician-line bg-clinician-cream-card'
          : 'border border-border-subtle bg-bg-surface-1/40'
      )}
    >
      <div className="flex items-start gap-3">
        <SkeletonAvatar theme={theme} className="h-10 w-10" />
        <div className="flex-1 space-y-2">
          <Skeleton theme={theme} className="h-3 w-[60%]" />
          <Skeleton theme={theme} className="h-2.5 w-[35%]" />
        </div>
      </div>
      <div className="mt-auto flex items-center justify-between">
        <Skeleton theme={theme} className="h-4 w-20 rounded-full" />
        <Skeleton theme={theme} className="h-3 w-16" />
      </div>
    </div>
  );
}

/** A grid of visit card skeletons. Defaults to 6 for dashboard. */
export function SkeletonVisitGrid({
  count = 6,
  theme = 'legacy',
}: {
  count?: number;
  theme?: SkeletonTheme;
} = {}) {
  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {Array.from({ length: count }).map((_, i) => (
        <SkeletonVisitCard key={i} theme={theme} />
      ))}
    </div>
  );
}

/** Settings-row skeleton — label + value stacked. */
export function SkeletonSettingsRow({
  theme = 'legacy',
}: {
  theme?: SkeletonTheme;
} = {}) {
  return (
    <div
      className={cn(
        'rounded-lg px-3.5 py-3',
        theme === 'clinician'
          ? 'border border-clinician-line bg-clinician-cream-card'
          : 'border border-border-subtle bg-bg-surface-1/40'
      )}
    >
      <Skeleton theme={theme} className="h-2.5 w-16" />
      <Skeleton theme={theme} className="mt-2 h-3 w-[70%]" />
    </div>
  );
}
