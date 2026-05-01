// Phase 5 — Linear V1 Faithful stat card.
// Reference: docs/design-directions-v8-linear/dashboard-v1.html (.stat)
//
// The Phase 4 Source-Serif big-numeral card on a cream surface is gone.
// Linear V1 stats are inline, mono numerals on the dark canvas with a
// hairline divider between siblings (caller composes them inside a
// `.stats-row` flex container — see dashboard/page.tsx).
//
// Each cell renders:
//   ▎  big mono number with optional small-caps unit
//   ▎  uppercase mono label below
//   ▎  optional sage / amber delta marker
//
// The legacy `theme` prop remains in the type signature for back-compat
// with unmigrated callers; the Linear V1 stat is the only render path.

import type { ReactNode } from 'react';

export type StatDeltaTone = 'mint' | 'amber' | 'coral' | 'accent-bright';
type StatCardTheme = 'legacy' | 'clinician';

interface StatCardProps {
  label: ReactNode;
  value: ReactNode;
  unit?: ReactNode;
  delta?: ReactNode;
  deltaTone?: StatDeltaTone;
  /** @deprecated kept for back-compat; Linear V1 is single-theme. */
  theme?: StatCardTheme;
}

/** Map the legacy delta tones to Linear V1 sage/amber/coral. */
function deltaColor(tone: StatDeltaTone): string {
  switch (tone) {
    case 'amber':
      return 'var(--color-linear-amber)';
    case 'coral':
      return 'var(--color-linear-coral)';
    case 'mint':
    case 'accent-bright':
    default:
      return 'var(--color-linear-sage-bright)';
  }
}

export function StatCard({
  label,
  value,
  unit,
  delta,
  deltaTone = 'mint',
}: StatCardProps) {
  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        gap: 6,
        padding: '0 18px',
        borderRight: '1px solid var(--color-linear-hairline)',
        minWidth: 0,
      }}
      // First/last children handle their own padding/border via inline
      // flex parent rules — caller composes inside a `.stats-row`-style
      // wrapper that strips the trailing border.
    >
      <div
        style={{
          display: 'flex',
          alignItems: 'baseline',
          gap: 2,
          fontFamily: 'var(--font-mono)',
          fontSize: 22,
          color: 'var(--color-linear-text)',
          fontWeight: 500,
          letterSpacing: '-0.01em',
          fontVariantNumeric: 'tabular-nums',
          lineHeight: 1.1,
        }}
      >
        {value}
        {unit && (
          <span
            style={{
              fontSize: 11,
              color: 'var(--color-linear-text-3)',
              marginLeft: 4,
              fontWeight: 400,
            }}
          >
            {unit}
          </span>
        )}
        {delta && (
          <span
            style={{
              fontSize: 11,
              color: deltaColor(deltaTone),
              fontFamily: 'var(--font-mono)',
              marginLeft: 6,
            }}
          >
            {delta}
          </span>
        )}
      </div>
      <div
        style={{
          fontFamily: 'var(--font-sans)',
          fontSize: 10,
          color: 'var(--color-linear-text-3)',
          letterSpacing: '0.07em',
          textTransform: 'uppercase',
          fontWeight: 500,
        }}
      >
        {label}
      </div>
    </div>
  );
}
