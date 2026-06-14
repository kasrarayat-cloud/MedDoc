'use client';

// H2 — LIGHT / CLINICAL. Locked to Perplexity Enterprise (uppercase "FOR ___" eyebrow +
// elegant serif on a sage band, product-as-proof card), grounded in Ease Health's
// forest-green CTA + shadowless tinted-surface system. The sage band doubles as
// QuillMD's existing sage (#7AA68C) — continuity by design.
import { SOAP } from '../motion/shared';
import { HeroHeadline, HeroSub, HeroCtas, HeroTrust } from './parts';

export function H2Clinical() {
  return (
    <section className="h-hero h2-hero" aria-label="Hero concept 2 — light, clinical">
      <div className="h-stage h2-stage">
        <div className="h2-band">
          <p className="h2-eyebrow">For clinicians</p>
          <HeroHeadline p="h2" />
          <HeroSub p="h2" />
          <HeroCtas p="h2" />
        </div>
        <div className="h2-card">
          <div className="h2-card-head">
            <span>SOAP · today’s visit</span>
            <span className="h2-card-pill">✓ verified</span>
          </div>
          <ol className="h2-soap" aria-label="Sample SOAP draft">
            {SOAP.map((l) => (
              <li key={l.tag} className="h2-soap-ln">
                <span className="h2-soap-tag">{l.tag}</span>
                <span>{l.text}</span>
              </li>
            ))}
          </ol>
        </div>
        <HeroTrust p="h2" />
      </div>
    </section>
  );
}
