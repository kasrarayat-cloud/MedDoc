'use client';

// SOAP-review v2 concept switcher (?v=1-2). Both concepts solve the SAME problem — the note/panel
// side-by-side collision — by keeping the note FULL-WIDTH and never placing secondary content
// beside it. V1 reads top-to-bottom; V2 is a badged full-width tab workspace. Static mockups,
// synthetic data, not wired to the real pipeline.
import { useEffect, useState } from 'react';
import { V1ReadDown } from './V1ReadDown';
import { V2Tabbed } from './V2Tabbed';

const CONCEPTS = [
  { v: 1, label: 'Read down', sub: 'one column, summary → note → resolve → sign' },
  { v: 2, label: 'Tabbed', sub: 'badged full-width tabs + persistent sign bar' },
];
const MAX = CONCEPTS.length;
function clampV(n: number) {
  return n >= 1 && n <= MAX ? n : 1;
}

export function SoapLabV2() {
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
      if (n >= 1 && n <= MAX) select(n);
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);

  return (
    <main className="sc-root">
      <div className="sc-concept" key={ready ? v : 'ssr'}>
        {v === 1 && <V1ReadDown />}
        {v === 2 && <V2Tabbed />}
      </div>

      <nav className="sc-switch" aria-label="SOAP v2 concept switcher">
        <span className="sc-switch-tag" aria-hidden>
          SOAP · V2
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
