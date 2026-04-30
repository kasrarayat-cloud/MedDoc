'use client';

import Link from 'next/link';
import { cn } from '@/lib/cn';

/**
 * Marketing button — Clinician variant. The original "specular" sweep is
 * neutralized in globals.css so this component renders as a calm pill in
 * sage-primary / cream-soft / ghost variants per the Clinician button
 * vocabulary. The component API (variant + size + sweep + href) is kept
 * unchanged so existing call sites in pricing-tiers, demo, signup,
 * not-found, etc. don't have to be edited.
 */
type Variant = 'primary' | 'secondary' | 'ghost';
type Size = 'sm' | 'md' | 'lg';

interface BaseProps {
  children: React.ReactNode;
  variant?: Variant;
  size?: Size;
  className?: string;
  /** Kept for API compatibility; the Clinician button has no light sweep. */
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
  'rounded-full font-medium',
  'transition-all duration-300 ease-[cubic-bezier(0.22,1,0.36,1)]',
  'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2',
  'select-none',
  // Sage focus ring on the cream offset.
  'focus-visible:ring-[#7AA68C] focus-visible:ring-offset-[#FAF7F2]',
].join(' ');

const VARIANT_CLASSES: Record<Variant, string> = {
  // Sage primary — solid, soft warm shadow, lifts 1px on hover.
  primary: [
    'text-[#FFFCF5]',
    'bg-[#7AA68C]',
    'shadow-[0_6px_18px_rgba(122,166,140,0.28)]',
    'hover:bg-[#6E9A80]',
    'hover:-translate-y-0.5',
    'hover:shadow-[0_8px_22px_rgba(122,166,140,0.36)]',
  ].join(' '),
  // Soft cream-card — used for "Watch demo" / "Back to home" / secondary CTAs.
  secondary: [
    'text-[#2B2620]',
    'bg-[#FFFCF5]',
    'border border-[rgba(43,38,32,0.10)]',
    'shadow-[0_1px_2px_rgba(43,38,32,0.05)]',
    'hover:bg-[#F2EDE3]',
    'hover:border-[rgba(43,38,32,0.18)]',
  ].join(' '),
  // Ghost — used for nav "Sign in".
  ghost: [
    'text-[#5C544A]',
    'bg-transparent',
    'border border-transparent',
    'hover:text-[#2B2620] hover:bg-[#F2EDE3]',
  ].join(' '),
};

export function SpecularButton(props: SpecularButtonProps) {
  const {
    children,
    variant = 'primary',
    size = 'md',
    className,
  } = props;

  const classes = cn(
    BASE,
    SIZE_CLASSES[size],
    VARIANT_CLASSES[variant],
    className
  );

  if ('href' in props && props.href) {
    return (
      <Link href={props.href} className={classes}>
        {children}
      </Link>
    );
  }
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
