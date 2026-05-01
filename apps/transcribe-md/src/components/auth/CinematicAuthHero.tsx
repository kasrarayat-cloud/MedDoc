'use client';

// ============================================================================
// Phase 4 — CinematicAuthHero
// ----------------------------------------------------------------------------
// Top-of-page photo band rendered above every auth route's form card.
// Visual reference: docs/design-directions-v6/studio-variations/auth-04.html
// Animation reference: docs/design-directions-v6/studio-variations/landing-11-anim-1.html
//
// The component renders the auth-hero.webp band (jpg fallback) with a
// cream gradient overlay, the page-specific headline split into three
// .av1-word spans (pre / em-glow / post), and an optional eyebrow row.
//
// On hydration, it sequences the anim-1 vocabulary:
//   1. Eyebrow fades in early (~120 ms).
//   2. Words reveal blur-to-sharp on a 120 ms-per-word stagger.
//   3. After the last word lands, the AuthShell card (rendered below
//      this band by the parent layout) is asked to slide-in from the
//      right via the .av1-card / .show pair. The card itself lives on
//      `[data-cin-card]` and is owned by <AuthShell> — the parent
//      includes the .av1-card class on its wrapper element so this
//      component's effect can apply .show on the same timeline.
//
// Reduced-motion: skip timers, snap everything to the final frame on
// mount.
//
// PROTECTED_CONTRACTS: this component is JSX-only. It doesn't read or
// touch any auth-logic, server-action, NextAuth, or API routes. The
// .av1-card crossfade target is found via a sibling selector that
// looks at the document for `[data-cin-card]` so we can decouple the
// hero from the card's exact placement in the AuthShell tree.
// ============================================================================

import { useEffect, useRef, type ReactNode } from 'react';

interface CinematicAuthHeroProps {
  /** Small mono uppercase eyebrow above the headline. Optional. */
  eyebrow?: ReactNode;
  /** Plain text BEFORE the italic-sage word (e.g., "Sign "). Trailing
   *  space is preserved by the inline-block .av1-word render. */
  headlinePre: string;
  /** The italic-sage glow word (e.g., "in"). Rendered with the
   *  .av1-word.em.glow modifiers. Trailing space included. */
  headlineEm: string;
  /** Plain text AFTER the italic word (e.g., " to your visit."). */
  headlinePost: string;
}

export function CinematicAuthHero({
  eyebrow,
  headlinePre,
  headlineEm,
  headlinePost,
}: CinematicAuthHeroProps) {
  const rootRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const root = rootRef.current;
    if (!root) return;

    // The card lives outside this band's subtree (in the AuthShell
    // below). Pull it from the document so the hero can sequence its
    // reveal alongside the words.
    const card = document.querySelector<HTMLElement>('[data-cin-card]');

    const reduce =
      typeof window !== 'undefined' &&
      window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (reduce) {
      root
        .querySelectorAll('.av1-word, .av1-fade, .av1-cta')
        .forEach((el) => el.classList.add('show'));
      if (card) card.classList.add('show');
      return;
    }

    const timers: number[] = [];
    // Eyebrow first.
    const eb = root.querySelector<HTMLElement>('[data-cin-eyebrow]');
    if (eb) {
      timers.push(
        window.setTimeout(() => eb.classList.add('show'), 120)
      );
    }
    // Words: stagger by their data-d attribute.
    root.querySelectorAll<HTMLElement>('.av1-word').forEach((w) => {
      const d = parseInt(w.dataset.d ?? '0', 10);
      timers.push(
        window.setTimeout(() => w.classList.add('show'), d + 80)
      );
    });
    // Form card (sibling): blur-to-sharp + slide from right after the
    // headline lands. Studio reference auth-04.html uses 600 ms.
    if (card) {
      timers.push(
        window.setTimeout(() => card.classList.add('show'), 500)
      );
    }
    // Any .av1-fade rows inside the card (fields, "Forgot?" row,
    // CTA) reveal in sequence after the card has begun its slide.
    timers.push(
      window.setTimeout(() => {
        document
          .querySelectorAll<HTMLElement>('[data-cin-card] .av1-fade')
          .forEach((el, i) => {
            window.setTimeout(() => el.classList.add('show'), i * 90);
          });
      }, 1000)
    );
    timers.push(
      window.setTimeout(() => {
        document
          .querySelectorAll<HTMLElement>('[data-cin-card] .av1-cta')
          .forEach((el, i) => {
            window.setTimeout(() => el.classList.add('show'), i * 100);
          });
      }, 1400)
    );

    return () => {
      timers.forEach((t) => window.clearTimeout(t));
    };
  }, []);

  return (
    <div ref={rootRef} className="qm-cin-auth-band" aria-hidden={false}>
      {/* Photo layer — webp via image-set with jpg fallback. The
         secondary jpg layer below it covers older Firefox / embedded
         webviews that don't support image-set yet. */}
      <div
        className="qm-cin-bg"
        style={{
          backgroundImage:
            "image-set(url('/images/cinematic/auth-hero.webp') type('image/webp'), url('/images/cinematic/auth-hero.jpg') type('image/jpeg'))",
        }}
      />
      <div
        className="qm-cin-bg"
        style={{
          backgroundImage: "url('/images/cinematic/auth-hero.jpg')",
          zIndex: -1,
        }}
        aria-hidden
      />
      <div className="qm-cin-inner qm-cin-inner-auth">
        {eyebrow && (
          <div className="qm-cin-eyebrow av1-fade" data-cin-eyebrow>
            <span className="dot" />
            {eyebrow}
          </div>
        )}
        <h1
          className="qm-cin-headline"
          aria-label={`${headlinePre}${headlineEm}${headlinePost}`.trim()}
        >
          <span className="av1-word" data-d="0">
            {headlinePre}
          </span>
          <span className="av1-word em glow" data-d="120">
            {headlineEm}
          </span>
          <span className="av1-word" data-d="240">
            {headlinePost}
          </span>
        </h1>
      </div>
    </div>
  );
}
