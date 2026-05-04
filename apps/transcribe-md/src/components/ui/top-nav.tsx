'use client';

// Phase 5 — Linear V1 Faithful top bar.
// Reference: docs/design-directions-v8-linear/dashboard-v1.html (.topbar)
//
// 48px sticky strip on the dark canvas. Slot order from the mockup:
//   brand mark | breadcrumb | spacer | ⌘K command pill | + New visit | avatar
//
// The brand mark is a sage gradient square with a "Q" — kept in line
// with dashboard-v1's `.brand-mark`. Breadcrumbs read straight from
// the route (workspace + current section). The Cmd+K trigger fires the
// existing CommandPalette via a synthesized Meta+K keydown, matching
// the dashboard mockup's prominent kbd-chip pattern. The "New visit"
// CTA is the sage primary button. The user avatar opens a Radix
// dropdown for Settings / Sign-out.
//
// `theme` prop remains for back-compat with unmigrated callers; both
// values render the single Linear V1 chrome.

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { signOut } from 'next-auth/react';
import * as DropdownMenu from '@radix-ui/react-dropdown-menu';
import { Ic } from './icon';
import { Avatar } from './avatar';

type TopNavTheme = 'legacy' | 'clinician';

type NavItem = { id: string; label: string; href: string };

const ITEMS: readonly NavItem[] = [
  { id: 'dashboard', label: 'Dashboard', href: '/dashboard' },
  { id: 'patients', label: 'Patients', href: '/patients' },
  { id: 'visits', label: 'Visits', href: '/visits' },
];

function isActive(pathname: string, href: string): boolean {
  if (href === '/dashboard') {
    return pathname === '/' || pathname.startsWith('/dashboard');
  }
  return pathname === href || pathname.startsWith(`${href}/`);
}

function deriveCrumbs(
  pathname: string,
): { label: string; href: string; active: boolean }[] {
  const match = ITEMS.find((it) => isActive(pathname, it.href));
  if (!match) return [];
  return [{ label: match.label, href: match.href, active: true }];
}

function openCmdK() {
  // The existing <CommandPalette> binds Meta+K via its keyboard hook.
  // Synthesising the keydown triggers the same toggle without needing
  // a separate imperative API. TODO(phase5-stage3): replace with a
  // direct store opener once the palette is re-wired.
  const ev = new KeyboardEvent('keydown', {
    key: 'k',
    metaKey: true,
    ctrlKey: true,
    bubbles: true,
  });
  document.dispatchEvent(ev);
}

interface TopNavProps {
  userName?: string;
  userEmail?: string;
  /** @deprecated kept for back-compat; Linear V1 is single-theme. */
  theme?: TopNavTheme;
}

