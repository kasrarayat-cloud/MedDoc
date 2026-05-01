import type { Metadata } from 'next';
import { Suspense } from 'react';
import { redirect } from 'next/navigation';
import { headers } from 'next/headers';

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
    // Host-aware redirect: a SUPER_ADMIN landing on admin.quillmd.com/login
    // while already signed in goes to `/admin`, not the clinician
    // `/dashboard`. The strict Caddy block on admin.quillmd.com returns
    // 404 for `/dashboard`, so without this branch the user would land
    // on a blank page after a refresh.
    const h = await headers();
    const host = (h.get('x-forwarded-host') ?? h.get('host') ?? '')
      .toLowerCase()
      .split(':')[0];
    const isAdminHost =
      host === 'admin.quillmd.com' || host.startsWith('admin.');
    redirect(isAdminHost ? '/admin' : '/dashboard');
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
            Sign <em>in</em>
          </>
        }
        subtitle="Continue to your clinical workspace."
      >
        <LoginForm />
      </AuthShell>
    </>
  );
}
