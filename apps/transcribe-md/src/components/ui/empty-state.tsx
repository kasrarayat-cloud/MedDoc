// Phase 5 — Linear V1 Faithful empty state.
// Reference: docs/design-directions-v8-linear/dashboard-v1.html
// (general chrome tokens — surface-1 card, hairline border, sage icon).
//
// Centered card on `--color-linear-surface-1` with a hairline border,
// sage tint icon well, Inter heading + linear-text-2 body, single
// primary CTA below. No serif italics.
//
// `theme` prop remains for back-compat; both values render the same
// Linear V1 surface.

import type { ReactNode } from 'react';
import { Ic } from './icon';

export type EmptyStateKind = 'sparkle' | 'stethoscope' | 'search' | 'folder';
type EmptyStateTheme = 'legacy' | 'clinician';

const ICON_MAP = {
  sparkle: Ic.sparkle,
  stethoscope: Ic.stethoscope,
  search: Ic.search,
  folder: Ic.folder,
} as const;

export function EmptyState({
  kind = 'sparkle',
  eyebrow,
  title,
  body,
  cta,
  illustration,
}: {
  kind?: EmptyStateKind;
  eyebrow?: string;
  title: ReactNode;
  body?: ReactNode;
  cta?: ReactNode;
  /** Optional render slot for a custom line-art illustration. When
   *  passed, it replaces the default `Ic[kind]` glyph entirely. */
  illustration?: ReactNode;
  /** @deprecated kept for back-compat; Linear V1 is single-theme. */
  theme?: EmptyStateTheme;
}) {
  const Illo = ICON_MAP[kind];

  return (
    <div
      style={{
        margin: '60px auto',
        maxWidth: 480,
        padding: '32px 28px',
        background: 'var(--color-linear-surface-1)',
        border: '1px solid var(--color-linear-border)',
        borderRadius: 10,
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        textAlign: 'center',
      }}
    >
      <div
        aria-hidden
        style={{
          width: 56,
          height: 56,
          borderRadius: 12,
          marginBottom: 18,
          background: 'var(--color-linear-sage-tint)',
          border: '1px solid rgba(122, 166, 140, 0.25)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          color: 'var(--color-linear-sage-bright)',
        }}
      >
        {illustration ?? <Illo width={26} height={26} />}
      </div>
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
      <h2
        style={{
          margin: 0,
          fontFamily: 'var(--font-sans)',
          fontSize: 17,
          fontWeight: 500,
          letterSpacing: '-0.012em',
          color: 'var(--color-linear-text)',
        }}
      >
        {title}
      </h2>
      {body && (
        <p
          style={{
            marginTop: 8,
            marginBottom: 0,
            fontFamily: 'var(--font-sans)',
            fontSize: 13,
            color: 'var(--color-linear-text-2)',
            lineHeight: 1.55,
            letterSpacing: '-0.005em',
            maxWidth: 400,
          }}
        >
          {body}
        </p>
      )}
      {cta && <div style={{ marginTop: 20 }}>{cta}</div>}
    </div>
  );
}
