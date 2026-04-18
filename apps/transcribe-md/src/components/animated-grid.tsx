import { cn } from '@/lib/cn';

/**
 * Raycast-style 48px grid background. Lines are 2.5% white so they're
 * present but not noisy; a radial mask fades them out at the edges so
 * the grid never competes with content.
 *
 * Use as an absolutely-positioned sibling inside a `relative` section:
 *
 *   <section className="relative overflow-hidden">
 *     <AnimatedGrid />
 *     <div className="relative z-10">…content…</div>
 *   </section>
 */
export function AnimatedGrid({ className }: { className?: string }) {
  return (
    <div
      aria-hidden
      className={cn(
        'grid-bg pointer-events-none absolute inset-0 z-0',
        className
      )}
    />
  );
}
