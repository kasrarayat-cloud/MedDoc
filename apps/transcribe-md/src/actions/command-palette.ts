'use server';

import prisma from '@meddoc/db';
import { visitScope } from '@/lib/practice-scope';
import { getSession } from '@/lib/auth';

export interface RecentVisitItem {
  id: string;
  patientName: string | null;
  specialty: string;
  createdAt: string;
}

/** Fetch the caller's 10 most recent visits for the Cmd+K palette.
 *  Returns [] when unauthenticated — the palette hides the "Recent"
 *  section in that case. Dates are serialised to ISO strings to stay
 *  RSC-friendly. */
export async function getRecentVisits(): Promise<RecentVisitItem[]> {
  const session = await getSession();
  if (!session) return [];

  const rows = await prisma.transcribeVisit.findMany({
    where: {
      ...visitScope(session.user.practiceId),
      deletedAt: null,
      archivedAt: null,
    },
    orderBy: { createdAt: 'desc' },
    take: 10,
    select: {
      id: true,
      patientName: true,
      specialty: true,
      createdAt: true,
    },
  });

  return rows.map((r: { id: string; patientName: string | null; specialty: string; createdAt: Date }) => ({
    id: r.id,
    patientName: r.patientName,
    specialty: r.specialty,
    createdAt: r.createdAt.toISOString(),
  }));
}
