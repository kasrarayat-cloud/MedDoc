'use client';

// H4 — BOLD-TYPE / STATEMENT. Locked to Tome + Washington Post Solutions (oversized heavy
// display on charcoal, ONE saturated CTA), grounded in Framer's #000→#080808 layering,
// tight display kerning (line-height 0.9, -0.04em) and 100px pill CTA. The headline IS
// the visual; one electric accent for the accent word + pill CTA only.
import { HeroHeadline, HeroSub, HeroCtas, HeroTrust } from './parts';

export function H4Statement() {
  return (
    <section className="h-hero h4-hero" aria-label="Hero concept 4 — bold type, statement">
      <div className="h4-layer" aria-hidden />
      <div className="h-stage h4-stage">
        <p className="h4-eyebrow">Ambient AI scribe</p>
        <HeroHeadline p="h4" />
        <HeroSub p="h4" />
        <HeroCtas p="h4" />
        <HeroTrust p="h4" />
      </div>
    </section>
  );
}
