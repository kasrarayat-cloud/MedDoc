// ============================================================================
// / — root redirect
// ----------------------------------------------------------------------------
// If the user is signed in → /dashboard.
// If not → /login. Keeps the root URL meaningful without rendering a page.
// ============================================================================

import { redirect } from 'next/navigation';
import { auth } from '@/lib/nextauth';

export default async function RootPage() {
  const session = await auth();
  if (session?.user?.id) {
    redirect('/dashboard');
  }
  redirect('/login');
}
