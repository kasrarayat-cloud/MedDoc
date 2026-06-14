'use client';

import { useEffect, useRef, useState } from 'react';
import { motion, useMotionValue, useSpring, useTransform } from 'framer-motion';
import { HEADLINE, HeroCopy, SOAP, useReducedMotion } from '../shared';

// v6 — "Ink Genesis": three motion systems layered into ONE cinematic hero with
// a clear hierarchy, NOT three effects fighting.
//   BG   particles (2D canvas)  — gold/turquoise atmosphere that converges to the
//        quill nib and SETTLES INTO THE INK TRAIL as the headline writes, then
//        relaxes back to a slow ambient drift. The particles ARE the ink.
//   MID  the quill (SVG)         — writes the real <h1> on load (rAF ink-reveal
//        synced to the nib), then idle-floats.
//   FG   kinetic type (framer)   — ONCE written, the headline lines spring toward
//        the cursor. Sequenced after the write so the layers never conflict.
// One shared rAF drives particles + quill; framer's spring loop only runs in the
// kinetic phase. No WebGL (canvas + SVG + framer only) to protect the frame budget.

const PER = 600; // ms to ink one line (matches v1)
const GAP = 130; // ms gap between lines

type P = {
  x: number; y: number; vx: number; vy: number;
  hx: number; hy: number; // ambient home
  tx: number; ty: number; // current spring target
  ink: boolean;           // recruited as ink along the trail?
  gold: boolean;          // colour family
  r: number;              // radius
  b: number;              // brightness 0..1
  ph: number;             // wander phase
};

