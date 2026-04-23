// ============================================================================
// /visits/new — app-redesign-v1 shell (Gate 8, HANDOFF §2.3 NewVisitScreen).
// ----------------------------------------------------------------------------
// The underlying flow (PatientPicker → VisitFormStep2 → createVisitAction)
// is preserved end-to-end — we wrap it in AppFrame + stepper + visit-summary
// rail. Step state is driven by the selected patient (absent → step 1,
// present → step 2). Full three-step URL routing lands in a later pass.
// ============================================================================

import type { Metadata } from 'next';
import { redirect } from 'next/navigation';

import prisma from '@meddoc/db';
import { auth } from '@/lib/nextauth';
import { AppFrame } from '@/components/ui/app-frame';
import { Ic } from '@/components/ui/icon';
import { PageHeader } from '@/components/ui/page-header';
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

  type MinimalUser = {
    name: string | null;
    email: string;
    practiceId: string;
  };
  type MinimalVisit = { specialty: string } | null;

  const [user, mostRecentVisit] = (await Promise.all([
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
  ])) as [MinimalUser | null, MinimalVisit];
  if (!user) redirect('/login');

  const params = await searchParams;
  const patientIdParam = Array.isArray(params.patientId)
    ? params.patientId[0]
    : params.patientId;

  let initialPatient: SelectedPatient | null = null;
  if (patientIdParam) {
    type PatientRow = {
      id: string;
      practiceId: string;
      name: string;
      dateOfBirth: Date | null;
      externalId: string | null;
      deletedAt: Date | null;
    };
    const patient: PatientRow | null = await prisma.transcribeMdPatient.findUnique({
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
    <AppFrame>
      <PageHeader
        eyebrow="§ New / Visit"
        title={
          <>
            Start a <em style={{ color: 'var(--accent-bright)' }}>new visit</em>
          </>
        }
        subtitle={
          initialPatient
            ? 'Pick a capture mode below and we\u2019ll take it from there.'
            : 'Pick the patient, then choose how you want to capture the encounter.'
        }
        actions={
          <a
            href="/dashboard"
            className="qm-btn qm-btn-ghost"
            style={{ textDecoration: 'none' }}
          >
            <Ic.close width={13} height={13} />
            Cancel
          </a>
        }
      />

      <div style={{ padding: '0 32px 48px', maxWidth: 1280 }}>
        <NewVisitClient
          initialPatient={initialPatient}
          specialties={SPECIALTIES}
          defaultSpecialty={defaultSpecialty}
        />
      </div>
    </AppFrame>
  );
}
