'use client';

// ============================================================================
// "Show archived" toggle for the dashboard All Visits tab
// (T-M17.3 Phase 4 Commit 9)
// ----------------------------------------------------------------------------
// Writes state to ?archived=1 in the URL so a bookmark / shared link
// preserves the archived view. Preserves the existing ?tab=visits
// query param on every navigation so the toggle doesn't kick the
// doctor back to the Patients tab.
// ============================================================================

import { useTransition } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { Archive } from 'lucide-react';
import { cn } from '@/lib/cn';

export function ShowArchivedToggle() {
  const router = useRouter();
  const params = useSearchParams();
  const [pending, startTransition] = useTransition();

  const on = params.get('archived') === '1';

  function toggle() {
    const next = new URLSearchParams(params);
    if (on) {
      next.delete('archived');
    } else {
      next.set('archived', '1');
    }
    // Preserve ?tab=visits if already present; always add if missing
    // — the toggle only renders on the All Visits tab, so defaulting
    // there is safe.
    if (next.get('tab') !== 'visits') {
      next.set('tab', 'visits');
    }
    const qs = next.toString();
    startTransition(() => {
      router.push(qs ? `/dashboard?${qs}` : '/dashboard');
    });
  }

  return (
    <button
      type="button"
      onClick={toggle}
      disabled={pending}
      aria-pressed={on}
      className={cn(
        'inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-[12px] font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500 focus-visible:ring-offset-2 focus-visible:ring-offset-bg-base',
        on
          ? 'border-violet-500/60 bg-violet-500/15 text-violet-200'
          : 'border-border-default bg-bg-surface-1/60 text-text-tertiary hover:text-text-secondary hover:border-border-emphasis',
        pending && 'opacity-60'
      )}
    >
      <Archive className="h-3 w-3" aria-hidden />
      {on ? 'Showing archived' : 'Show archived'}
    </button>
  );
}
