'use client';

// Hero switcher — mirrors the Motion Lab pattern. 1–4 toggle via ?v= + keyboard digits.
// H1 (Obsidian) is the SSR'd default so the page renders real content without JS. All
// four concepts are CSS-driven (no heavy libs), so each is statically renderable and the
// switch is instant. The active theme (light/dark) drives the root background so there's
// no flash when toggling between the dark and light heroes.
import { useEffect, useState } from 'react';
import { H1Obsidian } from './H1Obsidian';
import { H2Clinical } from './H2Clinical';
import { H3Editorial } from './H3Editorial';
import { H4Statement } from './H4Statement';

const CONCEPTS = [
  { v: 1, label: 'Obsidian', sub: 'dark · cinematic' },
  { v: 2, label: 'Clinical', sub: 'light · sage' },
  { v: 3, label: 'Editorial', sub: 'typographic' },
  { v: 4, label: 'Statement', sub: 'bold type' },
];
const LIGHT = new Set([2, 3]);
function clampV(n: number) {
  return n >= 1 && n <= 4 ? n : 1;
}

export function HeroLab() {
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

  // keyboard: 1–4 jump straight to a concept
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      // don't hijack browser shortcuts (Cmd/Ctrl/Alt+1..4 = tab switching)
      if (e.metaKey || e.ctrlKey || e.altKey) return;
      if (e.target instanceof HTMLElement && /INPUT|TEXTAREA/.test(e.target.tagName)) return;
      const n = parseInt(e.key, 10);
      if (n >= 1 && n <= 4) select(n);
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);

  const theme = LIGHT.has(v) ? 'hl-light' : 'hl-dark';

  return (
    <main className={`hl-root ${theme}`}>
      <div className="hl-concept" key={ready ? v : 'ssr'}>
        {v === 1 && <H1Obsidian />}
        {v === 2 && <H2Clinical />}
        {v === 3 && <H3Editorial />}
        {v === 4 && <H4Statement />}
      </div>

      <nav className="hl-switch" aria-label="Hero concept switcher">
        <span className="hl-switch-tag font-mono" aria-hidden>
          HEROES
        </span>
        <div className="hl-switch-btns">
          {CONCEPTS.map((c) => (
            <button
              key={c.v}
              type="button"
              aria-pressed={v === c.v}
              aria-label={`Concept ${c.v}: ${c.label} — ${c.sub}`}
              className={`hl-switch-btn ${v === c.v ? 'active' : ''}`}
              onClick={() => select(c.v)}
              title={`${c.v} — ${c.label}: ${c.sub}`}
            >
              <span className="hl-switch-num font-mono">{c.v}</span>
              <span className="hl-switch-label">{c.label}</span>
            </button>
          ))}
        </div>
      </nav>
    </main>
  );
}
