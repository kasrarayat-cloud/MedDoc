'use client';

import { useEffect } from 'react';
import { Hero } from '@/components/Hero';
import { Sandbox } from '@/components/Sandbox';
import { Journey } from '@/components/Journey';
import { Security } from '@/components/Security';
import { TerminalCTA } from '@/components/TerminalCTA';

export default function Page() {
  // Scroll-reveal: add .is-in as sections enter. Reduced-motion users get
  // everything visible immediately (the CSS .reveal rule no-ops under the
  // reduced-motion media query).
  useEffect(() => {
    const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    const els = Array.from(document.querySelectorAll('.reveal'));
    if (reduce) {
      els.forEach((el) => el.classList.add('is-in'));
      return;
    }
    const io = new IntersectionObserver(
      (entries) => {
        for (const e of entries) {
          if (e.isIntersecting) {
            e.target.classList.add('is-in');
            io.unobserve(e.target);
          }
        }
      },
      { threshold: 0.16, rootMargin: '0px 0px -8% 0px' }
    );
    els.forEach((el) => io.observe(el));
    return () => io.disconnect();
  }, []);

  return (
    <main>
      <Hero />
      <Sandbox />
      <Journey />
      <Security />
      <TerminalCTA />
    </main>
  );
}
