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

/**
 * A Rounds BOARD lane placeholder.
 *
 * ⚠️ SHAPE IS THE POINT, not colour. A skeleton exists to say "what resolves
 * here will look roughly like this" — so one whose shape contradicts what
 * arrives is worse than none at all: it moves the doctor's eye to where the
 * content is not. The board resolves to patient lanes on a hairline track, so
 * this is a lane: an identity block, then stage markers along a rule.
 *
 * Kept in this file rather than under `components/rounds/` on purpose — item F
 * deletes the skin's component namespace, and `loading.tsx` files survive it.
 * Same reasoning as `lib/recovery-href.ts`.
 */
export function SkeletonRoundsLane({ markers = 5 }: { markers?: number }) {
  return (
    <div
      aria-hidden
      className="qm-rounds-skel-lane"
      style={{ display: 'flex', alignItems: 'center', gap: 16, padding: '14px 0' }}
    >
      <div style={{ flex: '0 0 168px', display: 'grid', gap: 6 }}>
        <Skeleton className="h-3.5 w-28 rounded" />
        <Skeleton className="h-2.5 w-20 rounded" />
      </div>
      <div
        style={{
          flex: 1,
          position: 'relative',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
        }}
      >
        <span className="qm-rounds-skel-track" aria-hidden />
        {Array.from({ length: markers }).map((_, i) => (
          <Skeleton key={i} className="h-2.5 w-2.5 rounded-full" />
        ))}
      </div>
    </div>
  );
}
