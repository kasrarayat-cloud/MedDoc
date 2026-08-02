'use client';

// ============================================================================
// ROUNDS — the one top bar, for every authenticated surface.
// ----------------------------------------------------------------------------
// ⚠️ THIS EXISTS BECAUSE THE APP WAS SPLIT-BRAIN, MEASURED ON PRODUCTION:
//
//   /board      qm-rounds            0 asides   Board · Templates · Settings
//   /patients   qm-c3 qm-lin         1 aside    Home · Patients · Settings
//   /dashboard  qm-c3 qm-lin         1 aside    (same legacy shell)
//   /settings   qm-c3 qm-lin qm-rounds  1 aside (a Rounds host INSIDE the aside)
//
// The board grew its own nav inline because it was the first Rounds screen and
// nothing else had one. `AppFrame` — which wraps every OTHER authenticated
// route, including the Rounds visit stage — forks on `isSkinBeta()` and has no
// Rounds branch at all. So the skin's own stage rendered inside C3 chrome, and
// the brand mark pointed at `/dashboard` everywhere except the board.
//
// One component, used by both, so the nav cannot drift again. The active item is
// derived from the PATH rather than hardcoded — the board's version compared
// `n.label === 'Board'`, which is correct on exactly one route and silently
// wrong on every other route that renders it.
// ============================================================================

import Link from 'next/link';
import { usePathname } from 'next/navigation';

/** Board · Patients · Templates · Settings. `/patients` joined in R1; before
 *  that the route was reachable only from the legacy sidebar, so a doctor on
 *  the board could not get to their patient list at all. */
const NAV = [
  { href: '/board', label: 'Board' },
  { href: '/patients', label: 'Patients' },
  { href: '/settings/note-format', label: 'Templates' },
  { href: '/settings', label: 'Settings' },
] as const;

/** Longest-prefix match, so `/patients/<id>` lights Patients and
 *  `/settings/note-format` lights Templates rather than Settings. A plain
 *  `startsWith` would light BOTH — `/settings/note-format` starts with
 *  `/settings` — which is the substring trap this project has shipped before. */
export function activeNavHref(pathname: string): string | null {
  let best: string | null = null;
  for (const n of NAV) {
    if (pathname === n.href || pathname.startsWith(`${n.href}/`)) {
      if (!best || n.href.length > best.length) best = n.href;
    }
  }
  return best;
}

export function RoundsTopBar({ children }: { children?: React.ReactNode }) {
  const pathname = usePathname() ?? '';
  const active = activeNavHref(pathname);

  return (
    <header className="qm-rounds-topbar" data-testid="rounds-topbar">
      <Link href="/board" className="qm-rounds-topbar-brand">
        <span aria-hidden className="qm-rounds-topbar-mark">
          Q
        </span>
        <span className="qm-rounds-topbar-word">QuillMD</span>
      </Link>

      <nav aria-label="Main" className="qm-rounds-topbar-nav">
        {NAV.map((n) => (
          <Link
            key={n.href}
            href={n.href}
            data-testid={`rounds-nav-${n.label.toLowerCase()}`}
            aria-current={active === n.href ? 'page' : undefined}
            className="qm-rounds-topbar-link"
            data-active={active === n.href ? 'true' : 'false'}
          >
            {n.label}
          </Link>
        ))}
      </nav>

      <div style={{ flex: 1 }} />

      {children}
    </header>
  );
}
