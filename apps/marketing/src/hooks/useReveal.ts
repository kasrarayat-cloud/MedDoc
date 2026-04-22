'use client';

import { useEffect } from 'react';

/**
 * Add the `.in` class to every element matching `selector` (default `.reveal`)
 * once it scrolls into view. Pairs with the reveal CSS in landing.css which
 * animates opacity + translate on the `.in` state. One-shot: elements are
 * unobserved after the first intersection so the animation doesn't replay.
 */
export function useReveal(selector = '.reveal'): void {
  useEffect(() => {
    const els = document.querySelectorAll<HTMLElement>(selector);
    if (els.length === 0) return;

    const io = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            entry.target.classList.add('in');
            io.unobserve(entry.target);
          }
        }
      },
      { threshold: 0.12, rootMargin: '0px 0px -60px 0px' }
    );

    for (const el of els) io.observe(el);

    return () => io.disconnect();
  }, [selector]);
}
