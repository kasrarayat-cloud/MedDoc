'use client';

import Link from 'next/link';
import { cn } from '@/lib/cn';

/**
 * Linear-style button with a specular (light-sweep) effect on hover.
 * The sweep is a pseudo-element driven by .specular-button in globals.css.
 *
 * Supports three variants:
 *   - primary: solid violet gradient + white text (main CTA)
 *   - secondary: translucent surface + border (ghost)
 *   - ghost: fully transparent until hover
 *
 * Renders as an <a> via next/link when `href` is given, otherwise a
 * <button>. Keyboard focus ring is violet, offset from the surface.
 */
type Variant = 'primary' | 'secondary' | 'ghost';
type Size = 'sm' | 'md' | 'lg';

interface BaseProps {
  children: React.ReactNode;
  variant?: Variant;
  size?: Size;
  className?: string;
  sweep?: boolean;
}

type SpecularButtonProps =
  | (BaseProps & { href: string; type?: never; onClick?: never })
  | (BaseProps & {
      href?: undefined;
      type?: 'button' | 'submit' | 'reset';
      onClick?: React.MouseEventHandler<HTMLButtonElement>;
      disabled?: boolean;
    });

const SIZE_CLASSES: Record<Size, string> = {
  sm: 'px-4 py-2 text-[13px]',
  md: 'px-5 py-2.5 text-[14px]',
  lg: 'px-6 py-3 text-[15px]',
};

const BASE = [
  'inline-flex items-center justify-center gap-2',
  'rounded-full font-medium tracking-tight',
  'transition-all duration-300 ease-[cubic-bezier(0.4,0,0.2,1)]',
  'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500 focus-visible:ring-offset-2 focus-visible:ring-offset-bg-base',
  'select-none',
].join(' ');

const VARIANT_CLASSES: Record<Variant, string> = {
  primary: [
    'text-white',
    // Violet gradient; slightly deeper on hover.
    'bg-[linear-gradient(135deg,#7C3AED_0%,#A855F7_100%)]',
    'shadow-[0_0_0_1px_rgba(167,139,250,0.3),0_8px_32px_-8px_rgba(124,58,237,0.5)]',
    'hover:shadow-[0_0_0_1px_rgba(167,139,250,0.5),0_12px_40px_-8px_rgba(124,58,237,0.7)]',
    'hover:-translate-y-0.5',
  ].join(' '),
  secondary: [
    'text-text-primary',
    'bg-bg-surface-2/70 backdrop-blur',
    'border border-border-default',
    'hover:border-border-emphasis hover:bg-bg-surface-3/70',
  ].join(' '),
  ghost: [
    'text-text-secondary',
    'bg-transparent',
    'border border-transparent',
    'hover:text-text-primary hover:bg-bg-surface-2/50',
  ].join(' '),
};

export function SpecularButton(props: SpecularButtonProps) {
  const {
    children,
    variant = 'primary',
    size = 'md',
    className,
    sweep = true,
  } = props;

  const classes = cn(
    BASE,
    SIZE_CLASSES[size],
    VARIANT_CLASSES[variant],
    sweep && 'specular-button',
    className
  );

  if ('href' in props && props.href) {
    return (
      <Link href={props.href} className={classes}>
        {children}
      </Link>
    );
  }
  // Narrow to the button branch of the discriminated union so `disabled`
  // / `onClick` / `type` are all accessible without property-exists
  // gymnastics.
  const btnProps = props as Extract<SpecularButtonProps, { href?: undefined }>;
  return (
    <button
      type={btnProps.type ?? 'button'}
      onClick={btnProps.onClick}
      disabled={btnProps.disabled}
      className={cn(classes, 'disabled:opacity-50 disabled:pointer-events-none')}
    >
      {children}
    </button>
  );
}
