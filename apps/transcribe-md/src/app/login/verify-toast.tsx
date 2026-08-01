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
        // ⚠️ COPY REGISTER — "actions keep their names end-to-end". The old
        // string told the doctor to click "resend", and NO control in the
        // product carries that name: the two real ones are "Resend the
        // verification email" (login-form.tsx) and "Resend verification link"
        // (check-email-resend.tsx).
        //
        // ⚠️ AND THE FIRST ATTEMPT AT THIS SENT THEM SOMEWHERE THAT CANNOT
        // WORK, which is worth recording because it read as the safer option.
        // It said "Open /check-email and choose 'Resend verification link'".
        // But `/api/auth/verify-email` redirects here as
        // `/login?verify=invalid-or-expired` and carries NO email, and
        // `/check-email` derives its address solely from `?email=` — so a bare
        // visit leaves `canSend` false, the button renders DISABLED, and the
        // page offers no field to type an address into. A dead end, on an
        // account-recovery path, shipping FLAG-OFF (this component has no skin
        // fork, so only a revert would remove it).
        //
        // The path that works is the one the old copy meant: sign in with the
        // correct password and the login form itself offers the resend. That
        // affordance requires `isEmailDeliveryEnabled()` — but so does sending
        // the verification link in the first place (`actions/auth.ts` gates
        // both on it), so in every state where THIS toast can fire, that
        // button is there. Name it exactly, and name the step that reveals it.
        toast.error('That verification link is invalid or expired', {
          description:
            'Sign in with your password, then choose "Resend the verification email".',
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
