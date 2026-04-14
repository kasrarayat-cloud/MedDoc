// ============================================================================
// System Admin Layout — Role-gated (ADMIN only)
// ============================================================================

import { redirect } from 'next/navigation';
import { getSession } from '@/lib/auth';
import AdminSidebar from '@/components/system-admin/AdminSidebar';

// Force dynamic rendering — the layout calls getSession() on every request
// and must never serve a cached version with a stale role.
export const dynamic = 'force-dynamic';
export const revalidate = 0;

export default async function SystemAdminLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const session = await getSession();

  if (!session) {
    redirect('/login');
  }

  // ADMIN (practice-scoped) or SUPER_ADMIN (cross-practice) can reach
  // the admin surface. DOCTOR/STAFF get bounced.
  if (session.user.role !== 'ADMIN' && session.user.role !== 'SUPER_ADMIN') {
    redirect('/dashboard');
  }

  return (
    <div style={{ display: 'flex', minHeight: '100vh', background: '#0a0e17' }}>
      <AdminSidebar userName={session.user.fullName} />
      {/* pt-14 on mobile clears the fixed hamburger button; lg:pt-0 lets the
          admin page own its own top padding when the sidebar is in the flow. */}
      <main className="flex-1 min-w-0 pt-14 lg:pt-0">{children}</main>
    </div>
  );
}
