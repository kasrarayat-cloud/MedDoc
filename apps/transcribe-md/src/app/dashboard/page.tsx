import type { Metadata } from 'next';
import { redirect } from 'next/navigation';
import { Suspense } from 'react';

import prisma from '@meddoc/db';
import { auth } from '@/lib/nextauth';
import { NavBar } from '@/components/nav-bar';
import { EmptyState } from '@/components/empty-state';
import { VisitCard, type VisitCardData } from '@/components/visit-card';
import { PageWrapper } from '@/components/page-wrapper';
import { SkeletonVisitGrid } from '@/components/skeleton';

export const metadata: Metadata = { title: 'Dashboard' };

export default async function DashboardPage() {
  const session = await auth();
  if (!session?.user?.id) redirect('/login');

  // Resolve the user up front — the shell renders immediately with
  // NavBar + a visit-grid skeleton. The actual visits query is
  // suspended below so slow DB responses never block the paint.
  const user = await prisma.user.findUnique({
    where: { id: session.user.id },
    select: { name: true, email: true },
  });
  if (!user) redirect('/login');

  return (
    <PageWrapper>
      <NavBar name={user.name} email={user.email} />

      <main className="mx-auto max-w-7xl px-4 pb-24 pt-8 sm:px-6 lg:px-8 lg:pt-12">
        <Suspense fallback={<DashboardSkeleton />}>
          <DashboardVisits userId={session.user.id} />
        </Suspense>
      </main>
    </PageWrapper>
  );
}

async function DashboardVisits({ userId }: { userId: string }) {
  const visits = await prisma.transcribeVisit.findMany({
    where: { userId },
    orderBy: { createdAt: 'desc' },
    take: 50,
    select: {
      id: true,
      patientName: true,
      specialty: true,
      status: true,
      createdAt: true,
    },
  });

  if (visits.length === 0) return <EmptyState />;

  return (
    <>
      <div className="mb-6 flex items-end justify-between">
        <div>
          <h1 className="type-h1 text-text-primary">Your visits</h1>
          <p className="mt-1 text-[13px] text-text-tertiary">
            {visits.length} {visits.length === 1 ? 'visit' : 'visits'} · most
            recent first
          </p>
        </div>
      </div>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {(visits as VisitCardData[]).map((v) => (
          <VisitCard key={v.id} visit={v} />
        ))}
      </div>
    </>
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
