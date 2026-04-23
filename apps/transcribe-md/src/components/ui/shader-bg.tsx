'use client';

// HANDOFF §2.1 + §8.3 + §8.9 — canvas mesh-gradient backdrop. Four
// coloured blobs driven by requestAnimationFrame drift. Cleanup is
// guarded against React 19 StrictMode double-mount per §8.3, and the
// RAF loop pauses on `document.hidden` + short-circuits when the user
// has `prefers-reduced-motion: reduce` set per §8.9.

import { useEffect, useRef } from 'react';

type Blob = { x: number; y: number; r: number; color: [number, number, number] };

const BLOBS: Blob[] = [
  { x: 0.3, y: 0.2, r: 0.45, color: [139, 92, 255] },
  { x: 0.75, y: 0.35, r: 0.38, color: [217, 70, 239] },
  { x: 0.55, y: 0.8, r: 0.42, color: [96, 165, 250] },
  { x: 0.15, y: 0.7, r: 0.35, color: [168, 124, 255] },
];

export function ShaderBG({
  intensity = 0.3,
  seed = 0,
}: {
  /** 0..1. 0.3 for app chrome, 0.9 for signin / cinematic surfaces. */
  intensity?: number;
  /** Starting phase for the blob drift. Lets sibling shaders animate
   *  out-of-sync without a shared clock. */
  seed?: number;
}) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    let cancelled = false;
    let raf = 0;
    let t = seed;
    let width = 0;
    let height = 0;

    const resize = () => {
      const rect = canvas.getBoundingClientRect();
      width = rect.width;
      height = rect.height;
      const dpr = Math.min(2, window.devicePixelRatio || 1);
      canvas.width = Math.max(1, width * dpr);
      canvas.height = Math.max(1, height * dpr);
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    };
    resize();

    const ro = new ResizeObserver(resize);
    ro.observe(canvas);

    const reducedMotion = window.matchMedia(
      '(prefers-reduced-motion: reduce)'
    );

    const frame = () => {
      if (cancelled) return;
      t += 0.003;
      ctx.clearRect(0, 0, width, height);
      for (let i = 0; i < BLOBS.length; i++) {
        const b = BLOBS[i]!;
        const cx = (b.x + Math.sin(t + i) * 0.08) * width;
        const cy = (b.y + Math.cos(t * 0.7 + i) * 0.08) * height;
        const r = b.r * Math.min(width, height) * 1.1;
        const g = ctx.createRadialGradient(cx, cy, 0, cx, cy, r);
        const [rr, gg, bb] = b.color;
        const a = 0.22 * intensity;
        g.addColorStop(0, `rgba(${rr},${gg},${bb},${a})`);
        g.addColorStop(0.4, `rgba(${rr},${gg},${bb},${a * 0.4})`);
        g.addColorStop(1, `rgba(${rr},${gg},${bb},0)`);
        ctx.fillStyle = g;
        ctx.fillRect(0, 0, width, height);
      }
      raf = requestAnimationFrame(frame);
    };

    // Draw one static frame immediately so there's no blank flash while
    // the first RAF tick is scheduled — matters for reduced-motion + tab
    // revisits where the loop is paused.
    frame.call(null);

    const start = () => {
      if (reducedMotion.matches || document.hidden) return;
      cancelAnimationFrame(raf);
      cancelled = false;
      raf = requestAnimationFrame(frame);
    };
    const stop = () => {
      cancelled = true;
      cancelAnimationFrame(raf);
    };

    if (reducedMotion.matches) {
      // Static single frame already drawn — no RAF loop.
    } else if (!document.hidden) {
      start();
    }

    const onVis = () => {
      if (document.hidden) stop();
      else if (!reducedMotion.matches) start();
    };
    document.addEventListener('visibilitychange', onVis);

    return () => {
      cancelled = true;
      cancelAnimationFrame(raf);
      ro.disconnect();
      document.removeEventListener('visibilitychange', onVis);
    };
  }, [intensity, seed]);

  return (
    <div
      className="qm-shader"
      style={{ opacity: 0.55 * intensity + 0.2 }}
      aria-hidden
    >
      <canvas ref={canvasRef} />
    </div>
  );
}
