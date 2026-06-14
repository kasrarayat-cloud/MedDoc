'use client';

// C3 minimal top bar (Stage 1b). Reuses the 48px `.qm-lin-chrome` so every sticky
// offset / §8.2 overflow contract the existing surfaces rely on stays valid — we
// only quiet the CONTENT: a breadcrumb on desktop; the wordmark returns here on
// mobile (where the sidebar is hidden). No ⌘K pill, no "+ New visit" (those live
// in the sidebar / mobile bottom nav).
import Link from 'next/link';
import { usePathname } from 'next/navigation';

const ITEMS = [
  { label: 'Home', href: '/dashboard' },
  { label: 'Patients', href: '/patients' },
  { label: 'Visits', href: '/visits' },
  { label: 'Settings', href: '/settings' },
];

function crumb(p: string): string | null {
  const m = ITEMS.find(
    (it) => p === it.href || p.startsWith(`${it.href}/`) || (it.href === '/dashboard' && (p === '/' || p.startsWith('/dashboard'))),
  );
  return m?.label ?? null;
}

export function TopNavC3() {
  const pathname = usePathname() ?? '/';
  const c = crumb(pathname);
  return (
    <header className="qm-lin-chrome qm-c3-chrome">
      <Link
        href="/dashboard"
        aria-label="QuillMD"
        className="qm-c3-chrome-brand qm-tap-44"
        style={{ alignItems: 'center', gap: 8, color: 'var(--color-linear-text)', textDecoration: 'none', fontWeight: 600, fontSize: 13 }}
      >
        <span aria-hidden style={{ width: 18, height: 18, borderRadius: 5, background: 'linear-gradient(135deg, var(--color-linear-sage) 0%, var(--color-linear-sage-deep) 100%)', display: 'grid', placeItems: 'center', color: '#0c1410', fontSize: 10, fontWeight: 700 }}>Q</span>
        QuillMD
      </Link>
      {c && (
        <span style={{ fontSize: 13, color: 'var(--color-linear-text-2)', letterSpacing: '-0.005em' }}>{c}</span>
      )}
      <div style={{ flex: 1 }} />
    </header>
  );
}
