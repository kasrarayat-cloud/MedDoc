// ============================================================================
// /visits/new — Linear V1 shell.
// ----------------------------------------------------------------------------
// The underlying flow (PatientPicker → VisitFormStep2 → createVisitAction)
// is preserved end-to-end. Step state is driven by the selected patient
// (absent → step 1, present → step 2).
// ============================================================================

import type { Metadata } from 'next';
import { redirect } from 'next/navigation';

import prisma from '@meddoc/db';
import { auth } from '@/lib/nextauth';
import { isSkinBeta } from '@/config/skin-beta';
import { AppFrame } from '@/components/ui/app-frame';
import { Ic } from '@/components/ui/icon';
import { PageHeader } from '@/components/ui/page-header';
import { visibleSpecialties, findSpecialty } from '@meddoc/shared/specialties';
import { NewVisitClient } from './new-visit-client';
import { NewVisitClientC3 } from './new-visit-client-c3';
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

  // Default to the doctor's most recent visit's specialty, normalized
  // through the legacy-value table so a row that still holds a display
  // name maps onto the canonical id the dropdown expects.
  // Flag-aware picker list: Ultrasound appears only when its flag is on
  // (default OFF → exactly the pre-ultrasound list).
  const pickerSpecialties = visibleSpecialties({ forVisitCreate: true });
  const defaultSpecialty = mostRecentVisit?.specialty
    ? findSpecialty(mostRecentVisit.specialty).id
    : pickerSpecialties[0].id;

  // The doctor's OWN custom note formats, for the per-visit picker (active first,
  // then drafts). Empty for the vast majority (no custom template) → the picker
  // is not rendered and the flow is unchanged.
  const noteFormats = (await prisma.noteTemplate.findMany({
    where: {
      doctorId: session.user.id,
      isSystemDefault: false,
      status: { in: ['active', 'draft'] },
    },
    select: { id: true, name: true, status: true },
    orderBy: [{ status: 'asc' }, { updatedAt: 'desc' }],
  })) as Array<{ id: string; name: string; status: string }>;
  const templates = noteFormats.map((t) => ({
    id: t.id,
    name: t.name,
    isActive: t.status === 'active',
  }));

  // \u2500\u2500 C3 calm "just start" create flow (flag-gated) \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
  // SKIN-ONLY: identical auth + patient-scope reads + defaultSpecialty above.
  // The 3-step stepper + side rail collapse to one calm card; the SAME
  // PatientPicker + VisitFormStep2 (createVisitAction) do the real work. Flag
  // OFF \u2192 the stepper below renders verbatim.
  if (isSkinBeta()) {
    return (
      <AppFrame>
        <div className="qm-c3-nv-top">
          <span className="qm-c3-nv-eyebrow">New visit</span>
          <a href="/dashboard" className="qm-lin-btn" style={{ textDecoration: 'none' }}>
            <Ic.close width={13} height={13} />
            Cancel
          </a>
        </div>
        <NewVisitClientC3
          initialPatient={initialPatient}
          specialties={pickerSpecialties}
          defaultSpecialty={defaultSpecialty}
          templates={templates}
        />
      </AppFrame>
    );
  }

  return (
    <AppFrame>
      <PageHeader
        eyebrow="New visit"
        title="Start a new visit"
        subtitle={
          initialPatient
            ? 'Pick a capture mode below and we\u2019ll take it from there.'
            : 'Pick the patient, then choose how you want to capture the encounter.'
        }
        actions={
          <a
            href="/dashboard"
            className="qm-lin-btn"
            style={{ textDecoration: 'none' }}
          >
            <Ic.close width={13} height={13} />
            Cancel
          </a>
        }
      />

      <div style={{ padding: '24px 24px 48px', maxWidth: 1280 }}>
        <NewVisitClient
          initialPatient={initialPatient}
          specialties={pickerSpecialties}
          defaultSpecialty={defaultSpecialty}
          templates={templates}
        />
      </div>
    </AppFrame>
  );
}
