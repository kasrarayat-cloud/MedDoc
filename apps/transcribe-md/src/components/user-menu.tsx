'use client';

import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { Settings, LogOut } from 'lucide-react';
import * as DropdownMenu from '@radix-ui/react-dropdown-menu';

import { cn } from '@/lib/cn';
import { signOutAction } from '@/actions/session';

interface UserMenuProps {
  name: string | null;
  email: string;
}

/** Avatar circle + dropdown (Settings / Sign out). The name's first
 *  letter drives the avatar; the dropdown uses Radix primitives so
 *  keyboard nav + focus trap behave correctly out of the box. */
export function UserMenu({ name, email }: UserMenuProps) {
  const router = useRouter();
  const initial = (name ?? email).trim().charAt(0).toUpperCase() || '?';

  return (
    <DropdownMenu.Root>
      <DropdownMenu.Trigger asChild>
        <button
          type="button"
          aria-label="Open user menu"
          className={cn(
            'relative inline-flex h-9 w-9 items-center justify-center rounded-full',
            'text-[14px] font-semibold text-white',
            'bg-[linear-gradient(135deg,#7C3AED_0%,#A855F7_100%)]',
            'shadow-[0_0_0_1px_rgba(167,139,250,0.3)]',
            'transition-shadow duration-300 ease-[cubic-bezier(0.4,0,0.2,1)]',
            'hover:shadow-[0_0_0_1px_rgba(167,139,250,0.6),0_8px_24px_-8px_rgba(124,58,237,0.7)]',
            'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500 focus-visible:ring-offset-2 focus-visible:ring-offset-bg-base'
          )}
        >
          {initial}
        </button>
      </DropdownMenu.Trigger>

      <DropdownMenu.Portal>
        <DropdownMenu.Content
          sideOffset={8}
          align="end"
          className={cn(
            'z-[100] min-w-[220px] overflow-hidden rounded-lg',
            'border border-border-default bg-bg-surface-1 backdrop-blur',
            'shadow-[0_16px_48px_-16px_rgba(0,0,0,0.7)]'
            // Removed tailwindcss-animate classes (animate-in/fade-in-0/
            // zoom-in-95) — plugin not installed, caused invisible
            // content on production builds in T-M2.
          )}
        >
          <div className="border-b border-border-subtle px-3 py-2.5">
            <div className="truncate text-[13px] font-medium text-text-primary">
              {name ?? 'Unnamed'}
            </div>
            <div className="truncate text-[11px] text-text-muted">{email}</div>
          </div>

          <DropdownMenu.Item asChild>
            <Link
              href="/settings"
              className={cn(
                'flex items-center gap-2 px-3 py-2 text-[13px]',
                'text-text-secondary outline-none',
                'data-[highlighted]:bg-bg-surface-2 data-[highlighted]:text-text-primary',
                'cursor-pointer'
              )}
            >
              <Settings className="h-3.5 w-3.5" aria-hidden />
              Settings
            </Link>
          </DropdownMenu.Item>

          <DropdownMenu.Separator className="h-px bg-border-subtle" />

          <DropdownMenu.Item
            onSelect={async (e) => {
              e.preventDefault();
              await signOutAction();
              router.push('/login');
              router.refresh();
            }}
            className={cn(
              'flex items-center gap-2 px-3 py-2 text-[13px]',
              'text-text-secondary outline-none',
              'data-[highlighted]:bg-bg-surface-2 data-[highlighted]:text-text-primary',
              'cursor-pointer'
            )}
          >
            <LogOut className="h-3.5 w-3.5" aria-hidden />
            Sign out
          </DropdownMenu.Item>
        </DropdownMenu.Content>
      </DropdownMenu.Portal>
    </DropdownMenu.Root>
  );
}
