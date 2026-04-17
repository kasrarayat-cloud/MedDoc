'use client';

// ============================================================================
// LogoutButton — Reusable sign-out control
// ----------------------------------------------------------------------------
// Wraps next-auth/react's `signOut()`. Accepts optional className/children for
// flexible styling, and an optional `iconOnly` flag for compact sidebar use.
// ============================================================================

import { signOut } from 'next-auth/react';
import { LogOut, Loader2 } from 'lucide-react';
import { useTransition } from 'react';

interface LogoutButtonProps {
  /** Custom className to override default styling */
  className?: string;
  /** If true, render just the icon (for compact sidebars) */
  iconOnly?: boolean;
  /** Optional aria-label override */
  ariaLabel?: string;
}

export default function LogoutButton({
  className,
  iconOnly = false,
  ariaLabel = 'Logout',
}: LogoutButtonProps) {
  const [isPending, startTransition] = useTransition();

  const handleLogout = () => {
    startTransition(async () => {
      await signOut({ callbackUrl: '/login' });
    });
  };

  if (iconOnly) {
    return (
      <button
        type="button"
        onClick={handleLogout}
        disabled={isPending}
        aria-label={ariaLabel}
        className={
          className ??
          'p-2 text-slate-400 hover:text-red-400 hover:bg-red-500/10 rounded-lg transition-colors cursor-pointer disabled:opacity-60 disabled:cursor-not-allowed'
        }
      >
        {isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <LogOut className="w-4 h-4" />}
      </button>
    );
  }

  return (
    <button
      type="button"
      onClick={handleLogout}
      disabled={isPending}
      aria-label={ariaLabel}
      className={
        className ??
        'flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium text-slate-400 hover:text-red-400 hover:bg-red-500/10 transition-colors cursor-pointer disabled:opacity-60 disabled:cursor-not-allowed'
      }
    >
      {isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <LogOut className="w-4 h-4" />}
      <span>{isPending ? 'Signing out...' : 'Logout'}</span>
    </button>
  );
}
