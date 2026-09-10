'use client';

// ============================================================================
// Top-bar nav for the /admin/* surface
// ----------------------------------------------------------------------------
// Secondary nav strip below the main TopNav. Moves the operator between
// Overview, Users, API Usage, Threats, and HIPAA. Active link is rendered
// as a sage underline tab in the Linear V1 dark canvas.
//
// Placement: each page.tsx renders this just below its own header.
// Lightweight client component — only `usePathname` makes it client-only.
//
// Phase 5 (Linear V1 Faithful) — Phase 4's `theme` prop has been retired
// because every surface now renders against the same dark canvas. The
// prop is preserved as an optional no-op for caller-site compatibility.
// ============================================================================

import Link from 'next/link';
import { usePathname } from 'next/navigation';

const ITEMS = [
  { href: '/admin', label: 'Overview' },
  { href: '/admin/users', label: 'Users' },
  { href: '/admin/usage', label: 'API Usage' },
  { href: '/admin/threats', label: 'Threats' },
  { href: '/admin/hipaa', label: 'HIPAA' },
  // Console port (#310 step 3): the audit trail had an API and no page, and
  // the queue dashboard had a page and no link.
  { href: '/admin/audit', label: 'Audit' },
  { href: '/admin/queues', label: 'Queues' },
] as const;

interface AdminNavProps {
  /**
   * Retained for caller-site compatibility from Phase 2's dual-theme
   * Strategy A. In Phase 5 every admin surface uses the Linear V1 dark
   * chrome; the prop is accepted but ignored.
   */
  theme?: string;
}

export default function AdminNav(_props: AdminNavProps = {}) {
  const pathname = usePathname();
  return <LinearAdminNav pathname={pathname} />;
}

function isActive(href: string, pathname: string): boolean {
  // Match exact (/admin) or prefix (/admin/users → matches /admin/users/anything)
  return href === '/admin'
    ? pathname === '/admin'
    : pathname === href || pathname.startsWith(`${href}/`);
}

function LinearAdminNav({ pathname }: { pathname: string }) {
  // Linear V1 secondary nav strip — sage underline on active tab,
  // mono-cap labels match admin-v1.html's tabbar idiom.
  return (
    <nav className="border-b border-linear-border bg-linear-surface-1">
      <div className="mx-auto max-w-[1440px] px-6">
        <ul className="-mb-px flex items-center gap-1">
          {ITEMS.map((item) => {
            const active = isActive(item.href, pathname);
            return (
              <li key={item.href}>
                <Link
                  href={item.href}
                  className={
                    'inline-flex h-10 items-center border-b-2 px-3 text-[13px] font-medium transition-colors ' +
                    (active
                      ? 'border-linear-sage text-linear-text'
                      : 'border-transparent text-linear-text-3 hover:text-linear-text-2')
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