export function V6Combined() {
  const reduce = useReducedMotion();
  const [kinetic, setKinetic] = useState(false); // true once the headline finishes writing (desktop only)
  const stageRef = useRef<HTMLDivElement>(null);
  const quillRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const lineRefs = useRef<(HTMLSpanElement | null)[]>([]);
  const soapRef = useRef<HTMLOListElement>(null);
  const soapLineRefs = useRef<(HTMLLIElement | null)[]>([]);
  // cursor position, normalised −1..1 over the stage (drives the kinetic springs)
  const px = useMotionValue(0);
  const py = useMotionValue(0);

  // ── one shared loop: particle field (canvas) + quill write timeline ──────────
  useEffect(() => {
    const canvas = canvasRef.current;
    const stage = stageRef.current;
    const quill = quillRef.current;
    if (!canvas || !stage) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const mobile = window.matchMedia('(max-width: 820px)').matches;
    const dpr = Math.min(window.devicePixelRatio || 1, mobile ? 1.25 : 1.5);
    let w = 0, h = 0;
    let parts: P[] = [];
    let inkPtr = 0, inkMax = 0;

    const colour = (p: P, a: number) =>
      p.gold ? `rgba(232,184,92,${a})` : `rgba(63,216,200,${a})`;

    const build = () => {
      const r = canvas.getBoundingClientRect();
      if (r.width < 1 || r.height < 1) return; // degenerate layout — keep any existing seed; frame() retries
      w = r.width; h = r.height;
      canvas.width = Math.floor(w * dpr);
      canvas.height = Math.floor(h * dpr);
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      // Lower budget than standalone v5 (three systems share the frame): scale to
      // viewport, clamp hard. ~1300 desktop / ~600 mobile.
      const N = Math.min(mobile ? 600 : 1300, Math.floor((w * h) / (mobile ? 2600 : 1700)));
      inkMax = Math.floor(N * 0.42);
      inkPtr = 0;
      parts = new Array(N).fill(0).map(() => {
        const hx = Math.random() * w, hy = Math.random() * h;
        return {
          x: hx, y: hy, vx: 0, vy: 0, hx, hy, tx: hx, ty: hy,
          ink: false, gold: Math.random() < 0.5,
          r: Math.random() * 1.3 + 0.5, b: Math.random() * 0.35 + 0.12,
          ph: Math.random() * 6.283,
        };
      });
    };

    const drawStatic = () => {
      ctx.clearRect(0, 0, w, h);
      ctx.globalCompositeOperation = 'lighter';
      for (const p of parts) {
        ctx.fillStyle = colour(p, 0.22 + p.b * 0.3);
        ctx.beginPath(); ctx.arc(p.hx, p.hy, p.r, 0, 6.283); ctx.fill();
      }
      ctx.globalCompositeOperation = 'source-over';
    };

    build();
    // Reduced motion → one static ambient frame, redraw on resize, no loop/quill.
    const ro = new ResizeObserver(reduce ? () => { build(); drawStatic(); } : build);
    ro.observe(canvas);
    if (reduce) { drawStatic(); return () => ro.disconnect(); }

    // ----- quill write timeline -----
    const lines = lineRefs.current.filter(Boolean) as HTMLSpanElement[];
    stage.classList.add('v6-writing');
    let geom: { left: number; top: number; width: number; height: number }[] | null = null;
    const total = lines.length * (PER + GAP);
    let writing = lines.length > 0;
    let nibX = 0, nibY = 0, nibActive = false;

    const stepWrite = (t: number) => {
      if (!geom) {
        const sr = stage.getBoundingClientRect();
        geom = lines.map((ln) => {
          const r = ln.getBoundingClientRect();
          return { left: r.left - sr.left, top: r.top - sr.top, width: r.width, height: r.height };
        });
      }
      nibActive = false;
      lines.forEach((ln, i) => {
        const g = geom![i];
        const e = -(Math.cos(Math.PI * Math.min(Math.max((t - i * (PER + GAP)) / PER, 0), 1)) - 1) / 2;
        ln.style.setProperty('--p', `${e}`);
        if (t >= i * (PER + GAP) && t < (i + 1) * (PER + GAP)) {
          nibX = g.left + g.width * e;
          nibY = g.top + g.height * 0.7;
          nibActive = e > 0.012 && e < 0.99;
          if (quill) {
            quill.style.setProperty('--qx', `${nibX}px`);
            quill.style.setProperty('--qy', `${g.top + g.height * 0.82}px`);
          }
        }
      });
      if (t >= total) {
        lines.forEach((l) => l.style.setProperty('--p', '1'));
        if (quill) {
          const last = geom[geom.length - 1];
          quill.style.setProperty('--qx', `${last.left + last.width + 14}px`);
          quill.style.setProperty('--qy', `${last.top + last.height * 0.5}px`);
          quill.classList.add('v6-quill-rest');
        }
        writing = false;
        stage.classList.remove('v6-writing');
        // one-shot: `writing` is now false so stepWrite never reaches here again.
        // desktop: type goes kinetic; mobile: stays static-written.
        setKinetic(!mobile);
      }
    };

    // ----- particle update -----
    const SPRING = 0.14, DAMP = 0.82;
    const updateParticles = (now: number) => {
      // recruit ink along the nib while a line is actively inking → builds the trail
      if (writing && nibActive && inkPtr < inkMax) {
        for (let k = 0; k < 4 && inkPtr < inkMax; k++) {
          const p = parts[inkPtr++];
          if (!p) break;
          p.ink = true;
          p.gold = Math.random() < 0.8;            // ink skews gold
          p.tx = nibX + (Math.random() - 0.5) * 16; // fixed trail point at the nib
          p.ty = nibY + (Math.random() - 0.5) * 12;
          p.b = 0.92;
        }
      }
      for (const p of parts) {
        if (p.ink) {
          if (!writing) {
            // write done → relax ink back into ambient drift, dissolving the trail
            p.b += (0.3 - p.b) * 0.03;
            if (Math.random() < 0.012) p.ink = false;
          }
          // ink target stays fixed (the laid-down trail point) until released
        } else {
          let tx = p.hx + Math.cos(now * 0.0004 + p.ph) * 24;
          let ty = p.hy + Math.sin(now * 0.0005 + p.ph * 1.3) * 20;
          if (writing && nibActive) {
            // the whole field leans toward the nib while writing, then relaxes
            tx += (nibX - tx) * 0.05;
            ty += (nibY - ty) * 0.05;
          }
          p.tx = tx; p.ty = ty;
          p.b += ((0.2 + 0.12 * Math.sin(now * 0.001 + p.ph)) - p.b) * 0.05;
        }
        p.vx = (p.vx + (p.tx - p.x) * SPRING) * DAMP;
        p.vy = (p.vy + (p.ty - p.y) * SPRING) * DAMP;
        p.x += p.vx; p.y += p.vy;
      }
    };

    const draw = () => {
      // low-alpha obsidian wash → comet-trail glow
      ctx.globalCompositeOperation = 'source-over';
      ctx.fillStyle = 'rgba(6,7,10,0.30)';
      ctx.fillRect(0, 0, w, h);
      ctx.globalCompositeOperation = 'lighter';
      for (const p of parts) {
        const a = p.ink ? 0.35 + p.b * 0.5 : 0.16 + p.b * 0.4;
        ctx.fillStyle = colour(p, a);
        ctx.beginPath(); ctx.arc(p.x, p.y, p.ink ? p.r + 0.5 : p.r, 0, 6.283); ctx.fill();
      }
      ctx.globalCompositeOperation = 'source-over';
    };

    let raf = 0, first = 0;
    const frame = (now: number) => {
      if (!parts.length) { build(); raf = requestAnimationFrame(frame); return; } // retry seed until a non-zero layout
      if (!first) first = now;
      const t = now - first - 320; // 320ms beat before the quill starts
      if (writing && t >= 0) stepWrite(t);
      updateParticles(now);
      draw();
      raf = requestAnimationFrame(frame);
    };
    raf = requestAnimationFrame(frame);

    return () => { cancelAnimationFrame(raf); ro.disconnect(); };
  }, [reduce]);

  // ── cursor tracking for the kinetic phase ────────────────────────────────────
  useEffect(() => {
    if (reduce) return;
    const el = stageRef.current;
    if (!el) return;
    const onMove = (e: PointerEvent) => {
      const r = el.getBoundingClientRect();
      px.set(((e.clientX - r.left) / r.width) * 2 - 1);
      py.set(((e.clientY - r.top) / r.height) * 2 - 1);
    };
    const onLeave = () => { px.set(0); py.set(0); };
    el.addEventListener('pointermove', onMove);
    el.addEventListener('pointerleave', onLeave);
    return () => { el.removeEventListener('pointermove', onMove); el.removeEventListener('pointerleave', onLeave); };
  }, [reduce, px, py]);

  // ── subtle scroll-written SOAP note (reuses v1's reveal), kept understated ────
  useEffect(() => {
    if (reduce) return;
    const soap = soapRef.current;
    const sl = soapLineRefs.current.filter(Boolean) as HTMLLIElement[];
    if (!soap) return;
    let sraf = 0;
    const onScroll = () => {
      if (sraf) return;
      sraf = requestAnimationFrame(() => {
        sraf = 0;
        const r = soap.getBoundingClientRect();
        const prog = Math.min(Math.max((window.innerHeight - r.top) / (window.innerHeight * 0.6), 0), 1);
        sl.forEach((li, i) => li.style.setProperty('--p', `${Math.min(Math.max(prog * sl.length - i, 0), 1)}`));
      });
    };
    window.addEventListener('scroll', onScroll, { passive: true });
    window.addEventListener('resize', onScroll); // re-evaluate reveal on viewport change
    onScroll();
    return () => { cancelAnimationFrame(sraf); window.removeEventListener('scroll', onScroll); window.removeEventListener('resize', onScroll); };
  }, [reduce]);

  return (
    <section className={`ml-hero v6 ${reduce ? 'reduce' : ''}`} aria-label="Concept 6 — combined: quill, kinetic type, particle ink">
      <div className="v6-glow" aria-hidden />
      <canvas ref={canvasRef} className="v6-canvas" aria-hidden />
      <div className="ml-stage v6-stage" ref={stageRef}>
        <div className="v6-quill" ref={quillRef} aria-hidden>
          <svg viewBox="0 0 120 160" width="104" height="138" fill="none" aria-hidden>
            <defs>
              <linearGradient id="v6f" x1="0.2" y1="0" x2="0.8" y2="1"><stop offset="0" stopColor="#f4d28a" /><stop offset="0.5" stopColor="#e8b85c" /><stop offset="1" stopColor="#9c6f2e" /></linearGradient>
              <linearGradient id="v6n" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stopColor="#e8b85c" /><stop offset="1" stopColor="#3fd8c8" /></linearGradient>
            </defs>
            <path d="M86 8 C40 30 22 70 14 120 C44 104 70 70 96 26 C94 20 90 12 86 8 Z" fill="url(#v6f)" />
            <path d="M14 120 L40 148" stroke="url(#v6n)" strokeWidth="3.4" strokeLinecap="round" />
            <circle cx="41" cy="149" r="3.2" fill="#3fd8c8" /><circle cx="41" cy="149" r="7" fill="#3fd8c8" opacity="0.25" />
          </svg>
        </div>
        <div className="ml-copy v6-copy">
          <p className="ml-eyebrow">Ambient clinical documentation</p>
          <h1 className="font-display ml-title v6-title">
            {HEADLINE.map((l, i) => (
              <span className="ml-line-wrap" key={i}>
                {/* On the writing→kinetic swap the plain span unmounts and this
                    fresh motion.span has no inline --p, falling back to the CSS
                    `.v6-line { --p: 1 }` default → fully revealed (no stale mask). */}
                {kinetic ? (
                  <KineticLine text={l.text} accent={l.accent} px={px} py={py} index={i} />
                ) : (
                  <span
                    ref={(el) => { lineRefs.current[i] = el; }}
                    className={`ml-line v6-line ${l.accent ? 'text-turq' : ''}`}
                  >
                    {l.text}
                  </span>
                )}
              </span>
            ))}
          </h1>
          <HeroCopy />
        </div>
        <ol className="v6-soap font-mono" ref={soapRef} aria-hidden>
          {SOAP.map((l, i) => (
            <li key={l.tag} ref={(el) => { soapLineRefs.current[i] = el; }} className="v6-soap-ln">
              <span className={`v6-soap-tag v6-${l.tag}`}>{l.tag}</span>
              <span className="v6-soap-text">{l.text}</span>
            </li>
          ))}
        </ol>
      </div>
    </section>
  );
}

// One headline line as a cursor-reactive spring (foreground kinetic layer).
function KineticLine({
  text, accent, px, py, index,
}: {
  text: string; accent: boolean;
  px: ReturnType<typeof useMotionValue<number>>; py: ReturnType<typeof useMotionValue<number>>;
  index: number;
}) {
  const depth = 1 + index * 0.5;
  const sx = useSpring(useTransform(px, (v) => v * 22 * depth), { stiffness: 120, damping: 16, mass: 0.6 });
  const sy = useSpring(useTransform(py, (v) => v * 12 * depth), { stiffness: 120, damping: 16, mass: 0.6 });
  const skew = useSpring(useTransform(px, (v) => v * -4 * depth), { stiffness: 90, damping: 14 });
  return (
    <motion.span
      className={`ml-line v6-line ${accent ? 'text-turq' : ''}`}
      style={{ x: sx, y: sy, skewX: skew, display: 'inline-block', willChange: 'transform' }}
    >
      {text}
    </motion.span>
  );
}

export default V6Combined;
