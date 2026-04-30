'use client';

// HANDOFF §2.1 — 56px sticky top chrome. Logo + primary nav (Dashboard /
// Patients / Visits — Templates removed per post-T-M24 scope), search
// trigger that opens ⌘K, violet "+ New visit" CTA, and avatar dropdown.
// Active state is derived from usePathname(); each item is a real <Link>
// so middle-click / cmd-click work without a custom handler.
//
// Phase 2 (Clinician remodel) — Strategy A dual-theme via additive
// `theme` prop. Default `'legacy'` keeps the existing dark-glass top
// chrome byte-for-byte. `theme="clinician"` swaps to a cream-w-blur
// `.qm-cl-topbar` surface with a Source Serif 4 wordmark and quiet
// nav pills, paired with the cream sidebar that AppFrame mounts in
// the Clinician branch.

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { signOut } from 'next-auth/react';
import * as DropdownMenu from '@radix-ui/react-dropdown-menu';
import { Ic } from './icon';
import { QuillLogo } from './quill-logo';
import { WordMark } from './word-mark';
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

function openCmdK() {
  // The existing <CommandPalette> binds Meta+K via its keyboard hook.
  // Synthesising the keydown triggers the same toggle without needing
  // a separate imperative API — Gate 13 will replace this with a real
  // store-based opener when the palette is re-ported.
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
  theme?: TopNavTheme;
}

export function TopNav({
  userName = 'Doctor',
  userEmail,
  theme = 'legacy',
}: TopNavProps) {
  if (theme === 'clinician') {
    return <ClinicianTopNav userName={userName} userEmail={userEmail} />;
  }
  return <LegacyTopNav userName={userName} userEmail={userEmail} />;
}

