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
    // R1: the board is home. Sending the root at /dashboard — which itself
    // forwards to /board — worked, but it put a legacy URL in every signed-in
    // user's history and made the first hop after login a double redirect.
    // Unconditional since F-ret.3; there is no second home to choose between.
    redirect('/board');
  }
  redirect('/login');
}
