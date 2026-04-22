'use client';

import { useEffect, type RefObject } from 'react';

/**
 * Animate `ref.current.textContent` from 0 to `target` over `durationMs` once
 * the element enters the viewport. Uses a cubic ease-out and formats the
 * output via `format(value)` — caller's responsibility (e.g. `v => v.toFixed(1)`).
 *
 * Skips animation when the user prefers reduced motion; in that case the
 * target value is written once on mount so the UI still looks "done".
 */
export function useCounter(
  ref: RefObject<HTMLElement | null>,
  target: number,
  durationMs: number,
  format: (value: number) => string = (v) => v.toFixed(1)
): void {
  useEffect(() => {
    const el = ref.current;
    if (!el) return;

    if (
      typeof window !== 'undefined' &&
      window.matchMedia('(prefers-reduced-motion: reduce)').matches
    ) {
      el.textContent = format(target);
      return;
    }

    let raf = 0;

    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (!entry.isIntersecting) continue;
          const startedAt = performance.now();
          const tick = (now: number) => {
            const progress = Math.min(1, (now - startedAt) / durationMs);
            const eased = 1 - Math.pow(1 - progress, 3);
            el.textContent = format(target * eased);
            if (progress < 1) raf = requestAnimationFrame(tick);
          };
          raf = requestAnimationFrame(tick);
          observer.unobserve(entry.target);
        }
      },
      { threshold: 0.4 }
    );

    observer.observe(el);

    return () => {
      observer.disconnect();
      if (raf) cancelAnimationFrame(raf);
    };
  }, [ref, target, durationMs, format]);
}
