'use client';

// Phase 5 — Linear V1 Faithful avatar.
// Reference: docs/design-directions-v8-linear/dashboard-v1.html (.avatar-chip)
//
// Round avatar on `--color-linear-surface-1` with hairline border and
// initials in Inter weight 600. Hover state lifts the border to the
// sage-bright tint with a subtle sage glow shadow. The legacy 7-hue
// rainbow tinting is gone; Linear V1 is monochromatic.
//
// `theme` and `tint` props remain in the type signature for back-compat
// with unmigrated callers (e.g. TopNav previously passed
// theme="clinician"); both values render the same Linear V1 chip.

const SURFACE_GRADIENT =
  'linear-gradient(135deg, var(--color-linear-surface-3) 0%, var(--color-linear-surface-1) 100%)';

type AvatarTheme = 'legacy' | 'clinician';

function initialsFrom(name: string): string {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((s) => s[0] ?? '')
    .join('')
    .toUpperCase();
}

interface AvatarProps {
  name?: string;
  size?: number;
  /** @deprecated kept for back-compat; Linear V1 has no per-name tint. */
  tint?: string;
  /** @deprecated kept for back-compat; Linear V1 is single-theme. */
  theme?: AvatarTheme;
}

export function Avatar({
  name = 'JD',
  size = 24,
}: AvatarProps) {
  const initials = initialsFrom(name) || 'JD';
  // Inter 12px medium per dashboard-v1; scale gracefully for larger
  // sizes (settings page uses 36px etc.).
  const fontSize = Math.max(10.5, Math.round(size * 0.42));

  return (
    <div
      aria-hidden
      style={{
        width: size,
        height: size,
        flex: `0 0 ${size}px`,
        borderRadius: '50%',
        background: SURFACE_GRADIENT,
        border: '1px solid var(--color-linear-hairline-strong)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        fontFamily: 'var(--font-sans)',
        fontSize,
        fontWeight: 600,
        color: 'var(--color-linear-text)',
        letterSpacing: '0.02em',
        transition:
          'border-color 120ms ease-out, box-shadow 120ms ease-out',
      }}
      onMouseEnter={(e) => {
        e.currentTarget.style.borderColor =
          'var(--color-linear-sage-bright)';
        e.currentTarget.style.boxShadow =
          '0 0 0 2px var(--color-linear-sage-glow)';
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.borderColor =
          'var(--color-linear-hairline-strong)';
        e.currentTarget.style.boxShadow = 'none';
      }}
    >
      {initials}
    </div>
  );
}
