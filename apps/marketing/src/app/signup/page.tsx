import type { Metadata } from 'next';
import Link from 'next/link';
import { ArrowRight } from 'lucide-react';

import { NavBar } from '@/components/nav-bar';
import { Footer } from '@/components/footer';
import { GradientBorder } from '@/components/gradient-border';
import { GradientText } from '@/components/gradient-text';
import { SpecularButton } from '@/components/specular-button';
import { APP_SIGNUP_URL } from '@/lib/constants';

// T-M2: signup happens on the real app at APP_URL/signup, not here. This
// page now exists only so bookmarks + stale marketing links don't 404.
// A meta-refresh gets users there automatically after a short pause; the
// SpecularButton is the manual fallback.
export const metadata: Metadata = {
  title: 'Redirecting to signup',
  description: 'Create your QuillMD account — redirecting to the app.',
  // 1-second meta-refresh to the real signup surface. Short enough that
  // the banner below is mostly informational, long enough that browsers
  // that block meta-refresh still render the CTA before the redirect.
  other: {
    refresh: `1;url=${APP_SIGNUP_URL}`,
  },
};

export default function SignupRedirectPage() {
  return (
    <>
      <NavBar />
      <main>
        <section className="relative overflow-hidden pt-32 pb-24">
          <div
            aria-hidden
            className="pointer-events-none absolute inset-x-0 top-0 h-[500px]"
            style={{
              background:
                'radial-gradient(ellipse 60% 50% at 50% 0%, rgba(139,92,246,0.18) 0%, transparent 65%)',
            }}
          />
          <div className="relative mx-auto max-w-md px-6 lg:px-8">
            <GradientBorder>
              <div className="p-8 text-center">
                <p className="text-[12px] font-semibold uppercase tracking-[0.14em] text-text-muted">
                  Redirecting
                </p>
                <h1 className="mt-4 type-h1">
                  <GradientText>Sending you to the app…</GradientText>
                </h1>
                <p className="mx-auto mt-6 max-w-sm text-[15px] leading-relaxed text-text-secondary">
                  Signup lives on the app itself now. If this page doesn&apos;t
                  redirect in a second, the button below takes you there.
                </p>
                <div className="mt-8">
                  <SpecularButton href={APP_SIGNUP_URL} variant="primary" size="lg">
                    Continue to signup
                    <ArrowRight className="h-4 w-4" />
                  </SpecularButton>
                </div>
                <p className="mt-6 text-[12px] text-text-muted">
                  Already have an account?{' '}
                  <Link
                    href={`${APP_SIGNUP_URL.replace(/\/signup$/, '/login')}`}
                    className="text-violet-400 hover:text-violet-300 transition-colors"
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
