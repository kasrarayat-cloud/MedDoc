import { redirect } from 'next/navigation';
import { getSession } from '@/lib/auth';
import prisma from '@/lib/db';
import { isDatabaseHealthy } from '@/lib/db';
import SettingsClient from './SettingsClient';

export default async function SettingsPage() {
  const session = await getSession();
  if (!session) redirect('/login');

  let user: { name: string; email: string; role: string; mfaEnabled: boolean } | null = null;

  if (await isDatabaseHealthy()) {
    try {
      const row = await prisma.user.findUnique({
        where: { id: session.user.id },
        select: { name: true, email: true, role: true, mfaEnabled: true },
      });
      if (row) {
        user = {
          name: row.name ?? '',
          email: row.email,
          role: row.role,
          mfaEnabled: row.mfaEnabled,
        };
      }
    } catch {
      // Fall through to session data
    }
  }

  return (
    <SettingsClient
      user={{
        name: user?.name ?? session.user.fullName,
        email: user?.email ?? session.user.email,
        role: user?.role ?? session.user.role,
        mfaEnabled: user?.mfaEnabled ?? false,
      }}
    />
  );
}
