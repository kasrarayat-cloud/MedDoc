// ============================================================================
// /visits/new — Linear V1 shell.
// ----------------------------------------------------------------------------
// The underlying flow (PatientPicker → VisitFormStep2 → createVisitAction)
// is preserved end-to-end. Step state is driven by the selected patient
// (absent → step 1, present → step 2).
// ============================================================================

import type { Metadata } from "next";
import { redirect } from "next/navigation";

import prisma from "@meddoc/db";
import { isTemplateTwinSyntheticQaPatient } from "@/lib/template-twin/synthetic-qa-patient";
import { readTemplateTwinVisibleVisitPage } from "@/lib/template-twin/read-authority";
import { currentClinicalPatientWhere } from "@/lib/clinical-patient-authority";
import { auth } from "@/lib/nextauth";
import { isSkinBeta } from "@/config/skin-beta";
import { AppFrame } from "@/components/ui/app-frame";
import { Ic } from "@/components/ui/icon";
import { PageHeader } from "@/components/ui/page-header";
import { visibleSpecialties, findSpecialty } from "@meddoc/shared/specialties";
import { NewVisitClient } from "./new-visit-client";
import { NewVisitClientC3 } from "./new-visit-client-c3";
import type { SelectedPatient } from "./patient-types";

export const metadata: Metadata = { title: "New visit" };

type SearchParams = Record<string, string | string[] | undefined>;

export default async function NewVisitPage({
  searchParams,
}: {
  searchParams: Promise<SearchParams>;
}) {
  const session = await auth();
  if (!session?.user?.id) redirect("/login");

  type MinimalUser = {
    name: string | null;
    email: string;
    practiceId: string;
  };
  type MinimalVisit = { id: string; specialty: string };

  const [user, mostRecentVisits] = await Promise.all([
    prisma.user.findUnique({
      where: { id: session.user.id },
      select: { name: true, email: true, practiceId: true },
    }),
    readTemplateTwinVisibleVisitPage<MinimalVisit>({
      db: prisma,
      actorUserId: session.user.id,
      query: {
        scope: { deleted: "active", archived: "active" },
        orderBy: "createdAt",
        direction: "desc",
        take: 1,
      },
      hydrate: (tx, visitIds) =>
        tx.transcribeVisit.findMany({
          where: {
            id: { in: [...visitIds] },
            userId: session.user.id,
          },
          select: { id: true, specialty: true },
        }) as Promise<MinimalVisit[]>,
    }),
  ]);
  const mostRecentVisit = mostRecentVisits[0] ?? null;
  const typedUser = user as MinimalUser | null;
  if (!typedUser) redirect("/login");

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
    const patient: PatientRow | null =
      await prisma.transcribeMdPatient.findFirst({
        where: currentClinicalPatientWhere({
          actor: {
            userId: session.user.id,
            practiceId: typedUser.practiceId,
          },
          patientId: patientIdParam,
        }),
        select: {
          id: true,
          practiceId: true,
          name: true,
          dateOfBirth: true,
          externalId: true,
          deletedAt: true,
        },
      });
    if (!patient || isTemplateTwinSyntheticQaPatient(patient)) {
      redirect("/visits/new");
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
          <a
            href="/dashboard"
            className="qm-lin-btn"
            style={{ textDecoration: "none" }}
          >
            <Ic.close width={13} height={13} />
            Cancel
          </a>
        </div>
        <NewVisitClientC3
          initialPatient={initialPatient}
          specialties={pickerSpecialties}
          defaultSpecialty={defaultSpecialty}
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
            ? "Pick a capture mode below and we\u2019ll take it from there."
            : "Pick the patient, then choose how you want to capture the encounter."
        }
        actions={
          <a
            href="/dashboard"
            className="qm-lin-btn"
            style={{ textDecoration: "none" }}
          >
            <Ic.close width={13} height={13} />
            Cancel
          </a>
        }
      />

      <div style={{ padding: "24px 24px 48px", maxWidth: 1280 }}>
        <NewVisitClient
          initialPatient={initialPatient}
          specialties={pickerSpecialties}
          defaultSpecialty={defaultSpecialty}
        />
      </div>
    </AppFrame>
  );
}
