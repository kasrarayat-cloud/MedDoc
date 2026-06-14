'use client';

// H3 — EDITORIAL / TYPOGRAPHIC. Locked to Medium + Polar (one dominant headline, hairline
// dividers, magazine restraint, left alignment, huge negative space), grounded in Attio's
// soft-serif + 1px-border system. Colour-free headline — emphasis is serif ITALIC, not
// colour. Type IS the hero; no product card.
import { HeroHeadline, HeroSub, HeroCtas, HeroTrust } from './parts';

export function H3Editorial() {
  return (
    <section className="h-hero h3-hero" aria-label="Hero concept 3 — editorial, typographic">
      <div className="h3-dots" aria-hidden />
      <div className="h-stage h3-stage">
        <p className="h3-eyebrow">Clinical documentation, rethought</p>
        <HeroHeadline p="h3" />
        <div className="h3-rule" aria-hidden />
        <HeroSub p="h3" />
        <HeroCtas p="h3" />
        <HeroTrust p="h3" />
      </div>
    </section>
  );
}
