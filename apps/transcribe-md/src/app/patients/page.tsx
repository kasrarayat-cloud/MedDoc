// ============================================================================
// /patients — all-patients list (Gate 16).
// ----------------------------------------------------------------------------
// AppFrame shell + searchable grid of PatientCard. The dashboard shows
// a truncated first-page view of the same data; this route is the
// exhaustive list, sorted by updatedAt so doctors see their most-
// recently-touched charts first.
//
// Phase 5 (Linear V1 Faithful) — page renders inside the standard
// AppFrame (already migrated to Linear V1 in Stage 2.5). The header
// uses Inter at 600/700 instead of the earlier serif emphasis, and
// the page-level data fetches (auth, prisma queries, redirects) are
// unchanged per PROTECTED_CONTRACTS.md.
// ============================================================================

import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";

import prisma from "@meddoc/db";
import { auth } from "@/lib/nextauth";
import { logAudit } from "@/lib/audit";
import { isSkinBeta } from "@/config/skin-beta";
import { AppFrame } from "@/components/ui/app-frame";
import { EmptyState } from "@/components/ui/empty-state";
import { Ic } from "@/components/ui/icon";
import { PageHeader } from "@/components/ui/page-header";
import { type DashboardPatient } from "@/components/dashboard/patient-card";
import { PatientsListClient } from "./patients-list-client";
import { PatientsListC3 } from "./patients-list-c3";
import {
  C3_PATIENTS_PAGE_SIZE,
  type C3PatientsCursor,
  type C3PatientRow,
} from "@/lib/c3-list-pagination";
import {
  countTemplateTwinVisibleVisitsByPatient,
  readLatestTemplateTwinVisibleVisitByPatient,
} from "@/lib/template-twin/read-authority";
import { currentClinicalPatientCollectionWhere } from "@/lib/clinical-patient-authority";

export const metadata: Metadata = { title: "Patients" };

const PAGE_SIZE = 100;

