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
      <main>
        <section className="relative overflow-hidden pt-32 pb-24">
          <div
            aria-hidden
            className="pointer-events-none absolute inset-x-0 top-0 h-[600px]"
            style={{
              background:
                'radial-gradient(ellipse 70% 50% at 50% 0%, rgba(122,166,140,0.18) 0%, transparent 65%)',
            }}
          />
          <div className="relative mx-auto max-w-4xl px-6 text-center lg:px-8">
            <div className="flex justify-center">
              <Badge dot="violet">Coming soon</Badge>
            </div>
            <h1 className="mt-6 type-h1">
              A <GradientText>60-second</GradientText> walkthrough.
            </h1>
            <p
              className="mx-auto mt-6 max-w-xl text-[18px] leading-relaxed text-[#5C544A]"
              style={{ fontFamily: 'var(--font-serif), Georgia, serif' }}
            >
              We&apos;re shooting the demo this sprint. Start the free trial in
              the meantime — you&apos;ll be signed into the real product in
              under a minute.
            </p>

            <GradientBorder className="mx-auto mt-14 aspect-video max-w-3xl" angle="135deg">
              <div className="relative flex h-full w-full items-center justify-center overflow-hidden rounded-[15px] bg-[#FFFCF5]">
                <div
                  aria-hidden
                  className="absolute inset-0"
                  style={{
                    background:
                      'radial-gradient(ellipse at center, rgba(122,166,140,0.14) 0%, transparent 70%)',
                  }}
                />
                <div className="relative flex flex-col items-center gap-4">
                  <div className="flex h-16 w-16 items-center justify-center rounded-full bg-[rgba(122,166,140,0.18)]">
                    <Play className="h-6 w-6 text-[#2F5040]" />
                  </div>
                  <p className="text-[14px] text-[#5C544A]">
                    Video coming soon
                  </p>
                </div>
              </div>
            </GradientBorder>

            <div className="mt-12 flex flex-col items-center justify-center gap-3 sm:flex-row">
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
