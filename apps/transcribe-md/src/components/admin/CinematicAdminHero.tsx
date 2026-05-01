'use client';

// ============================================================================
// CinematicAdminHero — Phase 4 Apple Cinematic admin band
// ----------------------------------------------------------------------------
// A short (200 px) photo band that sits at the top of /admin/* before the
// existing dashboard chrome. Visual reference:
//   docs/design-directions-v6/studio-variations/admin-03.html
// Animation primitives (.av1-word / .av1-fade / .av1-card / .av1-cta) come
// from the marketing landing source of truth:
//   docs/design-directions-v6/studio-variations/landing-11-anim-1.html
//
// Responsibilities (visual-only — no business logic):
//   1. Render the photo backdrop with parallax + DOF blur on scroll
//   2. Render the eyebrow ("SUPER_ADMIN · {date} · {time}"), the
//      "Operations." italic-sage-glowed headline, and the coral-tinted
//      SUPER_ADMIN pill on the right
//   3. Drive the .av1-* reveal timeline (single useEffect, mirrors the
//      marketing app's HeroAnimator pattern):
//        eyebrow + badge fade in @ ~120 ms (.av1-fade)
//        "Operations." word blur-to-sharp + sage glow @ ~200 ms (.av1-word)
//        downstream .av1-card / .av1-fade beats stay coordinated with the
//        admin overview content (cards reveal at 600/700/800/900 ms,
//        late fades at 1500 ms+).
//
// IMPORTANT — protected boundary:
//   This component is purely presentational. It receives `hasSuperAdmin`
//   from the layout (already computed by the SUPER_ADMIN gate) for the
//   visual badge state. It does NOT re-check the gate; it does NOT call
//   any admin API; it does NOT mutate audit logs. The badge is a visual
//   announcement of a check that already passed upstream.
// ============================================================================

import { useEffect, useState } from 'react';

interface CinematicAdminHeroProps {
  /**
   * Result of the SUPER_ADMIN gate as already computed by the parent
   * layout. We only render the component when this is true (the layout
   * calls `notFound()` otherwise) — the prop exists so the badge can
   * still reflect gate state if a future caller chooses to render the
   * component in a non-gated context.
   */
  hasSuperAdmin: boolean;
}