export default async function PatientsPage() {
  const session = await auth();
  if (!session?.user?.id) redirect("/login");

  const user = await prisma.user.findUnique({
    where: { id: session.user.id },
    select: { practiceId: true },
  });
  if (!user) redirect("/login");
  const actor = {
    userId: session.user.id,
    practiceId: user.practiceId,
  };

  // ── C3 calm-skin patients list (flag-gated) ───────────────────────────────
  // SKIN-ONLY re-layout: same practice-scoped roster + same VIEWED_PATIENT_LIST
  // audit, re-laid-out as the calm row list with READ-ONLY server search +
  // cursor pagination (searchPatientsAction) so it scales past the old 100-row
  // client cap. Flag OFF → the existing card grid below runs verbatim.
  if (isSkinBeta()) {
    type C3PatientRaw = {
      id: string;
      name: string;
      dateOfBirth: Date | null;
      updatedAt: Date;
    };
    const [firstRaw, total] = (await Promise.all([
      prisma.transcribeMdPatient.findMany({
        where: currentClinicalPatientCollectionWhere({ actor }),
        orderBy: [{ updatedAt: "desc" }, { id: "desc" }],
        take: C3_PATIENTS_PAGE_SIZE + 1,
        select: {
          id: true,
          name: true,
          dateOfBirth: true,
          updatedAt: true,
        },
      }),
      prisma.transcribeMdPatient.count({
        where: currentClinicalPatientCollectionWhere({ actor }),
      }),
    ])) as [C3PatientRaw[], number];

    void logAudit({
      action: "VIEWED_PATIENT_LIST",
      targetType: "TranscribeMdPatient",
      metadata: {
        source: "rsc:/patients:c3",
        count: Math.min(firstRaw.length, C3_PATIENTS_PAGE_SIZE),
      },
    });

    const hasMore = firstRaw.length > C3_PATIENTS_PAGE_SIZE;
    const firstPage = hasMore
      ? firstRaw.slice(0, C3_PATIENTS_PAGE_SIZE)
      : firstRaw;
    const ids = firstPage.map((p) => p.id);
    type LatestC3Visit = {
      id: string;
      patientId: string;
      createdAt: Date;
      specialty: string;
      status: import("@prisma/client").TranscribeVisitStatus;
      needsReview: boolean;
      signedAt: Date | null;
    };
    const [latestVisits, counts] = await Promise.all([
      readLatestTemplateTwinVisibleVisitByPatient<LatestC3Visit>({
        db: prisma,
        actorUserId: session.user.id,
        patientIds: ids,
        scope: { deleted: "active", archived: "active" },
        hydrate: (tx, visitIds) =>
          tx.transcribeVisit.findMany({
            where: {
              id: { in: [...visitIds] },
              userId: session.user.id,
            },
            select: {
              id: true,
              patientId: true,
              createdAt: true,
              specialty: true,
              status: true,
              needsReview: true,
              signedAt: true,
            },
          }) as Promise<LatestC3Visit[]>,
      }),
      countTemplateTwinVisibleVisitsByPatient({
        db: prisma,
        actorUserId: session.user.id,
        patientIds: ids,
        scope: { deleted: "active", archived: "active" },
      }),
    ]);
    const latestByPatient = new Map(
      latestVisits.map((visit) => [visit.patientId, visit]),
    );
    const countBy = new Map<string, number>(
      counts.map((count) => [count.patientId, count.count]),
    );
    const firstRows: C3PatientRow[] = firstPage.map((p) => {
      const lv = latestByPatient.get(p.id);
      return {
        id: p.id,
        name: p.name,
        dateOfBirth: p.dateOfBirth
          ? p.dateOfBirth.toISOString().slice(0, 10)
          : null,
        visitCount: countBy.get(p.id) ?? 0,
        lastVisitAt: lv?.createdAt.toISOString() ?? null,
        lastVisitSpecialty: lv?.specialty ?? null,
        lastVisitStatus: lv?.status ?? null,
        lastVisitNeedsReview: lv?.needsReview ?? false,
        lastVisitSignedAt: lv?.signedAt ? lv.signedAt.toISOString() : null,
      };
    });
    const last = firstPage[firstPage.length - 1];
    const firstCursor: C3PatientsCursor | null =
      hasMore && last
        ? { updatedAt: last.updatedAt.toISOString(), id: last.id }
        : null;

    return (
      <AppFrame>
        <div
          style={{ maxWidth: 880, margin: "0 auto", padding: "22px 24px 0" }}
        >
          <PageHeader
            eyebrow="Patients"
            title="All patients"
            subtitle={`${total} patient${total === 1 ? "" : "s"} · most recently touched first`}
            actions={
              <Link
                href="/visits/new"
                className="qm-lin-btn-primary"
                style={{ textDecoration: "none" }}
              >
                <Ic.plus width={14} height={14} />
                New visit
              </Link>
            }
          />
        </div>
        {total === 0 ? (
          <EmptyState
            kind="sparkle"
            eyebrow="No patients"
            title="No patients yet"
            body="Start your first visit — we'll create the patient record along the way."
            cta={
              <Link
                href="/visits/new"
                className="qm-lin-btn-primary"
                style={{ textDecoration: "none" }}
              >
                <Ic.plus width={14} height={14} />
                Start your first visit
              </Link>
            }
          />
        ) : (
          <PatientsListC3
            initialRows={firstRows}
            initialCursor={firstCursor}
            total={total}
          />
        )}
      </AppFrame>
    );
  }

  type LatestVisit = {
    id: string;
    patientId: string;
    createdAt: Date;
    specialty: string;
    status: import("@prisma/client").TranscribeVisitStatus;
    needsReview: boolean;
  };
  type PatientRow = {
    id: string;
    name: string;
    dateOfBirth: Date | null;
  };

  const rows: PatientRow[] = await prisma.transcribeMdPatient.findMany({
    where: currentClinicalPatientCollectionWhere({ actor }),
    orderBy: { updatedAt: "desc" },
    take: PAGE_SIZE,
    select: {
      id: true,
      name: true,
      dateOfBirth: true,
    },
  });

  const patientIds = rows.map((r: PatientRow) => r.id);
  const [latestVisits, counts] = await Promise.all([
    readLatestTemplateTwinVisibleVisitByPatient<LatestVisit>({
      db: prisma,
      actorUserId: session.user.id,
      patientIds,
      scope: { deleted: "active", archived: "active" },
      hydrate: (tx, visitIds) =>
        tx.transcribeVisit.findMany({
          where: {
            id: { in: [...visitIds] },
            userId: session.user.id,
          },
          select: {
            id: true,
            patientId: true,
            createdAt: true,
            specialty: true,
            status: true,
            needsReview: true,
          },
        }) as Promise<LatestVisit[]>,
    }),
    countTemplateTwinVisibleVisitsByPatient({
      db: prisma,
      actorUserId: session.user.id,
      patientIds,
      scope: { deleted: "active", archived: "active" },
    }),
  ]);
  const latestByPatient = new Map(
    latestVisits.map((visit) => [visit.patientId, visit]),
  );
  const countByPatient = new Map<string, number>(
    counts.map((count) => [count.patientId, count.count]),
  );

  // Round 3 PR-C — §164.312(b) PHI-read audit (A05-P0-004). Patients
  // list reveals identity (name + DOB) for the practice's full roster.
  void logAudit({
    action: "VIEWED_PATIENT_LIST",
    targetType: "TranscribeMdPatient",
    metadata: {
      source: "rsc:/patients",
      count: rows.length,
    },
  });

  const patients: DashboardPatient[] = rows.map(
    (r: PatientRow): DashboardPatient => {
      const latest = latestByPatient.get(r.id);
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
    },
  );

  return (
    <AppFrame>
      <PageHeader
        eyebrow="Patients"
        title="All patients"
        subtitle={
          patients.length === PAGE_SIZE
            ? `Showing the ${PAGE_SIZE} most recently touched. Use ⌘K to search the full list.`
            : `${patients.length} patient${patients.length === 1 ? "" : "s"} · most recently touched first`
        }
        actions={
          <Link
            href="/visits/new"
            className="qm-lin-btn-primary"
            style={{ textDecoration: "none" }}
          >
            <Ic.plus width={14} height={14} />
            New visit
          </Link>
        }
      />

      {patients.length === 0 ? (
        <EmptyState
          kind="sparkle"
          eyebrow="No patients"
          title="No patients yet"
          body="Start your first visit — we'll create the patient record along the way."
          cta={
            <Link
              href="/visits/new"
              className="qm-lin-btn-primary"
              style={{ textDecoration: "none" }}
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
