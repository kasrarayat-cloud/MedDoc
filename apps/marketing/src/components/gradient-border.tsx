import { cn } from '@/lib/cn';

/**
 * Sage-tinted hairline card — Linear V1 (Faithful).
 *
 * Phase 4 rendered a soft sage-gradient ring on cream. Linear V1 drops
 * the gradient ring and uses a flat hairline border on `--color-linear-
 * surface-1`. Component API (surface/from/to/angle) is preserved for
 * back-compat — those props are ignored in Linear V1.
 */
export interface GradientBorderProps {
  children: React.ReactNode;
  className?: string;
  /** @deprecated Linear V1 uses surface-1; prop ignored. */
  surface?: string;
  /** @deprecated Linear V1 has no gradient stops; prop ignored. */
  from?: string;
  /** @deprecated Linear V1 has no gradient stops; prop ignored. */
  to?: string;
  /** @deprecated Linear V1 has no gradient angle; prop ignored. */
  angle?: string;
}

export function GradientBorder({ children, className }: GradientBorderProps) {
  return (
    <div
      className={cn('rounded-xl', className)}
      style={{
        background: 'var(--color-linear-surface-1)',
        border: '1px solid var(--color-linear-border)',
        boxShadow:
          '0 0 0 1px rgba(122, 166, 140, 0.06), 0 30px 60px -30px rgba(0, 0, 0, 0.6)',
      }}
    >
      {children}
    </div>
  );
}
