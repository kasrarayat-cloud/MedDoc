import { ShaderBackground } from '@/components/home/ShaderBackground';
import { CursorAura } from '@/components/home/CursorAura';
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

export default function HomePage() {
  return (
    <>
      <ShaderBackground />
      <CursorAura />
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
