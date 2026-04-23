'use client';

// HANDOFF §2.1 — 64px left rail with icon-only nav. Templates was
// removed from the product roadmap (T-M24 reverted); the rail reflects
// the post-T-M24 nav (Dashboard / Patients / Visits) plus the bottom
// Command + Settings pair.

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import type { ComponentType, SVGProps } from 'react';
import { Ic } from './icon';

type RailItem = {
  id: string;
  icon: ComponentType<SVGProps<SVGSVGElement>>;
  label: string;
  href: string;
};

const ITEMS: readonly RailItem[] = [
  { id: 'home', icon: Ic.home, label: 'Dashboard', href: '/dashboard' },
  { id: 'patients', icon: Ic.users, label: 'Patients', href: '/patients' },
  { id: 'visits', icon: Ic.visits, label: 'Visits', href: '/visits' },
];
const BOTTOM: readonly RailItem[] = [
  { id: 'settings', icon: Ic.settings, label: 'Settings', href: '/settings' },
];

function isActive(pathname: string, href: string): boolean {
  if (href === '/dashboard') {
    return pathname === '/' || pathname.startsWith('/dashboard');
  }
  return pathname === href || pathname.startsWith(`${href}/`);
}

function RailButton({
  item,
  active,
}: {
  item: RailItem;
  active: boolean;
}) {
  const Icon = item.icon;
  return (
    <Link
      href={item.href}
      title={item.label}
      aria-label={item.label}
      aria-current={active ? 'page' : undefined}
      style={{
        width: 40,
        height: 40,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        borderRadius: 10,
        border: `1px solid ${
          active ? 'rgba(139,92,255,0.28)' : 'transparent'
        }`,
        background: active ? 'rgba(139,92,255,0.1)' : 'transparent',
        color: active ? 'var(--fg)' : 'var(--fg-3)',
        cursor: 'pointer',
        transition: 'all .15s',
        position: 'relative',
      }}
    >
      <Icon width={17} height={17} />
      {active && (
        <span
          aria-hidden
          style={{
            position: 'absolute',
            left: -14,
            top: 10,
            bottom: 10,
            width: 2,
            background: 'var(--accent-bright)',
            borderRadius: 2,
          }}
        />
      )}
    </Link>
  );
}

export function IconRail() {
  const pathname = usePathname() ?? '/';
  return (
    <aside
      style={{
        width: 64,
        padding: '16px 12px',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        gap: 6,
        borderRight: '1px solid var(--line)',
        background: 'rgba(7,6,12,0.4)',
        position: 'relative',
        zIndex: 4,
      }}
    >
      {ITEMS.map((it) => (
        <RailButton key={it.id} item={it} active={isActive(pathname, it.href)} />
      ))}
      <div style={{ flex: 1 }} />
      <div
        aria-hidden
        style={{
          width: 24,
          height: 1,
          background: 'var(--line)',
          margin: '6px 0',
        }}
      />
      {BOTTOM.map((it) => (
        <RailButton key={it.id} item={it} active={isActive(pathname, it.href)} />
      ))}
    </aside>
  );
}
