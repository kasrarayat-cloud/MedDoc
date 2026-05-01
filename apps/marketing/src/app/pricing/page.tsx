import type { Metadata } from 'next';
import { NavBar } from '@/components/nav-bar';
import { Footer } from '@/components/footer';
import { PricingTiers } from './pricing-tiers';
import { PricingFaq } from './pricing-faq';

export const metadata: Metadata = {
  title: 'Pricing',
  description:
    'Transparent pricing. No sales calls. Start with 10 free notes, upgrade when the trial ends, cancel anytime.',
};

export default function PricingPage() {
  return (
    <>
      <NavBar />
      <main>
        <section
          className="relative overflow-hidden"
          style={{ paddingTop: 96, paddingBottom: 24 }}
        >
          <div
            aria-hidden
            className="pointer-events-none absolute inset-x-0 top-0"
            style={{
              height: 500,
              background:
                'radial-gradient(ellipse 70% 50% at 50% 0%, rgba(122,166,140,0.18) 0%, transparent 65%)',
            }}
          />
          <div
            className="container"
            style={{ maxWidth: 760, textAlign: 'center', position: 'relative' }}
          >
            <div className="section-eyebrow">Pricing</div>
            <h1 className="hero-title" style={{ marginTop: 16 }}>
              Simple. Transparent.{' '}
              <span style={{ color: 'var(--color-linear-sage-bright)' }}>
                Priced on the page.
              </span>
            </h1>
            <p className="hero-sub" style={{ marginTop: 20 }}>
              Start with 10 free notes. Upgrade whenever. Cancel whenever. No
              contracts, no sales calls.
            </p>
          </div>
        </section>

        <PricingTiers />
        <PricingFaq />
      </main>
      <Footer />
    </>
  );
}
