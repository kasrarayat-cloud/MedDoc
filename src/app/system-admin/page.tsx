// ============================================================================
// System Admin — Command Center Dashboard
// ============================================================================

import prisma, { isDatabaseHealthy } from '@/lib/db';
import { getSession } from '@/lib/auth';
import { tenantScope } from '@/lib/tenancy';
import AdminUsersTableClient from './AdminUsersTableClient';
import { mockAdminUsers } from './mock-users';
import type { Session } from '@/lib/auth';

export const dynamic = 'force-dynamic';

export interface AdminUserView {
  id: string;
  email: string;
  name: string | null;
  role: string;
  isActive: boolean;
  lastLogin: string | null;
  createdAt: string;
  failedLoginCount: number;
  lastSessionIp: string | null;
  lastSessionAt: string | null;
  lastSessionAgent: string | null;
  sessionCount: number;
}

async function getAdminUsers(session: Session): Promise<AdminUserView[]> {
  if (!(await isDatabaseHealthy())) {
    return [...mockAdminUsers];
  }

  try {
    const users = await prisma.user.findMany({
      where: tenantScope(session),
      orderBy: { createdAt: 'desc' },
      include: {
        sessionLogs: {
          orderBy: { createdAt: 'desc' },
          take: 1,
        },
        _count: {
          select: { sessionLogs: true },
        },
      },
    });

    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    return users.map((u: any) => ({
      id: u.id,
      email: u.email,
      name: u.name,
      role: u.role,
      isActive: u.isActive,
      lastLogin: u.lastLogin?.toISOString() ?? null,
      createdAt: u.createdAt.toISOString(),
      failedLoginCount: u.failedLoginCount,
      // Source of truth is User.lastLoginIp (written on successful login).
      // Fall back to the most recent SessionLog for rows that predate the
      // lastLoginIp wiring.
      lastSessionIp: u.lastLoginIp ?? u.sessionLogs?.[0]?.ipAddress ?? null,
      lastSessionAt: u.sessionLogs?.[0]?.createdAt?.toISOString() ?? null,
      lastSessionAgent: u.sessionLogs?.[0]?.userAgent ?? null,
      sessionCount: u._count?.sessionLogs ?? 0,
    }));
  } catch (err) {
    console.warn('[system-admin] Failed to fetch users:', err);
    return [];
  }
}

export default async function SystemAdminPage() {
  const session = await getSession();
  // Layout gate already guarantees ADMIN or SUPER_ADMIN, but guard here too.
  if (!session) return null;
  const users = await getAdminUsers(session);

  return (
    <AdminUsersTableClient
      users={users}
      currentUserId={session.user.id}
    />
  );
}
