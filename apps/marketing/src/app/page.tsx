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
 * Landing page — Phase 4 Apple Cinematic.
 *
 * The full-bleed cinematic Hero replaces the legacy ShaderBackground
 * canvas + CursorAura mouse-follow blob (both display:none'd in Phase 3
 * already; now removed entirely to drop their JS bundle weight on first
 * paint). RevealMount is kept because the post-hero `.reveal` blocks
 * (Trust / Problem / Features / etc.) still rely on it.
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
