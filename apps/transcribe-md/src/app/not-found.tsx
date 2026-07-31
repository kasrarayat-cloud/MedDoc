// Phase 5 — Linear V1 Faithful 404 page.
// Reference: dashboard-v1.html chrome (linear-bg + hairline grid).
//
// Sad-but-elegant. Pure typographic moment on the dark canvas with a
// quiet hairline grid behind, single sage CTA back to the dashboard,
// secondary ghost link to /login. The Phase 4 violet glow + animated
// grid + GradientText sweep are gone.

import Link from 'next/link';

import { GradientText } from '@/components/gradient-text';
import { SpecularButton } from '@/components/specular-button';
import { AnimatedGrid } from '@/components/animated-grid';
import { isSkinRounds } from '@/config/skin-rounds';
import { recoveryHref, recoveryLabel } from '@/lib/recovery-href';

export default function NotFound() {
  // ── THE ROUNDS BRANCH ──────────────────────────────────────────────────
  // A FORK, not a token swap, and the reason is what this page is made of.
  // The old 404 layers an `AnimatedGrid`, a `GradientText` sweep and a SAGE
  // radial over the canvas. The host bridge retints `--color-linear-*` custom
  // properties; it cannot touch a component that paints its own colours, so
  // bridging alone would leave a sage glow and a green gradient sitting on an
  // indigo stage.
  //
  // The stage is already a radial treatment — that is the whole idea of the
  // skin — so the Rounds branch drops the decoration entirely and lets `body`
  // do it. That also removes a continuously animating background from a page
  // Gate C has to axe: A2 defect 4 was an animation that made text unreadable
  // at the instant axe sampled it.
  if (isSkinRounds()) {
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

  return (
    <main
      style={{
        position: 'relative',
        display: 'flex',
        minHeight: '100vh',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '24px',
        textAlign: 'center',
        overflow: 'hidden',
        background: 'var(--color-linear-bg)',
        color: 'var(--color-linear-text)',
      }}
    >
      <AnimatedGrid />
      <div
        aria-hidden
        style={{
          position: 'absolute',
          inset: 0,
          pointerEvents: 'none',
          backgroundImage:
            'radial-gradient(ellipse 60% 50% at 50% 30%, var(--color-linear-sage-glow) 0%, transparent 65%)',
          opacity: 0.6,
        }}
      />
      <div style={{ position: 'relative', zIndex: 10, maxWidth: 480 }}>
        <div
          style={{
            fontFamily: 'var(--font-mono)',
            fontSize: 11,
            fontWeight: 500,
            letterSpacing: '0.10em',
            textTransform: 'uppercase',
            color: 'var(--color-linear-text-3)',
            marginBottom: 14,
          }}
        >
          404
        </div>
        <h1
          style={{
            margin: 0,
            fontFamily: 'var(--font-sans)',
            fontSize: 38,
            fontWeight: 500,
            letterSpacing: '-0.018em',
            color: 'var(--color-linear-text)',
            lineHeight: 1.15,
          }}
        >
          <GradientText>Not here.</GradientText>
        </h1>
        <p
          style={{
            margin: '14px auto 0',
            maxWidth: 380,
            fontFamily: 'var(--font-sans)',
            fontSize: 14,
            color: 'var(--color-linear-text-2)',
            lineHeight: 1.55,
          }}
        >
          We couldn&apos;t find that page. It may have moved, or you may not
          have access.
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
          <SpecularButton href={recoveryHref()} variant="primary" size="md">
            {isSkinRounds() ? 'Go to the board' : 'Go to dashboard'}
          </SpecularButton>
          <Link
            href="/login"
            style={{
              fontFamily: 'var(--font-sans)',
              fontSize: 12.5,
              color: 'var(--color-linear-text-3)',
              textDecoration: 'none',
              transition: 'color 120ms ease',
              display: 'inline-flex',
              alignItems: 'center',
            }}
            className="qm-tap-44 hover:!text-linear-text-2"
          >
            Sign in
          </Link>
        </div>
      </div>
    </main>
  );
}
