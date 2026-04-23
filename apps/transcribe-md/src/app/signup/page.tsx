import type { Metadata } from 'next';
import { redirect } from 'next/navigation';

import { auth } from '@/lib/nextauth';
import { AuthShell } from '@/components/ui/auth-shell';
import { SignupForm } from './signup-form';

export const metadata: Metadata = { title: 'Sign up' };

export default async function SignupPage() {
  const session = await auth();
  if (session?.user?.id) {
    redirect('/dashboard');
  }

  return (
    <AuthShell
      eyebrow="New to QuillMD"
      title={
        <>
          Create your <em style={{ color: 'var(--accent-bright)' }}>account</em>
        </>
      }
      subtitle="Free for 14 days. No credit card."
    >
      <SignupForm />
    </AuthShell>
  );
}
