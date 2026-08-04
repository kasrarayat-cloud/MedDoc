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

import { RoundsAccountMenu } from './account-menu';

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

/**
 * ⚠️ `userName` IS A PROP, NOT A CHILD, AND THAT IS THE WHOLE FIX.
 *
 * Before 2026-08-04 both callers rendered the clinician's name themselves —
 * `app-frame-rounds.tsx` as `<span className="qm-rounds-topbar-who">`,
 * `board-chrome.tsx` as an inline-styled span with the same three
 * declarations spelled out again. Two hand-maintained copies of one piece of
 * anatomy, and NEITHER of them had a sign-out in it.
 *
 * AGENTS.md § "Shared components — diff the callers BEFORE you replace them"
 * is explicit about the cure: *put the behaviour where it cannot be forgotten
 * — on the component.* So the account menu lives here, every present and
 * future mount inherits it, and the mount count is asserted by
 * `gate-rounds-account-menu` rather than kept correct by hand. R3.4 lost a
 * round to exactly the per-caller version of this mistake.
 */
export function RoundsTopBar({
  userName,
  children,
}: {
  userName?: string;
  children?: React.ReactNode;
}) {
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

      {/* LAST in the bar, after whatever instruments the caller supplied.
          Rendered only when a name is known — an "Account menu for undefined"
          is worse than none, and the guard test asserts BOTH directions so a
          future caller that forgets the prop fails loudly rather than
          silently dropping the only way out of the product. */}
      {userName ? <RoundsAccountMenu userName={userName} /> : null}
    </header>
  );
}
