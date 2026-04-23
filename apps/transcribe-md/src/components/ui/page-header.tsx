// HANDOFF §2.1 — page header with optional eyebrow, serif title, subtitle,
// and right-aligned actions. The `title` slot accepts JSX so callers can
// drop the `<em>` italic-accent pattern (§1.2) inline.

import type { ReactNode } from 'react';

export function PageHeader({
  eyebrow,
  title,
  subtitle,
  actions,
}: {
  eyebrow?: ReactNode;
  title: ReactNode;
  subtitle?: ReactNode;
  actions?: ReactNode;
}) {
  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'flex-end',
        justifyContent: 'space-between',
        gap: 24,
        padding: '28px 32px 20px',
      }}
    >
      <div>
        {eyebrow && (
          <div className="qm-sectlabel" style={{ marginBottom: 10 }}>
            {eyebrow}
          </div>
        )}
        <h1
          className="qm-serif"
          style={{
            fontSize: 36,
            margin: 0,
            fontWeight: 400,
            lineHeight: 1.05,
            letterSpacing: '-0.02em',
          }}
        >
          {title}
        </h1>
        {subtitle && (
          <div
            style={{
              color: 'var(--fg-3)',
              marginTop: 8,
              fontSize: 13.5,
            }}
          >
            {subtitle}
          </div>
        )}
      </div>
      {actions && (
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          {actions}
        </div>
      )}
    </div>
  );
}
