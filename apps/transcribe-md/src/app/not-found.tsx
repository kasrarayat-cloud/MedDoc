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

export default function NotFound() {
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
          <SpecularButton href="/dashboard" variant="primary" size="md">
            Go to dashboard
          </SpecularButton>
          <Link
            href="/login"
            style={{
              fontFamily: 'var(--font-sans)',
              fontSize: 12.5,
              color: 'var(--color-linear-text-3)',
              textDecoration: 'none',
              transition: 'color 120ms ease',
            }}
            className="hover:!text-linear-text-2"
          >
            Sign in
          </Link>
        </div>
      </div>
    </main>
  );
}
