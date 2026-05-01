import { cn } from '@/lib/cn';

/**
 * Sage-bright accent inside a heading — Linear V1 (Faithful).
 *
 * Phase 4 used a Source Serif italic gradient. Linear V1 drops the serif
 * italic and instead colours the accent phrase sage-bright in the same
 * Inter weight as the surrounding heading. Component API unchanged so
 * call sites (about/demo/signup/not-found/pricing) keep rendering.
 */
export function GradientText({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <span
      className={cn(className)}
      style={{ color: 'var(--color-linear-sage-bright)' }}
    >
      {children}
    </span>
  );
}
