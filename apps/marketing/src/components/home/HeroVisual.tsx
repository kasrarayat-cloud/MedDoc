'use client';

import { useEffect, useRef } from 'react';

/**
 * Hero product visual — Phase 7 v6 (Apple Product).
 *
 * The floating 3D SOAP card with two stacked back-cards behind it. CSS handles
 * the idle 9s float animation and 8°/-2° rotation; this client component just
 * adds desktop mouse-move parallax (hover the visual, the main card tilts
 * toward the cursor on a 6° X/Y range; release returns to the CSS animation).
 *
 * Below 960px the back cards are hidden and the float anim is disabled
 * (handled in landing.css), and parallax bails out via matchMedia.
 */
export function HeroVisual() {
  const wrapRef = useRef<HTMLDivElement>(null);
  const cardRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const wrap = wrapRef.current;
    const card = cardRef.current;
    if (!wrap || !card) return;

    const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    const widescreen = window.matchMedia('(min-width: 961px)').matches;
    if (reduced || !widescreen) return;

    function onMove(e: MouseEvent) {
      if (!wrap || !card) return;
      const rect = wrap.getBoundingClientRect();
      const px = (e.clientX - rect.left) / rect.width - 0.5;
      const py = (e.clientY - rect.top) / rect.height - 0.5;
      card.style.transform = `rotateX(${8 - py * 6}deg) rotateY(${-2 + px * 6}deg)`;
      card.style.animation = 'none';
    }
    function onLeave() {
      if (!card) return;
      card.style.transform = '';
      card.style.animation = '';
    }

    wrap.addEventListener('mousemove', onMove);
    wrap.addEventListener('mouseleave', onLeave);
    return () => {
      wrap.removeEventListener('mousemove', onMove);
      wrap.removeEventListener('mouseleave', onLeave);
    };
  }, []);

  return (
    <div className="hero-visual" aria-hidden ref={wrapRef}>
      <div className="hero-card back-2" />
      <div className="hero-card back-1" />
      <div className="hero-card main" ref={cardRef}>
        <div className="hero-card-chrome">
          <span className="chrome-dot" />
          <span className="chrome-dot" />
          <span className="chrome-dot" />
          <div className="chrome-tabs">
            <span className="chrome-tab">visit-7K2A</span>
            <span className="chrome-tab active">live</span>
            <span className="chrome-tab">soap.md</span>
          </div>
          <div className="chrome-meta">
            <span className="live-dot" />
            recording · 01:42
          </div>
        </div>
        <div className="hero-card-body">
          <div>
            <div className="hero-pane-label">Transcript · diarized</div>
            <div className="hero-transcript">
              <div className="ht-line">
                <span className="who">Pt</span>Started about three days ago. Dull, behind the
                sternum.
              </div>
              <div className="ht-line">
                <span className="who">Dr</span>Any radiation to jaw or arm?
              </div>
              <div className="ht-line">
                <span className="who">Pt</span>No jaw. Tight on stairs. I have asthma.
              </div>
            </div>
          </div>
          <div>
            <div className="hero-pane-label">SOAP draft · validated</div>
            <div className="hero-soap">
              <div className="hs-row">
                <span className="hs-letter">S</span>
                <span className="hs-text">
                  3-day retrosternal chest discomfort, positional, non-radiating. Mild exertional
                  dyspnea.
                </span>
              </div>
              <div className="hs-row">
                <span className="hs-letter">O</span>
                <span className="hs-text">BP 128/82, HR 76, lungs CTAB.</span>
              </div>
              <div className="hs-row">
                <span className="hs-letter">A</span>
                <span className="hs-text">Atypical chest pain · Asthma uncontrolled.</span>
              </div>
              <div className="hs-row">
                <span className="hs-letter">P</span>
                <span className="hs-text">ECG today. Trial PPI × 2 wks.</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
