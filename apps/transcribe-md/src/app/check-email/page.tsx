import type { Metadata } from 'next';

import { AuthShell } from '@/components/ui/auth-shell';
import { CheckEmailResend } from './check-email-resend';

export const metadata: Metadata = { title: 'Check your email' };

export default function CheckEmailPage() {
  return (
    <AuthShell
      eyebrow="One more step"
      title={
        <>
          Check your <em>email</em>
        </>
      }
      subtitle="If the address can receive a verification link, it should arrive shortly and expire in 24 hours."
    >
      <CheckEmailResend />
    </AuthShell>
  );
}
