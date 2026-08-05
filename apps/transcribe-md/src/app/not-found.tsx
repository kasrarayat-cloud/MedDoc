// The 404 page.
//
// Sad-but-elegant. A pure typographic moment on the Rounds stage, a single
// recovery CTA back to the board, secondary ghost link to /login.
//
// NO DECORATION, DELIBERATELY. This page paints no background of its own: the
// stage is already a radial treatment — that is the whole idea of the skin — so
// `body` does it. That also keeps a continuously animating background off a
// page Gate C has to axe: A2 defect 4 was an animation that made text
// unreadable at the instant axe sampled it.

import Link from 'next/link';

import { recoveryHref, recoveryLabel } from '@/lib/recovery-href';

export default function NotFound() {
  return (
    <main
      className="qm-rounds-host qm-rounds-notfound"
      style={{
        display: 'flex',
        minHeight: '100vh',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        padding: 24,
        textAlign: 'center',
        color: 'var(--rounds-text-1)',
      }}
    >
      <div style={{ maxWidth: 480 }}>
        <p
          style={{
            margin: 0,
            fontFamily: 'var(--rounds-font-mono)',
            fontSize: 11,
            letterSpacing: '0.14em',
            textTransform: 'uppercase',
            color: 'var(--rounds-text-3)',
          }}
        >
          404
        </p>
        <h1
          style={{
            margin: '14px 0 0',
            fontFamily: 'var(--rounds-font-display)',
            fontSize: 38,
            fontWeight: 500,
            letterSpacing: '-0.018em',
            lineHeight: 1.15,
            color: 'var(--rounds-text-1)',
          }}
        >
          Not here.
        </h1>
        <p
          style={{
            margin: '12px auto 0',
            maxWidth: 400,
            fontFamily: 'var(--rounds-font-ui)',
            fontSize: 13.5,
            lineHeight: 1.55,
            color: 'var(--rounds-text-2)',
          }}
        >
          That page doesn&apos;t exist. It may have moved, or the link may be
          out of date.
        </p>
        <div
          style={{
            marginTop: 28,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: 12,
            flexWrap: 'wrap',
          }}
        >
          <Link
            href={recoveryHref()}
            className="qm-rounds-btn"
            data-testid="notfound-recover"
          >
            {recoveryLabel()}
          </Link>
          <Link
            href="/login"
            style={{
              fontFamily: 'var(--rounds-font-ui)',
              fontSize: 12.5,
              color: 'var(--rounds-text-3)',
              textDecoration: 'underline',
            }}
          >
            Sign in
          </Link>
        </div>
      </div>
    </main>
  );
}
