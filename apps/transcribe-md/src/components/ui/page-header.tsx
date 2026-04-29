// HANDOFF §2.1 — page header with optional eyebrow, serif title, subtitle,
// and right-aligned actions. The `title` slot accepts JSX so callers can
// drop the `<em>` italic-accent pattern (§1.2) inline.
//
// Phase 2 (Clinician remodel) — Strategy A dual-theme via additive
// `theme` prop. Default `'legacy'` keeps the existing layout/typography
// byte-for-byte. `theme="clinician"` swaps to the warm-cream variant:
// `.qm-cl-eyebrow` (sage-deep ALL CAPS) above a serif title in `--ink`,
// with subtitle in `--ink-2`. Same JSX contract; only token + class
// scope changes so callers stay free of conditionals.

import type { ReactNode } from 'react';

type PageHeaderTheme = 'legacy' | 'clinician';

interface PageHeaderProps {
  eyebrow?: ReactNode;
  title: ReactNode;
  subtitle?: ReactNode;
  actions?: ReactNode;
  theme?: PageHeaderTheme;
}

export function PageHeader({
  eyebrow,
  title,
  subtitle,
  actions,
  theme = 'legacy',
}: PageHeaderProps) {
  if (theme === 'clinician') {
    return (
      <ClinicianPageHeader
        eyebrow={eyebrow}
        title={title}
        subtitle={subtitle}
        actions={actions}
      />
    );
  }
  return (
    <LegacyPageHeader
      eyebrow={eyebrow}
      title={title}
      subtitle={subtitle}
      actions={actions}
    />
  );
}

function LegacyPageHeader({
  eyebrow,
  title,
  subtitle,
  actions,
}: Omit<PageHeaderProps, 'theme'>) {
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

// ── Clinician branch ────────────────────────────────────────────
// Mockup ref: docs/design-directions-v3/clinician/dashboard.html greeting
// section + visit-detail.html patient header. Eyebrow uses
// `.qm-cl-eyebrow` (sage-deep ALL CAPS), title uses `.qm-cl-serif` at
// ~38px in `--ink`, subtitle is serif body in `--ink-2`.
function ClinicianPageHeader({
  eyebrow,
  title,
  subtitle,
  actions,
}: Omit<PageHeaderProps, 'theme'>) {
  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'flex-end',
        justifyContent: 'space-between',
        gap: 24,
        padding: '40px 40px 24px',
      }}
    >
      <div>
        {eyebrow && (
          <div className="qm-cl-eyebrow" style={{ marginBottom: 12 }}>
            {eyebrow}
          </div>
        )}
        <h1
          className="qm-cl-serif"
          style={{
            fontSize: 38,
            margin: 0,
            fontWeight: 400,
            lineHeight: 1.1,
            letterSpacing: '-0.01em',
            color: 'var(--ink)',
          }}
        >
          {title}
        </h1>
        {subtitle && (
          <div
            className="qm-cl-serif"
            style={{
              color: 'var(--ink-2)',
              marginTop: 10,
              fontSize: 16,
              lineHeight: 1.55,
              maxWidth: 560,
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
