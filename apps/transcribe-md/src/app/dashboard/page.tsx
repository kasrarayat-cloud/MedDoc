import type { Metadata } from 'next';
import { redirect } from 'next/navigation';

import prisma from '@meddoc/db';
import { auth } from '@/lib/nextauth';
import { NavBar } from '@/components/nav-bar';
import { EmptyState } from '@/components/empty-state';
import { VisitCard, type VisitCardData } from '@/components/visit-card';

export const metadata: Metadata = { title: 'Dashboard' };

export default async function DashboardPage() {
  const session = await auth();
  if (!session?.user?.id) redirect('/login');

  const [user, visits] = await Promise.all([
    prisma.user.findUnique({
      where: { id: session.user.id },
      select: { name: true, email: true },
    }),
    prisma.transcribeVisit.findMany({
      where: { userId: session.user.id },
      orderBy: { createdAt: 'desc' },
      take: 50,
      select: {
        id: true,
        patientName: true,
        specialty: true,
        status: true,
        createdAt: true,
      },
    }),
  ]);

  // `user` should always exist here — auth() already resolved — but the
  // null-guard keeps TypeScript honest and avoids a runtime crash if a
  // row was deleted mid-session.
  if (!user) redirect('/login');

  return (
    <>
      <NavBar name={user.name} email={user.email} />

      <main className="mx-auto max-w-7xl px-6 pb-24 pt-8 lg:px-8 lg:pt-12">
        {visits.length === 0 ? (
          <EmptyState />
        ) : (
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
        )}
      </main>
    </>
  );
}
