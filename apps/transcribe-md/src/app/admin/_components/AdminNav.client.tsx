'use client';

// ============================================================================
// Top-bar nav for the /admin/* surface
// ----------------------------------------------------------------------------
// The Phase 3 Overview page didn't ship a nav (it was the only admin page).
// Phase 6 adds /admin/users + /admin/usage, so we need a way to move
// between them. Active link gets the slate-900 underline pattern.
//
// Placement: each page.tsx renders this just below its own header.
// Lightweight client component — only `usePathname` makes it client-only.
//
// Phase 2 (Clinician remodel) — Strategy A dual-theme via additive
// `theme` prop. Default `'legacy'` keeps the slate-on-white nav. Pages
// opt in to the Clinician chrome by passing `theme="clinician"`, which
// renders the same shape using the `.qm-cl-tab-row` + `.qm-cl-tab`
// catalog (soft pill tabs in the cream-on-warm-charcoal palette).
// ============================================================================

import Link from 'next/link';
import { usePathname } from 'next/navigation';

const ITEMS = [
  { href: '/admin', label: 'Overview' },
  { href: '/admin/users', label: 'Users' },
  { href: '/admin/usage', label: 'API Usage' },
  { href: '/admin/threats', label: 'Threats' },
  { href: '/admin/hipaa', label: 'HIPAA' },
] as const;

type AdminNavTheme = 'legacy' | 'clinician';

interface AdminNavProps {
  theme?: AdminNavTheme;
}

export default function AdminNav({ theme = 'legacy' }: AdminNavProps) {
  const pathname = usePathname();
  if (theme === 'clinician') {
    return <ClinicianAdminNav pathname={pathname} />;
  }
  return <LegacyAdminNav pathname={pathname} />;
}

function isActive(href: string, pathname: string): boolean {
  // Match exact (/admin) or prefix (/admin/users → matches /admin/users/anything)
  return href === '/admin'
    ? pathname === '/admin'
    : pathname === href || pathname.startsWith(`${href}/`);
}

function LegacyAdminNav({ pathname }: { pathname: string }) {
  return (
    <nav className="border-b border-slate-200 bg-white">
      <div className="mx-auto max-w-[1440px] px-6">
        <ul className="-mb-px flex items-center gap-6">
          {ITEMS.map((item) => {
            const active = isActive(item.href, pathname);
            return (
              <li key={item.href}>
                <Link
                  href={item.href}
                  className={
                    'inline-flex h-10 items-center border-b-2 text-sm font-medium transition-colors ' +
                    (active
                      ? 'border-slate-900 text-slate-900'
                      : 'border-transparent text-slate-500 hover:text-slate-800')
                  }
                >
                  {item.label}
                </Link>
              </li>
            );
          })}
        </ul>
      </div>
    </nav>
  );
}

function ClinicianAdminNav({ pathname }: { pathname: string }) {
  // Solid nav strip across the page with a hairline bottom rule, sitting
  // on cream-card. Tabs reuse the visit-detail Tabs idiom (.qm-cl-tab-row
  // + .qm-cl-tab + .qm-cl-active) so the active state matches the rest
  // of the Clinician surface.
  return (
    <nav
      style={{
        borderBottom: '1px solid var(--line)',
        background: 'var(--cream-card)',
      }}
    >
      <div className="mx-auto max-w-[1440px] px-6">
        <div className="qm-cl-tab-row" style={{ borderBottom: 'none', paddingBottom: 0 }}>
          {ITEMS.map((item) => {
            const active = isActive(item.href, pathname);
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`qm-cl-tab${active ? ' qm-cl-active' : ''}`}
                style={{ textDecoration: 'none' }}
              >
                {item.label}
              </Link>
            );
          })}
        </div>
      </div>
    </nav>
  );
}
