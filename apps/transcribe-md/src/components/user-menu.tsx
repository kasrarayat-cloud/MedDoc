'use client';

// Phase 5 — Linear V1 Faithful user menu.
// Reference: docs/design-directions-v8-linear/dashboard-v1.html (.avatar-chip)
//
// Avatar trigger → Radix dropdown with Settings + Sign out. The Linear
// V1 chrome already lives in TopNav; this component is only used by the
// admin overview client surface. Keep the keyboard nav + focus trap
// from Radix; rebuild the trigger + content surfaces on the dark canvas
// with hairline borders and sage hover.

import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { Settings, LogOut } from 'lucide-react';
import * as DropdownMenu from '@radix-ui/react-dropdown-menu';

import { toast } from 'sonner';

import { signOutAction } from '@/actions/session';

interface UserMenuProps {
  name: string | null;
  email: string;
}

export function UserMenu({ name, email }: UserMenuProps) {
  const router = useRouter();
  const initial = (name ?? email).trim().charAt(0).toUpperCase() || '?';

  return (
    <DropdownMenu.Root>
      <DropdownMenu.Trigger asChild>
        <button
          type="button"
          aria-label="Open user menu"
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            justifyContent: 'center',
            width: 26,
            height: 26,
            borderRadius: 6,
            background:
              'linear-gradient(135deg, #3a4a52 0%, #2a3036 100%)',
            color: '#dde6ec',
            fontSize: 11,
            fontWeight: 600,
            letterSpacing: '0.02em',
            border: '1px solid var(--color-linear-hairline-strong)',
            cursor: 'pointer',
            transition: 'border-color 100ms ease',
          }}
          onMouseEnter={(e) => {
            (e.currentTarget as HTMLButtonElement).style.borderColor =
              'var(--color-linear-border-strong)';
          }}
          onMouseLeave={(e) => {
            (e.currentTarget as HTMLButtonElement).style.borderColor =
              'var(--color-linear-hairline-strong)';
          }}
        >
          {initial}
        </button>
      </DropdownMenu.Trigger>

      <DropdownMenu.Portal>
        <DropdownMenu.Content
          sideOffset={8}
          align="end"
          style={{
            zIndex: 100,
            minWidth: 220,
            overflow: 'hidden',
            borderRadius: 8,
            border: '1px solid var(--color-linear-border-strong)',
            background: 'var(--color-linear-surface-1)',
            boxShadow:
              '0 16px 48px rgba(0,0,0,0.5), 0 0 0 1px rgba(255,255,255,0.03)',
            color: 'var(--color-linear-text)',
          }}
          className="data-[state=open]:animate-in data-[state=open]:fade-in-0 data-[state=open]:zoom-in-95 data-[state=open]:slide-in-from-top-2"
        >
          <div
            style={{
              padding: '10px 12px',
              borderBottom: '1px solid var(--color-linear-hairline)',
            }}
          >
            <div
              style={{
                fontSize: 13,
                fontWeight: 500,
                color: 'var(--color-linear-text)',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap',
              }}
            >
              {name ?? 'Unnamed'}
            </div>
            <div
              style={{
                marginTop: 2,
                fontSize: 11,
                color: 'var(--color-linear-text-3)',
                fontFamily: 'var(--font-mono)',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap',
              }}
            >
              {email}
            </div>
          </div>

          <DropdownMenu.Item asChild>
            <Link
              href="/settings"
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 8,
                padding: '8px 12px',
                fontSize: 13,
                color: 'var(--color-linear-text-2)',
                textDecoration: 'none',
                outline: 'none',
                cursor: 'pointer',
              }}
              className="data-[highlighted]:!bg-linear-row-hover data-[highlighted]:!text-linear-text"
            >
              <Settings className="h-3.5 w-3.5" aria-hidden />
              Settings
            </Link>
          </DropdownMenu.Item>

          <DropdownMenu.Separator
            style={{
              height: 1,
              background: 'var(--color-linear-hairline)',
            }}
          />

          <DropdownMenu.Item
            onSelect={async (e) => {
              e.preventDefault();
              // ⚠️ #182(2)/(3) — the result is rendered. See command-palette.tsx
              // for why both of these were missed: the door list was authored,
              // not enumerated.
              const result = await signOutAction();
              if (!result.ok) {
                toast.error('Sign-out failed', { description: result.reason });
                return;
              }
              router.push('/login');
              router.refresh();
            }}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              padding: '8px 12px',
              fontSize: 13,
              color: 'var(--color-linear-text-2)',
              outline: 'none',
              cursor: 'pointer',
            }}
            className="data-[highlighted]:!bg-linear-row-hover data-[highlighted]:!text-linear-text"
          >
            <LogOut className="h-3.5 w-3.5" aria-hidden />
            Sign out
          </DropdownMenu.Item>
        </DropdownMenu.Content>
      </DropdownMenu.Portal>
    </DropdownMenu.Root>
  );
}