export function TopNav({
  userName = 'Doctor',
  userEmail,
}: TopNavProps) {
  const pathname = usePathname() ?? '/';
  const crumbs = deriveCrumbs(pathname);

  return (
    <header className="qm-lin-chrome">
      <Link
        href="/dashboard"
        aria-label="QuillMD — Dashboard"
        className="qm-tap-44"
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: 8,
          color: 'var(--color-linear-text)',
          textDecoration: 'none',
          fontWeight: 600,
          fontSize: 13,
          letterSpacing: '-0.01em',
        }}
      >
        <span
          aria-hidden
          style={{
            width: 18,
            height: 18,
            borderRadius: 5,
            background:
              'linear-gradient(135deg, var(--color-linear-sage) 0%, var(--color-linear-sage-deep) 100%)',
            display: 'grid',
            placeItems: 'center',
            color: '#0c1410',
            fontSize: 10,
            fontWeight: 700,
            boxShadow: 'inset 0 0 0 1px rgba(255,255,255,0.06)',
            fontFamily: 'var(--font-sans)',
          }}
        >
          Q
        </span>
        <span>QuillMD</span>
      </Link>

      {crumbs.length > 0 && (
        <>
          <span
            aria-hidden
            style={{
              color: 'var(--color-linear-text-3)',
              fontSize: 12,
            }}
          >
            /
          </span>
          {crumbs.map((c) => (
            <span
              key={c.href}
              style={{
                fontSize: 13,
                color: c.active
                  ? 'var(--color-linear-text)'
                  : 'var(--color-linear-text-2)',
                letterSpacing: '-0.005em',
              }}
            >
              {c.label}
            </span>
          ))}
        </>
      )}

      <div style={{ flex: 1 }} />

      <button
        type="button"
        onClick={openCmdK}
        aria-label="Open command palette"
        className="qm-lin-cmdk"
        style={{ minWidth: 220 }}
      >
        <Ic.search width={13} height={13} aria-hidden />
        <span style={{ flex: 1, textAlign: 'left' }}>
          Search patients, visits, codes…
        </span>
        <span
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: 3,
          }}
        >
          <kbd>⌘</kbd>
          <kbd>K</kbd>
        </span>
      </button>

      <Link
        href="/visits/new"
        className="qm-lin-btn-primary"
        style={{ textDecoration: 'none', height: 28 }}
      >
        <Ic.plus width={13} height={13} aria-hidden />
        New visit
      </Link>

      <DropdownMenu.Root>
        <DropdownMenu.Trigger asChild>
          <button
            type="button"
            aria-label={`Account menu for ${userName}`}
            className="qm-tap-44"
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 6,
              padding: '0 4px 0 8px',
              marginLeft: 2,
              background: 'transparent',
              border: 'none',
              cursor: 'pointer',
              color: 'var(--color-linear-text-3)',
              height: 32,
            }}
          >
            <Avatar name={userName} size={24} />
            <Ic.chevDown width={12} height={12} aria-hidden />
          </button>
        </DropdownMenu.Trigger>

        <DropdownMenu.Portal>
          <DropdownMenu.Content
            sideOffset={8}
            align="end"
            style={{
              minWidth: 220,
              background: 'var(--color-linear-surface-1)',
              border: '1px solid var(--color-linear-border)',
              borderRadius: 8,
              padding: 6,
              boxShadow: '0 12px 32px rgba(0,0,0,0.45)',
              zIndex: 50,
            }}
          >
            <div
              style={{
                padding: '8px 10px 8px',
                borderBottom: '1px solid var(--color-linear-hairline)',
                marginBottom: 4,
              }}
            >
              <div
                style={{
                  fontFamily: 'var(--font-sans)',
                  fontSize: 13,
                  color: 'var(--color-linear-text)',
                  fontWeight: 500,
                }}
              >
                {userName}
              </div>
              {userEmail && (
                <div
                  style={{
                    fontFamily: 'var(--font-mono)',
                    fontSize: 11,
                    color: 'var(--color-linear-text-3)',
                    marginTop: 2,
                  }}
                >
                  {userEmail}
                </div>
              )}
            </div>

            <DropdownMenu.Item asChild>
              <Link
                href="/settings"
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 8,
                  padding: '7px 10px',
                  borderRadius: 5,
                  fontSize: 12.5,
                  color: 'var(--color-linear-text-2)',
                  textDecoration: 'none',
                  outline: 'none',
                }}
              >
                <Ic.settings width={13} height={13} />
                Settings
              </Link>
            </DropdownMenu.Item>

            <DropdownMenu.Item asChild>
              <button
                type="button"
                onClick={() => signOut({ callbackUrl: '/login' })}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 8,
                  padding: '7px 10px',
                  borderRadius: 5,
                  fontSize: 12.5,
                  color: 'var(--color-linear-coral)',
                  background: 'transparent',
                  border: 'none',
                  cursor: 'pointer',
                  width: '100%',
                  textAlign: 'left',
                }}
              >
                <Ic.lock width={13} height={13} />
                Sign out
              </button>
            </DropdownMenu.Item>
          </DropdownMenu.Content>
        </DropdownMenu.Portal>
      </DropdownMenu.Root>
    </header>
  );
}
