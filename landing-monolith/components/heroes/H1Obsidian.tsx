'use client';

// H1 — DARK / CINEMATIC. Locked to Resend (dot-grid on near-black + framed product
// panel) and Rox (one warm-gold accent), grounded in Depot's layered-surface tokens.
// The SOAP note IS the product artifact, framed and floating on the grid.
import { SOAP } from '../motion/shared';
import { HeroHeadline, HeroSub, HeroCtas, HeroTrust } from './parts';

export function H1Obsidian() {
  return (
    <section className="h-hero h1-hero" aria-label="Hero concept 1 — dark, cinematic">
      <div className="h1-grid" aria-hidden />
      <div className="h1-glow" aria-hidden />
      <div className="h-stage h1-stage">
        <div className="h1-copy">
          <p className="h1-eyebrow">Evidence-anchored documentation</p>
          <HeroHeadline p="h1" />
          <HeroSub p="h1" />
          <HeroCtas p="h1" />
          <HeroTrust p="h1" />
        </div>
        <div className="h1-panel">
          <div className="h1-panel-head">
            <span>SOAP draft</span>
            <span className="h1-panel-tick">✓ transcript-anchored</span>
          </div>
          <ol className="h1-soap" aria-label="Sample SOAP draft">
            {SOAP.map((l) => (
              <li key={l.tag} className="h1-soap-ln">
                <span className="h1-soap-tag">{l.tag}</span>
                <span>{l.text}</span>
              </li>
            ))}
          </ol>
        </div>
      </div>
    </section>
  );
}
