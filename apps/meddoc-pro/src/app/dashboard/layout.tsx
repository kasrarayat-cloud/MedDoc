// ============================================================================
// Dashboard (Clinician) Layout
// ----------------------------------------------------------------------------
// Server component so we can read the session role and tell the client
// Sidebar whether to render the "Back to Admin" bridge. Auth gating itself
// is done by middleware + /login redirect, so this layout trusts the session.
// ============================================================================

import React from 'react';
import Sidebar from '@/components/dashboard/Sidebar';
import { getSession } from '@/lib/auth';

// Always fetch session fresh — we never want a cached layout that hides the
// Back to Admin link from a user who just had their role upgraded.
export const dynamic = 'force-dynamic';
export const revalidate = 0;

export default async function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const session = await getSession();

  return (
    <div className="flex h-screen bg-slate-50 dark:bg-slate-950 overflow-hidden">
      <Sidebar
        userRole={session?.user.role ?? null}
        userName={session?.user.fullName ?? null}
        userEmail={session?.user.email ?? null}
      />
      <main className="flex-1 overflow-y-auto">
        <div className="p-6 lg:p-8 pt-16 lg:pt-8 min-h-full">
          {children}
        </div>
      </main>
    </div>
  );
}
