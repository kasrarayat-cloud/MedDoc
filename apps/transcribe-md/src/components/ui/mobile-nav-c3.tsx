'use client';

// C3 real mobile bottom-tab nav (Stage 1b). Shown only ≤980px (where the sidebar
// is hidden). Home · Patients · center "+ New visit" · Search (⌘K) · Settings.
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { Ic } from './icon';

function openCmdK() {
  document.dispatchEvent(new KeyboardEvent('keydown', { key: 'k', metaKey: true, ctrlKey: true, bubbles: true }));
}
function isActive(p: string, h: string) {
  if (h === '/dashboard') return p === '/' || p.startsWith('/dashboard');
  return p === h || p.startsWith(`${h}/`);
}

export function MobileNavC3() {
  const p = usePathname() ?? '/';
  return (
    <nav className="qm-c3-mobilenav" aria-label="Primary mobile navigation">
      <Link href="/dashboard" className={`qm-c3-mtab ${isActive(p, '/dashboard') ? 'on' : ''}`} aria-current={isActive(p, '/dashboard') ? 'page' : undefined}>
        <Ic.home width={18} height={18} aria-hidden />
        <span>Home</span>
      </Link>
      <Link href="/patients" className={`qm-c3-mtab ${isActive(p, '/patients') ? 'on' : ''}`} aria-current={isActive(p, '/patients') ? 'page' : undefined}>
        <Ic.users width={18} height={18} aria-hidden />
        <span>Patients</span>
      </Link>
      <Link href="/visits/new" className="qm-c3-mnew" aria-label="New visit">
        <Ic.plus width={20} height={20} aria-hidden />
      </Link>
      <button type="button" className="qm-c3-mtab" onClick={openCmdK} aria-label="Search">
        <Ic.search width={18} height={18} aria-hidden />
        <span>Search</span>
      </button>
      <Link href="/settings" className={`qm-c3-mtab ${isActive(p, '/settings') ? 'on' : ''}`} aria-current={isActive(p, '/settings') ? 'page' : undefined}>
        <Ic.settings width={18} height={18} aria-hidden />
        <span>Settings</span>
      </Link>
    </nav>
  );
}
