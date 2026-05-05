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
 * Landing page — Phase 7 v6 (Apple Product Page).
 *
 * Hero-led full-viewport stages on dark canvas with sage accents. Massive
 * 108px headline with sage gradient on the middle line, floating 3D SOAP
 * card with mouse-move parallax (HeroVisual), then sentence-per-section
 * stages for HowItWorks (3) and Features (6). landing.css drives the
 * grammar; RevealMount wires the IntersectionObserver fade-up triggers.
 */
export default function HomePage() {
  return (
    <>
      <RevealMount />
      <Nav />
      <main id="main" tabIndex={-1} style={{ outline: 'none' }}>
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
