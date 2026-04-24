import type { Metadata } from 'next';
import { Suspense } from 'react';
import { redirect } from 'next/navigation';

import { auth } from '@/lib/nextauth';
import { AuthShell } from '@/components/ui/auth-shell';
import { LoginForm } from './login-form';
import { VerifyToast } from './verify-toast';

// Root layout noindexes all of app.quillmd.com; re-enable for /login
// so the public entry page can be surfaced via search.
export const metadata: Metadata = {
  title: 'Sign in',
  robots: { index: true, follow: true },
};

export default async function LoginPage() {
  const session = await auth();
  if (session?.user?.id) {
    redirect('/dashboard');
  }

  return (
    <>
      <Suspense fallback={null}>
        <VerifyToast />
      </Suspense>
      <AuthShell
        eyebrow="Welcome back"
        title={
          <>
            Sign <em style={{ color: 'var(--accent-bright)' }}>in</em>
          </>
        }
        subtitle="Continue to your clinical workspace."
      >
        <LoginForm />
      </AuthShell>
    </>
  );
}
