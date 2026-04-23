// HANDOFF §2.2 EmptyState — minimal violet line-art illustration + serif
// title + subcopy + optional CTA. Used by Dashboard / Patient detail /
// search results when there's no data to render yet.
//
// Illos are lightweight inline SVGs rather than ported IlloQuill /
// IlloStethoscope / IlloSearch from the handoff (those land in a
// follow-up); the accompanying text + button composition matches.

import type { ReactNode } from 'react';
import { Ic } from './icon';

export type EmptyStateKind = 'sparkle' | 'stethoscope' | 'search' | 'folder';

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
}: {
  kind?: EmptyStateKind;
  eyebrow?: string;
  title: ReactNode;
  body?: ReactNode;
  cta?: ReactNode;
}) {
  const Illo = ICON_MAP[kind];
  return (
    <div
      style={{
        margin: '60px auto',
        maxWidth: 440,
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        textAlign: 'center',
      }}
    >
      <div
        aria-hidden
        style={{
          width: 96,
          height: 96,
          borderRadius: 24,
          marginBottom: 22,
          background:
            'radial-gradient(circle at 30% 30%, rgba(209,181,255,0.3), rgba(107,63,217,0.05))',
          border: '1px solid rgba(139,92,255,0.18)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          color: 'var(--accent-bright)',
        }}
      >
        <Illo width={38} height={38} />
      </div>
      {eyebrow && (
        <div className="qm-sectlabel" style={{ marginBottom: 10 }}>
          {eyebrow}
        </div>
      )}
      <h2
        className="qm-serif"
        style={{
          margin: 0,
          fontSize: 24,
          fontWeight: 400,
          letterSpacing: '-0.015em',
        }}
      >
        {title}
      </h2>
      {body && (
        <p
          style={{
            marginTop: 10,
            fontSize: 13.5,
            color: 'var(--fg-3)',
            lineHeight: 1.55,
            maxWidth: 360,
          }}
        >
          {body}
        </p>
      )}
      {cta && <div style={{ marginTop: 20 }}>{cta}</div>}
    </div>
  );
}
