'use client';

// Structure switcher — mirrors the Motion/Hero lab pattern, 1–5. Each concept is a
// genuinely different PAGE ARCHITECTURE (not a re-skinned hero). S1 (Product) is the SSR'd
// default so the page renders real content without JS. The active theme drives the root
// background so there's no flash when toggling between dark and light concepts.
import { useEffect, useState } from 'react';
import { S1ProductFirst } from './S1ProductFirst';
import { S2Split } from './S2Split';
import { S3Horizontal } from './S3Horizontal';
import { S4Conversation } from './S4Conversation';
import { S5Statement } from './S5Statement';

const CONCEPTS = [
  { v: 1, label: 'Product', sub: 'land in the app' },
  { v: 2, label: 'Split', sub: 'before / after' },
  { v: 3, label: 'Chapters', sub: 'scroll sideways' },
  { v: 4, label: 'Transcript', sub: 'conversation-led' },
  { v: 5, label: 'Statement', sub: 'one line' },
];
const LIGHT = new Set([4]); // S4 reads on a light document; the rest are dark/split
function clampV(n: number) {
  return n >= 1 && n <= 5 ? n : 1;
}

export function StructureLab() {
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

  // keyboard: 1–5 jump straight to a concept (ignore browser modifier shortcuts + fields)
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.metaKey || e.ctrlKey || e.altKey) return;
      if (e.target instanceof HTMLElement && /INPUT|TEXTAREA/.test(e.target.tagName)) return;
      const n = parseInt(e.key, 10);
      if (n >= 1 && n <= 5) select(n);
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);

  const theme = LIGHT.has(v) ? 'st-light' : 'st-dark';

  return (
    <main className={`st-root ${theme}`}>
      <div className="st-concept" key={ready ? v : 'ssr'}>
        {v === 1 && <S1ProductFirst />}
        {v === 2 && <S2Split />}
        {v === 3 && <S3Horizontal />}
        {v === 4 && <S4Conversation />}
        {v === 5 && <S5Statement />}
      </div>

      <nav className="st-switch" aria-label="Structure concept switcher">
        <span className="st-switch-tag font-mono" aria-hidden>
          STRUCTURES
        </span>
        <div className="st-switch-btns">
          {CONCEPTS.map((c) => (
            <button
              key={c.v}
              type="button"
              aria-pressed={v === c.v}
              aria-label={`Concept ${c.v}: ${c.label} — ${c.sub}`}
              className={`st-switch-btn ${v === c.v ? 'active' : ''}`}
              onClick={() => select(c.v)}
              title={`${c.v} — ${c.label}: ${c.sub}`}
            >
              <span className="st-switch-num font-mono">{c.v}</span>
              <span className="st-switch-label">{c.label}</span>
            </button>
          ))}
        </div>
      </nav>
    </main>
  );
}
