import { cn } from '@/lib/cn';

/**
 * Linear/Resend-style gradient border. Uses the padding-box + border-box
 * layered-background trick so the "border" is actually a gradient while
 * the inside stays on-theme.
 *
 * The surface colour (inner fill) and the two gradient stops can be
 * overridden per-instance via CSS vars to match different section
 * backgrounds.
 */
export interface GradientBorderProps {
  children: React.ReactNode;
  className?: string;
  /** Inner surface colour (matches whichever bg layer the card sits on). */
  surface?: string;
  /** First gradient stop. */
  from?: string;
  /** Second gradient stop. */
  to?: string;
  /** Gradient angle (CSS). */
  angle?: string;
}

export function GradientBorder({
  children,
  className,
  surface = '#161822',
  from = '#7C3AED',
  to = '#A855F7',
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
