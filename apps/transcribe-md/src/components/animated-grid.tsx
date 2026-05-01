import { cn } from '@/lib/cn';

/**
 * Phase 5 — Linear V1 Faithful grid background.
 *
 * The Phase 4 64×64 violet-glow grid is gone. Linear V1 uses a quieter
 * hairline grid that fades to the dark canvas at the edges — mirrors
 * the AuthShell right-pane treatment so the not-found page has a
 * matching surface.
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
      className={cn('pointer-events-none absolute inset-0 z-0', className)}
      style={{
        backgroundImage:
          'linear-gradient(var(--color-linear-hairline) 1px, transparent 1px), linear-gradient(90deg, var(--color-linear-hairline) 1px, transparent 1px)',
        backgroundSize: '64px 64px',
        maskImage:
          'radial-gradient(circle at 50% 35%, #000 0%, transparent 70%)',
        WebkitMaskImage:
          'radial-gradient(circle at 50% 35%, #000 0%, transparent 70%)',
        opacity: 0.55,
      }}
    />
  );
}
