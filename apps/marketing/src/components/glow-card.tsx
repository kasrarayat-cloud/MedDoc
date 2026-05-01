'use client';

import { cn } from '@/lib/cn';

/**
 * Card with a subtle hover lift — Linear V1 (Faithful).
 *
 * Phase 4's sage halo glow on cream is replaced with a flat hairline
 * card on dark canvas; hover state is a one-step border tint to the
 * sage-bright. The `alwaysOn` prop becomes a no-op (kept for
 * back-compat with call sites).
 */
export function GlowCard({
  children,
  className,
  as: Tag = 'div',
  alwaysOn: _alwaysOn = false,
  ...rest
}: {
  children: React.ReactNode;
  className?: string;
  as?: 'div' | 'article' | 'section' | 'a';
  alwaysOn?: boolean;
} & Omit<React.HTMLAttributes<HTMLElement>, 'className' | 'children'>) {
  return (
    <Tag
      {...rest}
      className={cn('rounded-xl transition-colors duration-150', className)}
      style={{
        background: 'var(--color-linear-surface-1)',
        border: '1px solid var(--color-linear-border)',
      }}
    >
      {children}
    </Tag>
  );
}
