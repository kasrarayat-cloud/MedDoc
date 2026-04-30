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
        <section className="relative overflow-hidden pt-32 pb-12">
          <div
            aria-hidden
            className="pointer-events-none absolute inset-x-0 top-0 h-[500px]"
            style={{
              background:
                'radial-gradient(ellipse 70% 50% at 50% 0%, rgba(122,166,140,0.18) 0%, transparent 65%)',
            }}
          />
          <div className="relative mx-auto max-w-3xl px-6 text-center lg:px-8">
            <p className="qm-cl-eyebrow">Pricing</p>
            <h1 className="mt-4 type-h1">
              Simple. Transparent. <em style={{ fontStyle: 'italic', color: '#2F5040' }}>Priced on the page.</em>
            </h1>
            <p className="mt-6 type-body">
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
