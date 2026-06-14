'use client';

import { useEffect, useRef } from 'react';
import type { CSSProperties } from 'react';
import { Headline, HeroCopy, SOAP, useReducedMotion } from '../shared';

// v3 — the filmic scroll. Lenis smooth-scroll inertia + a GSAP ScrollTrigger
// pinned scene: the SOAP card assembles line-by-line as you scroll, with
// background glow, mid card, and foreground particles parallaxing at different
// depths. Reduced-motion → everything static and fully visible, no pin.
export function V3Cinematic() {
  const reduce = useReducedMotion();
  const rootRef = useRef<HTMLDivElement>(null);
  const pinRef = useRef<HTMLDivElement>(null);
  const glowRef = useRef<HTMLDivElement>(null);
  const cardRef = useRef<HTMLDivElement>(null);
  const fxRef = useRef<HTMLDivElement>(null);
  const copyRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    // On mobile the two-column scene stacks; a scroll-pin would lock the SOAP
    // card below the fold where it can never be seen. Skip the pin there and
    // let the page scroll normally — the card (visible by default) scrolls in.
    if (reduce || window.matchMedia('(max-width: 820px)').matches) return;
    let lenis: { destroy: () => void; raf: (t: number) => void; on: (e: string, cb: () => void) => void } | null = null;
    let st: { kill: () => void } | null = null;
    let tickerFn: ((t: number) => void) | null = null;
    // hold the resolved gsap so teardown is synchronous + ordered (no second
    // async import racing lenis.destroy()).
    let gsapRef: {
      ticker: {
        remove: (fn: (t: number) => void) => void;
        lagSmoothing: (threshold: number | boolean, adjustedLag?: number) => void;
      };
    } | null = null;
    let cancelled = false;

    (async () => {
      const [{ default: gsap }, stMod, { default: Lenis }] = await Promise.all([
        import('gsap'),
        import('gsap/ScrollTrigger'),
        import('lenis'),
      ]);
      if (cancelled || !pinRef.current) return;
      gsapRef = gsap;
      const ScrollTrigger = stMod.ScrollTrigger;
      gsap.registerPlugin(ScrollTrigger);

      lenis = new Lenis({ lerp: 0.09, wheelMultiplier: 1 }) as unknown as typeof lenis;
      lenis!.on('scroll', ScrollTrigger.update);
      tickerFn = (time: number) => lenis!.raf(time * 1000);
      gsap.ticker.add(tickerFn);
      gsap.ticker.lagSmoothing(0);

      const cards = cardRef.current!.querySelectorAll('.v3-soap-ln');
      const tl = gsap.timeline({
        scrollTrigger: { trigger: rootRef.current, start: 'top top', end: '+=220%', scrub: 0.6, pin: pinRef.current },
      });
      // parallax depths
      tl.to(glowRef.current, { yPercent: -18, scale: 1.25, ease: 'none' }, 0)
        .to(copyRef.current, { yPercent: -8, opacity: 0.86, ease: 'none' }, 0)
        .to(fxRef.current, { yPercent: 38, ease: 'none' }, 0)
        .fromTo(cardRef.current, { yPercent: 22, opacity: 0 }, { yPercent: 0, opacity: 1, ease: 'power2.out', duration: 0.35 }, 0.1)
        .fromTo(cards, { y: 40, opacity: 0, filter: 'blur(6px)' }, { y: 0, opacity: 1, filter: 'blur(0px)', stagger: 0.18, duration: 0.6, ease: 'power3.out' }, 0.2);
      st = tl.scrollTrigger as unknown as typeof st;
      ScrollTrigger.refresh();
    })();

    return () => {
      cancelled = true;
      if (st) st.kill();
      if (gsapRef && tickerFn) gsapRef.ticker.remove(tickerFn);
      if (gsapRef) gsapRef.ticker.lagSmoothing(1000, 16); // restore GSAP default
      if (lenis) lenis.destroy();
    };
  }, [reduce]);

  return (
    <div ref={rootRef} className={`v3-root ${reduce ? 'reduce' : ''}`}>
      <section ref={pinRef} className="ml-hero v3" aria-label="Concept 3 — scroll-cinematic">
        <div ref={glowRef} className="v3-glow" aria-hidden />
        <div ref={fxRef} className="v3-fx" aria-hidden>
          {Array.from({ length: 18 }).map((_, i) => (
            <span
              key={i}
              className="v3-dot"
              style={{ left: `${(i * 61 + 7) % 100}%`, top: `${(i * 37 + 13) % 100}%`, '--d': i % 6 } as CSSProperties}
            />
          ))}
        </div>
        <div className="ml-stage v3-stage">
          <div ref={copyRef} className="ml-copy v3-copy">
            <p className="ml-eyebrow">Ambient clinical documentation</p>
            <Headline />
            <HeroCopy />
          </div>
          <div ref={cardRef} className="glass glass-edge v3-card">
            <div className="v3-card-head font-mono"><span>SOAP draft</span><span className="text-turq">assembling…</span></div>
            <ol className="v3-soap font-mono" aria-hidden>
              {SOAP.map((l) => (
                <li key={l.tag} className="v3-soap-ln">
                  <span className={`v3-tag v3-${l.tag}`}>{l.tag}</span>
                  <span>{l.text}</span>
                </li>
              ))}
            </ol>
          </div>
        </div>
        {!reduce && <div className="ml-scrollcue font-mono" aria-hidden>↓ scroll</div>}
      </section>
    </div>
  );
}
