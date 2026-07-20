'use client';

// C3 calm-skin sidebar (Stage 1b, flag-gated). Reuses `.qm-lin-sidebar` (so the
// grid cell + sticky + responsive behavior is inherited verbatim) but consolidates
// to ONE nav: wordmark · the single "+ New visit" primary · Home/Patients/Settings ·
// a QUIET ⌘K search · account. No second nav, no loud 220px command pill.
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import * as DropdownMenu from '@radix-ui/react-dropdown-menu';
import { toast } from 'sonner';
import type { ComponentType, SVGProps } from 'react';
import { signOutAction } from '@/actions/session';
import { Ic } from './icon';
import { Avatar } from './avatar';

// Documented synthetic-keydown contract (see top-nav.tsx) — opens the existing
// CommandPalette. Kept quiet (a small search row, not a prominent pill).
function openCmdK() {
  document.dispatchEvent(new KeyboardEvent('keydown', { key: 'k', metaKey: true, ctrlKey: true, bubbles: true }));
}

type Item = { id: string; icon: ComponentType<SVGProps<SVGSVGElement>>; label: string; href: string };
const NAV: readonly Item[] = [
  { id: 'home', icon: Ic.home, label: 'Home', href: '/dashboard' },
  { id: 'patients', icon: Ic.users, label: 'Patients', href: '/patients' },
  { id: 'settings', icon: Ic.settings, label: 'Settings', href: '/settings' },
];
function isActive(p: string, href: string) {
  if (href === '/dashboard') return p === '/' || p.startsWith('/dashboard');
  return p === href || p.startsWith(`${href}/`);
}

export function SidebarC3({ userName, userEmail }: { userName: string; userEmail?: string }) {
  const pathname = usePathname() ?? '/';
  const router = useRouter();
  const handleSignOut = async () => {
    try {
      const result = await signOutAction();
      if (!result.ok) {
        toast.error('Sign-out was not completed', {
          description: result.message,
        });
        return;
      }
      router.push('/login');
      router.refresh();
    } catch {
      toast.error('Sign-out was not completed', {
        description: 'Please check your connection and try again.',
      });
    }
  };
  return (
    <aside className="qm-lin-sidebar qm-c3-sidebar" aria-label="Primary navigation" style={{ gap: 10 }}>
      <Link
        href="/dashboard"
        aria-label="QuillMD — Home"
        className="qm-tap-44"
        style={{ display: 'inline-flex', alignItems: 'center', gap: 8, color: 'var(--color-linear-text)', textDecoration: 'none', fontWeight: 600, fontSize: 14, padding: '2px 4px' }}
      >
        <span aria-hidden style={{ width: 18, height: 18, borderRadius: 5, background: 'linear-gradient(135deg, var(--color-linear-sage) 0%, var(--color-linear-sage-deep) 100%)', display: 'grid', placeItems: 'center', color: '#0c1410', fontSize: 10, fontWeight: 700 }}>Q</span>
        QuillMD
      </Link>

      <Link href="/visits/new" className="qm-lin-btn-primary qm-tap-44" style={{ textDecoration: 'none', justifyContent: 'center', height: 32, marginTop: 2 }}>
        <Ic.plus width={13} height={13} aria-hidden /> New visit
      </Link>

      <nav aria-label="Primary" style={{ display: 'flex', flexDirection: 'column', gap: 1, marginTop: 4 }}>
        {NAV.map((it) => (
          <Row key={it.id} item={it} active={isActive(pathname, it.href)} />
        ))}
      </nav>

      <div style={{ flex: 1 }} />

      <button
        type="button"
        onClick={openCmdK}
        className="qm-tap-44"
        aria-label="Search — open command palette"
        style={{ display: 'flex', alignItems: 'center', gap: 8, height: 30, padding: '0 8px', borderRadius: 6, border: '1px solid var(--color-linear-border)', background: 'var(--color-linear-surface-2)', color: 'var(--color-linear-text-3)', font: 'inherit', fontSize: 12.5, cursor: 'pointer' }}
      >
        <Ic.search width={13} height={13} aria-hidden />
        <span style={{ flex: 1, textAlign: 'left' }}>Search</span>
        <kbd style={{ fontFamily: 'var(--font-mono)', fontSize: 10.5, color: 'var(--color-linear-text-2)', background: 'rgba(255,255,255,0.04)', padding: '1px 4px', borderRadius: 3 }}>⌘K</kbd>
      </button>

      <DropdownMenu.Root>
        <DropdownMenu.Trigger asChild>
          <button type="button" aria-label={`Account menu for ${userName}`} className="qm-tap-44" style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '4px 6px', background: 'transparent', border: 'none', cursor: 'pointer', color: 'var(--color-linear-text-2)' }}>
            <Avatar name={userName} size={24} />
            <span style={{ flex: 1, textAlign: 'left', fontSize: 12.5, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{userName}</span>
            <Ic.chevDown width={12} height={12} aria-hidden />
          </button>
        </DropdownMenu.Trigger>
        <DropdownMenu.Portal>
          <DropdownMenu.Content sideOffset={8} align="start" side="top" style={{ minWidth: 200, background: 'var(--color-linear-surface-1)', border: '1px solid var(--color-linear-border)', borderRadius: 8, padding: 6, boxShadow: '0 12px 32px rgba(0,0,0,0.45)', zIndex: 50 }}>
            {userEmail && (
              <div style={{ padding: '8px 10px', borderBottom: '1px solid var(--color-linear-hairline)', marginBottom: 4, fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--color-linear-text-3)' }}>{userEmail}</div>
            )}
            <DropdownMenu.Item asChild>
              <Link href="/settings" style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '7px 10px', borderRadius: 5, fontSize: 12.5, color: 'var(--color-linear-text-2)', textDecoration: 'none', outline: 'none' }}>
                <Ic.settings width={13} height={13} /> Settings
              </Link>
            </DropdownMenu.Item>
            <DropdownMenu.Item asChild>
              <button type="button" onClick={handleSignOut} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '7px 10px', borderRadius: 5, fontSize: 12.5, color: 'var(--color-linear-coral)', background: 'transparent', border: 'none', cursor: 'pointer', width: '100%', textAlign: 'left' }}>
                <Ic.lock width={13} height={13} /> Sign out
              </button>
            </DropdownMenu.Item>
          </DropdownMenu.Content>
        </DropdownMenu.Portal>
      </DropdownMenu.Root>
    </aside>
  );
}

function Row({ item, active }: { item: Item; active: boolean }) {
  const Icon = item.icon;
  return (
    <Link
      href={item.href}
      aria-current={active ? 'page' : undefined}
      className="qm-tap-44"
      style={{ position: 'relative', display: 'flex', alignItems: 'center', gap: 8, height: 30, padding: '0 8px', borderRadius: 6, fontSize: 13, color: active ? 'var(--color-linear-text)' : 'var(--color-linear-text-2)', background: active ? 'var(--color-linear-sage-tint)' : 'transparent', textDecoration: 'none' }}
    >
      {active && <span aria-hidden style={{ position: 'absolute', left: -8, top: 6, bottom: 6, width: 3, background: 'var(--color-linear-sage)', borderRadius: '0 2px 2px 0' }} />}
      <span aria-hidden style={{ width: 14, height: 14, display: 'grid', placeItems: 'center', color: active ? 'var(--color-linear-sage-bright)' : 'var(--color-linear-text-3)' }}>
        <Icon width={14} height={14} />
      </span>
      <span style={{ flex: 1 }}>{item.label}</span>
    </Link>
  );
}
