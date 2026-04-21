// ============================================================================
// /visits/new — patient picker (Step 1) + capture form (Step 2)
// ----------------------------------------------------------------------------
// T-M17.2 Commit 9. Server component loads:
//   - user (for NavBar)
//   - SPECIALTIES + mostRecentVisit.specialty (for the Step 2 default)
//   - If ?patientId= is present, the patient row, validated against
//     the caller's practiceId and deletedAt=null. An invalid patientId
//     triggers a clean redirect to /visits/new (no query param) rather
//     than a 404 — the doctor wanted to start a visit, not hit a dead
//     end.
//
// Everything after the shell (picker vs form) is a client component —
// searching + inline-create + the duplicate modal need interactivity,
// and the transition Step 1 ↔ Step 2 happens without a re-fetch.
// ============================================================================

import type { Metadata } from 'next';
import { redirect } from 'next/navigation';

import prisma from '@meddoc/db';
import { auth } from '@/lib/nextauth';
import { NavBar } from '@/components/nav-bar';
import { PageWrapper } from '@/components/page-wrapper';
import { SPECIALTIES } from '@/lib/specialties';
import { NewVisitClient } from './new-visit-client';
import type { SelectedPatient } from './patient-types';

export const metadata: Metadata = { title: 'New visit' };

type SearchParams = Record<string, string | string[] | undefined>;

export default async function NewVisitPage({
  searchParams,
}: {
  searchParams: Promise<SearchParams>;
}) {
  const session = await auth();
  if (!session?.user?.id) redirect('/login');

  const [user, mostRecentVisit, templateRows] = await Promise.all([
    prisma.user.findUnique({
      where: { id: session.user.id },
      select: { name: true, email: true, practiceId: true },
    }),
    prisma.transcribeVisit.findFirst({
      where: {
        userId: session.user.id,
        deletedAt: null,
        archivedAt: null,
      },
      orderBy: { createdAt: 'desc' },
      select: { specialty: true },
    }),
    prisma.transcribeTemplate.findMany({
      where: { userId: session.user.id, deletedAt: null },
      orderBy: { createdAt: 'desc' },
      select: { id: true, name: true, tokens: true },
    }),
  ]);
  if (!user) redirect('/login');

  const templates = (
    templateRows as Array<{ id: string; name: string; tokens: string[] }>
  ).map((t) => ({
    id: t.id,
    name: t.name,
    tokenCount: t.tokens.length,
  }));

  const params = await searchParams;
  const patientIdParam = Array.isArray(params.patientId)
    ? params.patientId[0]
    : params.patientId;

  // Validate the deep-linked patient, if any. Invalid → redirect to
  // /visits/new with no query string so the picker shows up instead
  // of a confusing error page.
  let initialPatient: SelectedPatient | null = null;
  if (patientIdParam) {
    const patient = await prisma.transcribeMdPatient.findUnique({
      where: { id: patientIdParam },
      select: {
        id: true,
        practiceId: true,
        name: true,
        dateOfBirth: true,
        externalId: true,
        deletedAt: true,
      },
    });
    if (
      !patient ||
      patient.practiceId !== user.practiceId ||
      patient.deletedAt !== null
    ) {
      redirect('/visits/new');
    }
    initialPatient = {
      id: patient.id,
      name: patient.name,
      dateOfBirth: patient.dateOfBirth
        ? patient.dateOfBirth.toISOString().slice(0, 10)
        : null,
      externalId: patient.externalId,
    };
  }

  const defaultSpecialty =
    mostRecentVisit?.specialty ?? SPECIALTIES[0]?.displayName ?? '';

  return (
    <PageWrapper>
      <NavBar name={user.name} email={user.email} />

      <main className="mx-auto max-w-4xl px-4 pb-24 pt-8 sm:px-6 lg:px-8 lg:pt-12">
        <div className="mb-8">
          <h1 className="type-h1 text-text-primary">Start a new visit</h1>
          <p className="mt-2 text-[14px] text-text-tertiary">
            {initialPatient
              ? 'Pick a capture mode below and we&apos;ll take it from there.'
              : 'Pick the patient, then choose how you want to capture the encounter.'}
          </p>
        </div>

        <NewVisitClient
          initialPatient={initialPatient}
          specialties={SPECIALTIES}
          defaultSpecialty={defaultSpecialty}
          templates={templates}
        />
      </main>
    </PageWrapper>
  );
}
