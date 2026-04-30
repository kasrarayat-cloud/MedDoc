import { cn } from '@/lib/cn';

/**
 * Card with a soft sage-gradient hairline border. The structural CSS
 * (.gradient-border in globals.css) does the layered-background trick;
 * this wrapper just supplies the surface + gradient stops as CSS vars.
 *
 * Defaults are Clinician: cream-card surface, sage-deep → sage-bright
 * gradient stops. Existing call sites (pricing-tiers, demo, signup)
 * pass the API unchanged.
 */
export interface GradientBorderProps {
  children: React.ReactNode;
  className?: string;
  surface?: string;
  from?: string;
  to?: string;
  angle?: string;
}

export function GradientBorder({
  children,
  className,
  surface = '#FFFCF5',
  from = '#7AA68C',
  to = '#95BCA4',
  angle = '135deg',
}: GradientBorderProps) {
  return (
    <div
      className={cn('gradient-border rounded-2xl', className)}
      style={
        {
          ['--gb-surface']: surface,
          ['--gb-from']: from,
          ['--gb-to']: to,
          ['--gb-angle']: angle,
        } as React.CSSProperties
      }
    >
      {children}
    </div>
  );
}
