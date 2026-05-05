import type { Metadata } from 'next';
import { Play } from 'lucide-react';
import { NavBar } from '@/components/nav-bar';
import { Footer } from '@/components/footer';
import { Badge } from '@/components/badge';
import { GradientText } from '@/components/gradient-text';
import { GradientBorder } from '@/components/gradient-border';
import { SpecularButton } from '@/components/specular-button';
import { APP_SIGNUP_URL } from '@/lib/constants';

export const metadata: Metadata = {
  title: 'Demo',
  description: 'A 60-second walkthrough — coming soon.',
};

export default function DemoPage() {
  return (
    <>
      <NavBar />
      <main id="main" tabIndex={-1} style={{ outline: 'none' }}>
        <section
          className="relative overflow-hidden"
          style={{ paddingTop: 96, paddingBottom: 96 }}
        >
          <div
            aria-hidden
            className="pointer-events-none absolute inset-x-0 top-0"
            style={{
              height: 600,
              background:
                'radial-gradient(ellipse 70% 50% at 50% 0%, rgba(122,166,140,0.18) 0%, transparent 65%)',
            }}
          />
          <div
            className="container"
            style={{ maxWidth: 880, textAlign: 'center', position: 'relative' }}
          >
            <div style={{ display: 'flex', justifyContent: 'center' }}>
              <Badge dot="violet">Coming soon</Badge>
            </div>
            <h1 className="hero-title" style={{ marginTop: 20 }}>
              A <GradientText>60-second</GradientText> walkthrough.
            </h1>
            <p className="hero-sub" style={{ marginTop: 20 }}>
              We&apos;re shooting the demo this sprint. Start the free trial in
              the meantime — you&apos;ll be signed into the real product in
              under a minute.
            </p>

            <div style={{ marginTop: 48, marginInline: 'auto', maxWidth: 760 }}>
              <GradientBorder>
                <div
                  style={{
                    position: 'relative',
                    aspectRatio: '16 / 9',
                    overflow: 'hidden',
                    borderRadius: 11,
                    background: 'var(--color-linear-surface-2)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                  }}
                >
                  <div
                    aria-hidden
                    style={{
                      position: 'absolute',
                      inset: 0,
                      background:
                        'radial-gradient(ellipse at center, rgba(122,166,140,0.14) 0%, transparent 70%)',
                    }}
                  />
                  <div
                    style={{
                      position: 'relative',
                      display: 'flex',
                      flexDirection: 'column',
                      alignItems: 'center',
                      gap: 16,
                    }}
                  >
                    <div
                      style={{
                        display: 'flex',
                        height: 64,
                        width: 64,
                        alignItems: 'center',
                        justifyContent: 'center',
                        borderRadius: '50%',
                        background: 'var(--color-linear-sage-tint)',
                        border: '1px solid rgba(122, 166, 140, 0.3)',
                      }}
                    >
                      <Play
                        style={{
                          height: 22,
                          width: 22,
                          color: 'var(--color-linear-sage-bright)',
                        }}
                      />
                    </div>
                    <p
                      style={{
                        fontSize: 13,
                        color: 'var(--color-linear-text-3)',
                        fontFamily: 'var(--font-mono)',
                        letterSpacing: '0.06em',
                        textTransform: 'uppercase',
                      }}
                    >
                      Video coming soon
                    </p>
                  </div>
                </div>
              </GradientBorder>
            </div>

            <div
              style={{
                marginTop: 40,
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                justifyContent: 'center',
                gap: 12,
              }}
              className="sm:flex-row"
            >
              <SpecularButton href={APP_SIGNUP_URL} variant="primary" size="lg">
                Start free trial instead
              </SpecularButton>
              <SpecularButton href="/" variant="secondary" size="lg" sweep={false}>
                Back to home
              </SpecularButton>
            </div>
          </div>
        </section>
      </main>
      <Footer />
    </>
  );
}
