'use client';

import { cn } from '@/lib/cn';

/**
 * Card with a subtle sage halo behind it on hover. The halo lives in
 * globals.css as `.glow-violet` (legacy class name kept so existing
 * pricing-tiers callsites don't have to change); the colour was retoned
 * to sage in the Clinician remodel. `data-glow="on"` forces the halo
 * always-on for static showcase usage.
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
        'glow-violet relative isolate rounded-2xl',
        'border border-[rgba(43,38,32,0.10)] bg-[#FFFCF5]',
        'shadow-[0_4px_14px_rgba(43,38,32,0.04)]',
        'transition-colors duration-300',
        'hover:border-[rgba(122,166,140,0.35)]',
        className
      )}
    >
      {children}
    </Tag>
  );
}
