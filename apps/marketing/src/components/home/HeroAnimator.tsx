'use client';

import { useEffect } from 'react';

/**
 * Client-side orchestrator for the Phase 4 Apple Cinematic hero.
 *
 * Two responsibilities, both lifted verbatim from the source-of-truth mockup
 * `docs/design-directions-v6/studio-variations/landing-11-anim-1.html`:
 *
 * 1. **Word-stagger reveal.** On mount, schedule each `.av1-word` to add the
 *    `.show` class at its `data-d` ms offset, then run the `.av1-fade` /
 *    `.av1-cta` / `.av1-card` cohorts at the timeline beats baked into the
 *    mockup (eyebrow at 120 ms, SOAP card at 1200 ms, fade-ups at 1700 ms,
 *    CTAs at 1900 ms).
 *
 * 2. **Scroll-driven parallax + DOF.** A `requestAnimationFrame` loop reads
 *    `window.scrollY` and writes `transform`/`filter` onto the `#qm-cin-bg`
 *    element so the photo backdrop scales 1.00 → 1.05 across the first
 *    600 px and gains up to a 6 px DOF blur once the user scrolls past
 *    `window.innerHeight * 0.8`.
 *
 * Both branches honour `prefers-reduced-motion: reduce` — when set, every
 * `.av1-*` element gets `.show` immediately and the scroll handler never
 * mounts. Re-implementing this in JS (instead of inline `<script>`) avoids
 * the Next 16 dev-mode "do not use untrusted dangerouslySetInnerHTML" guard
 * and keeps both effects under a single useEffect cleanup.
 */
export function HeroAnimator() {
  useEffect(() => {
    const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    if (reducedMotion) {
      document
        .querySelectorAll<HTMLElement>('.av1-word, .av1-fade, .av1-card, .av1-cta')
        .forEach((el) => el.classList.add('show'));
      return;
    }

    // ── Animation timeline (verbatim from landing-11-anim-1.html) ──────────
    const timers: Array<ReturnType<typeof setTimeout>> = [];

    // Eyebrow leads first to feel like a sequence start.
    const eyebrow = document.getElementById('av1-eyebrow');
    if (eyebrow) timers.push(setTimeout(() => eyebrow.classList.add('show'), 120));

    // Word stagger — each .av1-word reveals at its data-d ms offset (+ 80ms
    // pre-roll buffer so the first paint isn't jittery).
    const raf = requestAnimationFrame(() => {
      document.querySelectorAll<HTMLElement>('.av1-word').forEach((w) => {
        const d = parseInt(w.dataset.d ?? '0', 10);
        timers.push(setTimeout(() => w.classList.add('show'), d + 80));
      });

      // SOAP card slides in 1200 ms after page load.
      timers.push(
        setTimeout(() => {
          const card = document.getElementById('av1-soap-card');
          if (card) card.classList.add('show');
        }, 1200),
      );

      // Standfirst + meta fade up after the headline settles.
      timers.push(
        setTimeout(() => {
          document
            .querySelectorAll<HTMLElement>('.av1-fade')
            .forEach((el) => el.classList.add('show'));
        }, 1700),
      );

      // CTAs scale-fade in last so the headline lands first.
      timers.push(
        setTimeout(() => {
          document
            .querySelectorAll<HTMLElement>('.av1-cta')
            .forEach((el) => el.classList.add('show'));
        }, 1900),
      );
    });

    // ── Scroll parallax + DOF blur ─────────────────────────────────────────
    const bg = document.getElementById('qm-cin-bg');
    let ticking = false;
    let scrollRaf = 0;

    function frame() {
      if (!bg) {
        ticking = false;
        return;
      }
      const y = window.scrollY;
      const p = Math.max(0, Math.min(1, y / 600));
      const scale = 1 + p * 0.05;
      const ty = -y * 0.18;
      const blurStart = window.innerHeight * 0.8;
      const blurAmt = Math.max(0, Math.min(1, (y - blurStart) / 280));
      const blur = blurAmt * 6;
      bg.style.transform = `translate3d(0, ${ty}px, 0) scale(${scale.toFixed(3)})`;
      bg.style.filter = blur > 0 ? `blur(${blur.toFixed(1)}px)` : 'none';
      ticking = false;
    }

    function onScroll() {
      if (!ticking) {
        scrollRaf = requestAnimationFrame(frame);
        ticking = true;
      }
    }

    window.addEventListener('scroll', onScroll, { passive: true });
    // Run once on mount to set initial transform (covers reload-mid-page).
    frame();

    return () => {
      timers.forEach((t) => clearTimeout(t));
      cancelAnimationFrame(raf);
      if (scrollRaf) cancelAnimationFrame(scrollRaf);
      window.removeEventListener('scroll', onScroll);
    };
  }, []);

  return null;
}
