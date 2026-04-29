import { cn } from '@/lib/cn';

/**
 * Violet gradient text, used for emphasis inside headings.
 * The gradient itself lives in globals.css as .text-gradient-violet so
 * we get consistent stops everywhere the brand accent shows up.
 *
 * Variant — `'violet'` (default, Source-of-truth class
 * `.text-gradient-violet` for App-redesign-v1) or `'sage'` (Clinician
 * direction — sage-deep → sage → sage-bright). The sage gradient is
 * defined inline so it doesn't need a globals.css addition; we also
 * stamp `data-variant="sage"` on the rendered span so future CSS can
 * pick it up if a class definition is preferred later.
 */
type GradientVariant = 'violet' | 'sage';

const SAGE_GRADIENT_STYLE: React.CSSProperties = {
  // sage-deep #2F5040 → sage #7AA68C → sage-bright #95BCA4
  backgroundImage:
    'linear-gradient(135deg, #2F5040 0%, #7AA68C 60%, #95BCA4 100%)',
  WebkitBackgroundClip: 'text',
  backgroundClip: 'text',
  color: 'transparent',
  WebkitTextFillColor: 'transparent',
};

export function GradientText({
  children,
  className,
  variant = 'violet',
}: {
  children: React.ReactNode;
  className?: string;
  variant?: GradientVariant;
}) {
  if (variant === 'sage') {
    return (
      <span
        data-variant="sage"
        className={className}
        style={SAGE_GRADIENT_STYLE}
      >
        {children}
      </span>
    );
  }
  return (
    <span
      data-variant="violet"
      className={cn('text-gradient-violet', className)}
    >
      {children}
    </span>
  );
}
