import type { Metadata } from 'next';
import { redirect } from 'next/navigation';

import { auth } from '@/lib/nextauth';
import { AuthShell } from '@/components/ui/auth-shell';
import { ForgotPasswordForm } from './forgot-password-form';

export const metadata: Metadata = { title: 'Forgot password' };

export default async function ForgotPasswordPage() {
  const session = await auth();
  if (session?.user?.id) redirect('/dashboard');

  return (
    <AuthShell
      theme="clinician"
      eyebrow="Account recovery"
      title={
        <>
          Reset <em style={{ color: 'var(--sage-deep)', fontStyle: 'italic' }}>password</em>
        </>
      }
      subtitle="Enter your account email and we'll send you a reset link."
      cinematic={{
        eyebrow: 'Account recovery',
        headlinePre: '',
        headlineEm: 'Reset ',
        headlinePost: 'your password.',
      }}
    >
      <ForgotPasswordForm />
    </AuthShell>
  );
}