export default function CinematicAdminHero({ hasSuperAdmin }: CinematicAdminHeroProps) {
  // Server-render a stable string ("SUPER_ADMIN · loading …") and
  // hydrate the live clock client-side so the SSR vs CSR markup
  // matches. The mockup uses MAY 1 · 17:42 — we follow the same
  // "MMM D · HH:MM" shape, lifted from the user's locale.
  const [stamp, setStamp] = useState<string>('SUPER_ADMIN');

  useEffect(() => {
    function tick() {
      const now = new Date();
      const date = now
        .toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
        .toUpperCase();
      const time = now.toLocaleTimeString(undefined, {
        hour: '2-digit',
        minute: '2-digit',
        hour12: false,
      });
      setStamp(`SUPER_ADMIN · ${date} · ${time}`);
    }
    tick();
    // Refresh every 30 s so the eyebrow doesn't stagnate while a
    // SUPER_ADMIN tab is left open all afternoon. No leak risk —
    // single interval cleared on unmount.
    const id = setInterval(tick, 30_000);
    return () => clearInterval(id);
  }, []);

  // ── Animation timeline ────────────────────────────────────────────────────
  // Mirrors apps/marketing/src/components/home/HeroAnimator.tsx, scoped
  // narrowly to the IDs / data-d offsets this hero uses. The downstream
  // .av1-card / .av1-fade beats on the admin body are also reached by
  // this single sweep — querySelectorAll is global to the document, but
  // the only matching elements live below us, so the choreography lines
  // up without per-component duplication.
  useEffect(() => {
    const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    if (reducedMotion) {
      document
        .querySelectorAll<HTMLElement>('.av1-word, .av1-fade, .av1-card, .av1-cta')
        .forEach((el) => el.classList.add('show'));
      return;
    }

    const timers: Array<ReturnType<typeof setTimeout>> = [];

    // Eyebrow + super-badge lead the sequence at 120 ms — same beat as
    // the marketing landing. SSR-rendered content gains its first
    // visible frame as the .av1-fade transition fires.
    const eyebrow = document.getElementById('av1-admin-eyebrow');
    const badge = document.getElementById('av1-admin-badge');
    if (eyebrow) timers.push(setTimeout(() => eyebrow.classList.add('show'), 120));
    if (badge) timers.push(setTimeout(() => badge.classList.add('show'), 200));

    const raf = requestAnimationFrame(() => {
      // .av1-word — "Operations." blur-to-sharp at its data-d offset
      // (admin-03.html uses data-d="0", we add the 80 ms pre-roll
      // buffer the marketing version uses to avoid first-paint jitter).
      document.querySelectorAll<HTMLElement>('.av1-word').forEach((w) => {
        const d = parseInt(w.dataset.d ?? '0', 10);
        timers.push(setTimeout(() => w.classList.add('show'), d + 80));
      });

      // .av1-card — admin body's stat-card row reveals at the data-d
      // offset on each card (defaults to 600 ms). The cards live in
      // AdminOverview.client.tsx; their classes get assigned there.
      document.querySelectorAll<HTMLElement>('.av1-card').forEach((c) => {
        const d = parseInt(c.dataset.d ?? '600', 10);
        timers.push(setTimeout(() => c.classList.add('show'), d));
      });

      // .av1-cta — admin action buttons (if any). Defaults to 1400 ms +
      // an index-based stagger, same beat as the landing-11 mockup.
      document.querySelectorAll<HTMLElement>('.av1-cta').forEach((c, i) => {
        const d = parseInt(c.dataset.d ?? `${1400 + i * 100}`, 10);
        timers.push(setTimeout(() => c.classList.add('show'), d));
      });

      // .av1-fade — generic late reveal for tables / drawers (1500 ms +
      // 90 ms stagger). The eyebrow + badge already got their explicit
      // earlier slots above, so we don't double-trigger them here —
      // adding `.show` twice is a no-op.
      document.querySelectorAll<HTMLElement>('.av1-fade').forEach((e, i) => {
        timers.push(setTimeout(() => e.classList.add('show'), 1500 + i * 90));
      });
    });

    // ── Scroll parallax + DOF blur ────────────────────────────────────────
    // Verbatim from admin-03.html's scroll handler. Reads scrollY and
    // writes transform/filter onto the photo backdrop layer.
    const bg = document.getElementById('qm-cin-admin-bg');
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
      // Admin band is short, so the blur engages sooner (60 % of
      // viewport) than on the full-bleed marketing hero (80 %).
      const blurStart = window.innerHeight * 0.6;
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
    // Initial paint — covers reload-mid-page (or browser back to a
    // pre-scrolled position).
    frame();

    return () => {
      timers.forEach((t) => clearTimeout(t));
      cancelAnimationFrame(raf);
      if (scrollRaf) cancelAnimationFrame(scrollRaf);
      window.removeEventListener('scroll', onScroll);
    };
  }, []);

  return (
    <section className="qm-cin-admin-hero" aria-label="Admin operations">
      <div className="qm-cin-admin-bg" id="qm-cin-admin-bg" aria-hidden="true" />
      <div className="qm-cin-admin-inner">
        <div>
          <div
            id="av1-admin-eyebrow"
            className="qm-cin-admin-eyebrow av1-fade"
          >
            {stamp}
          </div>
          <h1 className="qm-cin-admin-title">
            {/* The entire word is italic-sage-glowed (vs other surfaces
                where only one word is italicised) — `Operations.` is a
                single-word title, so the whole label gets the .em.glow
                treatment. */}
            <span className="av1-word em glow" data-d="0">Operations.</span>
          </h1>
        </div>
        {hasSuperAdmin && (
          <div
            id="av1-admin-badge"
            className="qm-cin-admin-badge av1-fade"
            aria-label="Super admin access"
          >
            SUPER_ADMIN
          </div>
        )}
      </div>
    </section>
  );
}
