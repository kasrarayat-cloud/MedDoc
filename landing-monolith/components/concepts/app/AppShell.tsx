'use client';

// Shared app chrome for the concept screens (dashboard + record), so they read as ONE app and as
// the same family as the C3 SOAP review. Fixes the inventory's chrome problems: ONE left nav (no
// double nav, no loud ⌘K — search is a quiet affordance), a single clear "+ New visit" primary,
// and a real mobile nav (bottom tab bar). Static mockup — nav links walk the flow, nothing calls
// the real pipeline.
import Link from 'next/link';
import type { ReactNode } from 'react';
import { DOCTOR, STATUS_LABEL } from './data';
import type { Status } from './data';

// minimal line icons (stroke = currentColor) — calmer + more premium than glyphs
// decorative-by-default: every icon is aria-hidden (icon-only controls carry aria-label on the button)
const stroke = { 'aria-hidden': true, fill: 'none', stroke: 'currentColor', strokeWidth: 1.6, strokeLinecap: 'round', strokeLinejoin: 'round' } as const;
const Ico = {
  home: () => (<svg width="18" height="18" viewBox="0 0 24 24" {...stroke}><path d="M3 10.5 12 3l9 7.5" /><path d="M5 9.5V20h14V9.5" /></svg>),
  patients: () => (<svg width="18" height="18" viewBox="0 0 24 24" {...stroke}><circle cx="9" cy="8" r="3" /><path d="M2.5 20a6.5 6.5 0 0 1 13 0" /><path d="M16 5.4a3 3 0 0 1 0 5.7" /><path d="M18.5 20a6.5 6.5 0 0 0-3-5.4" /></svg>),
  search: () => (<svg width="17" height="17" viewBox="0 0 24 24" {...stroke}><circle cx="11" cy="11" r="7" /><path d="m21 21-4.3-4.3" /></svg>),
  plus: () => (<svg width="20" height="20" viewBox="0 0 24 24" {...stroke}><path d="M12 5v14M5 12h14" /></svg>),
  settings: () => (<svg width="18" height="18" viewBox="0 0 24 24" {...stroke}><path d="M4 7h7" /><path d="M15 7h5" /><circle cx="13" cy="7" r="2" /><path d="M4 12h3" /><path d="M11 12h9" /><circle cx="9" cy="12" r="2" /><path d="M4 17h9" /><path d="M17 17h3" /><circle cx="15" cy="17" r="2" /></svg>),
};

export function StatusPill({ status }: { status: Status }) {
  return (
    <span className={`ax-status ax-status-${status}`}>
      <span className="ax-status-dot" aria-hidden />
      {STATUS_LABEL[status]}
    </span>
  );
}

const NAV = [
  { key: 'home', label: 'Home', href: '/concepts/dashboard', icon: Ico.home },
  { key: 'patients', label: 'Patients', href: '#', icon: Ico.patients },
  { key: 'settings', label: 'Settings', href: '#', icon: Ico.settings },
] as const;

export function AppShell({ active, children }: { active: 'home' | 'patients' | 'settings'; children: ReactNode }) {
  return (
    <div className="ax-root ax-app">
      {/* desktop: one left nav rail */}
      <aside className="ax-nav" aria-label="Sidebar">
        <div className="ax-nav-top">
          <Link href="/concepts/dashboard" className="ax-brand">
            <span className="ax-brand-mark" aria-hidden>◆</span> QuillMD
          </Link>
          <Link href="/concepts/record" className="ax-new">
            <Ico.plus /> New visit
          </Link>
          <nav className="ax-nav-links" aria-label="Primary">
            {NAV.map((item) => {
              const I = item.icon;
              return (
                <Link key={item.key} href={item.href} className={`ax-nav-link ${active === item.key ? 'on' : ''}`} aria-current={active === item.key ? 'page' : undefined}>
                  <I /> {item.label}
                </Link>
              );
            })}
          </nav>
        </div>
        <div className="ax-nav-bottom">
          <button className="ax-search" type="button">
            <Ico.search /> <span>Search</span> <kbd className="ax-kbd">⌘K</kbd>
          </button>
          <div className="ax-me">
            <span className="ax-me-av" aria-hidden>DS</span>
            <span className="ax-me-name">{DOCTOR.name}</span>
          </div>
        </div>
      </aside>

      {/* mobile: top bar */}
      <header className="ax-mtop">
        <Link href="/concepts/dashboard" className="ax-brand">
          <span className="ax-brand-mark" aria-hidden>◆</span> QuillMD
        </Link>
        <button className="ax-micon" type="button" aria-label="Search">
          <Ico.search />
        </button>
      </header>

      <main className="ax-content">{children}</main>

      {/* mobile: real bottom tab bar with a center create action */}
      <nav className="ax-mbottom" aria-label="Primary mobile navigation">
        <Link href="/concepts/dashboard" className={`ax-mtab ${active === 'home' ? 'on' : ''}`} aria-current={active === 'home' ? 'page' : undefined}>
          <Ico.home /> <span>Home</span>
        </Link>
        <Link href="#" className="ax-mtab">
          <Ico.patients /> <span>Patients</span>
        </Link>
        <Link href="/concepts/record" className="ax-mnew" aria-label="New visit">
          <Ico.plus />
        </Link>
        <button className="ax-mtab" type="button">
          <Ico.search /> <span>Search</span>
        </button>
        <Link href="#" className={`ax-mtab ${active === 'settings' ? 'on' : ''}`} aria-current={active === 'settings' ? 'page' : undefined}>
          <Ico.settings /> <span>Settings</span>
        </Link>
      </nav>
    </div>
  );
}
