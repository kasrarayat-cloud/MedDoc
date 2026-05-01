'use client';

import { cn } from '@/lib/cn';

/**
 * Card with a hairline border on the Linear V1 dark canvas. The Phase
 * 4 violet halo + clinician card-soft variants are dropped — Linear V1
 * relies on the border + sage hover state. The `theme` and `alwaysOn`
 * props are preserved as no-ops for caller back-compat.
 */
type GlowCardTheme = 'legacy' | 'clinician';

export function GlowCard({
  children,
  className,
  as: Tag = 'div',
  alwaysOn: _alwaysOn = false,
  theme: _theme = 'legacy',
  ...rest
}: {
  children: React.ReactNode;
  className?: string;
  as?: 'div' | 'article' | 'section' | 'a';
  /** @deprecated kept for back-compat; Linear V1 has no halo. */
  alwaysOn?: boolean;
  /** @deprecated kept for back-compat; Linear V1 is single-theme. */
  theme?: GlowCardTheme;
} & Omit<React.HTMLAttributes<HTMLElement>, 'className' | 'children'>) {
  return (
    <Tag
      {...rest}
      className={cn(
        'relative isolate rounded-lg border border-linear-border bg-linear-surface-1 transition-colors duration-150 hover:border-linear-border-strong',
        className
      )}
    >
      {children}
    </Tag>
  );
}
