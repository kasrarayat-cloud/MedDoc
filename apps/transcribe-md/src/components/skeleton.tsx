import { cn } from '@/lib/cn';

/**
 * Base shimmer rectangle. Every other skeleton is a styled preset of
 * this. Pure CSS (no framer-motion) — the `.shimmer` class in globals.css
 * drives the sweep, so skeletons are streaming-friendly and don't add
 * JS to first paint.
 */
export function Skeleton({
  className,
  ...rest
}: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      aria-hidden
      className={cn('shimmer rounded-md', className)}
      {...rest}
    />
  );
}

/** Avatar-sized circle — matches the NavBar user pill. */
export function SkeletonAvatar({ className }: { className?: string }) {
  return <Skeleton className={cn('h-9 w-9 rounded-full', className)} />;
}

/** A line of body text. Pass `className` to tune width; default 60%. */
export function SkeletonText({
  className,
  lines = 1,
}: {
  className?: string;
  lines?: number;
}) {
  return (
    <div className="space-y-2">
      {Array.from({ length: lines }).map((_, i) => (
        <Skeleton
          key={i}
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
export function SkeletonButton({ className }: { className?: string }) {
  return <Skeleton className={cn('h-10 w-28 rounded-full', className)} />;
}

/** Visit card placeholder — matches the shape of <VisitCard>. */
export function SkeletonVisitCard() {
  return (
    <div className="flex h-full flex-col gap-4 rounded-xl border border-border-subtle bg-bg-surface-1/40 p-5">
      <div className="flex items-start gap-3">
        <SkeletonAvatar className="h-10 w-10" />
        <div className="flex-1 space-y-2">
          <Skeleton className="h-3 w-[60%]" />
          <Skeleton className="h-2.5 w-[35%]" />
        </div>
      </div>
      <div className="mt-auto flex items-center justify-between">
        <Skeleton className="h-4 w-20 rounded-full" />
        <Skeleton className="h-3 w-16" />
      </div>
    </div>
  );
}

/** A grid of visit card skeletons. Defaults to 6 for dashboard. */
export function SkeletonVisitGrid({ count = 6 }: { count?: number }) {
  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {Array.from({ length: count }).map((_, i) => (
        <SkeletonVisitCard key={i} />
      ))}
    </div>
  );
}

/** Settings-row skeleton — label + value stacked. */
export function SkeletonSettingsRow() {
  return (
    <div className="rounded-lg border border-border-subtle bg-bg-surface-1/40 px-3.5 py-3">
      <Skeleton className="h-2.5 w-16" />
      <Skeleton className="mt-2 h-3 w-[70%]" />
    </div>
  );
}
