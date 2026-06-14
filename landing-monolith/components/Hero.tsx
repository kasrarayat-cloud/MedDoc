'use client';

import { useEffect, useRef } from 'react';

const TRUST = [
  'HIPAA-ready',
  'BAA included',
  'US-hosted',
  'You sign every note',
];

export function Hero() {
  const glowRef = useRef<HTMLDivElement>(null);
  const sectionRef = useRef<HTMLElement>(null);

  // Soft turquoise radial glow that tracks the pointer behind the monolith.
  // prefers-reduced-motion users get the static centered glow (no tracking).
  useEffect(() => {
    const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (reduce) return;
    const el = sectionRef.current;
    const glow = glowRef.current;
    if (!el || !glow) return;
    let raf = 0;
    const onMove = (e: PointerEvent) => {
      const r = el.getBoundingClientRect();
      const x = ((e.clientX - r.left) / r.width) * 100;
      const y = ((e.clientY - r.top) / r.height) * 100;
      cancelAnimationFrame(raf);
      raf = requestAnimationFrame(() => {
        glow.style.setProperty('--gx', `${x}%`);
        glow.style.setProperty('--gy', `${y}%`);
      });
    };
    el.addEventListener('pointermove', onMove);
    return () => {
      el.removeEventListener('pointermove', onMove);
      cancelAnimationFrame(raf);
    };
  }, []);

  return (
    <section
      ref={sectionRef}
      className="hero"
      aria-label="QuillMD — the note writes itself"
    >
      <div
        ref={glowRef}
        className="hero-glow"
        aria-hidden
        style={{ ['--gx' as string]: '50%', ['--gy' as string]: '38%' }}
      />

      <nav className="nav" aria-label="Primary">
        <a className="brand font-display" href="#top">
          Quill<span className="text-turq">MD</span>
        </a>
        <div className="nav-links">
          <a href="#sandbox">Sandbox</a>
          <a href="#journey">How it works</a>
          <a href="#security">Security</a>
          <a className="btn btn-ghost nav-cta" href="#start">Start free</a>
        </div>
      </nav>

      <div className="hero-stage" id="top">
        <div className="monolith-wrap">
          {/* The HERO_MONOLITH image. Self-hosted; swapped to the real
              Higgsfield render when its URL is provided. */}
          <img
            src="/assets/hero-monolith.webp"
            alt="A floating obsidian-glass prism with glowing internal data streams"
            className="monolith"
            width={1344}
            height={768}
            decoding="async"
          />
          <div className="monolith-floor" aria-hidden />
        </div>

        <div className="hero-copy">
          <p className="eyebrow reveal is-in">Ambient clinical documentation</p>
          <h1 className="font-display hero-title">
            The note<br />writes<br /><span className="text-turq">itself</span>
          </h1>
          <p className="hero-sub">
            QuillMD listens to the visit and drafts the note from what was
            actually said — every line anchored to the transcript, machine-verified,
            with a review lane for anything it can’t ground.
            <strong className="text-gold"> You sign every note.</strong>
          </p>
          <div className="hero-cta">
            <a className="btn btn-primary" href="#start">
              Start free <span aria-hidden>→</span>
            </a>
            <a className="btn btn-ghost" href="#sandbox">See it work</a>
          </div>
          <ul className="trust-row" aria-label="What QuillMD guarantees">
            {TRUST.map((t, i) => (
              <li key={t}>
                {i > 0 && <span className="trust-dot" aria-hidden>·</span>}
                {t}
              </li>
            ))}
          </ul>
        </div>
      </div>

      <a className="scroll-hint font-mono" href="#sandbox" aria-label="Scroll to the live sandbox">
        ↓ watch it write
      </a>
    </section>
  );
}
