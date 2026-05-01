import { cn } from '@/lib/cn';

/**
 * Phase 5 — Linear V1 Faithful gradient text.
 *
 * Linear V1 has no purple/violet brand accent; the only gradient text
 * we use is a subtle sage gradient (sage-deep → sage → sage-bright)
 * for emphasis inside large headings on the not-found page and the
 * AuthShell right pane.
 *
 * The legacy `variant="violet"` value remains in the type signature for
 * back-compat with unmigrated callers; both values render the sage
 * gradient. Stage 5 cleanup will drop the prop in one sweep.
 */
type GradientVariant = 'violet' | 'sage';

const SAGE_GRADIENT_STYLE: React.CSSProperties = {
  // sage-deep #2F5040 → sage #7AA68C → sage-bright #9BC4A8
  backgroundImage:
    'linear-gradient(135deg, #2F5040 0%, #7AA68C 60%, #9BC4A8 100%)',
  WebkitBackgroundClip: 'text',
  backgroundClip: 'text',
  color: 'transparent',
  WebkitTextFillColor: 'transparent',
};

export function GradientText({
  children,
  className,
  variant: _variant = 'sage',
}: {
  children: React.ReactNode;
  className?: string;
  variant?: GradientVariant;
}) {
  return (
    <span
      data-variant="sage"
      className={cn(className)}
      style={SAGE_GRADIENT_STYLE}
    >
      {children}
    </span>
  );
}
