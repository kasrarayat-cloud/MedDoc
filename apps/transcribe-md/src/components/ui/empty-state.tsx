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
  theme = 'legacy',
}: {
  kind?: EmptyStateKind;
  eyebrow?: string;
  title: ReactNode;
  body?: ReactNode;
  cta?: ReactNode;
  /** Optional render slot for a custom line-art illustration. When
   *  passed, it replaces the default `Ic[kind]` glyph entirely — used
   *  by Clinician routes that ship the IlloQuill / IlloStethoscope /
   *  IlloSearch family from the design handoff. */
  illustration?: ReactNode;
  theme?: EmptyStateTheme;
}) {
  const Illo = ICON_MAP[kind];

  if (theme === 'clinician') {
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
            background: 'var(--sage-tint, rgba(122, 166, 140, 0.14))',
            border: '1px solid var(--line, rgba(43, 38, 32, 0.08))',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: 'var(--sage-deep, #2F5040)',
          }}
        >
          {illustration ?? <Illo width={38} height={38} />}
        </div>
        {eyebrow && (
          <div className="qm-cl-eyebrow" style={{ marginBottom: 10 }}>
            {eyebrow}
          </div>
        )}
        <h2
          style={{
            margin: 0,
            fontFamily: 'var(--serif, "Source Serif 4", Georgia, serif)',
            fontSize: 24,
            fontWeight: 400,
            letterSpacing: '-0.015em',
            color: 'var(--ink, #2B2620)',
          }}
        >
          {title}
        </h2>
        {body && (
          <div
            className="qm-cl-prose"
            style={{ marginTop: 10, maxWidth: 360 }}
          >
            {typeof body === 'string' ? <p>{body}</p> : body}
          </div>
        )}
        {cta && <div style={{ marginTop: 20 }}>{cta}</div>}
      </div>
    );
  }

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
        {illustration ?? <Illo width={38} height={38} />}
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
