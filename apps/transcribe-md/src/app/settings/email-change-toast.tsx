'use client';

// ============================================================================
// Surfaces /settings?emailChange=<reason> flags as a one-shot toast.
// Reasons emitted by /api/auth/confirm-email:
//   ok                  — success
//   invalid-or-expired  — bad/used/expired token
//   conflict            — new email was taken while the link aged
//   error               — DB update failed (rare)
// ============================================================================

import { useEffect, useRef } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { toast } from 'sonner';

export function EmailChangeToast() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const reason = searchParams.get('emailChange');
  const fired = useRef(false);

  useEffect(() => {
    if (!reason || fired.current) return;
    fired.current = true;

    switch (reason) {
      case 'ok':
        toast.success('Email updated', {
          description: 'Next time you sign in, use your new address.',
        });
        break;
      case 'invalid-or-expired':
        toast.error('That link is invalid or expired', {
          description: 'Request a new one from Settings.',
        });
        break;
      case 'conflict':
        toast.error("That address isn't available", {
          description: 'Another account started using it while the link aged.',
        });
        break;
      case 'error':
        toast.error('Could not update email', {
          description: 'Please try again, or contact support.',
        });
        break;
      default:
        return;
    }

    // Clean the URL so a refresh doesn't retrigger.
    const url = new URL(window.location.href);
    url.searchParams.delete('emailChange');
    router.replace(url.pathname + url.search, { scroll: false });
  }, [reason, router]);

  return null;
}
