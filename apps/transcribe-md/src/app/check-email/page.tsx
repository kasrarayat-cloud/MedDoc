import type { Metadata } from 'next';

import { AuthShell } from '@/components/ui/auth-shell';
import { CheckEmailResend } from './check-email-resend';

export const metadata: Metadata = { title: 'Check your email' };

interface PageProps {
  searchParams: Promise<{ email?: string | string[] }>;
}

export default async function CheckEmailPage({ searchParams }: PageProps) {
  const sp = await searchParams;
  const rawEmail = Array.isArray(sp.email) ? sp.email[0] : sp.email;
  const email = typeof rawEmail === 'string' ? rawEmail : '';

  return (
    <AuthShell
      eyebrow="One more step"
      title={
        <>
          Check your <em>email</em>
        </>
      }
      subtitle={
        email
          ? `We sent a verification link to ${email}. It expires in 24 hours.`
          : 'We sent a verification link to your email. It expires in 24 hours.'
      }
    >
      <CheckEmailResend email={email} />
    </AuthShell>
  );
}
