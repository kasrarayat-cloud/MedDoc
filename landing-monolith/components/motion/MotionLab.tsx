'use client';

import { useEffect, useState } from 'react';
import dynamic from 'next/dynamic';
import { V1Quill } from './concepts/V1Quill';
import { V3Cinematic } from './concepts/V3Cinematic';
import { Headline } from './shared';

// Heavy / animation-lib concepts are code-split so their bundles (Three.js,
// the particle canvas, framer-motion) only load when selected. v1 stays the
// eager, SSR'd, no-JS-readable default. A lightweight content fallback shows
// the real headline + copy while a chunk streams in.
const Loading = () => (
  <section className="ml-hero ml-loading" aria-busy="true">
    <div className="ml-stage">
      <div className="ml-copy">
        <p className="ml-eyebrow">Ambient clinical documentation</p>
        <Headline />
      </div>
    </div>
  </section>
);
const V2Monolith = dynamic(() => import('./concepts/V2Monolith'), { ssr: false, loading: Loading });
const V4Kinetic = dynamic(() => import('./concepts/V4Kinetic'), { ssr: false, loading: Loading });
const V5Particle = dynamic(() => import('./concepts/V5Particle'), { ssr: false, loading: Loading });

const CONCEPTS = [
  { v: 1, label: 'Quill', sub: 'ink + reveal' },
  { v: 2, label: 'Monolith', sub: 'WebGL 3D' },
  { v: 3, label: 'Cinematic', sub: 'scroll film' },
  { v: 4, label: 'Kinetic', sub: 'live type' },
  { v: 5, label: 'Particles', sub: 'generative' },
];

function clampV(n: number) { return n >= 1 && n <= 5 ? n : 1; }

export function MotionLab() {
  // default to v1 (the SSR'd, no-JS-readable concept); hydrate to the ?v= choice
  const [v, setV] = useState(1);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    const p = new URLSearchParams(window.location.search);
    setV(clampV(parseInt(p.get('v') || '1', 10)));
    setReady(true);
  }, []);

  const select = (n: number) => {
    setV(n);
    const url = new URL(window.location.href);
    url.searchParams.set('v', String(n));
    window.history.replaceState({}, '', url);
  };

  // keyboard: 1–5 jump straight to a concept
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLElement && /INPUT|TEXTAREA/.test(e.target.tagName)) return;
      const n = parseInt(e.key, 10);
      if (n >= 1 && n <= 5) select(n);
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);

  return (
    <main className="ml-root">
      <div className="ml-concept" key={ready ? v : 'ssr'}>
        {v === 1 && <V1Quill />}
        {v === 2 && <V2Monolith />}
        {v === 3 && <V3Cinematic />}
        {v === 4 && <V4Kinetic />}
        {v === 5 && <V5Particle />}
      </div>

      <nav className="ml-switch" aria-label="Motion concept switcher">
        <span className="ml-switch-tag font-mono" aria-hidden>MOTION LAB</span>
        <div className="ml-switch-btns">
          {CONCEPTS.map((c) => (
            <button
              key={c.v}
              type="button"
              aria-pressed={v === c.v}
              aria-label={`Concept ${c.v}: ${c.label} — ${c.sub}`}
              className={`ml-switch-btn ${v === c.v ? 'active' : ''}`}
              onClick={() => select(c.v)}
              title={`${c.v} — ${c.label}: ${c.sub}`}
            >
              <span className="ml-switch-num font-mono">{c.v}</span>
              <span className="ml-switch-label">{c.label}</span>
            </button>
          ))}
        </div>
      </nav>
    </main>
  );
}
