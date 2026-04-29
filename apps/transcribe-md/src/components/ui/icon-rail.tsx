'use client';

// HANDOFF §2.1 — 64px left rail with icon-only nav. Templates was
// removed from the product roadmap (T-M24 reverted); the rail reflects
// the post-T-M24 nav (Dashboard / Patients / Visits) plus the bottom
// Command + Settings pair.
//
// Phase 2 (Clinician remodel) — Strategy A dual-theme via additive
// `theme` prop. Default `'legacy'` keeps the existing dark rail with
// the violet active accent. `theme="clinician"` swaps to a cream-2
// `.qm-cl-sidebar` surface using `.qm-cl-nav-item` rows with the
// sage active state (ref: visit-detail.html compact sidebar).

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

interface IconRailProps {
  theme?: IconRailTheme;
}

export function IconRail({ theme = 'legacy' }: IconRailProps = {}) {
  if (theme === 'clinician') {
    return <ClinicianIconRail />;
  }
  return <LegacyIconRail />;
}

function LegacyRailButton({
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

function LegacyIconRail() {
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
        <LegacyRailButton
          key={it.id}
          item={it}
          active={isActive(pathname, it.href)}
        />
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
        <LegacyRailButton
          key={it.id}
          item={it}
          active={isActive(pathname, it.href)}
        />
      ))}
    </aside>
  );
}

// ── Clinician branch ────────────────────────────────────────────
// Mockup ref: docs/design-directions-v3/clinician/visit-detail.html
// (compact 64px aside). Cream-2 surface + hairline right border via
// `.qm-cl-sidebar`. Each nav row uses `.qm-cl-nav-item` (icon-only
// icon-square padding via `style="padding:10px"`) with `.qm-cl-active`
// on the matched route. Icon glyphs inherit `.qm-cl-nav-icon` color
// transitions.
function ClinicianRailButton({
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
      className={
        active ? 'qm-cl-nav-item qm-cl-active' : 'qm-cl-nav-item'
      }
      style={{
        padding: 10,
        textDecoration: 'none',
        // Override the dot pseudo-element on the icon-only rail —
        // we keep the active styling but suppress the ::after dot
        // since there's no label to align it against.
      }}
    >
      <Icon className="qm-cl-nav-icon" width={18} height={18} />
    </Link>
  );
}

function ClinicianIconRail() {
  const pathname = usePathname() ?? '/';
  return (
    <aside
      className="qm-cl-sidebar"
      style={{
        width: 64,
        padding: '20px 10px',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        gap: 4,
        flex: '0 0 auto',
      }}
    >
      {ITEMS.map((it) => (
        <ClinicianRailButton
          key={it.id}
          item={it}
          active={isActive(pathname, it.href)}
        />
      ))}
      <div style={{ flex: 1 }} />
      <div
        aria-hidden
        style={{
          width: 24,
          height: 1,
          background: 'var(--line)',
          margin: '8px 0',
        }}
      />
      {BOTTOM.map((it) => (
        <ClinicianRailButton
          key={it.id}
          item={it}
          active={isActive(pathname, it.href)}
        />
      ))}
    </aside>
  );
}
