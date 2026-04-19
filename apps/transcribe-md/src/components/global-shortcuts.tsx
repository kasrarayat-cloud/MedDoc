'use client';

import { useRouter, usePathname } from 'next/navigation';
import { useShortcuts } from '@/lib/shortcuts';

interface GlobalShortcutsProps {
  authed: boolean;
}

/**
 * Page-agnostic keyboard shortcuts. Cmd+K is owned by <CommandPalette>
 * so this component intentionally doesn't register it.
 *
 *   N → /visits/new  (authed only, but allowed from any authed page)
 *   D → /dashboard
 *   S → /settings
 *   / → focus a visible search input if one exists — T-M3 doesn't add a
 *       page-level search yet, so "/" silently no-ops if nothing matches,
 *       which is preferable to a visible flash on an unused binding.
 */
export function GlobalShortcuts({ authed }: GlobalShortcutsProps) {
  const router = useRouter();
  const pathname = usePathname();

  useShortcuts(
    authed
      ? [
          {
            key: 'n',
            onFire: () => {
              if (pathname !== '/visits/new') router.push('/visits/new');
            },
          },
          {
            key: 'd',
            onFire: () => {
              if (pathname !== '/dashboard') router.push('/dashboard');
            },
          },
          {
            key: 's',
            onFire: () => {
              if (pathname !== '/settings') router.push('/settings');
            },
          },
          {
            key: '/',
            onFire: () => {
              const input = document.querySelector<HTMLInputElement>(
                'input[data-global-search], input[type="search"]'
              );
              if (input) input.focus();
            },
          },
        ]
      : []
  );

  return null;
}