function LegacyTopNav({
  userName = 'Doctor',
  userEmail,
}: {
  userName?: string;
  userEmail?: string;
}) {
  const pathname = usePathname() ?? '/';
  return (
    <header
      style={{
        height: 56,
        padding: '0 20px',
        display: 'flex',
        alignItems: 'center',
        gap: 20,
        borderBottom: '1px solid var(--line)',
        background:
          'linear-gradient(180deg, rgba(12,10,22,0.72), rgba(7,6,12,0.48))',
        backdropFilter: 'blur(14px)',
        position: 'relative',
        zIndex: 5,
        flex: '0 0 auto',
      }}
    >
      <Link
        href="/dashboard"
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 8,
          color: 'inherit',
          textDecoration: 'none',
        }}
        aria-label="QuillMD — Dashboard"
      >
        <QuillLogo size={22} />
        <WordMark size={15} />
      </Link>

      <nav
        aria-label="Primary"
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 2,
          marginLeft: 12,
        }}
      >
        {ITEMS.map((it) => {
          const active = isActive(pathname, it.href);
          return (
            <Link
              key={it.id}
              href={it.href}
              className="qm-btn qm-btn-sm"
              aria-current={active ? 'page' : undefined}
              style={{
                color: active ? 'var(--fg)' : 'var(--fg-3)',
                background: active
                  ? 'rgba(139,92,255,0.08)'
                  : 'transparent',
                border: `1px solid ${
                  active ? 'rgba(139,92,255,0.25)' : 'transparent'
                }`,
                textDecoration: 'none',
              }}
            >
              {it.label}
            </Link>
          );
        })}
      </nav>

      <div style={{ flex: 1 }} />

      <button
        type="button"
        onClick={openCmdK}
        className="qm-btn qm-btn-ghost"
        aria-label="Open command palette"
        style={{
          gap: 10,
          padding: '7px 10px 7px 12px',
          minWidth: 260,
          justifyContent: 'space-between',
        }}
      >
        <span
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            color: 'var(--fg-3)',
          }}
        >
          <Ic.search width={14} height={14} />
          <span style={{ fontSize: 12.5 }}>
            Search patients, visits, codes…
          </span>
        </span>
        <span style={{ display: 'flex', gap: 3 }}>
          <span className="qm-kbd">⌘</span>
          <span className="qm-kbd">K</span>
        </span>
      </button>

      <Link
        href="/visits/new"
        className="qm-btn qm-btn-primary"
        style={{ textDecoration: 'none' }}
      >
        <Ic.plus width={14} height={14} />
        New visit
      </Link>

      <DropdownMenu.Root>
        <DropdownMenu.Trigger asChild>
          <button
            type="button"
            aria-label={`Account menu for ${userName}`}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              paddingLeft: 8,
              marginLeft: 0,
              borderLeft: '1px solid var(--line)',
              background: 'transparent',
              border: 'none',
              borderLeftWidth: 1,
              borderLeftStyle: 'solid',
              borderLeftColor: 'var(--line)',
              cursor: 'pointer',
              color: 'var(--fg-3)',
              height: 40,
            }}
          >
            <Avatar name={userName} size={30} />
            <Ic.chevDown width={14} height={14} />
          </button>
        </DropdownMenu.Trigger>

        <DropdownMenu.Portal>
          <DropdownMenu.Content
            sideOffset={8}
            align="end"
            style={{
              minWidth: 220,
              background: 'var(--bg-2)',
              border: '1px solid var(--line)',
              borderRadius: 12,
              padding: 6,
              boxShadow: 'var(--shadow-2)',
              zIndex: 50,
            }}
          >
            <div
              style={{
                padding: '10px 12px 8px',
                borderBottom: '1px solid var(--line-soft)',
                marginBottom: 4,
              }}
            >
              <div
                style={{
                  fontFamily: 'var(--sans)',
                  fontSize: 13,
                  color: 'var(--fg)',
                  fontWeight: 500,
                }}
              >
                {userName}
              </div>
              {userEmail && (
                <div
                  style={{
                    fontFamily: 'var(--mono)',
                    fontSize: 11,
                    color: 'var(--fg-3)',
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
                className="qm-btn qm-btn-sm"
                style={{
                  width: '100%',
                  justifyContent: 'flex-start',
                  color: 'var(--fg-2)',
                  textDecoration: 'none',
                  borderRadius: 8,
                }}
              >
                <Ic.settings width={14} height={14} />
                Settings
              </Link>
            </DropdownMenu.Item>

            <DropdownMenu.Item asChild>
              <button
                type="button"
                onClick={() => signOut({ callbackUrl: '/login' })}
                className="qm-btn qm-btn-sm"
                style={{
                  width: '100%',
                  justifyContent: 'flex-start',
                  color: 'var(--coral)',
                  borderRadius: 8,
                }}
              >
                <Ic.lock width={14} height={14} />
                Sign out
              </button>
            </DropdownMenu.Item>
          </DropdownMenu.Content>
        </DropdownMenu.Portal>
      </DropdownMenu.Root>
    </header>
  );
}

// ── Clinician branch ────────────────────────────────────────────
// Mockup ref: docs/design-directions-v3/clinician/dashboard.html (top-bar)
// + visit-detail.html (compact top-bar). Cream-w-blur sticky strip,
// hairline bottom border (.qm-cl-topbar). Wordmark on the left in
// Source Serif 4 (.qm-cl-wordmark), nav pills mid, search trigger
// + primary CTA + avatar on the right. No theatrical motion (CL-5).
function ClinicianTopNav({
  userName = 'Doctor',
  userEmail,
}: {
  userName?: string;
  userEmail?: string;
}) {
  const pathname = usePathname() ?? '/';
  return (
    <header
      className="qm-cl-topbar"
      style={{
        height: 64,
        padding: '0 24px',
        display: 'flex',
        alignItems: 'center',
        gap: 24,
        position: 'sticky',
        top: 0,
        zIndex: 30,
        flex: '0 0 auto',
      }}
    >
      <Link
        href="/dashboard"
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 10,
          color: 'inherit',
          textDecoration: 'none',
        }}
        aria-label="QuillMD — Dashboard"
      >
        <svg
          width={22}
          height={22}
          viewBox="0 0 24 24"
          fill="none"
          aria-hidden
        >
          <path
            d="M4 19c4 -1 7 -3.5 9.5 -7c1.5 -2 3 -3.5 5 -4.5c1.2 -0.6 2 -0.4 1.6 0.8c-0.7 2 -2.4 4.4 -4.6 6.4c-2.6 2.4 -5.6 4 -8.5 4.7c-1 0.2 -2.4 0.3 -3 -0.4z"
            stroke="#7AA68C"
            strokeWidth={1.5}
            fill="rgba(122,166,140,0.14)"
          />
        </svg>
        <span className="qm-cl-wordmark">Quill</span>
      </Link>

      <nav
        aria-label="Primary"
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 4,
          marginLeft: 8,
        }}
      >
        {ITEMS.map((it) => {
          const active = isActive(pathname, it.href);
          return (
            <Link
              key={it.id}
              href={it.href}
              aria-current={active ? 'page' : undefined}
              className={
                active ? 'qm-cl-btn qm-cl-btn-soft' : 'qm-cl-btn qm-cl-btn-ghost'
              }
              style={{
                fontSize: 13.5,
                padding: '8px 14px',
                textDecoration: 'none',
              }}
            >
              {it.label}
            </Link>
          );
        })}
      </nav>

      <div style={{ flex: 1 }} />

      <button
        type="button"
        onClick={openCmdK}
        aria-label="Open command palette"
        className="qm-cl-btn qm-cl-btn-soft"
        style={{
          padding: '8px 12px 8px 14px',
          minWidth: 280,
          justifyContent: 'space-between',
          fontSize: 13,
          color: 'var(--ink-3)',
        }}
      >
        <span
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 8,
          }}
        >
          <Ic.search width={14} height={14} />
          <span>Search patients, visits, codes…</span>
        </span>
        <span
          style={{
            display: 'flex',
            gap: 3,
            fontFamily: 'var(--mono)',
            fontSize: 11,
            color: 'var(--ink-3)',
          }}
        >
          <span>⌘</span>
          <span>K</span>
        </span>
      </button>

      <Link
        href="/visits/new"
        className="qm-cl-btn qm-cl-btn-primary"
        style={{ textDecoration: 'none', fontSize: 13.5 }}
      >
        <Ic.plus width={14} height={14} />
        New visit
      </Link>

      <DropdownMenu.Root>
        <DropdownMenu.Trigger asChild>
          <button
            type="button"
            aria-label={`Account menu for ${userName}`}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              paddingLeft: 12,
              marginLeft: 4,
              borderLeft: '1px solid var(--line)',
              background: 'transparent',
              border: 'none',
              borderLeftWidth: 1,
              borderLeftStyle: 'solid',
              borderLeftColor: 'var(--line)',
              cursor: 'pointer',
              color: 'var(--ink-3)',
              height: 44,
            }}
          >
            <Avatar theme="clinician" name={userName} size={36} />
            <Ic.chevDown width={14} height={14} />
          </button>
        </DropdownMenu.Trigger>

        <DropdownMenu.Portal>
          <DropdownMenu.Content
            sideOffset={8}
            align="end"
            style={{
              minWidth: 220,
              background: 'var(--cream-card)',
              border: '1px solid var(--line)',
              borderRadius: 12,
              padding: 6,
              boxShadow: 'var(--shadow-card)',
              zIndex: 50,
            }}
          >
            <div
              style={{
                padding: '10px 12px 8px',
                borderBottom: '1px solid var(--line)',
                marginBottom: 4,
              }}
            >
              <div
                style={{
                  fontFamily: 'var(--sans)',
                  fontSize: 13,
                  color: 'var(--ink)',
                  fontWeight: 500,
                }}
              >
                {userName}
              </div>
              {userEmail && (
                <div
                  style={{
                    fontFamily: 'var(--mono)',
                    fontSize: 11,
                    color: 'var(--ink-3)',
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
                className="qm-cl-btn qm-cl-btn-ghost"
                style={{
                  width: '100%',
                  justifyContent: 'flex-start',
                  textDecoration: 'none',
                  borderRadius: 8,
                  fontSize: 13,
                  padding: '8px 12px',
                }}
              >
                <Ic.settings width={14} height={14} />
                Settings
              </Link>
            </DropdownMenu.Item>

            <DropdownMenu.Item asChild>
              <button
                type="button"
                onClick={() => signOut({ callbackUrl: '/login' })}
                className="qm-cl-btn qm-cl-btn-ghost"
                style={{
                  width: '100%',
                  justifyContent: 'flex-start',
                  color: 'var(--coral-deep)',
                  borderRadius: 8,
                  fontSize: 13,
                  padding: '8px 12px',
                }}
              >
                <Ic.lock width={14} height={14} />
                Sign out
              </button>
            </DropdownMenu.Item>
          </DropdownMenu.Content>
        </DropdownMenu.Portal>
      </DropdownMenu.Root>
    </header>
  );
}
