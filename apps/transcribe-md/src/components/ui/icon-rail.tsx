'use client';

// Phase 5 — Linear V1 Faithful sidebar.
// Reference: docs/design-directions-v8-linear/dashboard-v1.html (.sidebar)
//
// 240px left rail on `--color-linear-surface-1`, hairline right border,
// sticky to the top bar. Named rows (icon + label + optional badge),
// not the legacy 64px icon-only rail.
//
// Active state per the mockup:
//   - 3px sage left bar (::before) flush with the row's left edge
//   - sage-tint background
//   - text-1 label, sage-bright icon
//
// Inactive: text-2 label, text-3 icon, hover lifts to row-hover.
//
// `IconRail` keeps its name for back-compat even though the surface is
// no longer icon-only. The `theme` prop is retained in the signature
// for callers like AppFrame that still pass theme="clinician"; both
// values render the same Linear V1 sidebar.

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import type { ComponentType, SVGProps } from 'react';
import { Ic } from './icon';

type IconRailTheme = 'legacy' | 'clinician';

type RailItem = {
  id: string;
  icon: ComponentType<SVGProps<SVGSVGElement>>;
  label: string;
  href: string;
};

const PRIMARY: readonly RailItem[] = [
  { id: 'home', icon: Ic.home, label: 'Dashboard', href: '/dashboard' },
  { id: 'visits', icon: Ic.visits, label: 'Visits', href: '/visits' },
  { id: 'patients', icon: Ic.users, label: 'Patients', href: '/patients' },
];
const SECONDARY: readonly RailItem[] = [
  { id: 'settings', icon: Ic.settings, label: 'Settings', href: '/settings' },
];

function isActive(pathname: string, href: string): boolean {
  if (href === '/dashboard') {
    return pathname === '/' || pathname.startsWith('/dashboard');
  }
  return pathname === href || pathname.startsWith(`${href}/`);
}

interface IconRailProps {
  /** @deprecated kept for back-compat; Linear V1 is single-theme. */
  theme?: IconRailTheme;
}

export function IconRail(_props: IconRailProps = {}) {
  const pathname = usePathname() ?? '/';

  return (
    <aside
      className="qm-lin-sidebar"
      aria-label="Primary navigation"
      style={{
        // The base `.qm-lin-sidebar` defines surface, border, padding,
        // sticky positioning. We add the inner column gap here.
        gap: 14,
      }}
    >
      <nav
        aria-label="Primary"
        style={{
          display: 'flex',
          flexDirection: 'column',
          gap: 1,
        }}
      >
        {PRIMARY.map((it) => (
          <RailRow
            key={it.id}
            item={it}
            active={isActive(pathname, it.href)}
          />
        ))}
      </nav>

      <div style={{ flex: 1 }} />

      <nav
        aria-label="Secondary"
        style={{
          display: 'flex',
          flexDirection: 'column',
          gap: 1,
          paddingTop: 8,
          borderTop: '1px solid var(--color-linear-hairline)',
        }}
      >
        {SECONDARY.map((it) => (
          <RailRow
            key={it.id}
            item={it}
            active={isActive(pathname, it.href)}
          />
        ))}
      </nav>
    </aside>
  );
}

function RailRow({ item, active }: { item: RailItem; active: boolean }) {
  const Icon = item.icon;
  return (
    <Link
      href={item.href}
      aria-current={active ? 'page' : undefined}
      className="qm-tap-44"
      style={{
        position: 'relative',
        display: 'flex',
        alignItems: 'center',
        gap: 8,
        height: 28,
        padding: '0 8px',
        borderRadius: 5,
        fontSize: 13,
        letterSpacing: '-0.005em',
        color: active
          ? 'var(--color-linear-text)'
          : 'var(--color-linear-text-2)',
        background: active
          ? 'var(--color-linear-sage-tint)'
          : 'transparent',
        textDecoration: 'none',
        transition: 'background-color 80ms ease, color 80ms ease',
        userSelect: 'none',
      }}
      onMouseEnter={(e) => {
        if (!active) {
          (e.currentTarget as HTMLAnchorElement).style.background =
            'var(--color-linear-row-hover)';
          (e.currentTarget as HTMLAnchorElement).style.color =
            'var(--color-linear-text)';
        }
      }}
      onMouseLeave={(e) => {
        if (!active) {
          (e.currentTarget as HTMLAnchorElement).style.background =
            'transparent';
          (e.currentTarget as HTMLAnchorElement).style.color =
            'var(--color-linear-text-2)';
        }
      }}
    >
      {active && (
        <span
          aria-hidden
          style={{
            position: 'absolute',
            left: -8,
            top: 6,
            bottom: 6,
            width: 3,
            background: 'var(--color-linear-sage)',
            borderRadius: '0 2px 2px 0',
          }}
        />
      )}
      <span
        aria-hidden
        style={{
          width: 14,
          height: 14,
          flex: '0 0 14px',
          display: 'grid',
          placeItems: 'center',
          color: active
            ? 'var(--color-linear-sage-bright)'
            : 'var(--color-linear-text-3)',
        }}
      >
        <Icon width={14} height={14} />
      </span>
      <span style={{ flex: 1 }}>{item.label}</span>
    </Link>
  );
}
