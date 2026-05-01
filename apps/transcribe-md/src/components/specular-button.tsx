'use client';

import Link from 'next/link';
import { cn } from '@/lib/cn';

/**
 * Phase 5 — Linear V1 Faithful CTA primitive.
 *
 * Reference: docs/design-directions-v8-linear/dashboard-v1.html
 * `.btn-primary` (sage solid) and the `.kbd-chip` ghost pattern.
 *
 * The Phase 4 violet-gradient + specular-sweep treatment is gone. Linear
 * V1 has no specular sheen, no purple gradient, no rounded-pill shape;
 * buttons sit on a 6px radius with a subtle 1-pixel sage ring + a flat
 * sage fill. We re-skin the three variants onto the `.qm-lin-btn(*)`
 * family from globals.css so the rest of the app stays consistent.
 *
 * Variants:
 *   - primary   → sage solid (`.qm-lin-btn-primary`) — the only call to
 *                 action, never more than one per surface
 *   - secondary → ghost outline (`.qm-lin-btn`)
 *   - ghost     → transparent ghost (also `.qm-lin-btn`); no separate
 *                 utility in Linear V1, the visual difference is the
 *                 absence of a border on hover and we just let the
 *                 catalog handle it
 *
 * Sizes (sm/md/lg) tweak padding only — Linear V1 buttons are 28-32 px
 * tall depending on density.
 *
 * The legacy `theme`, `sweep`, `data-shine` props remain in the type
 * signature for back-compat — they're ignored at runtime, which keeps
 * existing call sites compiling. Stage 5 cleanup will drop them in one
 * sweep.
 *
 * Renders <a> via next/link when `href` is given, otherwise <button>.
 */
type Variant = 'primary' | 'secondary' | 'ghost';
type Size = 'sm' | 'md' | 'lg';
type ButtonTheme = 'legacy' | 'clinician';

interface BaseProps {
  children: React.ReactNode;
  variant?: Variant;
  size?: Size;
  className?: string;
  /** @deprecated kept for back-compat; Linear V1 has no specular sweep. */
  sweep?: boolean;
  /** @deprecated kept for back-compat; Linear V1 is single-theme. */
  theme?: ButtonTheme;
}

type SpecularButtonProps =
  | (BaseProps & { href: string; type?: never; onClick?: never })
  | (BaseProps & {
      href?: undefined;
      type?: 'button' | 'submit' | 'reset';
      onClick?: React.MouseEventHandler<HTMLButtonElement>;
      disabled?: boolean;
    });

const SIZE_STYLES: Record<Size, React.CSSProperties> = {
  sm: { height: 26, padding: '0 10px', fontSize: 11.5 },
  md: { height: 28, padding: '0 12px', fontSize: 12 },
  lg: { height: 32, padding: '0 16px', fontSize: 13 },
};

const VARIANT_CLASSES: Record<Variant, string> = {
  primary: 'qm-lin-btn-primary',
  secondary: 'qm-lin-btn',
  ghost: 'qm-lin-btn',
};

export function SpecularButton(props: SpecularButtonProps) {
  const { children, variant = 'primary', size = 'md', className } = props;

  const classes = cn(VARIANT_CLASSES[variant], className);
  const sizeStyle = SIZE_STYLES[size];

  if ('href' in props && props.href) {
    return (
      <Link href={props.href} className={classes} style={sizeStyle}>
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
      className={classes}
      style={sizeStyle}
    >
      {children}
    </button>
  );
}
