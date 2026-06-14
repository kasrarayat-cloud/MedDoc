'use client';

// SOAP-review concept switcher — mirrors the lab pattern. C1 (Rail/Grammarly) is the SSR'd
// default. Each concept is a different information architecture for the SAME screen, all with
// ONE clear Sign button. Static mockups (synthetic data, no real pipeline).
import { useEffect, useState } from 'react';
import { C1Grammarly } from './C1Grammarly';
import { C2Stepped } from './C2Stepped';
import { C3Drawer } from './C3Drawer';

const CONCEPTS = [
  { v: 1, label: 'Rail', sub: 'Grammarly model' },
  { v: 2, label: 'Stepped', sub: 'one step at a time' },
  { v: 3, label: 'Drawer', sub: 'note-only + drawer' },
];
function clampV(n: number) {
  return n >= 1 && n <= 3 ? n : 1;
}

export function SoapLab() {
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

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.metaKey || e.ctrlKey || e.altKey) return;
      if (e.target instanceof HTMLElement && /INPUT|TEXTAREA/.test(e.target.tagName)) return;
      const n = parseInt(e.key, 10);
      if (n >= 1 && n <= 3) select(n);
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);

  return (
    <main className="sc-root">
      <div className="sc-concept" key={ready ? v : 'ssr'}>
        {v === 1 && <C1Grammarly />}
        {v === 2 && <C2Stepped />}
        {v === 3 && <C3Drawer />}
      </div>

      <nav className="sc-switch" aria-label="SOAP concept switcher">
        <span className="sc-switch-tag" aria-hidden>
          SOAP · CONCEPTS
        </span>
        <div className="sc-switch-btns">
          {CONCEPTS.map((c) => (
            <button
              key={c.v}
              type="button"
              aria-pressed={v === c.v}
              aria-label={`Concept ${c.v}: ${c.label} — ${c.sub}`}
              className={`sc-switch-btn ${v === c.v ? 'active' : ''}`}
              onClick={() => select(c.v)}
              title={`${c.v} — ${c.label}: ${c.sub}`}
            >
              <span className="sc-switch-num">{c.v}</span>
              <span className="sc-switch-label">{c.label}</span>
            </button>
          ))}
        </div>
      </nav>
    </main>
  );
}
