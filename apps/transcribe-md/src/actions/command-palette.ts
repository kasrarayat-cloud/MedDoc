"use server";

import prisma from "@meddoc/db";
import { getSession } from "@/lib/auth";
import { readTemplateTwinVisibleVisitPage } from "@/lib/template-twin/read-authority";

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
  if (!session?.user?.id) return [];

  type RecentVisitRow = {
    id: string;
    patientName: string | null;
    specialty: string;
    createdAt: Date;
  };
  const rows = await readTemplateTwinVisibleVisitPage<RecentVisitRow>({
    db: prisma,
    actorUserId: session.user.id,
    query: {
      scope: { deleted: "active", archived: "active" },
      orderBy: "createdAt",
      direction: "desc",
      take: 10,
    },
    hydrate: (tx, visitIds) =>
      tx.transcribeVisit.findMany({
        where: {
          id: { in: [...visitIds] },
          userId: session.user.id,
        },
        select: {
          id: true,
          patientName: true,
          specialty: true,
          createdAt: true,
        },
      }) as Promise<RecentVisitRow[]>,
  });

  return rows.map((r) => ({
    id: r.id,
    patientName: r.patientName,
    specialty: r.specialty,
    createdAt: r.createdAt.toISOString(),
  }));
}
