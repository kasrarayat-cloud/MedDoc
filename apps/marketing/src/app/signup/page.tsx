import type { Metadata } from 'next';
import Link from 'next/link';
import { ArrowRight } from 'lucide-react';

import { NavBar } from '@/components/nav-bar';
import { Footer } from '@/components/footer';
import { GradientBorder } from '@/components/gradient-border';
import { GradientText } from '@/components/gradient-text';
import { SpecularButton } from '@/components/specular-button';
import { APP_WAITLIST_URL } from '@/lib/constants';

// T-M2: signup happened on the real app, not here; this page exists so old
// bookmarks don't 404.
//
// 2026-07-28 — INVITE-ONLY. It now forwards to the WAITLIST. A cold visitor
// landing on the invite-gated signup form would only be able to fail, and
// "here is a form you cannot submit" is a worse welcome than "join the list".
// A meta-refresh gets users there automatically after a short pause; the
// SpecularButton is the manual fallback.
export const metadata: Metadata = {
  title: 'Join the waitlist',
  description: 'QuillMD is invite-only during the pilot — join the waitlist.',
  // 1-second meta-refresh to the real signup surface. Short enough that
  // the banner below is mostly informational, long enough that browsers
  // that block meta-refresh still render the CTA before the redirect.
  other: {
    refresh: `1;url=${APP_WAITLIST_URL}`,
  },
};

export default function SignupRedirectPage() {
  return (
    <>
      <NavBar />
      <main id="main" tabIndex={-1} style={{ outline: 'none' }}>
        <section
          className="relative overflow-hidden"
          style={{ paddingTop: 96, paddingBottom: 64 }}
        >
          <div
            aria-hidden
            className="pointer-events-none absolute inset-x-0 top-0"
            style={{
              height: 500,
              background:
                'radial-gradient(ellipse 60% 50% at 50% 0%, rgba(122,166,140,0.18) 0%, transparent 65%)',
            }}
          />
          <div
            className="container"
            style={{ maxWidth: 480, position: 'relative' }}
          >
            <GradientBorder>
              <div style={{ padding: 32, textAlign: 'center' }}>
                <div className="section-eyebrow">Redirecting</div>
                <h1
                  className="hero-title"
                  style={{ marginTop: 16, fontSize: 28 }}
                >
                  <GradientText>Sending you to the app…</GradientText>
                </h1>
                <p className="hero-sub" style={{ marginTop: 20 }}>
                  Signup lives on the app itself now. If this page doesn&apos;t
                  redirect in a second, the button below takes you there.
                </p>
                <div style={{ marginTop: 28 }}>
                  <SpecularButton href={APP_WAITLIST_URL} variant="primary" size="lg">
                    Continue to signup
                    <ArrowRight className="h-4 w-4" />
                  </SpecularButton>
                </div>
                <p
                  style={{
                    marginTop: 20,
                    fontSize: 12.5,
                    color: 'var(--color-linear-text-3)',
                  }}
                >
                  Already have an account?{' '}
                  <Link
                    href={`${APP_WAITLIST_URL.replace(/\/signup$/, '/login')}`}
                    style={{
                      color: 'var(--color-linear-sage-bright)',
                      textDecoration: 'underline',
                      textDecorationColor: 'rgba(122,166,140,0.4)',
                    }}
                  >
                    Sign in →
                  </Link>
                </p>
              </div>
            </GradientBorder>
          </div>
        </section>
      </main>
      <Footer />
    </>
  );
}
