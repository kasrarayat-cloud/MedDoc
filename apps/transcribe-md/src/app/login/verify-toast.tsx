'use client';

// ============================================================================
// Surfaces /login?verify=<reason> flags from the /api/auth/verify-email
// redirect. Reasons:
//   ok                  — email verified; sign in as normal
//   invalid-or-expired  — bad/used/expired token
//   error               — DB update failed
// ============================================================================

import { useEffect, useRef } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { toast } from 'sonner';

export function VerifyToast() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const reason = searchParams.get('verify');
  const fired = useRef(false);

  useEffect(() => {
    if (!reason || fired.current) return;
    fired.current = true;

    switch (reason) {
      case 'ok':
        toast.success('Email verified', {
          description: 'Sign in to continue.',
        });
        break;
      case 'invalid-or-expired':
        toast.error('That verification link is invalid or expired', {
          description: 'Request a new one from Sign in, then click "resend".',
        });
        break;
      case 'error':
        toast.error('Could not verify email', {
          description: 'Please try again, or contact support.',
        });
        break;
      default:
        return;
    }

    const url = new URL(window.location.href);
    url.searchParams.delete('verify');
    router.replace(url.pathname + url.search, { scroll: false });
  }, [reason, router]);

  return null;
}
