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
// ============================================================================

import Link from 'next/link';
import { usePathname } from 'next/navigation';

const ITEMS = [
  { href: '/admin', label: 'Overview' },
  { href: '/admin/users', label: 'Users' },
  { href: '/admin/usage', label: 'API Usage' },
] as const;

export default function AdminNav() {
  const pathname = usePathname();
  return (
    <nav className="border-b border-slate-200 bg-white">
      <div className="mx-auto max-w-[1440px] px-6">
        <ul className="-mb-px flex items-center gap-6">
          {ITEMS.map((item) => {
            // Match exact (/admin) or prefix (/admin/users → matches /admin/users/anything)
            const active =
              item.href === '/admin'
                ? pathname === '/admin'
                : pathname === item.href || pathname.startsWith(`${item.href}/`);
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
