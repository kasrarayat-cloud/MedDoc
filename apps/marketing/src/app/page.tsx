import { RevealMount } from '@/components/home/RevealMount';
import { Nav } from '@/components/home/Nav';
import { Hero } from '@/components/home/Hero';
import { Trust } from '@/components/home/Trust';
import { Problem } from '@/components/home/Problem';
import { HowItWorks } from '@/components/home/HowItWorks';
import { Features } from '@/components/home/Features';
import { Compare } from '@/components/home/Compare';
import { Demo } from '@/components/home/Demo';
import { Security } from '@/components/home/Security';
import { Specialties } from '@/components/home/Specialties';
import { Pricing } from '@/components/home/Pricing';
import { FAQ } from '@/components/home/FAQ';
import { FinalCTA } from '@/components/home/FinalCTA';
import { Footer } from '@/components/home/Footer';

/**
 * Landing page — Phase 5 Linear V1 (Faithful).
 *
 * Centered hero on dark canvas, hairline-bordered grids, sage primary
 * accents. The full-bleed Phase 4 cinematic photo + word-stagger and
 * the legacy ShaderBackground canvas are gone; landing.css provides the
 * radial sage spotlight + grain via body::before/::after. RevealMount
 * is kept because the post-hero `.reveal` blocks still rely on it.
 */
export default function HomePage() {
  return (
    <>
      <RevealMount />
      <Nav />
      <main>
        <Hero />
        <Trust />
        <Problem />
        <HowItWorks />
        <Features />
        <Compare />
        <Demo />
        <Security />
        <Specialties />
        <Pricing />
        <FAQ />
        <FinalCTA />
      </main>
      <Footer />
    </>
  );
}
