'use client';

// The complete QuillMD landing — split-screen spine resolving to full-width. Nav + Hero + the
// seven sections + Footer. Scroll-reveal (.fx-reveal) rises sections in as they enter; under
// reduced-motion or no-JS everything is shown immediately (the reveal is purely additive).
import { useEffect } from 'react';
import { APP_WAITLIST_URL, APP_URL } from '@/lib/constants';
import { HeroSplit } from './HeroSplit';
import { VerificationSplit } from './VerificationSplit';
import { HowItWorks, Comparison, Pricing, Faq, FinalCta } from './sections';
import { FOOTER_TRUST } from './content';

const NAV: [string, string][] = [
  ['How it works', '#how'],
  ['Verification', '#verification'],
  ['Pricing', '#pricing'],
  ['FAQ', '#faq'],
];

export function FinalLanding() {
  useEffect(() => {
    const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    const els = Array.from(document.querySelectorAll('.fx-reveal'));
    if (reduce) {
      els.forEach((e) => e.classList.add('is-in'));
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
      { threshold: 0.15, rootMargin: '0px 0px -8% 0px' }
    );
    els.forEach((e) => io.observe(e));
    return () => io.disconnect();
  }, []);

  return (
    <div className="fx-root">
      <header className="fx-nav">
        <a className="fx-nav-brand" href="#top">
          Quill<span className="fx-nav-md">MD</span>
        </a>
        <nav className="fx-nav-links" aria-label="Primary">
          {NAV.map(([label, href]) => (
            <a key={href} href={href}>
              {label}
            </a>
          ))}
          <a href={`${APP_URL}/login`}>Sign in</a>
        </nav>
        <a className="fx-nav-cta" href={APP_WAITLIST_URL}>
          Get started
        </a>
      </header>

      <main id="main" tabIndex={-1} style={{ outline: 'none' }}>
        <span id="top" />
        <HeroSplit />
        <HowItWorks />
        <VerificationSplit />
        <Comparison />
        <Pricing />
        <Faq />
        <FinalCta />
      </main>

      <footer className="fx-foot">
        <div className="fx-foot-top">
          <a className="fx-nav-brand" href="#top">
            Quill<span className="fx-nav-md">MD</span>
          </a>
          <p className="fx-foot-tag">The note writes itself — you sign it.</p>
        </div>
        <ul className="fx-foot-trust font-mono" aria-label="What QuillMD guarantees">
          {FOOTER_TRUST.map((t, i) => (
            <li key={t}>
              {i > 0 && <span aria-hidden>·</span>}
              {t}
            </li>
          ))}
        </ul>
        <p className="fx-foot-fine font-mono">© 2026 QuillMD · All rights reserved.</p>
      </footer>
    </div>
  );
}
