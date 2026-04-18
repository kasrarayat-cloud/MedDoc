'use client';

import { cn } from '@/lib/cn';

/**
 * Card with a subtle violet halo behind it. The halo is an ::after
 * pseudo-element defined in globals.css; it fades in on hover (and can
 * be forced on via data-glow="on" for static showcase usage).
 */
export function GlowCard({
  children,
  className,
  as: Tag = 'div',
  alwaysOn = false,
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
      data-glow={alwaysOn ? 'on' : undefined}
      className={cn(
        'glow-violet relative isolate rounded-2xl border border-border-default bg-bg-surface-2',
        'transition-colors duration-300 hover:border-border-emphasis',
        className
      )}
    >
      {children}
    </Tag>
  );
}
