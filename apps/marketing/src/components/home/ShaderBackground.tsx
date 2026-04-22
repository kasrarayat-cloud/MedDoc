'use client';

import { useEffect, useRef } from 'react';

/**
 * Fixed-position canvas rendering 4 drifting radial-gradient blobs, tinted to
 * the accent palette. Pauses when `document.hidden` to save battery, and skips
 * the animation loop entirely when the user prefers reduced motion (the canvas
 * stays blank — the static grid overlay behind it carries enough texture).
 */
export function ShaderBackground() {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    let width = 0;
    let height = 0;
    const dpr = Math.min(2, window.devicePixelRatio || 1);

    function resize() {
      if (!canvas || !ctx) return;
      width = window.innerWidth;
      height = window.innerHeight;
      canvas.width = width * dpr;
      canvas.height = height * dpr;
      canvas.style.width = `${width}px`;
      canvas.style.height = `${height}px`;
      ctx.setTransform(1, 0, 0, 1, 0, 0);
      ctx.scale(dpr, dpr);
    }

    resize();
    window.addEventListener('resize', resize);

    const blobs: Array<{ x: number; y: number; r: number; color: [number, number, number] }> = [
      { x: 0.3, y: 0.2, r: 0.45, color: [139, 92, 255] },
      { x: 0.75, y: 0.35, r: 0.38, color: [217, 70, 239] },
      { x: 0.55, y: 0.8, r: 0.42, color: [96, 165, 250] },
      { x: 0.15, y: 0.7, r: 0.35, color: [168, 124, 255] },
    ];

    let t = 0;
    let raf = 0;
    let paused = document.hidden;

    function frame() {
      if (paused || !ctx) {
        raf = 0;
        return;
      }
      t += 0.003;
      const scrollRatio = window.scrollY / window.innerHeight;
      ctx.clearRect(0, 0, width, height);
      for (let i = 0; i < blobs.length; i++) {
        const b = blobs[i];
        const cx = (b.x + Math.sin(t + i) * 0.08) * width;
        const cy = (b.y + Math.cos(t * 0.7 + i) * 0.08 - scrollRatio * 0.2) * height;
        const r = b.r * Math.min(width, height) * 1.1;
        const g = ctx.createRadialGradient(cx, cy, 0, cx, cy, r);
        const [rr, gg, bb] = b.color;
        g.addColorStop(0, `rgba(${rr},${gg},${bb},0.22)`);
        g.addColorStop(0.4, `rgba(${rr},${gg},${bb},0.08)`);
        g.addColorStop(1, `rgba(${rr},${gg},${bb},0)`);
        ctx.fillStyle = g;
        ctx.fillRect(0, 0, width, height);
      }
      raf = requestAnimationFrame(frame);
    }

    const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    function onVisibility() {
      paused = document.hidden;
      if (!paused && !raf && !reducedMotion) {
        raf = requestAnimationFrame(frame);
      }
    }
    document.addEventListener('visibilitychange', onVisibility);

    if (!reducedMotion) {
      raf = requestAnimationFrame(frame);
    }

    return () => {
      window.removeEventListener('resize', resize);
      document.removeEventListener('visibilitychange', onVisibility);
      if (raf) cancelAnimationFrame(raf);
    };
  }, []);

  return (
    <div className="shader-bg" aria-hidden>
      <canvas ref={canvasRef} />
      <div className="shader-grid" />
    </div>
  );
}
