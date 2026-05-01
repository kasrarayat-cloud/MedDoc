'use client';

import Link from 'next/link';
import { cn } from '@/lib/cn';

/**
 * Marketing button — Linear V1 (Faithful).
 *
 * Maps to landing.css's `.btn` family (.btn-primary / .btn-secondary /
 * .btn-ghost / .btn-lg). Phase 4's specular sweep is gone; the API
 * (variant + size + sweep + href) is preserved for back-compat with
 * pricing-tiers, demo, signup, not-found, etc.
 */
type Variant = 'primary' | 'secondary' | 'ghost';
type Size = 'sm' | 'md' | 'lg';

interface BaseProps {
  children: React.ReactNode;
  variant?: Variant;
  size?: Size;
  className?: string;
  /** @deprecated Linear V1 has no sweep; prop ignored. */
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

const VARIANT_CLASSES: Record<Variant, string> = {
  primary: 'btn btn-primary',
  secondary: 'btn btn-secondary',
  ghost: 'btn btn-ghost',
};

const SIZE_CLASSES: Record<Size, string> = {
  sm: '',
  md: '',
  lg: 'btn-lg',
};

export function SpecularButton(props: SpecularButtonProps) {
  const { children, variant = 'primary', size = 'md', className } = props;

  const classes = cn(VARIANT_CLASSES[variant], SIZE_CLASSES[size], className);

  if ('href' in props && props.href) {
    // External URLs (http/https) and mailto/tel use a plain <a> so Next
    // doesn't try to client-route them; in-app paths use <Link>.
    const isExternal =
      props.href.startsWith('http://') ||
      props.href.startsWith('https://') ||
      props.href.startsWith('mailto:') ||
      props.href.startsWith('tel:');
    if (isExternal) {
      return (
        <a href={props.href} className={classes}>
          {children}
        </a>
      );
    }
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
