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

/** Board · Patients · Settings. `/patients` joined in R1; before that the
 *  route was reachable only from the legacy sidebar, so a doctor on the board
 *  could not get to their patient list at all.
 *
 *  ⚠️ R2 — TEMPLATES FOLDED INTO SETTINGS, AND IT WAS ALREADY THERE.
 *  The item pointed at `/settings/note-format`: a fourth top-level noun for a
 *  destination that is a SECTION of the third. A doctor reading the bar saw two
 *  peers and reached one page. Note format is reached from Settings now, and
 *  `/templates` — a deep link that has never had a route and 404'd — forwards
 *  there (`config/rounds-redirects.ts`).
 *
 *  This subtracts a NAME, not a capability: the note-format screen, its URL and
 *  every existing link into it are untouched. */
const NAV = [
  { href: '/board', label: 'Board' },
  { href: '/patients', label: 'Patients' },
  { href: '/settings', label: 'Settings' },
] as const;

/** Longest-prefix match, so `/patients/<id>` lights Patients.
 *
 *  ⚠️ IT IS STILL LONGEST-PREFIX AFTER R2, AND DELETING THAT WOULD BE A SILENT
 *  REGRESSION. With `Templates` gone the two-candidate case it was written for
 *  (`/settings/note-format` matching both `/settings` and the Templates entry)
 *  no longer arises from NAV — so a plain `startsWith` would pass every test
 *  here today. It stays because the property it enforces is "the most specific
 *  entry wins", which is what makes `/settings/note-format` light **Settings**
 *  rather than nothing, and what will hold the next time a nested entry is
 *  added. A guard that only looks unnecessary is not the same as one that is. */
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
