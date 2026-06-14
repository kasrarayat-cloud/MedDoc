'use client';

import { useEffect, useRef } from 'react';
import { Headline, HeroCopy, useReducedMotion } from '../shared';

// v5 — generative particles. Thousands of gold/turquoise points drift on the
// obsidian field, then converge into a waveform, hold, dissolve, and reform.
// Perf-capped (particle count scales to viewport, DPR clamped, alpha-trails).
// Reduced motion → one resolved static frame (the formed waveform), no loop.
export function V5Particle() {
  const reduce = useReducedMotion();
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const dpr = Math.min(window.devicePixelRatio || 1, 1.75);
    let w = 0, h = 0;
    type P = { x: number; y: number; hx: number; hy: number; tx: number; ty: number; c: string; r: number };
    let parts: P[] = [];

    // target shape: a centered waveform (audio → note motif)
    const targets = (cw: number, ch: number, n: number) => {
      const out: { x: number; y: number }[] = [];
      const midY = ch * 0.5;
      const span = cw * 0.74;
      const x0 = (cw - span) / 2;
      for (let i = 0; i < n; i++) {
        const t = i / n;
        const x = x0 + t * span;
        // layered sines → a lively waveform envelope
        const env = Math.sin(t * Math.PI); // taper ends
        const a = (Math.sin(t * 38) * 0.5 + Math.sin(t * 7.3 + 1.2) * 0.5) * env;
        out.push({ x, y: midY + a * ch * 0.17 });
      }
      return out;
    };

    const build = () => {
      const r = canvas.getBoundingClientRect();
      w = r.width; h = r.height;
      canvas.width = Math.floor(w * dpr);
      canvas.height = Math.floor(h * dpr);
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      // particle budget scales with area, hard-capped for perf
      const N = Math.min(2600, Math.floor((w * h) / 900));
      const tg = targets(w, h, N);
      parts = new Array(N).fill(0).map((_, i) => {
        const t = tg[i];
        return {
          x: Math.random() * w, y: Math.random() * h,
          hx: Math.random() * w, hy: Math.random() * h,
          tx: t.x, ty: t.y,
          c: Math.random() < 0.5 ? 'rgba(232,184,92,' : 'rgba(63,216,200,',
          r: Math.random() * 1.3 + 0.5,
        };
      });
    };
    const drawStatic = () => {
      ctx.clearRect(0, 0, w, h);
      for (const p of parts) {
        ctx.fillStyle = p.c + '0.9)';
        ctx.beginPath(); ctx.arc(p.tx, p.ty, p.r, 0, 6.283); ctx.fill();
      }
    };

    build();
    // Under reduced motion, a resize must rebuild AND redraw the static frame —
    // otherwise the canvas goes blank after a resize. Under motion, the rAF loop
    // repaints every frame so a plain rebuild is enough.
    const ro = new ResizeObserver(reduce ? () => { build(); drawStatic(); } : build);
    ro.observe(canvas);

    if (reduce) { drawStatic(); return () => ro.disconnect(); }

    // cycle: 0..1 converge → hold → 1..2 disperse, looping
    let raf = 0, t0 = 0;
    const CYCLE = 7200; // ms
    const frame = (now: number) => {
      if (!t0) t0 = now;
      const phase = ((now - t0) % CYCLE) / CYCLE; // 0..1
      // ease converge in first 45%, hold to 65%, disperse to 100%
      let k: number;
      if (phase < 0.45) k = ease(phase / 0.45);
      else if (phase < 0.65) k = 1;
      else k = 1 - ease((phase - 0.65) / 0.35);
      // alpha-trail for a comet feel
      ctx.fillStyle = 'rgba(5,6,8,0.28)';
      ctx.fillRect(0, 0, w, h);
      for (const p of parts) {
        const gx = p.hx + (p.tx - p.hx) * k;
        const gy = p.hy + (p.ty - p.hy) * k;
        // subtle drift while dispersed
        p.x += (gx - p.x) * 0.12 + Math.sin(now * 0.001 + p.tx) * (1 - k) * 0.2;
        p.y += (gy - p.y) * 0.12;
        ctx.fillStyle = p.c + (0.25 + k * 0.65) + ')';
        ctx.beginPath(); ctx.arc(p.x, p.y, p.r, 0, 6.283); ctx.fill();
      }
      raf = requestAnimationFrame(frame);
    };
    raf = requestAnimationFrame(frame);

    return () => { cancelAnimationFrame(raf); ro.disconnect(); };
  }, [reduce]);

  return (
    <section className={`ml-hero v5 ${reduce ? 'reduce' : ''}`} aria-label="Concept 5 — generative particles">
      <canvas ref={canvasRef} className="v5-canvas" aria-hidden />
      <div className="v5-vignette" aria-hidden />
      <div className="ml-stage v5-stage">
        <div className="ml-copy v5-copy">
          <p className="ml-eyebrow">Ambient clinical documentation</p>
          <Headline />
          <HeroCopy />
        </div>
      </div>
    </section>
  );
}

function ease(x: number) { return x < 0.5 ? 2 * x * x : 1 - Math.pow(-2 * x + 2, 2) / 2; }

export default V5Particle;
