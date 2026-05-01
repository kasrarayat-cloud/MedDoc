import { cn } from '@/lib/cn';

/**
 * Phase 5 — Linear V1 Faithful skeleton primitives.
 *
 * Reference: dashboard-v1.html chrome (linear-surface-2 + hairline).
 * Linear V1 skeletons: subtle pulse on linear-surface-2, no shimmer
 * sweep, rounded 4-6 px corners. The legacy `theme` prop remains in
 * the type signature for back-compat with unmigrated callers; both
 * values render the same Linear V1 placeholder.
 *
 * Pure CSS animation (animate-pulse from tailwindcss-animate) — no JS,
 * streaming-friendly, zero first-paint cost.
 */
type SkeletonTheme = 'legacy' | 'clinician';

export function Skeleton({
  className,
  theme: _theme = 'legacy',
  ...rest
}: React.HTMLAttributes<HTMLDivElement> & { theme?: SkeletonTheme }) {
  return (
    <div
      aria-hidden
      className={cn(
        'animate-pulse rounded-md bg-linear-surface-2',
        className,
      )}
      {...rest}
    />
  );
}

/** Avatar-sized circle. */
export function SkeletonAvatar({
  className,
  theme: _theme = 'legacy',
}: {
  className?: string;
  theme?: SkeletonTheme;
}) {
  return (
    <Skeleton className={cn('h-9 w-9 rounded-full', className)} />
  );
}

/** A line of body text. Pass `className` to tune width; default 60%. */
export function SkeletonText({
  className,
  lines = 1,
  theme: _theme = 'legacy',
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
          className={cn(
            'h-3',
            i === lines - 1 ? 'w-[50%]' : 'w-[80%]',
            className,
          )}
        />
      ))}
    </div>
  );
}

/** Short pill for primary CTAs. */
export function SkeletonButton({
  className,
  theme: _theme = 'legacy',
}: {
  className?: string;
  theme?: SkeletonTheme;
}) {
  return (
    <Skeleton className={cn('h-7 w-24 rounded-md', className)} />
  );
}

/** Visit card placeholder — matches the shape of <VisitCard>. */
export function SkeletonVisitCard({
  theme: _theme = 'legacy',
}: {
  theme?: SkeletonTheme;
} = {}) {
  return (
    <div
      className={cn(
        'flex h-full flex-col gap-4 rounded-lg p-5',
        'border border-linear-border bg-linear-surface-1',
      )}
    >
      <div className="flex items-start gap-3">
        <SkeletonAvatar className="h-10 w-10" />
        <div className="flex-1 space-y-2">
          <Skeleton className="h-3 w-[60%]" />
          <Skeleton className="h-2.5 w-[35%]" />
        </div>
      </div>
      <div className="mt-auto flex items-center justify-between">
        <Skeleton className="h-4 w-20 rounded" />
        <Skeleton className="h-3 w-16" />
      </div>
    </div>
  );
}

/** A grid of visit card skeletons. Defaults to 6 for dashboard. */
export function SkeletonVisitGrid({
  count = 6,
  theme: _theme = 'legacy',
}: {
  count?: number;
  theme?: SkeletonTheme;
} = {}) {
  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {Array.from({ length: count }).map((_, i) => (
        <SkeletonVisitCard key={i} />
      ))}
    </div>
  );
}

/** Settings-row skeleton — label + value stacked. */
export function SkeletonSettingsRow({
  theme: _theme = 'legacy',
}: {
  theme?: SkeletonTheme;
} = {}) {
  return (
    <div
      className={cn(
        'rounded-lg px-3.5 py-3',
        'border border-linear-border bg-linear-surface-1',
      )}
    >
      <Skeleton className="h-2.5 w-16" />
      <Skeleton className="mt-2 h-3 w-[70%]" />
    </div>
  );
}
