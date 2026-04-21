// ============================================================================
// Dashboard — tabbed [Patients] / [All visits] / [Trash] layout
// ----------------------------------------------------------------------------
// /dashboard                 → Patients tab (default)
// /dashboard?tab=visits      → All visits tab
// /dashboard?tab=trash       → T-M18.2 A12 — global trash view across
//                              ALL patients. Only surfaces when
//                              trashCount > 0 so a healthy account's
//                              tab row stays clean.
//
// All three tabs SSR their first page so the initial paint is fast.
// Switching tabs is a Link navigation — the RSC re-renders with the
// new searchParams value. "Load more" within each tab calls the
// corresponding action.
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
import { ShowArchivedToggle } from './show-archived-toggle';
import {
  TrashedVisitCard,
  type TrashedVisitCardData,
} from '@/app/patients/[id]/trashed-visit-card';

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
  const activeTab: 'patients' | 'visits' | 'trash' =
    tabParam === 'visits' ? 'visits' : tabParam === 'trash' ? 'trash' : 'patients';
  const archivedParam = Array.isArray(params.archived)
    ? params.archived[0]
    : params.archived;
  const includeArchived = archivedParam === '1';

  return (
    <PageWrapper>
      <NavBar name={user.name} email={user.email} />

      <main className="mx-auto max-w-7xl px-4 pb-24 pt-8 sm:px-6 lg:px-8 lg:pt-12">
        <Suspense fallback={<DashboardSkeleton />}>
          <DashboardBody
            userId={session.user.id}
            practiceId={user.practiceId}
            activeTab={activeTab}
            includeArchived={includeArchived}
          />
        </Suspense>
        {/* DashboardBody signature updated below — `activeTab` now
            accepts 'trash'. */}
      </main>
    </PageWrapper>
  );
}

async function DashboardBody({
  userId,
  practiceId,
  activeTab,
  includeArchived,
}: {
  userId: string;
  practiceId: string;
  activeTab: 'patients' | 'visits' | 'trash';
  includeArchived: boolean;
}) {
  // Small COUNT queries for the tab badges. All four are cheap via
  // the existing indexes.
  //
  // visitCount stays archive-exclusive even when the toggle is on —
  // the badge shows "active visits on this account", not "visits
  // currently rendered in the grid". T-M18.2 A11 adds archivedCount
  // so the header subheading can disambiguate. T-M18.2 A12 adds
  // trashCount so the global Trash tab is only offered when it has
  // something to show.
  const [patientCount, visitCount, archivedCount, trashCount] =
    await Promise.all([
      prisma.transcribeMdPatient.count({
        where: { practiceId, deletedAt: null },
      }),
      prisma.transcribeVisit.count({
        where: { userId, deletedAt: null, archivedAt: null },
      }),
      prisma.transcribeVisit.count({
        where: { userId, deletedAt: null, archivedAt: { not: null } },
      }),
      prisma.transcribeVisit.count({
        where: { userId, deletedAt: { not: null } },
      }),
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
              : activeTab === 'trash'
                ? `${trashCount} trashed · auto-delete countdown on each card`
                : includeArchived
                  ? `${visitCount} active · ${archivedCount} archived · most recent first`
                  : `${visitCount} ${visitCount === 1 ? 'visit' : 'visits'} · most recent first`}
          </p>
        </div>
      </div>

      <TabNav
        active={activeTab}
        patientCount={patientCount}
        visitCount={visitCount}
        trashCount={trashCount}
      />

      {activeTab === 'patients' ? (
        <PatientsTabBody practiceId={practiceId} patientCount={patientCount} />
      ) : activeTab === 'trash' ? (
        <TrashTabBody userId={userId} trashCount={trashCount} />
      ) : (
        <VisitsTabBody
          userId={userId}
          visitCount={visitCount}
          includeArchived={includeArchived}
        />
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

async function TrashTabBody({
  userId,
  trashCount,
}: {
  userId: string;
  trashCount: number;
}) {
  if (trashCount === 0) {
    // Edge case — doctor restored the last trashed visit while on
    // the tab. The tab itself hides when trashCount=0 on the next
    // render, but for this render we still want a clean state.
    return (
      <div className="rounded-xl border border-border-subtle bg-bg-surface-1/40 px-6 py-10 text-center">
        <p className="text-[14px] text-text-tertiary">No deleted visits.</p>
      </div>
    );
  }
  // Fetch all trashed visits ordered by when they were deleted (most-
  // recently-trashed first so the auto-delete countdown is intuitive).
  // Per-practice volume caps this at a small number; no pagination
  // for now.
  const rows = await prisma.transcribeVisit.findMany({
    where: { userId, deletedAt: { not: null } },
    orderBy: [{ deletedAt: 'desc' }, { id: 'desc' }],
    select: {
      id: true,
      patientName: true,
      specialty: true,
      status: true,
      createdAt: true,
      deletedAt: true,
    },
  });

  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {rows.map((v: TrashedVisitCardData) => (
        <TrashedVisitCard key={v.id} visit={v} />
      ))}
    </div>
  );
}

async function VisitsTabBody({
  userId,
  visitCount,
  includeArchived,
}: {
  userId: string;
  visitCount: number;
  includeArchived: boolean;
}) {
  if (visitCount === 0 && !includeArchived) {
    return <VisitsEmptyTabBody />;
  }
  // Matches the T-M16.4 first-page render — fetch PAGE_SIZE+1 to
  // detect hasMore without a second query. When the toggle is on
  // we drop the archivedAt filter; deletedAt filter stays (trash
  // belongs on the patient detail page, not this dashboard).
  const rows = await prisma.transcribeVisit.findMany({
    where: {
      userId,
      deletedAt: null,
      ...(includeArchived ? {} : { archivedAt: null }),
    },
    orderBy: [{ createdAt: 'desc' }, { id: 'desc' }],
    take: DASHBOARD_PAGE_SIZE + 1,
    select: {
      id: true,
      patientName: true,
      specialty: true,
      status: true,
      createdAt: true,
      archivedAt: true,
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
    <>
      <div className="mb-3 flex justify-end">
        <ShowArchivedToggle />
      </div>
      <VisitsGrid
        initialVisits={firstPage as VisitCardData[]}
        initialCursor={initialCursor}
        includeArchived={includeArchived}
      />
    </>
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
