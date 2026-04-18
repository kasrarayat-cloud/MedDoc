import { NavBar } from '@/components/nav-bar';
import { Footer } from '@/components/footer';
import { Hero } from '@/components/home/hero';
import { HowItWorks } from '@/components/home/how-it-works';
import { Features } from '@/components/home/features';
import { Comparison } from '@/components/home/comparison';
import { PricingTeaser } from '@/components/home/pricing-teaser';
import { FinalCTA } from '@/components/home/final-cta';

export default function HomePage() {
  return (
    <>
      <NavBar />
      <main>
        <Hero />
        <HowItWorks />
        <Features />
        <Comparison />
        <PricingTeaser />
        <FinalCTA />
      </main>
      <Footer />
    </>
  );
}
