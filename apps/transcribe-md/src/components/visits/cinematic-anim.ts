// ============================================================================
// cinematic-anim — small client helpers for the Phase 4 cinematic hero
// animation. Pulled out of CinematicVisitHero / CinematicRecordingHero so
// both components can call the same sequencing logic without duplication.
// Source of truth (vanilla-JS implementation):
//   docs/design-directions-v6/studio-variations/landing-11-anim-1.html
//   docs/design-directions-v6/studio-variations/visit-detail-04.html
//   docs/design-directions-v6/studio-variations/recording-04.html
// ============================================================================

/**
 * Drives the .av1-word / .av1-fade / .av1-card / .av1-cta entry sequence
 * inside `root`. Reads each element's optional `data-d` attribute (a
 * delay in milliseconds) and adds the `.show` class via setTimeout so the
 * blur-to-sharp + slide-up transition fires.
 *
 * Returns a cancellation function the caller should invoke on unmount.
 *
 * Reduced-motion aware: when `(prefers-reduced-motion: reduce)` matches,
 * every targeted element gets `.show` applied immediately so the page
 * lands in its final visual state without any transitions.
 */
export function runCinematicEntry(root: HTMLElement): (() => void) | undefined {
  if (typeof window === 'undefined') return;

  const reduceMotion =
    typeof window.matchMedia === 'function' &&
    window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  const targets = root.querySelectorAll<HTMLElement>(
    '.av1-word, .av1-fade, .av1-card, .av1-cta'
  );
  if (reduceMotion) {
    targets.forEach((el) => el.classList.add('show'));
    return;
  }

  const timers: ReturnType<typeof setTimeout>[] = [];

  // Fire on the next frame so the initial styles (opacity 0, blur 14px)
  // are committed by the browser before the .show class flips them.
  const raf = requestAnimationFrame(() => {
    targets.forEach((el) => {
      // Default delays per element type — match the cadence in
      // landing-11-anim-1.html so the hero "feels" identical:
      //   .av1-word  → use the explicit data-d (defaults to 0)
      //   .av1-fade  → 1500ms unless data-d set
      //   .av1-card  → 1200ms unless data-d set (slightly later than fade)
      //   .av1-cta   → 1900ms unless data-d set
      const explicit = el.dataset.d;
      let delay = 0;
      if (explicit !== undefined) {
        delay = parseInt(explicit, 10) || 0;
      } else if (el.classList.contains('av1-card')) {
        delay = 1200;
      } else if (el.classList.contains('av1-cta')) {
        delay = 1900;
      } else if (el.classList.contains('av1-fade')) {
        delay = 1500;
      } else if (el.classList.contains('av1-word')) {
        delay = 0;
      }
      const t = setTimeout(() => el.classList.add('show'), delay + 80);
      timers.push(t);
    });
  });

  return () => {
    cancelAnimationFrame(raf);
    timers.forEach((t) => clearTimeout(t));
  };
}

/**
 * Wires the parallax + DOF blur scroll handler to the supplied
 * background element. Mirrors the vanilla-JS implementation in
 * landing-11-anim-1.html (and the visit-detail-04.html / recording-04.html
 * variants — the shorter band uses a smaller `blurStartFactor`):
 *
 *   - Vertical translate scales linearly with scroll (-y * 0.18)
 *   - Photo scales up to 1.05 over the first 600px of scroll
 *   - DOF blur ramps from 0 → 6px once scroll exceeds blurStart
 *
 * Returns a cancellation function the caller should invoke on unmount.
 * No-op when `bg` is null or when reduced-motion is requested.
 */
export function scheduleParallaxScroll(
  bg: HTMLElement | null,
  blurStartFactor = 0.6
): (() => void) | undefined {
  if (typeof window === 'undefined' || !bg) return;
  if (
    typeof window.matchMedia === 'function' &&
    window.matchMedia('(prefers-reduced-motion: reduce)').matches
  ) {
    return;
  }

  let ticking = false;
  function frame() {
    if (!bg) return;
    const y = window.scrollY;
    const p = Math.max(0, Math.min(1, y / 600));
    const scale = 1 + p * 0.05;
    const ty = -y * 0.18;
    const blurStart = window.innerHeight * blurStartFactor;
    const blurAmt = Math.max(0, Math.min(1, (y - blurStart) / 280));
    const blur = blurAmt * 6;
    bg.style.transform = `translate3d(0, ${ty}px, 0) scale(${scale.toFixed(3)})`;
    bg.style.filter = blur > 0 ? `blur(${blur.toFixed(1)}px)` : 'none';
    ticking = false;
  }
  function onScroll() {
    if (!ticking) {
      requestAnimationFrame(frame);
      ticking = true;
    }
  }
  window.addEventListener('scroll', onScroll, { passive: true });
  frame();
  return () => {
    window.removeEventListener('scroll', onScroll);
  };
}
