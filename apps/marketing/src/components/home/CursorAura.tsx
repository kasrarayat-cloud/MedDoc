'use client';

import { useEffect, useRef } from 'react';

/**
 * 420px radial blob that trails the cursor with a 0.12 lerp. Mix-blend screen
 * over the rest of the page. Stays invisible until the first `mousemove` (the
 * `body.cursor-ready` class toggles opacity in landing.css). The `hover: none`
 * media query hides it on touch, so this runs safely on desktop only; mobile
 * visitors never see it.
 */
export function CursorAura() {
  const auraRef = useRef<HTMLDivElement | null>(null);
  const orbRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    const aura = auraRef.current;
    if (!aura) return;

    orbRef.current = document.getElementById('orbWrap');

    const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (reducedMotion) return;

    let mx = window.innerWidth / 2;
    let my = window.innerHeight / 2;
    let cx = mx;
    let cy = my;
    let raf = 0;

    function onMove(event: MouseEvent) {
      mx = event.clientX;
      my = event.clientY;
      document.body.classList.add('cursor-ready');
    }

    function tick() {
      cx += (mx - cx) * 0.12;
      cy += (my - cy) * 0.12;
      if (aura) {
        aura.style.transform = `translate(${cx}px, ${cy}px) translate(-50%, -50%)`;
      }
      const orb = orbRef.current;
      if (orb) {
        const rect = orb.getBoundingClientRect();
        const px = (mx - (rect.left + rect.width / 2)) / window.innerWidth;
        const py = (my - (rect.top + rect.height / 2)) / window.innerHeight;
        orb.style.transform = `rotateY(${px * 8}deg) rotateX(${-py * 8}deg)`;
      }
      raf = requestAnimationFrame(tick);
    }

    window.addEventListener('mousemove', onMove, { passive: true });
    raf = requestAnimationFrame(tick);

    return () => {
      window.removeEventListener('mousemove', onMove);
      if (raf) cancelAnimationFrame(raf);
    };
  }, []);

  return <div ref={auraRef} className="cursor-aura" aria-hidden />;
}
