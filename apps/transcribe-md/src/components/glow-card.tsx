'use client';

import { cn } from '@/lib/cn';

/**
 * Card with a subtle violet halo behind it. The halo is an ::after
 * pseudo-element defined in globals.css; it fades in on hover (and can
 * be forced on via data-glow="on" for static showcase usage).
 *
 * Theme — `'legacy'` keeps the violet glow on a dark surface;
 * `'clinician'` swaps to `.qm-cl-card-soft` (warm cream + paper-on-desk
 * shadow + gentle hover lift). The violet halo is removed in Clinician
 * — the warm surface + lift IS the affordance.
 */
type GlowCardTheme = 'legacy' | 'clinician';

export function GlowCard({
  children,
  className,
  as: Tag = 'div',
  alwaysOn = false,
  theme = 'legacy',
  ...rest
}: {
  children: React.ReactNode;
  className?: string;
  as?: 'div' | 'article' | 'section' | 'a';
  alwaysOn?: boolean;
  theme?: GlowCardTheme;
} & Omit<React.HTMLAttributes<HTMLElement>, 'className' | 'children'>) {
  return (
    <Tag
      {...rest}
      data-glow={theme === 'legacy' && alwaysOn ? 'on' : undefined}
      className={cn(
        theme === 'clinician'
          ? 'qm-cl-card-soft relative isolate'
          : [
              'glow-violet relative isolate rounded-2xl border border-border-default bg-bg-surface-2',
              'transition-colors duration-300 hover:border-border-emphasis',
            ].join(' '),
        className
      )}
    >
      {children}
    </Tag>
  );
}
