// Phase 5 — Linear V1 Faithful page header.
// Reference: docs/design-directions-v8-linear/visit-detail.html (heading
// + status pill + actions row).
//
// A horizontal strip with the page title in Inter (NOT serif),
// optional eyebrow above, optional subtitle below, and right-aligned
// actions. The serif italic accents from Phase 2 are dropped: titles
// are sans, weight 500, with tight tracking.
//
// `theme` prop remains for back-compat; both values render the same
// Linear V1 header.

import type { ReactNode } from 'react';

type PageHeaderTheme = 'legacy' | 'clinician';

interface PageHeaderProps {
  /** Small mono-uppercase eyebrow line above the title. */
  eyebrow?: ReactNode;
  /** Page title — Inter sans, weight 500. JSX accepted. */
  title: ReactNode;
  /** Optional secondary line below the title. */
  subtitle?: ReactNode;
  /** Right-aligned action buttons (.qm-lin-btn / .qm-lin-btn-primary). */
  actions?: ReactNode;
  /** @deprecated kept for back-compat; Linear V1 is single-theme. */
  theme?: PageHeaderTheme;
}

export function PageHeader({
  eyebrow,
  title,
  subtitle,
  actions,
}: PageHeaderProps) {
  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'flex-end',
        justifyContent: 'space-between',
        gap: 24,
        padding: '20px 24px 16px',
        borderBottom: '1px solid var(--color-linear-hairline)',
      }}
    >
      <div style={{ minWidth: 0 }}>
        {eyebrow && (
          <div
            style={{
              fontFamily: 'var(--font-mono)',
              fontSize: 10.5,
              fontWeight: 500,
              letterSpacing: '0.07em',
              textTransform: 'uppercase',
              color: 'var(--color-linear-text-3)',
              marginBottom: 8,
            }}
          >
            {eyebrow}
          </div>
        )}
        <h1
          style={{
            margin: 0,
            fontFamily: 'var(--font-sans)',
            fontSize: 24,
            fontWeight: 500,
            lineHeight: 1.2,
            letterSpacing: '-0.012em',
            color: 'var(--color-linear-text)',
          }}
        >
          {title}
        </h1>
        {subtitle && (
          <div
            style={{
              fontFamily: 'var(--font-sans)',
              fontSize: 13,
              color: 'var(--color-linear-text-2)',
              marginTop: 6,
              letterSpacing: '-0.005em',
              lineHeight: 1.45,
              maxWidth: 640,
            }}
          >
            {subtitle}
          </div>
        )}
      </div>
      {actions && (
        <div
          style={{
            display: 'flex',
            gap: 6,
            alignItems: 'center',
            flex: '0 0 auto',
          }}
        >
          {actions}
        </div>
      )}
    </div>
  );
}
