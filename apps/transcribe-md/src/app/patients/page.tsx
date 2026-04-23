// ============================================================================
// /patients — all-patients list (Gate 16).
// ----------------------------------------------------------------------------
// AppFrame shell + searchable grid of PatientCard. The dashboard shows
// a truncated first-page view of the same data; this route is the
// exhaustive list, sorted by updatedAt so doctors see their most-
// recently-touched charts first.
// ============================================================================

import type { Metadata } from 'next';
import Link from 'next/link';
import { redirect } from 'next/navigation';

import prisma from '@meddoc/db';
import { auth } from '@/lib/nextauth';
import { AppFrame } from '@/components/ui/app-frame';
import { EmptyState } from '@/components/ui/empty-state';
import { Ic } from '@/components/ui/icon';
import { PageHeader } from '@/components/ui/page-header';
import { type DashboardPatient } from '@/components/dashboard/patient-card';
import { PatientsListClient } from './patients-list-client';

export const metadata: Metadata = { title: 'Patients' };

const PAGE_SIZE = 100;

export default async function PatientsPage() {
  const session = await auth();
  if (!session?.user?.id) redirect('/login');

  const user = await prisma.user.findUnique({
    where: { id: session.user.id },
    select: { practiceId: true },
  });
  if (!user) redirect('/login');

  type LatestVisit = {
    createdAt: Date;
    specialty: string;
    status: import('@prisma/client').TranscribeVisitStatus;
    needsReview: boolean;
  };
  type PatientRow = {
    id: string;
    name: string;
    dateOfBirth: Date | null;
    transcribeVisits: LatestVisit[];
  };
  type CountRow = { patientId: string; _count: { _all: number } };

  const rows: PatientRow[] = await prisma.transcribeMdPatient.findMany({
    where: { practiceId: user.practiceId, deletedAt: null },
    orderBy: { updatedAt: 'desc' },
    take: PAGE_SIZE,
    select: {
      id: true,
      name: true,
      dateOfBirth: true,
      transcribeVisits: {
        where: { deletedAt: null, archivedAt: null },
        orderBy: { createdAt: 'desc' },
        take: 1,
        select: {
          createdAt: true,
          specialty: true,
          status: true,
          needsReview: true,
        },
      },
    },
  });

  const patientIds = rows.map((r: PatientRow) => r.id);
  const counts: CountRow[] = patientIds.length
    ? await prisma.transcribeVisit.groupBy({
        by: ['patientId'],
        where: {
          patientId: { in: patientIds },
          deletedAt: null,
          archivedAt: null,
        },
        _count: { _all: true },
      })
    : [];
  const countByPatient = new Map<string, number>(
    counts.map((c: CountRow) => [c.patientId, c._count._all])
  );

  const patients: DashboardPatient[] = rows.map(
    (r: PatientRow): DashboardPatient => {
      const latest = r.transcribeVisits[0];
      return {
        id: r.id,
        name: r.name,
        dateOfBirth: r.dateOfBirth
          ? r.dateOfBirth.toISOString().slice(0, 10)
          : null,
        visitCount: countByPatient.get(r.id) ?? 0,
        lastVisitAt: latest?.createdAt.toISOString() ?? null,
        lastVisitSpecialty: latest?.specialty ?? null,
        lastVisitStatus: latest?.status ?? null,
        lastVisitNeedsReview: latest?.needsReview ?? false,
      };
    }
  );

  return (
    <AppFrame>
      <PageHeader
        eyebrow="§ Patients"
        title={
          <>
            All <em style={{ color: 'var(--accent-bright)' }}>patients</em>
          </>
        }
        subtitle={
          patients.length === PAGE_SIZE
            ? `Showing the ${PAGE_SIZE} most recently touched. Use ⌘K to search the full list.`
            : `${patients.length} patient${patients.length === 1 ? '' : 's'} · most recently touched first`
        }
        actions={
          <Link
            href="/visits/new"
            className="qm-btn qm-btn-primary"
            style={{ textDecoration: 'none' }}
          >
            <Ic.plus width={14} height={14} />
            New visit
          </Link>
        }
      />

      {patients.length === 0 ? (
        <EmptyState
          eyebrow="§ No patients"
          title={
            <>
              No patients <em style={{ color: 'var(--accent-bright)' }}>yet</em>
            </>
          }
          body="Start your first visit — we'll create the patient record along the way."
          cta={
            <Link
              href="/visits/new"
              className="qm-btn qm-btn-primary"
              style={{ textDecoration: 'none' }}
            >
              <Ic.plus width={14} height={14} />
              Start your first visit
            </Link>
          }
        />
      ) : (
        <PatientsListClient patients={patients} />
      )}
    </AppFrame>
  );
}
