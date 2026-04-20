// ============================================================================
// Dashboard — tabbed [Patients] / [All visits] layout (T-M17.2 Commit 7)
// ----------------------------------------------------------------------------
// /dashboard                 → Patients tab (default)
// /dashboard?tab=visits      → All visits tab
//
// Both tabs SSR their first page so the initial paint is fast. Switching
// tabs is a Link navigation — the RSC re-renders with the new searchParams
// value. "Load more" within each tab calls the corresponding action
// (loadMorePatientsAction / loadMoreVisitsAction).
// ============================================================================

import type { Metadata } from 'next';
import Link from 'next/link';
import { redirect } from 'next/navigation';
import { Suspense } from 'react';

import prisma from '@meddoc/db';
import { auth } from '@/lib/nextauth';
import { NavBar } from '@/components/nav-bar';
import { EmptyState } from '@/components/empty-state';
import { SpecularButton } from '@/components/specular-button';
import type { VisitCardData } from '@/components/visit-card';
import { PageWrapper } from '@/components/page-wrapper';
import { SkeletonVisitGrid } from '@/components/skeleton';
import {
  DASHBOARD_PAGE_SIZE,
  type DashboardCursor,
} from '@/lib/dashboard-pagination';
import { fetchPatientsPage } from '@/lib/patients-query';
import { VisitsGrid } from './visits-grid';
import { PatientsGrid } from './patients-grid';
import { TabNav } from './tab-nav';

export const metadata: Metadata = { title: 'Dashboard' };

type SearchParams = Record<string, string | string[] | undefined>;

export default async function DashboardPage({
  searchParams,
}: {
  searchParams: Promise<SearchParams>;
}) {
  const session = await auth();
  if (!session?.user?.id) redirect('/login');

  const user = await prisma.user.findUnique({
    where: { id: session.user.id },
    select: { name: true, email: true, practiceId: true },
  });
  if (!user) redirect('/login');

  const params = await searchParams;
  const tabParam = Array.isArray(params.tab) ? params.tab[0] : params.tab;
  const activeTab: 'patients' | 'visits' =
    tabParam === 'visits' ? 'visits' : 'patients';

  return (
    <PageWrapper>
      <NavBar name={user.name} email={user.email} />

      <main className="mx-auto max-w-7xl px-4 pb-24 pt-8 sm:px-6 lg:px-8 lg:pt-12">
        <Suspense fallback={<DashboardSkeleton />}>
          <DashboardBody
            userId={session.user.id}
            practiceId={user.practiceId}
            activeTab={activeTab}
          />
        </Suspense>
      </main>
    </PageWrapper>
  );
}

async function DashboardBody({
  userId,
  practiceId,
  activeTab,
}: {
  userId: string;
  practiceId: string;
  activeTab: 'patients' | 'visits';
}) {
  // Small COUNT queries for the tab badges — both always visible, so
  // both need a number. Cheap via the existing indexes.
  const [patientCount, visitCount] = await Promise.all([
    prisma.transcribeMdPatient.count({
      where: { practiceId, deletedAt: null },
    }),
    prisma.transcribeVisit.count({ where: { userId } }),
  ]);

  // Brand-new user (no patients, no visits) — keep the full-bleed
  // orb empty state. Landing on a row of tabs with zeroed badges
  // feels clinical; the orb matches the rest of the first-session
  // onboarding moment.
  if (patientCount === 0 && visitCount === 0) {
    return <EmptyState />;
  }

  return (
    <>
      <div className="mb-6 flex items-end justify-between">
        <div>
          <h1 className="type-h1 text-text-primary">Your dashboard</h1>
          <p className="mt-1 text-[13px] text-text-tertiary">
            {activeTab === 'patients'
              ? `${patientCount} patient${patientCount === 1 ? '' : 's'} · most-recent visit first`
              : `${visitCount} ${visitCount === 1 ? 'visit' : 'visits'} · most recent first`}
          </p>
        </div>
      </div>

      <TabNav
        active={activeTab}
        patientCount={patientCount}
        visitCount={visitCount}
      />

      {activeTab === 'patients' ? (
        <PatientsTabBody practiceId={practiceId} patientCount={patientCount} />
      ) : (
        <VisitsTabBody userId={userId} visitCount={visitCount} />
      )}
    </>
  );
}

async function PatientsTabBody({
  practiceId,
  patientCount,
}: {
  practiceId: string;
  patientCount: number;
}) {
  if (patientCount === 0) {
    return <PatientsEmptyState />;
  }
  const firstPage = await fetchPatientsPage(practiceId, null);
  return (
    <PatientsGrid
      initialPatients={firstPage.patients}
      initialCursor={firstPage.nextCursor}
    />
  );
}

async function VisitsTabBody({
  userId,
  visitCount,
}: {
  userId: string;
  visitCount: number;
}) {
  if (visitCount === 0) {
    return <VisitsEmptyTabBody />;
  }
  // Matches the T-M16.4 first-page render — fetch PAGE_SIZE+1 to
  // detect hasMore without a second query.
  const rows = await prisma.transcribeVisit.findMany({
    where: { userId },
    orderBy: [{ createdAt: 'desc' }, { id: 'desc' }],
    take: DASHBOARD_PAGE_SIZE + 1,
    select: {
      id: true,
      patientName: true,
      specialty: true,
      status: true,
      createdAt: true,
    },
  });
  const hasMore = rows.length > DASHBOARD_PAGE_SIZE;
  const firstPage = hasMore ? rows.slice(0, DASHBOARD_PAGE_SIZE) : rows;
  const last = firstPage[firstPage.length - 1];
  const initialCursor: DashboardCursor | null =
    hasMore && last
      ? { createdAt: last.createdAt.toISOString(), id: last.id }
      : null;

  return (
    <VisitsGrid
      initialVisits={firstPage as VisitCardData[]}
      initialCursor={initialCursor}
    />
  );
}

function PatientsEmptyState() {
  return (
    <div className="mx-auto flex max-w-md flex-col items-center py-20 text-center">
      <div
        aria-hidden
        className="mb-6 flex h-14 w-14 items-center justify-center rounded-full bg-[linear-gradient(135deg,#4C1D95_0%,#7C3AED_50%,#A855F7_100%)] text-[22px] font-semibold text-white shadow-[0_0_0_1px_rgba(167,139,250,0.3)]"
      >
        +
      </div>
      <h2 className="type-h2 text-text-primary">No patients yet</h2>
      <p className="mt-3 max-w-sm text-[14px] leading-relaxed text-text-tertiary">
        Start your first visit — we&apos;ll create a patient record for
        you along the way.
      </p>
      <div className="mt-6">
        <SpecularButton href="/visits/new" variant="primary" size="md">
          Create first patient
        </SpecularButton>
      </div>
    </div>
  );
}

function VisitsEmptyTabBody() {
  // Narrow case: patients exist but zero visits. Keep it understated —
  // the big orb EmptyState handles brand-new accounts above.
  return (
    <div className="mx-auto max-w-md py-16 text-center">
      <p className="text-[14px] text-text-tertiary">
        No visits yet for any patient.{' '}
        <Link
          href="/visits/new"
          className="font-medium text-violet-300 hover:text-violet-200"
        >
          Start one
        </Link>
        .
      </p>
    </div>
  );
}

function DashboardSkeleton() {
  return (
    <>
      <div className="mb-6 space-y-2">
        <div className="h-8 w-44 shimmer rounded-md" />
        <div className="h-3 w-32 shimmer rounded-md" />
      </div>
      <SkeletonVisitGrid count={6} />
    </>
  );
}
